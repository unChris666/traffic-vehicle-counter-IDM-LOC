"""Source-only review fixture; no detector, tracker, ReID or counting replay."""
from pathlib import Path
import csv
import gzip
import hashlib
import json
import sys

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
VIDEO = Path('/tmp/qc-source/TGDI-WEEKDAY-SIANG.mp4')
CACHE = Path('/tmp/qc-donor/phase_8_tgdi_research/20261015T083731_664817Z/weekday_siang/track_records.jsonl.gz')
BASE = ROOT / 'results/b_v7/execution/pilot_v7_machine_final/weekday_siang'
BRIEF = Path('/workspace/attachments/2d5b66c7-b363-4659-bd5f-89492f47a658/Teks tempel.txt')
SELECTED = [7860, 7874, 7888, 7899, 7904, 7905, 7907, 7915, 7920, 7928,
            7930, 7935, 7942, 7950, 7955, 7960, 7964]
TRACKS = {4808, 4843, 4913}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(name, value):
    data = (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode()
    path = OUT / name
    path.write_bytes(gzip.compress(data, mtime=0) if path.suffix == '.gz' else data)


def main():
    if (OUT / 'source_decode_receipt.json').exists():
        raise RuntimeError('Preserve retained fixture; use a new version to rebuild')
    sys.path.insert(0, str(ROOT / 'notebooks'))
    from phase_5_geometry_helpers import Geometry
    from phase_8_b_v5_counting import finite_band
    source = json.loads((BASE / 'source_identity.json').read_text())
    assert sha(VIDEO.read_bytes()) == source['video_sha256']
    assert sha(CACHE.read_bytes()) == source['records_sha256']
    geometry_path = BASE / 'geometry.json'
    geometry = Geometry.from_draft(geometry_path, 640, 480)
    records = []
    with gzip.open(CACHE, 'rt') as handle:
        for line in handle:
            row = json.loads(line)
            if 7800 <= row['frame_index'] <= 8010:
                records.append(row)
            if row['frame_index'] > 8010:
                break
    assert [r['frame_index'] for r in records] == list(range(7800, 8011))
    write('source_records_7800_8010.json.gz', records)
    write('source_identity.json', source)
    (OUT / 'geometry.json').write_bytes(geometry_path.read_bytes())
    (OUT / 'user_task.txt').write_bytes(BRIEF.read_bytes())
    indexed = {r['frame_index']: r for r in records}
    measured = []
    selected_by_frame = {}
    for row in records:
        observations = []
        for item in row['emitted_tracks']:
            if item['track_id'] not in TRACKS:
                continue
            box = item['raw_bbox']
            detection = row['raw_detections'][item['original_detection_index']]
            assert box == detection['bbox_xyxy_pixels']
            assert item['class_id'] == detection['class_id'] and item['emitted'] is True
            bc = [(box[0] + box[2]) / 2, box[3]]
            band = finite_band(bc, geometry, 25)
            ref = {'frame_index': row['frame_index'], 'track_id': item['track_id'],
                'original_detection_index': item['original_detection_index'],
                'raw_bbox': box, 'point': bc, 'class_name': item['class_name'],
                'class_id': item['class_id'], 'confidence': item['confidence'],
                'observed': True, 'emitted': item['emitted'],
                'observed_basis': 'EXACT_RETAINED_DETECTION_INDEX_BBOX_CLASS_MATCH',
                'measurement_provenance': item['measurement_provenance'],
                'roi': geometry.side(bc), 'finite_band': band}
            measured.append(ref)
            observations.append(item)
        selected_by_frame[row['frame_index']] = observations
    write('selected_measurements.json.gz', measured)
    with (OUT / 'geometry_measurements.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['frame_index', 'track_id', 'roi',
            'band', 'signed_distance_px', 'projection', 'bc_x', 'bc_y'])
        writer.writeheader()
        for ref in measured:
            band = ref['finite_band']
            writer.writerow({'frame_index': ref['frame_index'], 'track_id': ref['track_id'],
                'roi': ref['roi'], 'band': band['inside'], 'signed_distance_px': band['signed_distance_px'],
                'projection': band['projection'], 'bc_x': ref['point'][0], 'bc_y': ref['point'][1]})
    pixels, images = [], []
    capture = cv2.VideoCapture(str(VIDEO))
    assert capture.isOpened()
    wanted = set(SELECTED)
    for frame in range(max(SELECTED) + 1):
        ok, image = capture.read()
        assert ok, f'Decode failed at source frame {frame}'
        if frame not in wanted:
            continue
        actual = sha(image.tobytes())
        expected = indexed[frame]['detector_input_frame_pixel_sha256']
        assert actual == expected, f'Source pixel mismatch {frame}'
        pixels.append({'frame_index': frame, 'source_frame_pixel_sha256': actual,
                       'matches_frozen_detector_input': True})
        annotated = image.copy()
        cv2.line(annotated, tuple(round(v) for v in geometry.p1),
                 tuple(round(v) for v in geometry.p2), (0, 255, 255), 1)
        for item in selected_by_frame[frame]:
            b = [round(v) for v in item['raw_bbox']]
            cv2.rectangle(annotated, tuple(b[:2]), tuple(b[2:]), (255, 255, 255), 1)
            cv2.putText(annotated, str(item['track_id']), (b[0], max(12, b[1] - 3)),
                        cv2.FONT_HERSHEY_SIMPLEX, .42, (255, 255, 255), 1, cv2.LINE_AA)
        crop = annotated[145:350, 60:640]
        crop = cv2.resize(crop, (580, 205), interpolation=cv2.INTER_AREA)
        tile = np.zeros((231, 580, 3), np.uint8)
        tile[26:] = crop
        cv2.putText(tile, f'SOURCE {frame}; raw vehicle boxes; yellow finite line', (5, 18),
                    cv2.FONT_HERSHEY_SIMPLEX, .43, (255, 255, 255), 1, cv2.LINE_AA)
        images.append(tile)
    capture.release()
    for group, tiles in enumerate([images[i:i+6] for i in range(0, len(images), 6)]):
        while len(tiles) % 2:
            tiles.append(np.zeros_like(images[0]))
        sheet = np.vstack([np.hstack(tiles[i:i+2]) for i in range(0, len(tiles), 2)])
        path = OUT / f'source_contact_{group+1}.jpg'
        assert cv2.imwrite(str(path), sheet, [cv2.IMWRITE_JPEG_QUALITY, 94])
    receipt = {'schema_version': 'phase9_b_v8_blocker_source_fixture_v1',
        'source_identity': source, 'source_video_path': str(VIDEO), 'source_cache_path': str(CACHE),
        'decode_method': 'SEQUENTIAL_FROM_SOURCE_FRAME_ZERO', 'decoded_through_frame': max(SELECTED),
        'selected_frames': pixels, 'raw_source_frame_count': len(records),
        'selected_measurement_count': len(measured),
        'geometry_assessment_only_not_counting_replay': True,
        'new_model_tracker_reid_counting_enhancement_execution': False,
        'user_decision_authority': {'path': (OUT / 'user_task.txt').relative_to(ROOT).as_posix(),
            'sha256': sha(BRIEF.read_bytes()), 'kind': 'EXPLICIT_USER_INSTRUCTION'},
        'visual_review_status': 'SOURCE_IMAGES_GENERATED_AWAIT_REVIEW',
        'fixture_is_development_not_holdout': True}
    write('source_decode_receipt.json', receipt)
    print(json.dumps({'source_frames': len(records), 'measured_target_observations': len(measured),
                      'source_pixels_verified': len(pixels)}))


if __name__ == '__main__':
    main()
