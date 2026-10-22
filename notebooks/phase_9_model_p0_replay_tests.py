import copy
import unittest
from phase_9_model_p0_replay import adapt_records,SOURCE_SHA256


class ClipAdapterTests(unittest.TestCase):
    def rows(self):
        result=[]
        for local in range(2):
            detection={"bbox_xyxy_pixels":[10.,20.,30.,40.],"class_id":2,"class_name":"car","confidence":.7}
            track={"track_id":1,"original_detection_index":0,"raw_bbox":detection["bbox_xyxy_pixels"],
                   "frame_index":7380+local,"class_id":2,"class_name":"car","confidence":.7,
                   "observed":True,"emitted":True}
            result.append({"frame_index":7380+local,"clip_local_frame_index":local,"video_sha256":SOURCE_SHA256,
                           "width":640,"height":480,"detections":[detection],"emitted_tracks":[track]})
        return result

    def test_explicit_mapping_without_prehistory(self):
        frames,mapping=adapt_records(self.rows(),end_frame=7381)
        self.assertEqual([r["frame_index"] for r in frames],[0,1])
        self.assertEqual(frames[0]["observations"][0]["source_global_frame_index"],7380)
        self.assertEqual(mapping["synthetic_prehistory_frames"],0)
        self.assertFalse(frames[0]["observations"][0]["association_verified"])
        self.assertEqual(frames[0]["observations"][0]["original_detection_index"],0)

    def test_adapter_to_identity_to_counting_retains_measured_source_link(self):
        from phase_5_geometry_helpers import Geometry
        import phase_8_b_v5_identity as identity
        import phase_8_b_v5_counting as counting
        from phase_8_b_v5_counting_tests import POLICY
        rows=self.rows()
        for row,y in zip(rows,(180.,300.)):
            box=[280.,y-160.,360.,y]
            row['detections'][0]['bbox_xyxy_pixels']=box
            row['emitted_tracks'][0]['raw_bbox']=box
        frames,_=adapt_records(rows,end_frame=7381)
        geometry=Geometry((10,240),(630,240),((0,0),(640,0),(640,200),(0,200)),
            ((0,280),(640,280),(640,480),(0,480)),640,480,'synthetic-native')
        policy=copy.deepcopy(POLICY);policy['identity']=identity.experimental_identity_policy()
        resolved=identity.prepare_identity_frames(frames,geometry,policy)
        result=counting.replay_frames(resolved['frames'],geometry,
            source_identity={'video_sha256':SOURCE_SHA256,'records_sha256':'b'*64,
                             'geometry_sha256':'c'*64,'width':640,'height':480},policy=policy)
        self.assertEqual(result['aggregate']['measured_total'],1)
        self.assertTrue(all(ref['original_detection_index']==0
            for ref in result['events'][0]['evidence']['source_refs']))

    def test_out_of_frame_raw_box_rejected(self):
        rows=self.rows()
        for row in rows:
            row['detections'][0]['bbox_xyxy_pixels']=[10.,20.,641.,40.]
            row['emitted_tracks'][0]['raw_bbox']=[10.,20.,641.,40.]
        with self.assertRaises(ValueError):adapt_records(rows,end_frame=7381)

    def test_missing_or_foreign_frame_rejected(self):
        rows=self.rows();rows[1]["frame_index"]=7382
        with self.assertRaises(ValueError):adapt_records(rows,end_frame=7381)

    def test_bbox_or_class_or_score_cannot_be_rewritten(self):
        for key,new in (("raw_bbox",[11.,20.,30.,40.]),("class_name","truck"),("confidence",.8)):
            rows=self.rows();rows[0]["emitted_tracks"][0][key]=new
            with self.subTest(key=key),self.assertRaises(ValueError):adapt_records(rows,end_frame=7381)

    def test_prediction_and_duplicate_source_rejected(self):
        rows=self.rows();rows[0]["emitted_tracks"][0]["observed"]=False
        with self.assertRaises(ValueError):adapt_records(rows,end_frame=7381)
        rows=self.rows();other=copy.deepcopy(rows[0]["emitted_tracks"][0]);other["track_id"]=2
        rows[0]["emitted_tracks"].append(other)
        with self.assertRaises(ValueError):adapt_records(rows,end_frame=7381)

    def test_legacy_role_and_alias_not_inherited(self):
        rows=self.rows();rows[0]["emitted_tracks"][0].update(unit_id="oldgroup",role="pedestrian",review_ref={"old":True})
        frames,_=adapt_records(rows,end_frame=7381)
        obj=frames[0]["observations"][0]
        self.assertEqual(obj["role"],"vehicle");self.assertNotEqual(obj["unit_id"],"oldgroup")
        self.assertNotIn("review_ref",obj)


if __name__=='__main__':unittest.main()
