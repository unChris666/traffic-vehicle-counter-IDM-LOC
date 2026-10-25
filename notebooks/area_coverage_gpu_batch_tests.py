"""Regression: speculative GPU windows must not change entrance selection."""
import unittest,json,tempfile
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
from area_coverage_gpu_v2_tests import GeometryOracle


def parallel_case(count=70,first_valid=40):
    from li3_integration_tests import ConnectorTests
    f=ConnectorTests();f.setUp()
    f.f['policy']['connectors']['building_entrance_profile']='SINGLE_NEAREST_VALID_V1'
    f.metrics['selected_buildings']=[];f.metrics['all_buildings']=[]
    template=deepcopy(f.base['graph']['edges'][0]);f.base['graph']['nodes']=[];f.base['graph']['edges']=[]
    f.base['edge_sources']={};f.base['edge_rules']={}
    for j in range(count):
        key=f'w{j+1}_s0_f';a=f'a{j}';b=f'b{j}';y=-j*10.
        f.base['graph']['nodes'] += [{'node_id':a,'x':0.,'y':y},{'node_id':b,'x':100.,'y':y}]
        f.base['graph']['edges'].append({**template,'edge_id':key,'u':a,'v':b,
            'geometry':{'type':'LineString','coordinates':[[0.,y],[100.,y]]}})
        tags={'highway':'residential'}
        if first_valid is None or j<first_valid:tags['bridge']='yes'
        f.base['edge_sources'][key]={'osm_way_id':j+1,'segment_index':0,'direction':'f','raw_tags':tags}
        f.base['edge_rules'][key]={'allowed':True,'raw_tags':{},'evidence_refs':['fixture']}
    return f


class SpeculativeBatchTests(unittest.TestCase):
    def compare(self,f,window):
        from location_intelligent_li3_connectors import generate_connectors
        from location_intelligent_gpu_connectors import generate_connectors_gpu
        expected=generate_connectors(f.base,f.metrics,f.features,f.f)
        with patch('location_intelligent_gpu_geometry.GpuGeometry',GeometryOracle):
            actual=generate_connectors_gpu(f.base,f.metrics,f.features,f.f,candidate_window=window)
        for name in ['graph','edge_sources','edge_rules','connectors','blocked_turns','rejected_candidates']:
            self.assertEqual(actual[name],expected[name],name)
        return actual

    def test_first_valid_after_window_no_extra_cuts_or_rejections(self):
        for window in [1,7,32,64]:
            result=self.compare(parallel_case(),window)
            self.assertEqual(result['diagnostics']['gpu_geometry']['canonical_candidates_checked'],41)
            self.assertEqual(len(result['rejected_candidates']),40)
            self.assertEqual(result['connectors'][0]['source_segment'],'w41_s0')

    def test_unbounded_search_exhausts_without_fabricated_connector(self):
        result=self.compare(parallel_case(first_valid=None),32)
        self.assertEqual(result['connectors'],[])
        self.assertEqual(result['diagnostics']['gpu_geometry']['canonical_candidates_checked'],70)
        self.assertEqual(result['diagnostics']['gpu_geometry']['exhausted_targets'],1)

    def test_discarded_valid_candidates_do_not_split_graph(self):
        result=self.compare(parallel_case(first_valid=0),32)
        self.assertEqual(len(result['graph']['edges']),71)
        self.assertEqual(result['diagnostics']['gpu_geometry']['canonical_candidates_checked'],1)


class ExecutionModeTests(unittest.TestCase):
    def test_gpu_execution_does_not_launch_full_cpu_market(self):
        notebook=json.loads(Path(__file__).with_name('area_coverage_market_gpu_2km.ipynb').read_text())
        code=next(''.join(c['source']) for c in notebook['cells'] if "if begin_notebook_stage('allocation'" in ''.join(c['source']))
        result={'status':'SUCCEEDED','attractor_gate':{'state':'OPEN','reason':'fixture','evidence':[]},
                'market_inputs_complete':True,'summary':{'candidate_whole_buildings':0,'market_status_counts':{},
                    'whole_buildings_by_store':{},'assigned':0,'unassigned':0,'rows':0},'excluded_stores':[],
                'competitor_groups':{},'routing_clusters':{}}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);env={'begin_notebook_stage':lambda *a:True,'finish_notebook_stage':lambda *a:None,
                'fail_notebook_stage':lambda stage,error:(_ for _ in ()).throw(error),
                'CONFIG':{},'MARKET_CONFIG':{},'PILOT':root,'layers':{},'facilities':{},'OUTPUT':root,
                'GPU_REPORT':root/'gpu.json','GPU_DEVICE':0,'GPU_VALIDATION_MODE':'GPU_EXECUTE',
                'GPU_EQUIVALENCE':root/'eq.json','display':lambda *a:None,'report':{'source_records':0}}
            import pandas as pd
            env['pd']=pd
            with patch('importlib.reload',side_effect=lambda m:m),patch('location_intelligent_gpu_runtime.build_market_gpu',return_value=result),patch(
                'location_intelligent_gpu_validation.validate_market',side_effect=AssertionError('Full CPU validation was requested')):
                exec(code,env)
            self.assertEqual(json.loads((root/'eq.json').read_text())['market']['status'],'NOT_RUN')


if __name__=='__main__':unittest.main()
