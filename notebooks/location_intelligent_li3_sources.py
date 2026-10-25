"""Explicit LI-3 acquisition/cache I/O. No network at import or during replay."""
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path


def utc():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def write_json(path, value, *, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical_bytes(value)
    if path.suffix == '.gz':
        data = gzip.compress(data, mtime=0)
    with path.open('xb' if exclusive else 'wb') as stream:
        stream.write(data)
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    data = Path(path).read_bytes()
    if str(path).endswith('.gz'):
        data = gzip.decompress(data)
    return json.loads(data)


def build_queries(bbox, policy):
    """Pinned OSMnx filter plus explicit motor-only supplements, raw topology."""
    import osmnx as ox
    from osmnx._overpass import _get_network_filter
    if ox.__version__ != policy['sources']['roads_access_barriers_turns']['planned_library_version']:
        raise ValueError('OSMnx version differs from frozen source plan')
    if policy['li3']['network_type'] != 'drive_service':
        raise ValueError('Only approved drive_service acquisition is supported')
    west, south, east, north = bbox
    region = f'({south},{west},{north},{east})'
    filters = [_get_network_filter('drive_service')]
    if policy['li3']['motor_supplements']:
        filters += ['["highway"~"^(track|path)$"]["motorcycle"~"^(yes|designated|permissive)$"]',
                    '["highway"~"^(track|path)$"]["motor_vehicle"~"^(yes|designated|permissive)$"]',
                    '["highway"]["motorcar"="no"]["motorcycle"~"^(yes|designated|permissive)$"]']
    settings = f'[out:json][timeout:{policy["li3"]["request_timeout_s"]}][maxsize:{policy["li3"]["max_response_bytes"]}];'
    roads = settings + '(' + ''.join('way'+f+region+';' for f in filters) + ');(._;>;);out meta;'
    features = settings + ('(node["barrier"]'+region+';way["barrier"]'+region+';way["waterway"]'+region+
        ';way["natural"="water"]'+region+';relation["natural"="water"]'+region+
        ';relation["type"="restriction"]'+region+';);(._;>>;);out meta;')
    return {'roads': roads, 'features': features, 'filters': filters}


def acquire_overpass(query, endpoints, timeout, max_bytes, session=None):
    """HTTP failure/remark/incomplete response never becomes valid empty data."""
    import requests
    if session is None:
        session = requests.Session()
        session.headers.update({'User-Agent': 'LocationIntelligent-LI3-Research/1.0 (+https://github.com/unChris666/traffic-vehicle-counter-IDM-LOC)'})
    attempts = []
    for endpoint in endpoints:
        attempt = {'endpoint': endpoint, 'started_at': utc(), 'query_sha256': hashlib.sha256(query.encode()).hexdigest()}
        attempts.append(attempt)
        try:
            response = session.post(endpoint, data={'data': query}, timeout=timeout+5, stream=True)
            attempt['http_status'] = response.status_code
            if response.status_code != 200:
                attempt['status'] = 'HTTP_ERROR'
                response.close()
                continue
            chunks, size = [], 0
            for block in response.iter_content(65536):
                size += len(block)
                if size > max_bytes:
                    response.close()
                    raise ValueError('RESPONSE_BYTE_LIMIT_EXCEEDED')
                chunks.append(block)
            response.close()
            raw = b''.join(chunks)
            payload = json.loads(raw)
            if payload.get('remark') or not isinstance(payload.get('elements'), list) or not isinstance(payload.get('osm3s'), dict):
                attempt.update(status='PARTIAL_OR_INVALID', remark=str(payload.get('remark') or '')[:2000],
                               failure_reason='OVERPASS_REMARK' if payload.get('remark') else 'INCOMPLETE_RESPONSE_SCHEMA')
                continue
            attempt.update(status='SUCCEEDED', finished_at=utc(), response_bytes=size,
                           response_sha256=hashlib.sha256(raw).hexdigest(),
                           source_as_of=payload['osm3s'].get('timestamp_osm_base'), generator=payload.get('generator'))
            return {'status': 'SUCCEEDED', 'payload': payload, 'attempts': attempts}
        except (OSError, ValueError, RuntimeError) as exc:
            attempt.update(status='REQUEST_ERROR', error_type=type(exc).__name__, error=str(exc)[:300])
        except requests.RequestException as exc:
            attempt.update(status='REQUEST_ERROR', error_type=type(exc).__name__, error=str(exc)[:300])
    return {'status': 'RETRIEVAL_FAILED', 'payload': None, 'attempts': attempts}



def timed_call(label, function, *args, **kwargs):
    """Operational timing outside frozen result packets; domain outputs unchanged."""
    import time,os
    started=time.perf_counter();state='FAILED'
    print('Calculation: '+label+' START',flush=True)
    try:
        result=function(*args,**kwargs);state='SUCCEEDED';return result
    finally:
        elapsed=time.perf_counter()-started
        print('Calculation: '+label+' '+state+' '+format(elapsed,'.3f')+' s',flush=True)
        target=os.environ.get('LI_PERFORMANCE_REPORT')
        if target:
            try:
                path=Path(target);path.parent.mkdir(parents=True,exist_ok=True)
                rows=read_json(path) if path.exists() else []
                if not isinstance(rows,list):raise ValueError('Invalid timing journal')
                rows.append({'stage':label,'status':state,'duration_seconds':elapsed})
                tmp=path.with_suffix('.partial');write_json(tmp,rows);tmp.replace(path)
            except (OSError,ValueError,TypeError):
                # Telemetry must not mask domain success or the original failure.
                print('Calculation timing: journal unavailable; console duration retained',flush=True)
