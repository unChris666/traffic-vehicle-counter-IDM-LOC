"""The supported counting facade. Frozen algorithms, explicit stage boundaries."""
from copy import deepcopy
from pathlib import Path
from ..contracts.source import ArtifactRef, FrozenDocument
from ..contracts.execution import VideoRequest, Operation
from ..contracts.results import VideoResult
from ..contracts.versioning import decode_request, decode_review
from ..contracts.review import SourceContextReview, CandidateAdjudication
from ..config.loader import load_effective_config
from ..config.schema import EffectiveConfig
from ..adapters import measurement, notebook_measurements, video_input
from ..domain import trajectory, identity, role_association, counting, finalization
from ..domain import source_context_review, candidate_adjudication
from ..results import wrap_native
from ...artifacts import artifact, read, sha, require, semantic_hash


def implementation_hash() -> str:
    """Counting dependency closure only: presentation/runtime changes are separate."""
    root = Path(__file__).resolve().parents[1]
    paths = [p for p in (root / '_kernel').glob('*.py') if not p.name.startswith('render')]
    for folder in ('contracts', 'config', 'domain'):
        paths.extend((root / folder).glob('*.py'))
    paths.extend(root / name for name in ('validation.py', 'measurements.py', 'fresh_bridge.py', 'results.py'))
    paths.extend(root / 'adapters' / name for name in ('measurement.py', 'notebook_measurements.py', 'fresh_measurements.py', 'video_input.py'))
    paths.append(Path(__file__))
    # Shared serialization/integrity utilities affect numerical artifact identity.
    paths.append(root.parent / 'artifacts.py')
    return semantic_hash({str(p.relative_to(root.parent)): sha(p) for p in sorted(set(paths))})


def _historical_reviews(request, paths):
    if 'baseline_reviews' not in paths:
        return []
    source = request['source_identity']; refs = request['artifacts']
    historical = read(paths['historical_baseline'])
    require(historical['source_identity'] == source and historical['report']['policy']['review_manifest_sha256'] == refs['baseline_reviews']['sha256'], 'Historical baseline/review binding differs')
    manifest = read(paths['baseline_reviews'])
    require(manifest.get('donor_manifest_sha256') == request['source_manifest_sha256'], 'Historical review source manifest differs')
    entries = [v for v in manifest['videos'] if v['video_id'] == request['video_id']]
    require(len(entries) == 1, 'Historical review video missing/duplicate')
    require(all(entries[0][k] == source[k] for k in ['video_sha256', 'records_sha256', 'geometry_sha256']), 'Historical review source differs')
    rows = entries[0].get('reviews', [])
    for review in rows:
        require(review.get('confirmed_frames') and review.get('scopes'), 'Unbounded historical review')
        for scope in review['scopes']:
            require(type(scope.get('start_frame')) is int and type(scope.get('end_frame')) is int and 0 <= scope['start_frame'] <= scope['end_frame'] < request['frame_count'], 'Historical review scope outside video')
    return rows


def process_video(request: VideoRequest, config: EffectiveConfig | None = None, *, root: str | Path) -> VideoResult:
    if not isinstance(request, VideoRequest):
        raise TypeError('VideoRequest required; use decode_request at JSON boundary')
    # Revalidate even directly constructed DTOs, not only the JSON decoder path.
    checked = decode_request(request.legacy.object())
    require(checked.branch is request.branch, 'DTO branch differs from payload')
    from ..experiments.performance import active_progress
    timing = active_progress()
    data = checked.legacy.object(); branch = checked.branch.value
    root = Path(root).resolve(); refs = data['artifacts']
    paths = {k: artifact(v, root) for k, v in refs.items()}
    before = {k: sha(p) for k, p in paths.items()}
    policy_ref = ArtifactRef(**refs['policy'])
    frozen = load_effective_config(policy_ref, root=root, branch=checked.branch)
    if config is not None:
        # Alternate config requires a new policy artifact/request revision.
        require(config == frozen, 'Effective config differs from hash-bound request; create a new policy revision')
    source = deepcopy(data['source_identity']); policy = frozen.policy.object(); audit = {}
    geometry = video_input.load_geometry(paths['geometry'], source)
    links = notebook_measurements.relationship_evidence(paths['relationships']) if 'relationships' in paths else {}
    base_reviews = _historical_reviews(data, paths)
    timing.snapshot('measurement_load')
    with timing.stage('measurement_load'):
        frames = measurement.read_frames(data, paths, links=links, baseline_reviews=base_reviews, audit=audit)
    overlay = None
    guards = []
    if branch == 'review_assisted':
        overlay = read(paths['review_overlay'])
        require(overlay.get('donor_manifest_sha256') == data['source_manifest_sha256'], 'Overlay parent manifest differs')
        typed_review = decode_review(overlay)
        require(isinstance(typed_review, SourceContextReview), 'Wrong review phase')
        frames = list(frames)
        verified, anchors, guards = notebook_measurements.verify_source_review(frames, overlay,
            source_identity=source, root=root, records_path=paths['measurements'], video_id=data['video_id'],
            frame_count=data['frame_count'], overlay_sha256=refs['review_overlay']['sha256'])
        reviewed = source_context_review.apply(frames, typed_review, source_identity=source,
            frame_count=data['frame_count'], overlay_sha256=refs['review_overlay']['sha256'],
            verified_reviews=verified, records=anchors, guarded=guards)
        frames = reviewed['frames']
    timing.snapshot('identity')
    with timing.stage('identity'):
        resolved = identity.resolve(frames, geometry, policy, relationships=links)
    trajectory.validate_scope(resolved['frames'], data['frame_count'])
    effective = deepcopy(policy)
    effective['episode_relations'], _ = role_association.relations(resolved)
    timing.snapshot('counting')
    with timing.stage('counting'):
        native = counting.count(resolved['frames'], geometry, source_identity=source, policy=effective)
    if branch == 'review_assisted':
        manifest = read(paths['adjudications'])
        require(manifest['baseline_result_sha256'] == refs['baseline_result']['sha256'], 'Review baseline bytes mismatch')
        typed_adjudication = decode_review(manifest)
        require(isinstance(typed_adjudication, CandidateAdjudication), 'Wrong review phase')
        baseline = read(paths['baseline_result'])
        notebook_measurements.verify_adjudications(native, manifest, baseline=baseline, source=source, root=root)
        native = candidate_adjudication.apply(native, typed_adjudication, baseline_result=baseline, finalization_frame=data['frame_count'] - 1)
    timing.snapshot('finalization')
    with timing.stage('finalization'):
        native = finalization.finalize(native, request=data, branch=branch, resolved=resolved, overlay=overlay)
    require(all(sha(paths[k]) == h for k, h in before.items()), 'Input mutated during execution')
    require(all(sha(g['path']) == g['sha256'] for g in guards), 'Review proof mutated during execution')
    envelope = wrap_native(native, request=data, branch=branch, implementation_hash=implementation_hash())
    envelope.update(schema_version='traffic_result_v2', operation_executed=Operation.COUNT_REPLAY.value,
        measurement_origin='fresh_inference' if data.get('measurement_format') == 'fresh_v1' else 'notebook_measurement',
        fresh_inference_executed=False, counting_executed=True, effective_config_sha256=frozen.fingerprint,
        contract_version='traffic_facade_v2', algorithm_lineage='FROZEN_B_V8_COMPATIBILITY_KERNEL')
    with timing.stage('result_freeze'):
        result = VideoResult(FrozenDocument.freeze(envelope), FrozenDocument.freeze(native), FrozenDocument.freeze(audit))
    timing.snapshot('counting_finished', completed=data['frame_count'], total=data['frame_count'])
    return result


def run(request, *, root):
    """Mapping compatibility for notebook/CLI callers; typed API is process_video."""
    value = process_video(decode_request(request), root=root)
    return {'result': value.envelope.object(), 'native': value.native.object(), 'adapter_audit': value.adapter_audit.object()}
