"""PRE_RESOLVER context application only. No file/network/model I/O."""
from collections import Counter
from copy import deepcopy
from .._kernel.reviews import _require, _matches, RAW_KEYS, IDENTITY_TYPES, _digest
from .._kernel import identity
from ..contracts.review import SourceContextReview

def apply(frames, review, *, source_identity, frame_count, overlay_sha256, verified_reviews, records, guarded):
    if not isinstance(review, SourceContextReview):
        raise ValueError('PRE_RESOLVER review required')
    overlay = review.payload.object()
    copied = deepcopy(list(frames))
    frame_ids = [row['frame_index'] for row in copied]
    _require(copied and frame_ids == sorted(set(frame_ids)) and all(type(f) is int and 0 <= f < frame_count for f in frame_ids), 'Invalid source review scope')
    semantic = _digest(overlay)
    manifest_digest = overlay_sha256
    reviews = verified_reviews
    branch = 'review_assisted'
    source = {(row['frame_index'], item['track_id']): item for row in copied for item in row.get('observations', [])}
    _require(len(source) == sum((len(row.get('observations', [])) for row in copied)), 'Repeated raw track within a source frame')
    counts, matched, assignments = (Counter(), set(), [])
    scope_counts = Counter()
    for review in reviews:
        rid = review['review_id']
        for frame in review['confirmed_frames']:
            proof = review['_pixel_anchor_proofs'][frame]
            record = records[frame]
            _require(record.get('detector_input_frame_pixel_sha256') == proof['raw_bgr_pixel_sha256'], 'Review pixel receipt differs from actual source cache frame')
            actual = {item['track_id']: item for item in record['emitted_tracks']}
            anchor_matches = 0
            for scope in review['scopes']:
                item = source.get((frame, scope['track_id']))
                if item is None or not _matches(scope, item, frame):
                    continue
                cached = actual.get(item['track_id'], {})
                _require(all((cached.get(k) == item.get(k) for k in ('raw_bbox', 'class_name', 'original_detection_index'))), 'Review anchor differs from actual source measurement')
                anchor_matches += 1
                matched.add((rid, item['track_id'], frame))
            _require(anchor_matches, 'Confirmed review frame has no measured target in its own scope')
    for row in copied:
        frame = row['frame_index']
        for item in row.get('observations', []):
            original = deepcopy(item)
            for review in reviews:
                for si, scope in enumerate(review['scopes']):
                    if not _matches(scope, item, frame):
                        continue
                    rid, kind = (review['review_id'], review['type'])
                    before = {k: deepcopy(item.get(k)) for k in ('unit_id', 'episode_id', 'role', 'resolved_class_name', 'association_verified', 'association_id', 'component_of_unit_id')}
                    if kind in IDENTITY_TYPES:
                        unit = scope.get('physical_unit_id', review.get('physical_unit_id'))
                        episode = scope.get('episode_id', review.get('episode_id'))
                        if identity._identity_review_proof(item):
                            _require((unit, episode) == (item['unit_id'], item.get('episode_id')), 'Conflicting positive identity review requires explicit replacement')
                        item.update(unit_id=unit, episode_id=episode, association_verified=kind == 'SAME_VEHICLE', association_id=rid if kind == 'SAME_VEHICLE' else None)
                    elif kind == 'COMPONENT_OF':
                        _require(item.get('role') != 'pedestrian', 'Contradictory positive role review')
                        item.update(role='rider', component_of_unit_id=review['component_of_unit_id'], role_scope_id=rid)
                    elif kind == 'PEDESTRIAN_ROLE':
                        _require(item.get('role') != 'rider', 'Contradictory positive role review')
                        item.update(role='pedestrian', resolved_class_name='pedestrian', unit_id=review.get('physical_unit_id', f'reviewed-pedestrian:{rid}'), episode_id=review.get('episode_id', f'reviewed-role:{rid}'), role_scope_id=rid)
                    resolved = scope.get('resolved_class_name', review.get('resolved_class_name'))
                    if resolved:
                        item['resolved_class_name'] = resolved
                    item.setdefault('review_refs', []).append({'review_id': rid, 'reviews_sha256': manifest_digest, 'source_frame': frame, 'track_id': item['track_id'], 'review_type': kind, 'claim_type': review['claim_type'], 'decision_origin': 'HUMAN_REVIEW' if review['claim_type'] == 'USER_REVIEW' else 'AI_ASSISTED_REVIEW_NOT_NEW_HUMAN_CONFIRMATION', 'scope_extent_is_engineering_assumption': True})
                    counts[rid] += 1
                    scope_counts[rid, si] += 1
                    assignments.append({'frame_index': frame, 'track_id': item['track_id'], 'original_detection_index': item['original_detection_index'], 'raw_bbox': deepcopy(item['raw_bbox']), 'review_id': rid, 'review_type': kind, 'before': before, 'after': {k: deepcopy(item.get(k)) for k in before}, 'claim_type': review['claim_type'], 'source_measurement_unchanged': True})
            _require(all((item.get(k) == original.get(k) for k in RAW_KEYS)), 'A review cannot modify raw measurements')
    _require(all((scope_counts[r['review_id'], i] > 0 for r in reviews for i, _ in enumerate(r['scopes']))), 'Review scope did not match a measured observation')
    audit = {'applied_measurements': dict(sorted(counts.items())), 'matched_reviewed_anchors': [{'review_id': rid, 'track_id': track, 'frame_index': frame} for rid, track, frame in sorted(matched)], 'source_links_checked': True, 'raw_measurements_modified': False, 'new_observations_created': 0, 'review_assignments': assignments}
    return {'frames': copied, 'application_audit': audit, 'guarded_inputs': guarded, 'provenance': {'schema_version': 'phase8_b_v8_review_application_v1', 'branch': branch, 'review_manifest_sha256': manifest_digest, 'review_semantic_sha256': semantic, 'source_identity': deepcopy(source_identity), 'qc_used_as_machine_predictions': False, 'source_records_sha256_verified': True, 'typed_identity_provenance': True, 'decision_origin': 'SOURCE_BOUND_REVIEW_ASSISTED_NOT_AUTOMATIC_MODEL_RESULT'}}
