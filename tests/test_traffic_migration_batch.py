"""Reject a bad locked batch before counting any of its videos."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from traffic_location.artifacts import read, write, sha
from traffic_location.traffic.contracts.source import ArtifactRef
from traffic_location.traffic.application.batch import run_batch
ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / 'results/traffic_migration/20261024/locked_batch'

class LockedBatchTests(unittest.TestCase):
    def setUp(self):
        self.manifest = read(LOCK / 'manifest.json')
        self.requests = read(LOCK / 'requests.json')

    def rejected(self, message):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'manifest.json'; write(path, self.manifest)
            with patch('traffic_location.traffic.application.batch.run') as engine:
                with self.assertRaisesRegex(ValueError, message):
                    run_batch(self.requests, locked_manifest=ArtifactRef(str(path), sha(path)), root=ROOT)
                engine.assert_not_called()

    def test_unknown_manifest_schema(self):
        self.manifest['schema_version'] = 'traffic_batch_run_v99'
        self.rejected('supported locked batch')

    def test_duplicate_request_slots(self):
        self.requests[1] = deepcopy(self.requests[0])
        self.rejected('Eight unique expected')

    def test_prefix_cannot_claim_full_video(self):
        self.requests[0]['frame_count'] = 32
        self.rejected('Full-video frame scope differs')

    def test_changed_counting_policy_rejected(self):
        self.requests[0]['artifacts']['policy']['sha256'] = 'e'*64
        self.rejected('Mixed counting policy')

    def test_changed_geometry_rejected(self):
        self.requests[0]['artifacts']['geometry']['sha256'] = 'e'*64
        self.requests[0]['source_identity']['geometry_sha256'] = 'e'*64
        self.rejected('Batch artifact lock differs')

    def test_source_identity_foreign_video(self):
        self.requests[0]['source_identity']['video_sha256'] = 'e'*64
        self.rejected('Batch source differs')

    def test_machine_review_mixing_rejected(self):
        self.requests[0]['profile'] = 'review_assisted'
        self.rejected('Fresh machine input cannot inherit')

if __name__ == '__main__':
    unittest.main()
