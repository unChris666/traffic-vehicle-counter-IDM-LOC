import unittest
from copy import deepcopy
from unittest.mock import patch
from location_intelligent_market_scope import configure_scope,store_in_scope,radial_poi_gate,market_scope
from location_intelligent_market_config import get_market_config

class ScopeTests(unittest.TestCase):
    def test_store_boundary_both_types(self):
        for kind in ['competitor','indomaret']:
            for distance,expected in [(0,True),(799,True),(800,True),(800.01,False),(2000,False)]:
                self.assertEqual(store_in_scope(kind,distance,{}),expected)
    def test_config_isolated_and_explicit(self):
        old=get_market_config();before=deepcopy(old);new=configure_scope(old)
        self.assertEqual(old,before);self.assertEqual(new['allocation_requirements']['attractor_radius_m'],400)
        for k,v in before['allocation_requirements'].items():
            if k!='attractor_gate':self.assertEqual(new['allocation_requirements'][k],v)
    def gate(self,distance,status='SUCCEEDED'):
        from pyproj import Geod
        lon,lat,_=Geod(ellps='WGS84').fwd(106.83,-6.19,90,distance)
        config={'longitude':106.83,'latitude':-6.19,'metric_crs':'EPSG:32748'}
        policy=configure_scope(get_market_config())['allocation_requirements']
        poi={'source_id':'node/1','longitude':lon,'latitude':lat,'category':'hospital'}
        class NoGraph:
            def __getattr__(self,name):raise AssertionError('No routing allowed')
        return radial_poi_gate(config,policy,{'status':status},{},[poi],{},network=NoGraph())
    def test_radial_gate_no_network_or_connector_required(self):
        self.assertEqual(self.gate(399)['state'],'OPEN')
        self.assertEqual(self.gate(401)['state'],'CLOSED')
        self.assertFalse(self.gate(399)['poi_routing_performed'])
    def test_missing_poi_remains_unknown(self):
        self.assertEqual(self.gate(1,status='FAILED')['state'],'UNKNOWN')
    def test_restaurant_cluster_retains_area_count_and_corridor_without_routing(self):
        from pyproj import Transformer
        from shapely.geometry import Polygon,mapping
        from shapely.ops import transform
        tx=Transformer.from_crs(4326,32748,always_xy=True);inv=Transformer.from_crs(32748,4326,always_xy=True)
        x,y=tx.transform(106.83,-6.19)
        pois=[];features=[]
        for i in range(5):
            px=x+50+i*15;py=y+20;lon,lat=inv.transform(px,py);sid='way/'+str(i)
            pois.append({'source_id':sid,'category':'restaurant','longitude':lon,'latitude':lat})
            footprint=Polygon([(px-5,py-5),(px+5,py-5),(px+5,py+5),(px-5,py+5)])
            features.append({'geometry':mapping(transform(inv.transform,footprint)),'properties':{'building_id':sid}})
        package={'graph':{'edges':[{'edge_id':'e','geometry':{'coordinates':[[x,y],[x+200,y]]}}]},
                 'edge_sources':{'e':{'raw_tags':{'name':'Jalan Uji'}}}}
        config={'longitude':106.83,'latitude':-6.19,'metric_crs':'EPSG:32748'}
        policy=configure_scope(get_market_config())['allocation_requirements']
        result=radial_poi_gate(config,policy,{'status':'SUCCEEDED'},package,pois,{'features':features})
        self.assertEqual(result['state'],'OPEN');self.assertEqual(len(result['restaurant_cluster']),5)
        result=radial_poi_gate(config,policy,{'status':'SUCCEEDED'},package,pois[:4],{'features':features})
        self.assertEqual(result['state'],'CLOSED')

    def test_scoped_adapter_removes_pois_and_restores_functions(self):
        import location_intelligent_market_runtime as r
        before=(r._poi_gate,r._market_store_in_scope,r._reuse_calculation_connectors)
        with patch.object(r,'_reuse_calculation_connectors',return_value={}) as original:
            with self.assertRaisesRegex(RuntimeError,'fixture'):
                with market_scope():
                    r._reuse_calculation_connectors(None,None,None,None,[{'store_key':'store'},{'store_key':'poi:1'}])
                    self.assertEqual(original.call_args.args[-1],[{'store_key':'store'}])
                    self.assertIs(r._poi_gate,radial_poi_gate)
                    raise RuntimeError('fixture')
        self.assertEqual(before,(r._poi_gate,r._market_store_in_scope,r._reuse_calculation_connectors))

if __name__=='__main__':unittest.main()
