import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np
import nighttime_input_inspection as inspect
import nighttime_review_filter as filters


class FilterTests(unittest.TestCase):
    def setUp(self):
        self.frame = np.random.default_rng(7).integers(0, 256, (17, 19, 3), dtype=np.uint8)
        self.config = {'schema_version': filters.SCHEMA, 'operation_order': filters.ORDER.copy(),
                       'profiles': {k: dict(filters.RAW) for k in filters.CONDITIONS},
                       'videos': [{'filename': 'actual.mp4', 'source_sha256': 'a'*64, 'condition': None,
                                   'settings': dict(filters.RAW)}]}

    def test_raw_is_exact_copy(self):
        result = filters.apply_filter(self.frame, filters.RAW)
        np.testing.assert_array_equal(self.frame, result)
        self.assertIsNot(self.frame, result)

    def test_invalid_parameters_fail_closed(self):
        for change in [{'gamma': 0}, {'gamma': True}, {'gamma': float('nan')}, {'extra': 1}, {'shadows': 101}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                filters.apply_filter(self.frame, {**filters.RAW, **change})

    def test_no_resize_and_source_immutable(self):
        before = self.frame.copy()
        result = filters.apply_filter(self.frame, dict(gamma=.7, exposure=.5, brightness=4, shadows=20, sharpness=.5))
        self.assertEqual(result.shape, self.frame.shape)
        np.testing.assert_array_equal(before, self.frame)

    def test_rgb_js_and_bgr_python_pixel_parity(self):
        module = Path(__file__).resolve().parents[1]/'results/nighttime_review_filter.js'
        script = 'const f=require(process.argv[1]);let s="";process.stdin.on("data",c=>s+=c);process.stdin.on("end",()=>{const d=JSON.parse(s);console.log(JSON.stringify(Array.from(f.apply(d.pixels,d.width,d.height,d.settings))))});'
        settings = [dict(filters.RAW), dict(gamma=.7, exposure=.3, brightness=4, shadows=12, sharpness=.5),
                    dict(gamma=2.2, exposure=-1.1, brightness=-17, shadows=-25, sharpness=2)]
        ramp = np.tile(np.arange(256, dtype=np.uint8).reshape(16,16,1), (1,1,3))
        for frame in [self.frame, ramp, np.zeros((1,1,3), np.uint8), np.full((1,1,3),255,np.uint8)]:
            for s in settings:
                rgb = frame[:,:,::-1].copy()
                inp = json.dumps({'pixels': rgb.reshape(-1).tolist(), 'width': frame.shape[1], 'height': frame.shape[0], 'settings': s})
                proc = subprocess.run(['node', '-e', script, str(module)], input=inp, text=True, capture_output=True, check=True)
                actual = np.asarray(json.loads(proc.stdout),dtype=np.uint8).reshape(rgb.shape)[:,:,::-1]
                np.testing.assert_array_equal(filters.apply_filter(frame,s), actual)

    def test_eight_profiles_independent(self):
        self.config['profiles']['weekday_malam']['gamma'] = .7
        c = filters.validate_config(self.config)
        self.assertEqual(c['profiles']['weekend_malam']['gamma'], 1)
        self.assertEqual(filters.settings_for_video(c, 'a'*64)['gamma'], 1)

    def test_no_filename_or_slot_fallback(self):
        with self.assertRaises(ValueError): filters.settings_for_video(self.config, 'b'*64)

    def test_unknown_condition_allowed_not_fabricated(self):
        self.assertIsNone(filters.validate_config(self.config)['videos'][0]['condition'])

    def test_order_and_duplicate_source_rejected(self):
        for edit in ['order', 'duplicate', 'missing_slot']:
            c = copy.deepcopy(self.config)
            if edit == 'order': c['operation_order'].reverse()
            elif edit == 'duplicate': c['videos'].append(copy.deepcopy(c['videos'][0]))
            else: del c['profiles']['weekday_pagi']
            with self.assertRaises(ValueError): filters.validate_config(c)

    def test_prepared_frame_equals_preview_contract(self):
        self.config['videos'][0]['settings']['gamma'] = .7
        result, proof = filters.prepare_inference_frame(self.frame, self.config, 'a'*64)
        np.testing.assert_array_equal(result, filters.apply_filter(self.frame,self.config['videos'][0]['settings']))
        self.assertEqual(len(proof['output_bgr_sha256']),64)

    def test_portable_html_embeds_exact_shared_javascript(self):
        root = Path(__file__).resolve().parents[1]
        html = (root/'results/review-filter.html').read_text()
        shared = (root/'results/nighttime_review_filter.js').read_text()
        self.assertIn('<script id="filter-contract">\n'+shared+'</script>', html)
        self.assertNotIn('src="nighttime_review_filter.js"', html)


class InspectionTests(unittest.TestCase):
    def test_unknown_metadata_remains_unknown(self):
        for value in [0, float('nan'), None, -1]: self.assertIsNone(inspect.positive(value))
        for value in ['0/0', 'N/A', None]: self.assertIsNone(inspect.fraction_rate(value))

    def test_missing_dataset_blocks(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(FileNotFoundError):
            inspect.inspect_dataset(Path(tmp)/'missing', Path(tmp)/'out', execution_context='test')

    def test_output_under_input_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            inspect.inspect_dataset(tmp, Path(tmp)/'output', execution_context='test')

    def test_corrupt_actual_file_not_reported_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'invalid.mp4';source.write_bytes(b'not a video')
            row=inspect.inspect_video(source,root/'out',root)
            self.assertEqual(row['frame_count_decoded'],0)
            self.assertEqual(row['decode_status'],'UNREADABLE_OR_NO_DECODABLE_FRAMES')
            self.assertIsNone(row['codec'])

    def test_sequential_sampling_and_native_dimensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'five.avi'
            writer=cv2.VideoWriter(str(source),cv2.VideoWriter_fourcc(*'MJPG'),10,(32,24))
            self.assertTrue(writer.isOpened())
            for i in range(5): writer.write(np.full((24,32,3),i*40,np.uint8))
            writer.release();before=inspect.file_sha256(source)
            row=inspect.inspect_video(source,root/'out',root)
            self.assertEqual(row['frame_count_decoded'],5)
            self.assertEqual([x['frame_index'] for x in row['samples']],[0,1,2,3,4])
            self.assertEqual(row['decoded_dimensions'],[(32,24)])
            self.assertEqual(before,inspect.file_sha256(source))

    def test_missing_ffprobe_is_explicit(self):
        with patch.object(inspect.shutil,'which',return_value=None):
            result=inspect.probe('unused')
            self.assertFalse(result['available']);self.assertEqual(result['stream'],{})


if __name__ == '__main__': unittest.main()
