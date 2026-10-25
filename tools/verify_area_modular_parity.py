"""Verify real retained Area baseline without provider fetch or fresh CUDA inference.

Private inputs and per-building rows remain under --work; only aggregate proof
is written to --report. Recorded-label replay is not full fresh-GPU parity.
"""
import argparse,json,subprocess,sys
from pathlib import Path
from traffic_location.artifacts import read,write,sha
from traffic_location.location.area.validation import reopen_execution


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('baseline');p.add_argument('--sha256',required=True)
    p.add_argument('--work',required=True);p.add_argument('--report',required=True);p.add_argument('--core-python',default='/usr/bin/python3')
    a=p.parse_args();source=Path(a.baseline).resolve()
    if sha(source)!=a.sha256:raise ValueError('AREA_BASELINE_HASH_MISMATCH')
    work=Path(a.work).resolve();work.mkdir(parents=True,exist_ok=True)
    results=[]
    for i in range(3):
        q={'schema_version':'area_execution_request_v1','operation':'replay_recorded',
           'baseline':{'path':str(source),'sha256':a.sha256},'core_python':a.core_python,'render':False,'timeout_seconds':900}
        request=work/f'request{i}.json';write(request,q);output=work/f'run{i}'
        subprocess.run([sys.executable,'-m','traffic_location.location.area','execute','--request',str(request),'--output',str(output)],
                       check=True,stdout=subprocess.DEVNULL)
        results.append(reopen_execution(output));print('Verified isolated recorded replay',i+1,'/3',flush=True)
    first=results[0]
    if any(r!=first for r in results):raise ValueError('AREA_RECORDED_REPLAY_REPETITIONS_DIFFER')
    report={'schema':'area_modular_actual_parity_v1','status':'PASS_IN_DECLARED_SCOPE',
            'source_zip_sha256':a.sha256,'repetitions':3,'independent_worker_processes':True,
            'identical_results_and_versions':True,'domain_sha256':first['native_domain_sha256'],
            'scope':first['parity_scope'],'source_rows':first['summary']['rows'],
            'assigned':first['summary']['assigned'],'unassigned':first['summary']['unassigned'],
            'candidate_whole_buildings':first['summary']['candidate_whole_buildings'],
            'market_status_counts':first['summary']['market_status_counts'],
            'business_status':first['data_quality_status'],'environment':first['environment'],
            'fresh_gpu_parity':'NOT_RUN','production_ready':False,'result_version':first['result_version']}
    write(a.report,report);print(json.dumps(report,indent=2))
if __name__=='__main__':main()
