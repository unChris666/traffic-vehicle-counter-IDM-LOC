"""Explicit runtime boundaries: GDAL selection; Shapely Recount. No network."""
import shutil,tempfile,platform
from pathlib import Path
from .snapshot import SnapshotAdapter
from ..artifacts import read,write,require,sha,semantic_hash
from ..persistence import verify_manifest

def run_selection(request,*,root):
 require(set(request)=={'schema_version','snapshot','manifest_sha256'} and request['schema_version']=='location_selection_request_v1','Invalid snapshot request')
 adapter=SnapshotAdapter(Path(root)/request['snapshot'],request['manifest_sha256'])
 selection,capacity=adapter.selection_capacity()
 from osgeo import gdal,ogr,osr
 from .recount import engine_digest
 code_hash=engine_digest()
 runtime={'python':platform.python_version(),'gdal':gdal.VersionInfo('RELEASE_NAME'),
  'geos':'.'.join(str(f()) for f in [ogr.GetGEOSVersionMajor,ogr.GetGEOSVersionMinor,ogr.GetGEOSVersionMicro]),
  'proj':'.'.join(str(f()) for f in [osr.GetPROJVersionMajor,osr.GetPROJVersionMinor,osr.GetPROJVersionMicro])}
 return {'schema_version':'location_selection_result_v1','execution_status':'SUCCEEDED',
  'result_quality':'PARTIAL' if 'PARTIAL' in {selection['status'],capacity['status'],adapter.source_summary['analysis_status']} else 'COMPLETE_IN_SCOPE',
  'source_analysis_status':adapter.source_summary['analysis_status'],'operation':'OFFLINE_SELECTION_CAPACITY_NOT_ROUTING',
  'claim_type':'EXPERIMENTAL_SCENARIO','source_manifest_sha256':adapter.manifest_sha256,
  'result_version':semantic_hash({'source':adapter.manifest_sha256,'selection':selection,'capacity':capacity,'runtime':runtime,'code':code_hash}),
  'engine_sha256':code_hash,'runtime':runtime,'selection':selection,'capacity':capacity}

def run_recount(request,*,root):
 require(set(request)<={'schema_version','packet','manifest_sha256','previous'} and
  set(request)>={'schema_version','packet','manifest_sha256'} and request['schema_version']=='location_recount_request_v1','Invalid Recount request')
 packet=(Path(root)/request['packet']).resolve()
 require(sha(packet/'manifest.json')==request['manifest_sha256'],'Recount packet binding differs')
 manifest=verify_manifest(packet)
 require(manifest['schema_version']=='li5_manifest_v1','Expected a finalized LI5 offline packet')
 binding=read(packet/'input_binding.json');parent=read(packet/'input/parent_manifest.json')
 require(sha(packet/'input/parent_manifest.json')==binding['parent_manifest_sha256'],'Parent binding differs')
 from .recount import derive
 from .recount import software_versions
 require(manifest['software']==software_versions(),'Use recorded Recount geometry runtime; no silent backend change')
 runtime={'python':platform.python_version(),**software_versions()}
 names=['buildings.json','summary.json','snapshot/building_results/selection.json','snapshot/config/pilot.json','snapshot/normalized/context.json']
 parent_rows={r['path']:r for r in parent['files']}
 for name in names:require(sha(packet/'input'/name)==parent_rows[name]['sha256'],'Parent input differs: '+name)
 # The old previous_result has a different code identity. New revisions use only
 # a verified previous result produced by this same module/runtime/source.
 with tempfile.TemporaryDirectory(prefix='li-recount-') as d:
  stage=Path(d);shutil.copytree(packet/'input',stage/'input')
  for name in ['input_binding.json','policy.json','polygons.geojson']:shutil.copyfile(packet/name,stage/name)
  if request.get('previous'):
   from ..artifacts import artifact
   prev=artifact(request['previous'],root);previous=read(prev)
   require(previous.get('runtime')==runtime,'Previous Recount runtime differs')
   write(stage/'previous_result.json',previous['result'])
  result,ledger,delta=derive(stage)
 require(len(ledger)==result['source_records'] and result['mixed_unit_total'] is None,'Recount reconciliation failed')
 return {'schema_version':'location_recount_bundle_v1','execution_status':'SUCCEEDED',
  'operation':'OFFLINE_RECOUNT','result':result,'membership':ledger,'delta':delta,'runtime':runtime,
  'result_version':semantic_hash({'native_result_version':result['result_version'],'runtime':runtime,
   'previous_sha256':request.get('previous',{}).get('sha256')}),
  'historical_previous_result_imported':False}
