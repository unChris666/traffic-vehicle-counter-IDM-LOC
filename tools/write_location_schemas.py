"""Write the narrow offline boundary schemas; API/job schemas remain separate."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'src/traffic_location/schemas'
def document(name,properties,required=None):
 value={'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'urn:traffic-location:'+name,
  'type':'object','required':list(properties) if required is None else required,'additionalProperties':False,'properties':properties}
 (ROOT/(name+'.json')).write_text(json.dumps(value,indent=2)+'\n')
def main():
 text={'type':'string','minLength':1};hashref={'type':'string','pattern':'^[0-9a-f]{64}$'}
 artifact=json.loads((ROOT/'artifact.v1.json').read_text());artifact.pop('$id',None);artifact.pop('$schema',None)
 document('location_selection_request.v1',{'schema_version':{'const':'location_selection_request_v1'},'snapshot':text,'manifest_sha256':hashref})
 document('location_recount_request.v1',{'schema_version':{'const':'location_recount_request_v1'},'packet':text,'manifest_sha256':hashref,'previous':artifact},['schema_version','packet','manifest_sha256'])
 document('location_selection_result.v1',{'schema_version':{'const':'location_selection_result_v1'},'execution_status':{'const':'SUCCEEDED'},
  'result_quality':{'enum':['PARTIAL','COMPLETE_IN_SCOPE']},'claim_type':{'const':'EXPERIMENTAL_SCENARIO'},'source_manifest_sha256':hashref,
  'source_analysis_status':{'type':'string'},'operation':{'const':'OFFLINE_SELECTION_CAPACITY_NOT_ROUTING'},
  'result_version':hashref,'engine_sha256':hashref,'runtime':{'type':'object'},'selection':{'type':'object'},'capacity':{'type':'object','properties':{'mixed_unit_total':{'type':'null'},'final_business_capacity':{'type':'null'}}}})
 document('location_recount_bundle.v1',{'schema_version':{'const':'location_recount_bundle_v1'},'execution_status':{'const':'SUCCEEDED'},
  'operation':{'const':'OFFLINE_RECOUNT'},'result':{'type':'object','properties':{'mixed_unit_total':{'type':'null'},'final_business_capacity':{'type':'null'}}},
  'membership':{'type':'array','items':{'type':'object'}},'delta':{'type':['object','null']},
  'runtime':{'type':'object'},'result_version':hashref,'historical_previous_result_imported':{'const':False}})
if __name__=='__main__':main()
