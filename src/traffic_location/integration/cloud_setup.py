"""Print safe setup SQL by default; --apply explicitly creates missing output objects."""
import argparse
from .cloud_schema import CloudDestination,setup_sql


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--dataset',default=CloudDestination.dataset)
    p.add_argument('--apply',action='store_true');args=p.parse_args()
    destination=CloudDestination(dataset=args.dataset);sql=setup_sql(destination)
    if not args.apply:print(sql,end='');return
    from google.cloud import bigquery
    client=bigquery.Client(project=destination.dataset.split('.')[0])
    dataset=client.get_dataset(destination.dataset)
    client.query(sql,location=dataset.location).result()
    print('Output tables/views prepared in '+destination.dataset+'; no engine or source table changed.')

if __name__=='__main__':main()
