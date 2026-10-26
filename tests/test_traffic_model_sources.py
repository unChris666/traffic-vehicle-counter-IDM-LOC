"""Owner GCS addresses are shared by readiness and model staging."""
from pathlib import Path
import unittest
from unittest.mock import patch
from traffic_location.artifacts import read
from traffic_location.traffic.adapters.model_sources import gcs_model_ref

ROOT=Path(__file__).resolve().parents[1]

class TrafficModelSourcesTests(unittest.TestCase):
    def test_owner_model_uris_exact(self):
        artifacts=read(ROOT/'results/t7sl_modular/config/fresh_request.json')['artifacts']
        expected={
          'detector':'gs://feeder-location-intelligent/models/traffic/detector/401cea9ab23ad19246ff7744859816bc599f350e93c9dd30367b6f0a0745d0b7/yolo26m.pt',
          'reid':'gs://feeder-location-intelligent/models/traffic/reid/8529c383197ae4c468eda535d1b165f8b4162cf17bf5fbcff49c7cb6455bc0bb/yolo26n-reid.onnx'}
        for role,uri in expected.items():
            ref=gcs_model_ref(role,artifacts[role])
            self.assertEqual('gs://'+ref['bucket']+'/'+ref['object'],uri)
            self.assertEqual(ref['sha256'],artifacts[role]['sha256'])
    def test_wrong_role_name_or_hash_rejected(self):
        for role,artifact in [('unknown',{'path':'x','sha256':'a'*64}),('detector',{'path':'wrong.pt','sha256':'a'*64}),('reid',{'path':'yolo26n-reid.onnx','sha256':'bad'})]:
            with self.subTest(role=role),self.assertRaises(ValueError):gcs_model_ref(role,artifact)

if __name__=='__main__':unittest.main()
