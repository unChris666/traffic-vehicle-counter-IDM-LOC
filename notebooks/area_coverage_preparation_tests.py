"""Execute the published preparation cell in fresh globals with isolated services.

Real filesystem/cache/tar code runs; pip/apt, HTTP, basemap build and GCS use
explicit fixtures. This is not a national ingestion or live cloud test.
"""
import contextlib,hashlib,io,json,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import folium  # Load native dependencies before temporary sys.modules patches.

ROOT=Path(__file__).resolve().parents[1]


class Blob:
    def __init__(self,bucket,name):self.bucket=bucket;self.name=name;self.metadata={};self.generation=None
    def exists(self):return self.name in self.bucket.objects
    def reload(self):
        data=self.bucket.objects[self.name];self.metadata=data['metadata'];self.generation=data['generation'];self.size=len(data['bytes'])
    def store(self,body,condition):
        old=self.bucket.objects.get(self.name);actual=old['generation'] if old else 0
        if condition!=actual:raise RuntimeError('Fixture generation precondition violated')
        self.bucket.objects[self.name]={'bytes':body,'metadata':dict(self.metadata),'generation':actual+1}
    def upload_from_filename(self,path,**kw):
        if self.bucket.fail_upload:raise RuntimeError('FIXTURE_UPLOAD_FAILED')
        assert kw['checksum']=='crc32c'
        self.bucket.events.append('archive_upload');self.store(Path(path).read_bytes(),kw['if_generation_match'])
    def upload_from_string(self,body,**kw):
        self.bucket.events.append('manifest_upload')
        self.store(body.encode() if isinstance(body,str) else body,kw['if_generation_match'])


class Bucket:
    def __init__(self):self.name='TEST_ONLY';self.objects={};self.events=[];self.fail_upload=False
    def blob(self,name):return Blob(self,name)


class Harness:
    def __init__(self,root):
        self.root=root;self.bucket=Bucket();self.commands=[];self.basemap_error=None;self.native_error=False
        self.basemap={'status':'READY','scope':'FIXTURE_NOT_NATIONAL_DATA'};self.stdout=io.StringIO()

    def path(self,value):
        value=str(value)
        return self.root/value.removeprefix('/kaggle/working/') if value.startswith('/kaggle/working/') else Path(value)

    def command(self,command,**kw):
        self.commands.append(command)
        if 'download' in command and 'pip' in command:
            dest=Path(command[command.index('--dest')+1]);(dest/'fixture.whl').write_bytes(b'fixture wheel, never installed')
        elif command[:2]==['apt-get','download']:
            if self.native_error:raise RuntimeError('FIXTURE_NATIVE_DOWNLOAD_FAILED')
            (Path(kw['cwd'])/'fixture.deb').write_bytes(b'fixture deb, never installed')
        elif command[0]=='dpkg-deb':
            dest=Path(command[-1]);(dest/'usr/lib/fixture').mkdir(parents=True,exist_ok=True)
            (dest/'usr/lib/fixture/libfixture.so').write_bytes(b'fixture native file, never loaded')
        return SimpleNamespace(returncode=0,stdout='',stderr='')

    def fetch(self,url,**kwargs):
        css=url.endswith('.css')
        return SimpleNamespace(text='/*# sourceMappingURL=debug.map */ p{background:url("font.woff2")}' if css else 'window.TEST=true;',
            content=b'fixture font',headers={'content-type':'font/woff2'},raise_for_status=lambda:None)

    def build(self,*args):
        self.bucket.events.append('basemap_check')
        if self.basemap_error:raise self.basemap_error
        return self.basemap

    def execute(self,source=None):
        source=source or ''.join(json.loads((ROOT/'notebooks/area_gcs_runtime_preparation.ipynb').read_text())['cells'][-1]['source'])
        # Deliberately do not inherit test-module imports or notebook state.
        env={'__name__':'hermetic_preparation_cell'};exec(compile(source,'published_preparation_cell','exec'),env)
        env['Path']=self.path
        env['fingerprint']=lambda:{'python':'fixture','retained_packages':{'numpy':'fixture'}}
        secret=types.ModuleType('kaggle_secrets');secret.UserSecretsClient=lambda:SimpleNamespace(get_secret=lambda name:'{}')
        storage=types.ModuleType('google.cloud.storage');storage.Client=lambda **kw:SimpleNamespace(bucket=lambda name:self.bucket)
        basemap=types.ModuleType('national_basemap');basemap.ensure_basemap=self.build
        # The Google namespace itself is real; credential construction/network is not.
        with patch.dict(sys.modules,{'kaggle_secrets':secret,'google.cloud.storage':storage,'national_basemap':basemap}),patch(
            'google.oauth2.service_account.Credentials.from_service_account_info',return_value=object()),patch(
            'subprocess.run',side_effect=self.command),patch('subprocess.check_output',return_value='fixture-package\n'),patch(
            'requests.get',side_effect=self.fetch),contextlib.redirect_stdout(self.stdout):
            env['run']()
        return env


class PreparationExecutionTests(unittest.TestCase):
    def test_fresh_cell_runs_full_control_flow_and_commits_last(self):
        with tempfile.TemporaryDirectory() as d:
            harness=Harness(Path(d));env=harness.execute()
            self.assertIn('shutil',env)
            self.assertEqual(sum('download' in c and 'pip' in c for c in harness.commands),1)
            self.assertEqual(harness.bucket.events,['basemap_check','archive_upload','manifest_upload'])
            manifest=next(v for k,v in harness.bucket.objects.items() if k.endswith('/manifest.json'))
            self.assertEqual(json.loads(manifest['bytes'])['basemap']['status'],'READY')
            self.assertIn('\nREADY:', '\n'+harness.stdout.getvalue())
            inventory=json.loads(next(harness.root.rglob('bundle.json')).read_text())
            self.assertNotIn('bundle.json',inventory['files'])

    def test_second_run_reuses_verified_wheels(self):
        with tempfile.TemporaryDirectory() as d:
            harness=Harness(Path(d));harness.execute();harness.commands=[];harness.execute()
            self.assertFalse(any('download' in c and 'pip' in c for c in harness.commands))

    def test_corrupt_cache_rejected_before_build_or_publication(self):
        with tempfile.TemporaryDirectory() as d:
            harness=Harness(Path(d));harness.execute();before=dict(harness.bucket.objects);harness.bucket.events=[]
            next(harness.root.rglob('fixture.whl')).write_bytes(b'CORRUPT')
            with self.assertRaisesRegex(RuntimeError,'WHEEL_CACHE_CHANGED'):harness.execute()
            self.assertEqual(harness.bucket.events,[]);self.assertEqual(harness.bucket.objects,before)

    def test_basemap_failure_or_partial_never_publishes_ready(self):
        for kind in ['error','partial']:
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as d:
                harness=Harness(Path(d))
                if kind=='error':harness.basemap_error=RuntimeError('FIXTURE_BUILD_FAILED')
                else:harness.basemap={'status':'BUILDING'}
                with self.assertRaises(RuntimeError):harness.execute()
                self.assertFalse(harness.bucket.objects)
                self.assertNotIn('\nREADY:', '\n'+harness.stdout.getvalue())

    def test_upload_failure_never_publishes_ready(self):
        with tempfile.TemporaryDirectory() as d:
            harness=Harness(Path(d));harness.bucket.fail_upload=True
            with self.assertRaisesRegex(RuntimeError,'FIXTURE_UPLOAD_FAILED'):harness.execute()
            self.assertNotIn('manifest_upload',harness.bucket.events)
            self.assertNotIn('\nREADY:', '\n'+harness.stdout.getvalue())

    def test_native_dependency_failure_stops_before_basemap(self):
        with tempfile.TemporaryDirectory() as d:
            harness=Harness(Path(d));harness.native_error=True
            with self.assertRaisesRegex(RuntimeError,'FIXTURE_NATIVE_DOWNLOAD_FAILED'):harness.execute()
            self.assertEqual(harness.bucket.events,[])


if __name__=='__main__':unittest.main()
