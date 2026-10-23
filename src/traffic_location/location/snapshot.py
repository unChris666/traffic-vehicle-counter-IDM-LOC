"""Verified offline LI4 snapshot adapter. Never fetches, routes or repairs data."""
from pathlib import Path
from ..artifacts import read,require,sha
from ..persistence import verify_manifest

class SnapshotAdapter:
 def __init__(self,root,manifest_sha256):
  self.root=Path(root).resolve()
  require(sha(self.root/'manifest.json')==manifest_sha256,'Snapshot manifest binding differs')
  self.manifest=verify_manifest(self.root)
  require(self.manifest['schema_version']=='li4_package_v1','Expected a finalized LI4 offline packet')
  self.context=read(self.root/'snapshot/normalized/context.json')
  self.source_manifest=read(self.root/'snapshot/normalized/input_manifest.json')
  self.policy=read(self.root/'snapshot/config/pilot.json')['policy']
  self.rows=read(self.root/'buildings.json')
  summary=read(self.root/'summary.json');self.source_summary=summary
  require(sorted(r['source_row_index'] for r in self.rows)==list(range(summary['source_records'])),'Snapshot rows do not reconcile')
  require(summary['mixed_unit_total'] is None,'Mixed capacity units are not supported')
  self.manifest_sha256=manifest_sha256
 def source_id(self):
  ids=[s['source_ref_id'] for s in self.source_manifest['sources'] if s['inventory_id']=='SRC04']
  require(len(ids)==1,'Specify a snapshot with one explicit building source')
  return ids[0]
 def selection_capacity(self):
  from .selection import select_buildings
  from .capacity import estimate_capacity
  selection=select_buildings(self.context,self.source_manifest,root=self.root/'snapshot',source_ref_id=self.source_id())
  require(selection['status'] in {'SUCCEEDED','PARTIAL'},'Offline selection failed/blocked')
  capacity=estimate_capacity(selection,self.policy)
  return selection,capacity
