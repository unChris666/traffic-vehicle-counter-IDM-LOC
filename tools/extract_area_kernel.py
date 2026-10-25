"""Mechanical compatibility extraction from a VERIFIED actual V5 baseline ZIP."""
import argparse,ast,hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PREFIX='traffic_location.location.area._kernel.'

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('baseline');p.add_argument('--sha256',required=True);a=p.parse_args()
    data=Path(a.baseline).read_bytes()
    if hashlib.sha256(data).hexdigest()!=a.sha256:raise ValueError('BASELINE_HASH_CHANGED')
    dest=ROOT/'src/traffic_location/location/area/_kernel';dest.mkdir(parents=True,exist_ok=True)
    (dest/'__init__.py').write_text('"""Frozen compatibility algorithms; no notebook imports at runtime."""\n')
    rows=[]
    with zipfile.ZipFile(a.baseline) as z:
        names={Path(n).stem for n in z.namelist() if n.startswith('source/') and n.endswith('.py')}
        class Rewrite(ast.NodeTransformer):
            def visit_ImportFrom(self,n):
                if n.module in names:n.module=PREFIX+n.module
                return n
            def visit_Import(self,n):
                for alias in n.names:
                    if alias.name in names:
                        alias.asname=alias.asname or alias.name;alias.name=PREFIX+alias.name
                return n
            def visit_Constant(self,n):
                if isinstance(n.value,str) and not n.value.endswith(('.py','.json','.gz','.ipynb')):
                    for name in names:
                        if n.value==name or n.value.startswith(name+'.'):
                            n.value=PREFIX+n.value;break
                return n
            def visit_Assign(self,n):
                n=self.generic_visit(n)
                if any(isinstance(t,ast.Name) and t.id=='CORE' for t in n.targets):
                    n.value=ast.parse("Path(__file__).with_name('location_intelligent_li3_core.py')",mode='eval').body
                return n
        for name in sorted(names):
            source=z.read('source/'+name+'.py');tree=Rewrite().visit(ast.parse(source.decode()));ast.fix_missing_locations(tree)
            if name=='location_intelligent_map_pilot':
                tree.body.insert(1,ast.Assign(targets=[ast.Name(id='_NOTEBOOK_BQ_CREDENTIALS',ctx=ast.Store())],value=ast.Constant(None)))
                ast.fix_missing_locations(tree)
            module=ast.unparse(tree)+'\n';target=dest/(name+'.py');target.write_text(module)
            digest=hashlib.sha256(source).hexdigest()
            archive=ROOT/'results/area_modularization/source_archive'/digest/(name+'.py');archive.parent.mkdir(parents=True,exist_ok=True);archive.write_bytes(source)
            rows.append({'source':str(archive.relative_to(ROOT)),'source_sha256':digest,
                         'module':str(target.relative_to(ROOT)),'module_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
                         'origin_zip_sha256':a.sha256,'origin_member':'source/'+name+'.py',
                         'changes':['qualified package imports/module patch targets','portable CORE worker locator','AST formatting; optional credential hook initialized None']})
    output=ROOT/'results/area_modularization/source_extraction.json';output.write_text(json.dumps(rows,indent=2))
    print('Extracted verified helpers:',len(rows))
if __name__=='__main__':main()
