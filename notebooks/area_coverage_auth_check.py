"""Run in the owner Kaggle session; no key or table rows are displayed."""
import json
from google.cloud import bigquery
from google.oauth2 import service_account
from kaggle_secrets import UserSecretsClient

stage = 'KAGGLE_SECRET'
try:
    info = json.loads(UserSecretsClient().get_secret('LocatioIntelligent'))
    stage = 'SERVICE_ACCOUNT_JSON'
    if not isinstance(info, dict) or info.get('type') != 'service_account':
        raise ValueError('Expected service-account JSON')
    credentials = service_account.Credentials.from_service_account_info(info)
    if credentials.service_account_email != 'locationinteligent@locdeproject.iam.gserviceaccount.com':
        raise ValueError('Service account differs from owner-specified account')
    client = bigquery.Client(project='locdeproject', credentials=credentials)
    for table_id in ['locdeproject.DWH_NS_LOC.COMPETITOR', 'locdeproject.DWH_NS_LOC.AREA_COVERAGE']:
        stage = 'TABLE_METADATA:' + table_id
        table = client.get_table(table_id, timeout=30)
        stage = 'QUERY_PERMISSION:' + table_id
        job = client.query(f'SELECT 1 AS access_check FROM `{table_id}` LIMIT 1',
                           location=table.location,
                           job_config=bigquery.QueryJobConfig(maximum_bytes_billed=10_485_760))
        list(job.result(timeout=60))
        print('OK:', table_id)
    print('AUTH_CHECK_PASSED')
except Exception as error:
    print('FAILED_STAGE:', stage)
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        code = getattr(error, 'code', None)
        print('ERROR_TYPE:', type(error).__name__, 'HTTP_STATUS:', code if isinstance(code, int) else None)
        error = error.__cause__ or error.__context__
