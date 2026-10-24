"""Eight locked jobs, isolated state, reconciled category × direction × evidence."""
from ..contracts.versioning import decode_request
from ..contracts.source import ArtifactRef, digest
from ..domain.aggregation import aggregate
from ...artifacts import artifact, read, require, semantic_hash
from .pipeline import run


def run_batch(requests, *, locked_manifest: ArtifactRef, root, on_video_result=None):
    """An independently inspected full-frame inventory must be frozen first.

    Per-video geometry may differ; policy/model/preprocessing must be locked.
    This operation only replays retained measurements. Fresh inference belongs
    to runtime and requires its own source/model/config receipts.
    """
    manifest = read(artifact({'path': locked_manifest.path, 'sha256': locked_manifest.sha256}, root))
    require(manifest.get('schema_version') == 'traffic_batch_run_v2' and
            set(manifest) == {'schema_version', 'slots', 'policy_sha256', 'inference_profile_sha256'},
            'Explicit supported locked batch manifest required')
    slots = manifest['slots']
    require(isinstance(slots, list) and len(slots) == 8 and len(requests) == 8, 'Eight slots/requests required')
    ids = [s['video_id'] for s in slots]
    require(len(set(ids)) == 8, 'Duplicate source slots')
    require(len({s['video_sha256'] for s in slots}) == 8, 'Source repeated across slots')
    checked = [decode_request(r) for r in requests]
    request_ids = [v.legacy.object()['video_id'] for v in checked]
    require(len(set(request_ids)) == 8 and set(request_ids) == set(ids), 'Eight unique expected videos required')
    require(all(v.branch.value == 'machine' for v in checked), 'Machine batch cannot contain reviewed snapshots')
    expected, prepared = {}, []
    for slot in slots:
        request = next(v.legacy.object() for v in checked if v.legacy.object()['video_id'] == slot['video_id'])
        require(type(slot['frame_count']) is int and slot['frame_count'] > 0 and request['frame_count'] == slot['frame_count'], 'Full-video frame scope differs')
        digest(slot['video_sha256'])
        expected[slot['video_id']] = slot['video_sha256']
        require(request['source_identity']['video_sha256'] == slot['video_sha256'], 'Batch source differs')
        for key in ('measurements', 'geometry'):
            require(request['artifacts'][key]['sha256'] == slot[key + '_sha256'], 'Batch artifact lock differs: ' + key)
        require(request['artifacts']['policy']['sha256'] == manifest['policy_sha256'], 'Mixed counting policy')
        for ref in request['artifacts'].values():
            artifact(ref, root)
        # Proof from the actual producer, not an unverified experiment label.
        require(request.get('measurement_format') == 'fresh_v1', 'This batch profile requires explicit fresh-origin measurements')
        producer = read(artifact(slot['producer_request'], root))
        measurement = read(artifact(request['artifacts']['measurements'], root))
        require(measurement['request_fingerprint'] == semantic_hash(producer), 'Producer receipt differs')
        require(measurement['status'] == 'SUCCEEDED' and measurement['frames'] == slot['frame_count'] == len(measurement['records']), 'Measurement coverage differs')
        require(measurement['records_semantic_sha256'] == semantic_hash(measurement['records']), 'Measurement content differs')
        require(producer['artifacts']['video']['sha256'] == slot['video_sha256'] and producer['frame_limit'] == slot['frame_count'] and producer['start_frame'] == 0, 'Producer is not the locked full-video source')
        profile = {k: v for k, v in producer.items() if k not in {'artifacts', 'input_root', 'frame_limit'}}
        profile['model_hashes'] = {k: producer['artifacts'][k]['sha256'] for k in ('detector', 'reid')}
        require(semantic_hash(profile) == manifest['inference_profile_sha256'], 'Mixed inference/model/preprocessing profile')
        prepared.append(request)
    # Validate every slot before doing any counting, so late input failures do
    # not consume seven jobs or publish an apparently complete subtotal.
    rows = []
    for request in prepared:
        value = run(request, root=root)
        if on_video_result is not None:
            on_video_result(request, value)
        rows.append({'video_id': request['video_id'], 'status': 'SUCCEEDED', 'scope': 'FULL_VIDEO',
            'experiment_sha256': locked_manifest.sha256, 'branch': 'machine', 'native': value['native'],
            'result_version': value['result']['result_version']})
    return aggregate(expected, rows, experiment_sha256=locked_manifest.sha256)
