"""Coordinate SAVE is independent of video/PPAC readiness and engine work."""
import importlib.util,tempfile,unittest,subprocess,signal
from pathlib import Path
from unittest.mock import Mock
from traffic_location.artifacts import write,read
from traffic_location.integration.gradio_app import Controller
from traffic_location.integration.failure_details import details
class LocationSaveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        write(self.root/'config/experiment.json',{'videos':[]});self.factory=Mock()
        self.c=Controller(self.root/'ui',self.root/'config',runtime_factory=self.factory)
    def test_invalid_coordinate_is_not_persisted_or_sent_to_engine(self):
        for lat,lon in ((float('nan'),106),(-6,999),(True,106)):
            html,status=self.c.save_location(lat,lon)
            self.assertEqual(html,'');self.assertIn('Koordinat',status)
        self.assertFalse((self.root/'ui/locations').exists());self.factory.assert_not_called()
    @unittest.skipUnless(importlib.util.find_spec('folium'),'Run GIS presentation environment')
    def test_save_only_coordinates_without_store_videos_rwi_or_cloud(self):
        html,status=self.c.save_location(-6.125998763810821,106.70635526552414)
        self.assertIn('height:460px',html);self.assertIn('Calon toko',html);self.assertIn('Snapshot GCS dibuat saat Running',status)
        files=list((self.root/'ui/locations').glob('*.json'));self.assertEqual(len(files),1)
        self.assertEqual(read(files[0])['longitude'],106.70635526552414)
        self.assertFalse(list((self.root/'ui').rglob('job-input.json')));self.factory.assert_not_called()
    def test_sigint_does_not_get_classified_as_computation_fault(self):
        error=subprocess.CalledProcessError(-signal.SIGINT,['python','prepare-area'])
        self.assertEqual(details(self.root,error)['category'],'INTERRUPTED')
