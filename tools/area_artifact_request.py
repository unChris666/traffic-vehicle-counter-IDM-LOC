"""Print explicit freeze/reopen request; never computes or contacts providers."""
import argparse,json
from pathlib import Path
from traffic_location.artifacts import sha

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('archive');p.add_argument('--operation',choices=['freeze','reopen'],default='freeze')
a=p.parse_args();path=Path(a.archive).resolve()
print(json.dumps({'schema_version':'area_artifact_request_v1','operation':a.operation,
                  'path':str(path),'sha256':sha(path)},indent=2))
