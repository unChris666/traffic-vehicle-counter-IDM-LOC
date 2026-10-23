"""Mechanical source extraction; original notebook helpers are never modified.

Only relative import targets and adapter dependency references change. A registry
records source/output hashes and exact extraction names for review/reproduction.
"""
import ast,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'src/traffic_location/traffic/_kernel'
MAPPING={
 'phase_5_geometry_helpers':'geometry',
 'phase_8_b_v5_counting':'passage', 'phase_8_b_v6_counting':'eligibility',
 'phase_8_b_v7_counting':'publication','phase_8_b_v4_identity':'identity_core',
 'phase_8_b_v5_identity':'identity_lifecycle','phase_8_b_v6_identity':'identity',
 'phase_8_b_v7_handoff':'handoff','phase_8_b_v8_finalize':'review_finalizer',
 'phase_8_b_v8_review':'reviews','phase_8_b_v4_batch':'overlay',
 'phase_8_b_v6_annotation':'render_kernel','phase_8_b_v3_annotation':'render_base',
 'phase_8_annotation_helpers':'render_sources',
}
class Imports(ast.NodeTransformer):
 def visit_Import(self,node):
  out=[]
  for name in node.names:
   if name.name in MAPPING:
    out.append(ast.ImportFrom(module=None,names=[ast.alias(name=MAPPING[name.name],asname=name.asname or name.name)],level=1))
   else:
    if name.name.startswith('phase_'):raise ValueError('Unmapped '+name.name)
    out.append(ast.Import(names=[name]))
  return out
 def visit_ImportFrom(self,node):
  if node.module in MAPPING:node.module=MAPPING[node.module];node.level=1
  elif node.module and node.module.startswith('phase_'):raise ValueError('Unmapped '+node.module)
  return node

def functions(name,names):
 source=(ROOT/'notebooks'/name).read_text();tree=ast.parse(source)
 selected=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names]
 if {n.name for n in selected}!=set(names):raise ValueError('Missing extraction name')
 return '\n\n'.join(ast.get_source_segment(source,n) for n in selected)

def main():
 registry=[]
 for old,new in MAPPING.items():
  path=ROOT/'notebooks'/(old+'.py');text=path.read_text();notes=['relative imports only; algorithm constants and bodies retained']
  if new=='overlay':
   text='''from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from .support import require, read, bound, sha
KINDS={'SAME_VEHICLE','SPLIT_IDENTITY','COMPONENT_OF','PEDESTRIAN_ROLE'}
'''+functions(old+'.py',['validate_overlay'])
   text=text.replace('donor._require','require').replace('donor._read','read').replace('donor.sha256_file','sha').replace('previous.KINDS','KINDS')
   text=text.replace('donor.DONOR_MANIFEST_SHA256','jobs[0]["source_manifest_sha256"]')
   text=text.replace('set(donor.VIDEO_IDS)','{job["video_id"] for job in jobs}')
   text=text.replace('_bound_artifact(root, entry["path"], entry["sha256"], guarded)','bound(root, entry["path"], entry["sha256"], guarded)')
   notes=['extracted validate_overlay only','source_manifest_sha256 and video IDs explicit in supplied jobs; no global TGDI list','bound/read/require use standalone identical guards']
  if new=='reviews':
   text=text.replace('import phase_8_b_v4_batch as previous','import phase_8_b_v4_batch as previous\nfrom . import measurement_adapter')
   text=text.replace('previous.previous._family(item["class_name"])','measurement_adapter._family(item["class_name"])')
   text=text.replace('"metadata": {"frame_count": frame_count}}]', '"metadata": {"frame_count": frame_count}, "source_manifest_sha256": overlay["donor_manifest_sha256"]}]')
   notes+=['family helper is measurement adapter; source manifest binding supplied by validated request']
  tree=Imports().visit(ast.parse(text));ast.fix_missing_locations(tree)
  target=DEST/(new+'.py');target.write_text(ast.unparse(tree)+'\n')
  registry.append({'source':str(path.relative_to(ROOT)),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
   'module':str(target.relative_to(ROOT)),'module_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'transformations':notes})
 # Unchanged measurement adaptation algorithm, without batch orchestration imports.
 text='''from collections import Counter,defaultdict
from copy import deepcopy
import math
from .support import require,records,bbox,iter_json_array
VEHICLES={'motorcycle','car','truck','bus'}
'''+functions('phase_8_b_v2_batch.py',['retained_relationships'])+'\n'+functions('phase_8_b_v3_batch.py',[
 'relationship_evidence','_family','_scope_matches','_review_at','_same_reviewed_pair','_local_retained_associations','adapted_frames'])
 for a,b in [('donor._require','require'),('retained._records','records'),('retained._bbox','bbox'),('retained.iter_json_array','iter_json_array'),('baseline.retained_relationships','retained_relationships')]:text=text.replace(a,b)
 tree=ast.parse(text);target=DEST/'measurement_adapter.py';target.write_text(ast.unparse(tree)+'\n')
 for old in ['phase_8_b_v2_batch.py','phase_8_b_v3_batch.py']:
  p=ROOT/'notebooks'/old;registry.append({'source':str(p.relative_to(ROOT)),'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
   'module':str(target.relative_to(ROOT)),'module_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'transformations':['selected measurement/relation functions only; no batch globals; identical raw-link/BC/role rules']})
 source=ROOT/'notebooks/phase_8_b_v8_batch.py';target=DEST/'review_metadata.py'
 target.write_text('from copy import deepcopy\n'+functions(source.name,['_rename_event_ids','_decision_provenance'])+'\n')
 registry.append({'source':str(source.relative_to(ROOT)),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
  'module':str(target.relative_to(ROOT)),'module_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'transformations':['review event naming/provenance functions only; no batch orchestration']})
 (ROOT/'results/engine_modularization/source_extraction.json').write_text(json.dumps(registry,indent=2)+'\n')
if __name__=='__main__':main()
