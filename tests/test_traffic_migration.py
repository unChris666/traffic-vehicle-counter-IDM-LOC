"""Migration acceptance: authority, immutable DTOs, versioning, DAG, retries."""
import ast
from copy import deepcopy
from dataclasses import FrozenInstanceError
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from traffic_location.artifacts import read, write, sha, semantic_hash
from traffic_location.traffic.contracts.source import FrozenDocument, SourceIdentity, FrameScope, ArtifactRef
from traffic_location.traffic.contracts.execution import Branch, Operation, VideoRequest
from traffic_location.traffic.contracts.measurement import RawObservation, MeasuredFrame
from traffic_location.traffic.contracts.review import SourceContextReview, CandidateAdjudication
from traffic_location.traffic.contracts.versioning import decode_request, decode_review
from traffic_location.traffic.config.loader import load_effective_config
from traffic_location.traffic.config.profiles import merge_policy
from traffic_location.traffic.domain import source_context_review, candidate_adjudication
from traffic_location.traffic.application.pipeline import implementation_hash, process_video
from traffic_location.traffic.application.runtime import fresh_inference
from traffic_location.traffic.artifact_store import LocalArtifactStore
ROOT = Path(__file__).resolve().parents[1]
REQUEST = ROOT / 'results/engine_modularization/20261023/requests/machine.json'


def retained_request(path):
    value = read(path)
    for ref in value['artifacts'].values():
        if not Path(ref['path']).exists() and '/results/' in ref['path']:
            ref['path'] = str(ROOT / 'results' / ref['path'].split('/results/', 1)[1])
    return value


class FrozenBaselineTests(unittest.TestCase):
    def test_source_archive_and_kernel_retention(self):
        import zipfile, hashlib
        folder = ROOT / 'results/traffic_migration/20261024'
        manifest = read(folder / 'frozen.json')
        self.assertEqual(sha(folder / 'pre_migration_source.zip'), manifest['source_archive_sha256'])
        with zipfile.ZipFile(folder / 'pre_migration_source.zip') as archive:
            for name, digest in manifest['source_files'].items():
                self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), digest, name)
                if '/_kernel/' in name:
                    self.assertEqual(sha(ROOT / name), digest, name)


class ContractTests(unittest.TestCase):
    def test_nested_state_frozen_and_lossless(self):
        original = {'nested': [{'a': None, 'b': [1, 2.3, False]}]}
        doc = FrozenDocument.freeze(original)
        copied = doc.thaw(); copied['nested'][0]['b'].append(4)
        self.assertEqual(doc.thaw(), original)
        with self.assertRaises(FrozenInstanceError): doc.encoded = b'{}'
        with self.assertRaises(TypeError): FrozenDocument(bytearray(b'{}'))

    def test_direct_constructors_cannot_hold_mutable_nested_payloads(self):
        from traffic_location.traffic.contracts.identity import RoleAssociation, Role
        from traffic_location.traffic.contracts.passage import Passage, CrossingEvidence
        from traffic_location.traffic.contracts.results import VideoResult
        doc = FrozenDocument.freeze({})
        calls = [lambda: VideoRequest({}, Branch.MACHINE),
                 lambda: SourceIdentity({}),
                 lambda: RawObservation(0, 1, 0, (0., 0., 2., 2.), 'car', {}),
                 lambda: RoleAssociation(1, Role.RIDER, FrameScope(0, 1), 'vehicle1', {}),
                 lambda: Passage('e', 'car', 'A_TO_B', CrossingEvidence.MEASURED, {}),
                 lambda: VideoResult(doc, {}, doc)]
        for call in calls:
            with self.assertRaises(TypeError): call()

    def test_nonfinite_and_noncanonical_rejected(self):
        with self.assertRaises(ValueError): FrozenDocument.freeze({'x': float('nan')})
        with self.assertRaises(ValueError): FrozenDocument(b'{ "x": 1}')

    def test_request_roundtrip_preserves_every_legacy_field(self):
        request = retained_request(REQUEST)
        self.assertEqual(decode_request(request).legacy.object(), request)
        request['schema_version'] = 'traffic_request_v999'
        with self.assertRaises(ValueError): decode_request(request)

    def test_unknown_source_identity_rejected(self):
        with self.assertRaises(ValueError): SourceIdentity(FrozenDocument.freeze({}))
        with self.assertRaises(ValueError): FrameScope(9, 4)
        with self.assertRaises(ValueError): ArtifactRef('x', 'wrong')

    def test_raw_bc_only_and_source_link(self):
        o = RawObservation(3, 7, 2, (2., 3., 12., 20.), 'car', FrozenDocument.freeze({}))
        self.assertEqual(o.bottom_center, (7., 20.))
        self.assertEqual(MeasuredFrame(3, (o,)).observations, (o,))
        with self.assertRaises(ValueError): MeasuredFrame(4, (o,))
        with self.assertRaises(ValueError): MeasuredFrame(3, (o, o))

    def test_wrong_operation_never_runs_in_count_facade(self):
        request = decode_request(retained_request(REQUEST))
        with self.assertRaises(ValueError): VideoRequest(request.legacy, request.branch, Operation.FRESH_INFERENCE)
        with self.assertRaises(TypeError): process_video(retained_request(REQUEST), root=ROOT)

    def test_wrong_branch_direct_constructor_rechecked(self):
        request = VideoRequest(FrozenDocument.freeze(retained_request(REQUEST)), Branch.REVIEW_ASSISTED)
        with self.assertRaises(ValueError): process_video(request, root=ROOT)

    def test_fresh_review_assisted_unsupported(self):
        request = retained_request(REQUEST); request.update(measurement_format='fresh_v1', profile='review_assisted')
        with self.assertRaises(ValueError): decode_request(request)


class ReviewAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r = retained_request(ROOT / 'results/engine_modularization/20261023/requests/review_assisted.json')
        cls.source = read(r['artifacts']['review_overlay']['path'])
        cls.adjudication = read(r['artifacts']['adjudications']['path'])

    def test_known_reviews_roundtrip_no_evidence_loss(self):
        for data in (self.source, self.adjudication):
            self.assertEqual(decode_review(data).payload.object(), data)

    def test_wrong_review_type_rejected_before_processing(self):
        with self.assertRaises(ValueError):
            source_context_review.apply([], decode_review(self.adjudication), source_identity={},
                frame_count=1, overlay_sha256='a'*64, verified_reviews=[], records={}, guarded=[])
        with self.assertRaises(ValueError):
            candidate_adjudication.apply({}, decode_review(self.source), baseline_result={}, finalization_frame=0)

    def test_unknown_phase_schema_action_rejected(self):
        with self.assertRaises(ValueError): SourceContextReview(FrozenDocument.freeze(self.source), 'POST_COUNTING')
        with self.assertRaises(ValueError): CandidateAdjudication(FrozenDocument.freeze(self.adjudication), 'PRE_RESOLVER')
        data = deepcopy(self.source); data['videos'][0]['reviews'][0]['type'] = 'FORCE_ACCEPT'
        with self.assertRaises(ValueError): decode_review(data)
        data['schema_version'] = 'future_v99'
        with self.assertRaises(ValueError): decode_review(data)

    def test_adjudication_cannot_promote_pending_or_change_crossing(self):
        for key, value in [('final_status', 'accepted'), ('force_accept', True), ('measured_crossing', True), ('new_event', {})]:
            data = deepcopy(self.adjudication); data['adjudications'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): decode_review(data)

    def test_unknown_fields_are_not_ignored(self):
        data = deepcopy(self.source); data['silent_override'] = True
        with self.assertRaises(ValueError): decode_review(data)
        data = deepcopy(self.adjudication); data['adjudications'][0]['magic'] = True
        with self.assertRaises(ValueError): decode_review(data)


class ConfigTests(unittest.TestCase):
    def test_frozen_hash_and_no_environment_defaults(self):
        request = retained_request(REQUEST); ref = ArtifactRef(**request['artifacts']['policy'])
        a = load_effective_config(ref, root=ROOT, branch=Branch.MACHINE)
        with patch.dict(os.environ, {'CONF': '0.99', 'TRAFFIC_THRESHOLD': '100'}):
            b = load_effective_config(ref, root=ROOT, branch=Branch.MACHINE)
        self.assertEqual(a, b)
        self.assertEqual(a.fingerprint, semantic_hash(a.policy.object()))
        with self.assertRaises(FrozenInstanceError): a.branch = Branch.REVIEW_ASSISTED

    def test_explicit_precedence_and_no_base_mutation(self):
        base = {'x': {'a': 1}, 'z': 4}
        self.assertEqual(merge_policy(base, {'x': {'a': 2}}, {'x': {'a': 3}})['x']['a'], 3)
        self.assertEqual(base['x']['a'], 1)
        for patch_value in ({'missing': 1}, {'x': {'missing': 2}}, {'x': {'a': '3'}}, {'execution_branch': 'machine'}):
            with self.assertRaises(ValueError): merge_policy(base, job_overrides=patch_value)

    def test_branch_and_future_schema_rejected(self):
        from traffic_location.traffic.config.validation import validate_policy
        with self.assertRaises(ValueError): validate_policy({'schema_version': 'future', 'execution_branch': 'machine'}, Branch.MACHINE)
        with self.assertRaises(ValueError): load_effective_config(ArtifactRef(**retained_request(REQUEST)['artifacts']['policy']), root=ROOT, branch=Branch.REVIEW_ASSISTED)


class StorageRuntimeTests(unittest.TestCase):
    def files(self):
        native = {'events': [], 'decisions': [], 'invalid_decisions': [],
            'aggregate': {'total': 0, 'measured_total': 0, 'inferred_total': 0, 'pending': 0, 'invalid': 0, 'by_category': {}, 'by_direction': {}}}
        return {'native.json.gz': native, 'result.json': {'native_semantic_sha256': semantic_hash(native)}}

    def test_atomic_publish_reopen_and_idempotent_retry(self):
        with tempfile.TemporaryDirectory() as d:
            store = LocalArtifactStore(d); files = self.files()
            first = store.publish_result('job', files, metadata={'version': 'x'})
            self.assertEqual(store.publish_result('job', files, metadata={'version': 'x'}), first)
            self.assertEqual(store.reopen('job'), files['result.json'])
            with self.assertRaises(ValueError): store.publish_result('job', files, metadata={'version': 'y'})
            with self.assertRaises(ValueError): store.publish_result('job', {**files, 'extra.json': {}}, metadata={'version': 'x'})
            files['result.json']['different'] = True
            with self.assertRaises(ValueError): store.publish_result('job', files, metadata={'version': 'x'})

    def test_export_failure_and_corruption_never_success(self):
        with tempfile.TemporaryDirectory() as d:
            store = LocalArtifactStore(d)
            with self.assertRaises((ValueError, TypeError)):
                store.publish_result('bad', {'a.json': {}, 'b.json': object()}, metadata={})
            self.assertFalse((Path(d) / 'bad').exists())
            store.publish_result('job', self.files(), metadata={})
            (Path(d) / 'job/result.json').write_text('{}')
            with self.assertRaises(ValueError): store.reopen('job')

    def test_crashed_publisher_lock_does_not_block_retry(self):
        import hashlib
        with tempfile.TemporaryDirectory() as d:
            store = LocalArtifactStore(d)
            lock_root = Path(d) / '.locks'; lock_root.mkdir()
            lock = lock_root / (hashlib.sha256(b'job').hexdigest() + '.lock')
            code = "import os,fcntl; f=os.open(" + repr(str(lock)) + ",os.O_CREAT|os.O_RDWR,0o600);fcntl.flock(f,fcntl.LOCK_EX);os._exit(17)"
            result = subprocess.run([sys.executable, '-c', code])
            self.assertEqual(result.returncode, 17)
            store.publish_result('job', self.files(), metadata={})
            self.assertEqual(store.reopen('job'), self.files()['result.json'])

    def test_concurrent_publisher_is_rejected_without_success(self):
        import hashlib, fcntl
        with tempfile.TemporaryDirectory() as d:
            store = LocalArtifactStore(d)
            lock_root = Path(d) / '.locks'; lock_root.mkdir()
            lock = lock_root / (hashlib.sha256(b'job').hexdigest() + '.lock')
            with lock.open('w') as handle:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaises(BlockingIOError): store.publish_result('job', self.files(), metadata={})
                self.assertFalse(store.path('job').exists())
            store.publish_result('job', self.files(), metadata={})

    def test_unsafe_keys_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            store = LocalArtifactStore(d)
            for key in ('../escape', '/tmp/escape', '.', ''):
                with self.assertRaises(ValueError): store.publish_result(key, {}, metadata={})

    def test_binary_artifact_reopen_retry_and_tamper(self):
        with tempfile.TemporaryDirectory() as d:
            store = LocalArtifactStore(Path(d) / 'store')
            source = Path(d) / 'video.mp4'; source.write_bytes(b'retained-test-payload-not-an-executed-video')
            files = self.files(); files['video.mp4'] = ArtifactRef(str(source), sha(source))
            files['pivot.csv'] = b'category,total\ncar,0\n'
            first = store.publish_result('job', files, metadata={})
            self.assertEqual(store.publish_result('job', files, metadata={}), first)
            self.assertEqual(store.reopen('job'), files['result.json'])
            (store.path('job') / 'video.mp4').write_bytes(b'tampered')
            with self.assertRaises(ValueError): store.reopen('job')

    def test_invalid_native_never_published(self):
        with tempfile.TemporaryDirectory() as d:
            store = LocalArtifactStore(d); files = self.files()
            files['native.json.gz']['aggregate']['total'] = 1
            with self.assertRaises(ValueError): store.publish_result('job', files, metadata={})
            self.assertFalse(store.path('job').exists())

    def test_inference_timeout_failure_logs_retained(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); request = d / 'request.json'
            write(request, {'schema_version': 'fresh_inference_request_v1', 'preprocessing': 'RAW', 'half': False, 'tracker': {}})
            with patch('traffic_location.traffic.application.runtime.execute_worker', side_effect=subprocess.TimeoutExpired('worker', 1)):
                with self.assertRaises(subprocess.TimeoutExpired): fresh_inference(request, d / 'out', python_executable=sys.executable, timeout_seconds=1)
            self.assertFalse((d / 'out').exists())
            failure = next(d.glob('.inference-*/failure.json'))
            self.assertFalse(read(failure)['published_success'])

    def test_renderer_cannot_change_counting_version(self):
        baseline = implementation_hash()
        def renderer_changed(path):
            p = Path(path)
            if p.name.startswith('render') or p.name in {'annotation.py', 'exports.py'}:
                return '0'*64
            return sha(p)
        with patch('traffic_location.traffic.application.pipeline.sha', side_effect=renderer_changed):
            self.assertEqual(implementation_hash(), baseline)
        def counting_changed(path):
            return '0'*64 if Path(path).name == 'counting.py' else sha(path)
        with patch('traffic_location.traffic.application.pipeline.sha', side_effect=counting_changed):
            self.assertNotEqual(implementation_hash(), baseline)


class ExportTests(unittest.TestCase):
    def test_json_csv_html_reconcile_without_changing_snapshot(self):
        import csv, io
        from traffic_location.traffic.adapters.exports import batch_files
        path = ROOT / 'results/traffic_migration/20261024/parity_final/combined.json'
        if not path.exists(): self.skipTest('Final parity receipt unavailable')
        batch = FrozenDocument.freeze(read(path)); before = batch.encoded
        files = batch_files(batch)
        rows = list(csv.DictReader(io.StringIO(files['combined.csv'].decode())))
        total = sum(int(r['measured']) + int(r['estimated']) for r in rows)
        self.assertEqual(total, batch.object()['complete_vehicle_total'] + batch.object()['pedestrian_total'])
        self.assertEqual(files['combined.json'], batch.object())
        self.assertEqual(batch.encoded, before)
        value = batch.object(); value.update(execution_status='PARTIAL', videos_completed=7, complete_vehicle_total=None)
        partial = batch_files(FrozenDocument.freeze(value))
        self.assertIn('UNKNOWN', partial['review.html'].decode())
        self.assertIn('OBSERVED_SUBTOTAL_ONLY', partial['combined.csv'].decode())


class ImportDagTests(unittest.TestCase):
    def test_every_contract_config_domain_imports_without_gpu_or_network(self):
        modules = []
        base = ROOT / 'src/traffic_location/traffic'
        for folder in ('contracts', 'config', 'domain', 'application', 'adapters'):
            modules += ['traffic_location.traffic.' + '.'.join(p.relative_to(base).with_suffix('').parts)
                        for p in (base / folder).glob('*.py') if p.name != '__init__.py']
        code = "import importlib,sys;[importlib.import_module(n) for n in " + repr(modules) + "];assert not {'torch','cv2','onnxruntime','ultralytics'} & set(sys.modules)"
        with tempfile.TemporaryDirectory() as d:
            run = subprocess.run([sys.executable, '-B', '-c', code], cwd=d,
                env={**os.environ, 'PYTHONPATH': str(ROOT / 'src')}, text=True, capture_output=True)
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_layers_and_no_import_cycles(self):
        base = ROOT / 'src'
        modules = {'.'.join(p.relative_to(base).with_suffix('').parts).removesuffix('.__init__'): p
                   for p in (base / 'traffic_location/traffic').rglob('*.py')}
        edges = {name: set() for name in modules}
        for name, path in modules.items():
            package = name if path.name == '__init__.py' else name.rsplit('.', 1)[0]
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.ImportFrom):
                    target = importlib.util.resolve_name('.' * node.level + (node.module or ''), package) if node.level else (node.module or '')
                    if target in modules: edges[name].add(target)
                    for item in node.names:
                        if target + '.' + item.name in modules: edges[name].add(target + '.' + item.name)
                elif isinstance(node, ast.Import):
                    edges[name].update(i.name for i in node.names if i.name in modules)
            if '.contracts.' in name:
                self.assertFalse(any(any('.' + layer + '.' in e for layer in ('domain', 'application', 'adapters', 'config')) for e in edges[name]), name)
            if '.domain.' in name:
                self.assertFalse(any(any('.' + layer + '.' in e for layer in ('application', 'adapters', 'config')) for e in edges[name]), name)
            if '.adapters.' in name:
                self.assertFalse(any('.application.' in e or '.domain.' in e for e in edges[name]), name)
        done, active = set(), set()
        def visit(name):
            if name in active: self.fail('Import cycle: ' + name)
            if name in done: return
            active.add(name)
            for target in edges[name]: visit(target)
            active.remove(name); done.add(name)
        for name in edges: visit(name)


if __name__ == '__main__':
    unittest.main()
