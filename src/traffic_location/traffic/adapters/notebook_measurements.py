"""Notebook cache version adapter, including explicit historical context only."""
from ..measurements import read_measurements, relationship_evidence
__all__ = ['read_measurements', 'relationship_evidence']

"""Consumer exports and verification of retained review proof bytes."""
from pathlib import Path
from ...artifacts import require, semantic_hash
from .._kernel import reviews, review_finalizer

def verify_source_review(frames, overlay, *, source_identity, root, records_path,
                         video_id, frame_count, overlay_sha256):
    guarded = []
    rows = reviews._validated_reviews(overlay, source_identity, video_id, frame_count, Path(root).resolve(), guarded)
    anchors = {f for review in rows for f in review['confirmed_frames']}
    records = reviews._anchor_records(records_path, source_identity, anchors)
    guarded.append({'path': str(Path(records_path).resolve()), 'sha256': source_identity['records_sha256']})
    return rows, records, guarded

def verify_adjudications(result, manifest, *, baseline, source, root):
    require(manifest.get('schema_version') == review_finalizer.SCHEMA, 'Unsupported adjudication schema')
    review_finalizer._require(review_finalizer._sha(manifest.get('baseline_result_sha256')), 'Baseline SHA required')
    for key in review_finalizer.SOURCE_KEYS:
        require(review_finalizer._sha(source.get(key)) and manifest.get('source_identity', {}).get(key) == source[key] and baseline.get('source_identity', {}).get(key) == source[key] and result.get('source_identity', result.get('report', {}).get('source_identity', {})).get(key) == source[key], 'Adjudication source mismatch')
    baseline_index = review_finalizer._pending_index(baseline)
    for review in manifest['adjudications']:
        review_finalizer._validate_review(review, baseline_index, source, Path(root).resolve())

