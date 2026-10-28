import importlib.util
import unittest,tempfile
from pathlib import Path
from traffic_location.integration.population import estimate,total,RWI
from traffic_location.ppac.residential import calculate
class PopulationTests(unittest.TestCase):
    def test_defaults_occupancy_and_minimums_both_rwi(self):
        cases=[('hotel',[120.,40.]),('apartments',[560.,1000/36*8*2*.75]),('kost',[1000/45*4*2*.98,1000/36*2*2*.95]),('dormitory',[1000/60*2*.98,1000/45*.95])]
        for kind,expected in cases:
            for rwi,value in zip(RWI,expected):self.assertAlmostEqual(estimate({'osm_tags':{'building':kind}},1000,rwi)['population'],value)
        for kind in ('kost','dormitory'):
            e=estimate({'subclass':kind,'num_floors':1},1000,RWI[0]);self.assertEqual(e['effective_levels'],2);self.assertGreater(e['population'],0);self.assertEqual(e['actual_levels'],1)
    def test_unknown_preserves_four_people_and_missing_area_not_fake_zero(self):
        self.assertEqual(estimate({},None,RWI[0])['population'],4)
        self.assertIsNone(estimate({'subclass':'hotel'},None,RWI[0])['population'])
        with self.assertRaises(ValueError):estimate({},5,'unknown')
    def test_ppac_uses_population_once_and_requires_matching_rwi(self):
        native={'population_estimates':[{'rwi':RWI[0],'population':120.,'included':True},{'rwi':RWI[0],'population':999.,'included':False}]}
        population=total(native,RWI[0]);self.assertEqual(population['population'],120)
        result=calculate(1,outer_zone_open=False,combined_coefficient=1,operating_days_per_week=7,swot_factor=1,rwi=RWI[0],population_estimate=population)
        self.assertEqual(result['total_penghuni'],120)
        with self.assertRaises(ValueError):total(native,RWI[1])
        with self.assertRaises(ValueError):calculate(1,outer_zone_open=False,combined_coefficient=1,operating_days_per_week=7,swot_factor=1,rwi=RWI[0])
    def test_rwi_is_bound_to_review(self):
        import test_gradio_ui as f
        from traffic_location.integration.gradio_app import validate
        from traffic_location.integration.job_input import review,checked_review
        values=list(f.inputs(mode='Area Coverage'))
        values += ['Dataset T7SL (contoh)',[],None,False,None,False,RWI[0]]
        first=validate(values,[]);token=review(first)
        values[20]=RWI[1]
        with self.assertRaises(ValueError):checked_review(validate(values,[]),token,True)

class CombinedPopulationTests(unittest.TestCase):
    def test_combined_gate_accepts_rwi_and_uses_owner_population_not_times_four(self):
        import test_gate2 as fixture
        from traffic_location.integration.adapters import inspect
        from traffic_location.integration.gate import features
        from traffic_location.ppac.service import calculate
        f=fixture.Gate2Tests('runTest');f.setUp();self.addCleanup(f.doCleanups);f.use_mvp()
        results={j['id']:inspect(j['engine'],j['result_ref'],f.root) for j in f.q['jobs']}
        native=results['area']['native']
        native['population_estimates']=[{'building_id':r['building_id'],'rwi':RWI[0],'population':1.,'included':True} for r in native['rows']]
        f.params['residential']['rwi']=RWI[0]
        out=calculate(features(f.binding,results,f.params),f.params)
        self.assertEqual(out['execution_status'],'SUCCEEDED');self.assertEqual(out['residential']['total_penghuni'],1000)
        self.assertIsNotNone(out['std_total'])

@unittest.skipUnless(importlib.util.find_spec('folium'),'Run GIS presentation environment')
class PopulationMapTests(unittest.TestCase):
    def test_wrapped_tooltip_pane_and_typed_estimates(self):
        import folium
        from traffic_location.location.area.outputs.map import building_tooltips
        m=folium.Map([0,0]);g=folium.GeoJson({'type':'FeatureCollection','features':[{'type':'Feature','geometry':{'type':'Polygon','coordinates':[[[0,0],[.001,0],[.001,.001],[0,0]]]},'properties':{'ID':'b1','AREA':100,'Status':'UNVERIFIED','Reason':'unknown'}}]}).add_to(m)
        building_tooltips(m,{'population_estimates':[{'building_id':'b1','type':'Hotel','population':12.5}]})
        html=m.get_root().render()
        self.assertIn('width:200px',html);self.assertIn('max-height:115px',html);self.assertIn('overflow-y:auto',html)
        self.assertIn('Populasi estimasi',html);self.assertIn('building-info',html)
        self.assertEqual(g.data['features'][0]['properties']['Status'],'UNVERIFIED')
        self.assertEqual(g.data['features'][0]['properties']['Populasi estimasi (orang)'],12.5)
    def test_area_table_includes_unverified_and_filters_nameless_poi(self):
        from traffic_location.artifacts import write
        from traffic_location.location.area.outputs.map import display_tables
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);features=[]
            for bid in ('b1','b2'):
                features.append({'type':'Feature','properties':{'building_id':bid},'geometry':{'type':'Polygon','coordinates':[[[106,-6],[106.0001,-6],[106.0001,-6.0001],[106,-6]]]}})
            write(p/'pilot/normalized/buildings.geojson',{'features':features})
            result={'rows':[{'building_id':'b1','count_candidate':1},{'building_id':'b2','count_candidate':0}], 'stores':[], 'output_path':str(p/'out'),
                    'population_estimates':[{'building_id':'b1','included':True,'type':'Residential','population':4},{'building_id':'b2','included':True,'type':'Hotel','population':120}]}
            table=display_tables({'latitude':-6,'longitude':106},p/'pilot',{'rows':[{'category':'school','name':None},{'category':'school','name':'A'}]},result)
            self.assertEqual(sum(v['jumlah kepala'] for v in table['area']),124)
            self.assertEqual(sum(v['Jumlah bangunan'] for v in table['area']),2)
            self.assertEqual(len(table['poi']),1)
