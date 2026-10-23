"""Extract offline domain functions, preserving geometry backends and formulas."""
import ast,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'src/traffic_location/location'
MAP={'location_intelligent_config':'config','location_intelligent_validator':'validation',
 'location_intelligent_buildings':'selection','location_intelligent_capacity':'capacity'}
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 rows=[]
 for old,new in MAP.items():
  source=ROOT/'notebooks'/(old+'.py');tree=ast.parse(source.read_text())
  # CLI stays at the package boundary; no notebook imports at runtime.
  tree.body=[n for n in tree.body if not (isinstance(n,ast.FunctionDef) and n.name=='main') and not (isinstance(n,ast.If) and '__name__' in ast.unparse(n.test))]
  for node in ast.walk(tree):
   if isinstance(node,ast.ImportFrom) and node.module in MAP:node.module=MAP[node.module];node.level=1
  target=DEST/(new+'.py');target.write_text(ast.unparse(tree)+'\n')
  rows.append({'source':str(source.relative_to(ROOT)),'source_sha256':digest(source),'module':str(target.relative_to(ROOT)),
   'module_sha256':digest(target),'transformations':['relative imports; remove CLI only; unchanged algorithms/backends']})
 source=ROOT/'notebooks/location_intelligent_li4.py';tree=ast.parse(source.read_text())
 names={'capacity_groups'}
 selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
 target=DEST/'summary.py';target.write_text('import math\n'+ast.unparse(ast.Module(body=selected,type_ignores=[]))+'\n')
 rows.append({'source':str(source.relative_to(ROOT)),'source_sha256':digest(source),'module':str(target.relative_to(ROOT)),'module_sha256':digest(target),'transformations':['capacity_groups only; no LI4 renderer/acquisition dependency']})
 source=ROOT/'notebooks/location_intelligent_recount.py';tree=ast.parse(source.read_text())
 names={'software_versions','checked_policy','validate_polygons','rings','evaluate','load_inputs','derive'}
 selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
 text='''from collections import Counter
import hashlib,json,math
from pathlib import Path
from ..artifacts import read as read_json,canonical as canonical_bytes,sha as digest
from .summary import capacity_groups
VERSION='LI5_OFFLINE_V1'
HERE=Path(__file__).resolve().parent
def engine_digest():
 from ..artifacts import semantic_hash
 return semantic_hash({p.name:digest(p) for p in sorted(HERE.iterdir()) if p.suffix in {'.py','.json'}})
'''+ast.unparse(ast.Module(body=selected,type_ignores=[]))+'\n'
 text=text.replace("HERE / 'fixtures/li5/policy.json'","HERE / 'recount_policy.json'")
 text=text.replace('digest(Path(__file__))','engine_digest()')
 target=DEST/'recount.py';target.write_text(text)
 rows.append({'source':str(source.relative_to(ROOT)),'source_sha256':digest(source),'module':str(target.relative_to(ROOT)),
  'module_sha256':digest(target),'transformations':['offline membership/derive only','policy resource local','new code version hashes the complete Location module set; old baselines stay immutable']})
 shutil.copyfile(ROOT/'notebooks/fixtures/li5/policy.json',DEST/'recount_policy.json')
 (ROOT/'results/engine_modularization/location_source_extraction.json').write_text(json.dumps(rows,indent=2)+'\n')
if __name__=='__main__':main()
