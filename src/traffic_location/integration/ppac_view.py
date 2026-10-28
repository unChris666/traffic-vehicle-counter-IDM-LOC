"""Readable PPAC rows; every value comes from the saved result, never recomputed."""
import math
from datetime import date,datetime
from decimal import Decimal

HEADERS=['Bagian','Rincian','Nilai','Status','Reason']

def scalar(value):
    if value is None:return None
    if isinstance(value,(datetime,date)):return value.isoformat()
    if isinstance(value,Decimal):return str(value)
    if isinstance(value,float) and not math.isfinite(value):return None
    if hasattr(value,'item'):
        try:return scalar(value.item())
        except (ValueError,TypeError):pass
    return value

def rows(result):
    if not result:return []
    output=[]
    def add(section,label,value,status='',reason=''):
        output.append([section,label,scalar(value),status,reason])
    def walk(section,value,path=''):
        if isinstance(value,dict):
            for key,item in value.items():walk(section,item,(path+' / ' if path else '')+key.replace('_',' '))
        elif isinstance(value,list):
            for i,item in enumerate(value):walk(section,item,path+' / '+str(i+1))
        else:add(section,path,value)
    for key,label in [('residential','Breakdown Residential'),('traffic','Breakdown Traffic'),('fasum','Breakdown Fasum'),('total','Total')]:
        if key in result:walk(label,result[key])
        else:add(label,'Belum tersedia',None)
    status=result.get('execution_status','UNKNOWN')
    reasons=result.get('diagnostics') or result.get('reason') or result.get('total',{}).get('reason') or []
    def explain(item):
        if isinstance(item,dict):return '; '.join(str(k)+': '+explain(v) for k,v in item.items())
        if isinstance(item,list):return '; '.join(explain(v) for v in item)
        return str(item)
    reason=explain(reasons)
    add('STD Total','STD/hari',result.get('std_total'),status,reason)
    add('Status','Eksekusi',status,status,reason)
    add('Status','Kualitas',result.get('result_quality'))
    if result.get('scope'):add('Status','Cakupan hasil',{'area':'Residential + Fasum saja','traffic':'Traffic saja','combined':'Area + Traffic + PPAC'}.get(result['scope'],result['scope']))
    for component,state in result.get('components_status',{}).items():add('Status','Komponen '+component,state)
    if result.get('std_total_status'):add('Status','Kelengkapan STD total',result['std_total_status'])
    add('Reason','Alasan / diagnosis',reason or ('Tidak ada diagnosis kegagalan.' if status=='SUCCEEDED' else 'Alasan tidak tersedia pada hasil tersimpan.'))
    return output
