import copy,unittest
from traffic_location.integration.area_residential import building_basis

class BuildingBasisTests(unittest.TestCase):
    def test_policy_adds_only_unverified_without_double_count_or_changing_ownership(self):
        native={'status':'PARTIAL','rows':[
            {'building_id':'a','count_candidate':1,'market_status':'VALID'},
            {'building_id':'b','count_candidate':0,'market_status':'UNVERIFIED'},
            {'building_id':'c','count_candidate':1,'market_status':'UNVERIFIED'},
            {'building_id':'d','count_candidate':0,'market_status':'COMPETITOR_OWNED'},
            {'building_id':'e','count_candidate':0,'market_status':'INDOMARET_OWNED'},
            {'building_id':'f','count_candidate':0,'market_status':'OTHERS'}]}
        original=copy.deepcopy(native);basis=building_basis(native)
        self.assertEqual(basis['allocated_buildings'],2)
        self.assertEqual(basis['unverified_buildings_included'],1)
        self.assertEqual(basis['ppac_buildings'],3);self.assertEqual(basis['status'],'UNVERIFIED')
        self.assertEqual(native,original)
