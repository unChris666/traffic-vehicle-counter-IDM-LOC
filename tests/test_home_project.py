import tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from traffic_location.artifacts import write,read
from traffic_location.integration.gradio_app import Controller,build_app,annotation_buttons
from test_gradio_ui import inputs,VIDEOS

class ProjectUITests(unittest.TestCase):
    def test_home_result_tabs_and_eight_rows(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);write(root/'config/experiment.json',{'videos':[]})
            app,c=build_app(root/'app',root/'config',runtime_factory=Mock())
            config=app.get_config_file()['components']
            self.assertEqual([v['props']['label'] for v in config if v['type']=='tabitem'],['HOME','RESULT'])
            self.assertEqual(sum(v['props'].get('label')=='Nama video' for v in config),8)
            self.assertTrue(any(v['props'].get('value')=='Save Project' for v in config));app.close()
    def test_save_project_is_metadata_not_engine_execution(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);write(root/'config/experiment.json',{'videos':[{'filename':v+'.mp4'} for v in VIDEOS]})
            runtime=Mock();factory=Mock(return_value=runtime)
            controller=Controller(root/'app',root/'config',runtime_factory=factory)
            values=inputs()+['Upload video',[],'Toko Uji',False]
            status=controller.save_project(*values)
            self.assertIn('Project tersimpan',status);runtime.execute.assert_not_called()
            snapshot=next((controller.base/'projects').glob('*.json'));project=read(snapshot)
            self.assertEqual(project['store_name'],'Toko Uji');self.assertEqual(len(project['kdtk']),4)
            runtime.connect.return_value.bucket.return_value.blob.return_value.upload_from_filename.assert_called_once()
            values[1]='BAD';self.assertIn('4 karakter',controller.save_project(*values))
    def test_no_annotated_link_is_fabricated_for_original_input(self):
        buttons=annotation_buttons({'traffic_counts':[{'day_group':'weekday','session':'pagi','filename':'actual.mp4'}]})
        self.assertFalse(buttons[0]['interactive']);self.assertIsNone(buttons[0]['link']);self.assertEqual(buttons[8]['value'],'actual.mp4')

if __name__=='__main__':unittest.main()
