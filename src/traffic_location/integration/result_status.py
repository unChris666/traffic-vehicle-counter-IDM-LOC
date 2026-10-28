"""Explicit component availability, separate from execution and verification."""
def annotate(ppac,mode):
    requested={'residential','fasum'} if mode=='area' else {'traffic'} if mode=='traffic' else {'residential','fasum','traffic'}
    matrix={}
    for name in ('residential','fasum','traffic'):
        value=ppac.get(name)
        status='NOT_REQUESTED' if name not in requested else 'UNAVAILABLE' if not isinstance(value,dict) else 'AVAILABLE'
        if isinstance(value,dict):
            if name=='traffic' and value.get('status')!='lengkap':status='INCOMPLETE'
            if name=='residential' and value.get('building_basis',{}).get('status')=='UNVERIFIED':status='UNVERIFIED'
        matrix[name]=status
    ppac['components_status']=matrix
    ppac['std_total_status']='COMPLETE' if mode=='workflow' and ppac.get('std_total') is not None and ppac.get('execution_status')=='SUCCEEDED' else 'INCOMPLETE'
    return ppac
