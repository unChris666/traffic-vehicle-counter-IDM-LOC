from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from .support import require, read, bound, sha
KINDS = {'SAME_VEHICLE', 'SPLIT_IDENTITY', 'COMPONENT_OF', 'PEDESTRIAN_ROLE'}

def validate_overlay(value, jobs, root, guarded):
    """Bind adjudications to exact input bytes and retained native-pixel anchors.

    The additional claims are research review inputs, never automatic model
    predictions or newly confirmed user labels. The immutable old adapter checks
    anchor pixels again against each actual retained frame during replay.
    """
    require(value.get('schema_version') == 'phase8_b_v4_review_overlay_v1' and value.get('donor_manifest_sha256') == jobs[0]['source_manifest_sha256'], 'Unknown B v4 overlay schema or foreign donor')
    videos = {v['video_id']: v for v in value.get('videos', [])}
    require(len(videos) == len(value.get('videos', [])) and set(videos) <= {job['video_id'] for job in jobs}, 'Overlay has duplicate or unknown video IDs')
    seen = set()
    for job in jobs:
        vid = job['video_id']
        if vid not in videos:
            continue
        video, source = (videos[vid], job['b_v2_source_identity'])
        require(all((video.get(key) == source[key] for key in ('video_sha256', 'records_sha256', 'geometry_sha256'))), 'Overlay source binding differs')
        for review in video.get('reviews', []):
            rid = review.get('review_id')
            require(isinstance(rid, str) and rid and (rid not in seen), 'Missing or duplicate overlay review ID')
            seen.add(rid)
            require(review.get('claim_type') == 'ADJUDICATED_AI_PIXELS_REVIEW' and review.get('type') in KINDS and (review.get('human_confirmation_status') == 'NOT_NEWLY_ADJUDICATED_BY_USER'), 'Overlay must retain explicit AI adjudication provenance')
            scopes, anchors = (review.get('scopes', []), review.get('confirmed_frames', []))
            require(scopes and anchors and all((type(f) is int for f in anchors)), 'Overlay needs bounded scopes and confirmed frames')
            for scope in scopes:
                start, end = (scope.get('start_frame'), scope.get('end_frame'))
                require(type(scope.get('track_id')) is int and scope['track_id'] > 0 and (type(start) is int) and (type(end) is int) and (0 <= start <= end < job['metadata']['frame_count']) and (scope.get('raw_family') in ('person', 'vehicle')), 'Invalid overlay scope')
            if review['type'] in ('PEDESTRIAN_ROLE', 'COMPONENT_OF'):
                require(all((s['raw_family'] == 'person' for s in scopes)), 'Role review may only relabel raw person measurements')
            if review['type'] == 'COMPONENT_OF':
                require(bool(review.get('component_of_unit_id')), 'Rider review needs parent')
            if review['type'] in ('SAME_VEHICLE', 'SPLIT_IDENTITY'):
                require(all((s.get('physical_unit_id', review.get('physical_unit_id')) and s.get('episode_id', review.get('episode_id')) for s in scopes)), 'Identity overlay needs unit and episode')
            evidence = review.get('evidence', [])
            require(evidence, 'Adjudication must bind retained evidence')
            proofs = {}
            for entry in evidence:
                path = bound(root, entry['path'], entry['sha256'], guarded)
                proof = read(path)
                frame = entry.get('frame_index')
                require(frame in anchors, 'Overlay evidence is not a confirmed frame')
                if 'checks' in proof:
                    require(proof.get('source_sha256') == source['video_sha256'] and proof.get('retained_cache_file_sha256') == source['records_sha256'], 'Overlay pixel evidence belongs to another input')
                    found = [c for c in proof['checks'] if c['frame_index'] == frame]
                    require(len(found) == 1 and found[0].get('status') == 'PASS' and (found[0].get('actual_bgr_pixel_sha256') == entry.get('source_frame_pixel_sha256')) and (found[0].get('expected_retained_detector_input_pixel_sha256') == entry.get('source_frame_pixel_sha256')), 'Overlay native pixel evidence differs')
                    check = found[0]
                    png = check.get('retained_native_png_path')
                    if png:
                        image = path.parent.parent / png
                        require(image.is_file() and sha(image) == check.get('sequentially_decoded_native_png_sha256'), 'Retained adjudication image bytes differ')
                        guarded.append({'path': str(image), 'sha256': sha(image)})
                    proofs[frame] = {'raw_bgr_pixel_sha256': entry['source_frame_pixel_sha256'], 'observations': []}
                else:
                    require(proof.get('video_sha256') == source['video_sha256'] and proof.get('source_records_sha256') == source['records_sha256'], 'Overlay pixel evidence belongs to another input')
                    images = [image for image in proof.get('images', []) if image['frame_index'] == frame]
                    require(len(images) == 1 and images[0].get('verified_decode_pixel_sha256') is True and (images[0].get('raw_bgr_pixel_sha256') == entry.get('source_frame_pixel_sha256')), 'Overlay native pixel evidence differs')
                    proofs[frame] = images[0]
            require(set(anchors) <= set(proofs), 'Every overlay anchor needs pixel evidence')
            require(all((any((s['start_frame'] <= f <= s['end_frame'] for s in scopes)) for f in anchors)), 'Overlay anchor outside its bounded scope')
            review['_pixel_anchor_proofs'] = proofs
    return videos
