"""Replace notebook11's exact embedded wheel while preserving its quiz cells."""
import ast
import base64
import hashlib
import io
import json
from pathlib import Path
import zipfile
import argparse


def refresh(wheel,notebook):
    wheel=Path(wheel);path=Path(notebook);n=json.loads(path.read_text())
    with zipfile.ZipFile(wheel) as package:
        for name in package.namelist():
            if name.startswith('traffic_location/') and name.endswith('.py'):
                assert package.read(name)==(path.resolve().parents[1]/'src'/name).read_bytes(),name
    for c in n['cells']:
        source=''.join(c['source'])
        if c['cell_type']!='code' or 'PAYLOAD=' not in source:continue
        node=next(x for x in ast.walk(ast.parse(source)) if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PAYLOAD' for t in x.targets))
        old=base64.b64decode(ast.literal_eval(node.value.args[0]));data=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(old)) as z,zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED) as new:
            names=[name for name in z.namelist() if name.startswith('package/')]
            assert len(names)==1
            old_name=names[0];old_wheel=z.read(old_name)
            for name in z.namelist():
                if name!=old_name:new.writestr(name,z.read(name))
            new.writestr('package/'+wheel.name,wheel.read_bytes())
        payload=data.getvalue()
        source=source.replace(base64.b64encode(old).decode(),base64.b64encode(payload).decode())
        source=source.replace(hashlib.sha256(old).hexdigest(),hashlib.sha256(payload).hexdigest())
        source=source.replace(hashlib.sha256(old_wheel).hexdigest(),hashlib.sha256(wheel.read_bytes()).hexdigest())
        old_version=Path(old_name).name.split('-')[1];version=wheel.name.split('-')[1]
        source=source.replace(old_version,version);compile(source,str(path),'exec')
        c['source']=source.splitlines(keepends=True);c['outputs']=[];c['execution_count']=None
    path.write_text(json.dumps(n,ensure_ascii=False,indent=1)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wheel',required=True)
    p.add_argument('--notebook',default='notebooks/11_gate2_t7sl_sorong_quiz.ipynb')
    a=p.parse_args();refresh(a.wheel,a.notebook)
