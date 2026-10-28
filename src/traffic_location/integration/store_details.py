"""Optional source metadata, never fabricate unavailable commercial attributes."""
from ..artifacts import read,write
ALIASES={'TGL_GO':['tgl_go','tanggal_go'],'TIPE_TOKO':['tipe_toko'],'DOMAIN':['domain'],'SOCIO_CLASS':['socio_class'],'Investasi':['investasi'],'RAB':['rab'],'STD':['std']}
def snapshot(config,folder,credentials):
    from google.cloud import bigquery
    from ..location.area._kernel.location_intelligent_map_pilot import resolve_bq_fields
    path=folder/'indomaret-details.json'
    try:
        ids=list({str(r['store_id']) for r in read(folder/'indomaret.json')['rows'] if r.get('store_id') is not None})
        client=bigquery.Client(project=config['bq_billing_project'],credentials=credentials)
        table=client.get_table(config['bq_tables']['indomaret'],timeout=30)
        names={f.name.lower():f.name for f in table.schema};identity=resolve_bq_fields(table,'indomaret')['id']['name']
        columns=['CAST(`'+identity+'` AS STRING) AS KDTK']
        for label,choices in ALIASES.items():
            field=next((names[k] for k in choices if k in names),None)
            columns.append(('CAST(`'+field+'` AS STRING)' if field else 'CAST(NULL AS STRING)')+' AS `'+label+'`')
        query='SELECT '+','.join(columns)+' FROM `'+table.full_table_id.replace(':','.')+'` WHERE CAST(`'+identity+'` AS STRING) IN UNNEST(@ids)'
        job=bigquery.QueryJobConfig(query_parameters=[bigquery.ArrayQueryParameter('ids','STRING',ids)],maximum_bytes_billed=config['bq_maximum_bytes_billed'])
        rows=[dict(r) for r in client.query(query,job_config=job).result(timeout=60)] if ids else []
        write(path,{'status':'READY','rows':rows})
    except Exception as exc:write(path,{'status':'UNAVAILABLE','error_type':type(exc).__name__,'rows':[]})
