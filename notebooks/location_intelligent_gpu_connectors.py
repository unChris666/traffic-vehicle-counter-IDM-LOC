"""Visible GPU-batched adapter; generated from frozen CPU graph assembly.

Rebuild with build_gpu_connector_adapter.py; business baseline is unchanged.
GPU FP64 candidate distances + batched polygon intersection. Canonical scalar
endpoint construction remains GEOS; ambiguous intersection falls back with audit.
"""
from collections import defaultdict
from copy import deepcopy
import math
def generate_connectors_gpu(base, metrics, feature_source, frozen, *, alternative_targets=None,device=0,audit_path=None):
    from shapely import STRtree
    from shapely.geometry import LineString, Point, shape
    from shapely.ops import nearest_points
    from location_intelligent_li3_connectors import barrier_index,check_barriers
    from location_intelligent_gpu_geometry import GpuGeometry,GpuCandidatePlanner
    from location_intelligent_li3_graph import apply_turns
    graph = base['graph']
    sources, rules = base['edge_sources'], base['edge_rules']
    policy = frozen['policy']
    profile=policy['connectors'].get('building_entrance_profile','MULTI_ACCESS_LEGACY')
    if profile not in {'MULTI_ACCESS_LEGACY','SINGLE_HIGHEST_CLASS_NEAREST_V1','SINGLE_NEAREST_VALID_V1'}:
        raise ValueError('Unknown building entrance profile')
    single=profile!='MULTI_ACCESS_LEGACY'
    nearest=profile=='SINGLE_NEAREST_VALID_V1'
    epsilon = policy['li3']['projection_position_precision_m']
    inset = policy['li3']['entrance_inset_m']
    maximum = policy['connectors']['max_building_to_road_m']['value']
    ranking = {name: i for i, names in enumerate(policy['connectors']['road_class_hierarchy']) for name in names}
    groups = {}
    for edge in graph['edges']:
        key = edge['edge_id']; source = sources[key]
        group = f'w{source["osm_way_id"]}_s{source["segment_index"]}'
        if group not in groups:
            coords = edge['geometry']['coordinates']
            if source['direction'] == 'r':
                coords = list(reversed(coords))
            a, b = (edge['u'], edge['v']) if source['direction'] == 'f' else (edge['v'], edge['u'])
            groups[group] = {'line': LineString(coords), 'a': a, 'b': b, 'members': [], 'tags': source['raw_tags'], 'road_class': edge['highway']}
        groups[group]['members'].append(edge)
    group_ids = sorted(groups)
    geometries = [groups[g]['line'] for g in group_ids]
    tree = STRtree(geometries)
    bounds=[g.bounds for g in geometries]
    road_extent=(min(b[0] for b in bounds),min(b[1] for b in bounds),max(b[2] for b in bounds),max(b[3] for b in bounds)) if bounds else None
    barrier = barrier_index(feature_source, frozen)
    footprints = {b['building_id']: shape(b['metric_geometry']) for b in metrics['all_buildings']}
    footprint_ids = sorted(footprints)
    footprint_geoms = [footprints[k] for k in footprint_ids]
    footprint_tree = STRtree(footprint_geoms)
    # Each footprint inset is calculated at most once, including neighbours.
    buffered={}
    def inset_geometry(bid):
        if bid not in buffered:buffered[bid]=footprints[bid].buffer(-inset)
        return buffered[bid]
    for gid,group in groups.items():
        name=group['road_class'];name=name[:-5] if name.endswith('_link') else name
        group['rank']=ranking.get(name,float('inf'))
        group['length']=group['line'].length
    cuts, candidates, rejected = defaultdict(dict), [], []
    target = Point(*metrics['target_xy'])
    diagnostics = {'barrier_features': len(barrier['shapes']), 'unresolved_barrier_geometries': barrier['unresolved'],
                   'building_entrance_profile':profile,
                   'entrance_selection':('REPRESENTATIVE_POINT_DISTANCE_THEN_SEGMENT_ID' if nearest else 'CLASS_RANK_THEN_REPRESENTATIVE_POINT_DISTANCE_THEN_SEGMENT_ID') if single else 'LEGACY_MULTI_ACCESS',
                   'route_failure_fallback':False if single else True,
                   'entrance_claim': 'OWNER_ACCEPTED_ASSUMPTION_NOT_OBSERVED_ENTRANCE'}

    def prepare(kind, building_id, rep, footprint, index, measured_distance=None):
        group_id = group_ids[index]; group = groups[group_id]
        reason = None
        name = group['road_class']
        name = name[:-5] if name.endswith('_link') else name
        if name not in ranking:
            reason = 'UNRANKED_FRONTAGE_CLASS'
        elif not any(rules[e['edge_id']]['allowed'] is True for e in group['members']):
            reason = 'ACCESS_UNVERIFIED' if any(rules[e['edge_id']]['allowed'] is None for e in group['members']) else 'ACCESS_PROHIBITED'
        elif group['tags'].get('bridge') not in {None, 'no'} or group['tags'].get('tunnel') not in {None, 'no'} or group['tags'].get('layer', '0') not in {'0', '0.0'}:
            reason = 'GRADE_SEPARATED_DIRECT_ENTRY_UNVERIFIED'
        distance = rep.distance(group['line']) if measured_distance is None else measured_distance
        if kind == 'BUILDING' and distance > maximum:
            return None
        if reason:
            rejected.append({'kind': kind, 'building_id': building_id, 'source_segment': group_id, 'reason': reason, 'distance_m': distance})
            return None
        if kind == 'BUILDING':
            interior = inset_geometry(building_id)
            interior = interior if not interior.is_empty else footprint.representative_point()
            entrance, access = nearest_points(interior, group['line'])
        else:
            entrance, access = rep, nearest_points(rep, group['line'])[1]
        position = group['line'].project(access)
        length = group['length']
        if position <= epsilon:
            node, access, position = group['a'], Point(group['line'].coords[0]), 0.0
        elif length-position <= epsilon:
            node, access, position = group['b'], Point(group['line'].coords[-1]), length
        else:
            q = round(position/epsilon)
            position = min(max(q*epsilon, epsilon), length-epsilon)
            access = group['line'].interpolate(position)
            node = group_id + f'_x{q}'
        coords = [[entrance.x, entrance.y], [access.x, access.y]] if kind == 'BUILDING' else [[access.x, access.y], [rep.x, rep.y]]
        line = LineString(coords)
        return {'kind':kind,'building_id':building_id,'target':rep,'line':line,'epsilon':epsilon,
                'group_id':group_id,'node':node,'position':position,'coords':coords,'distance':distance}

    def commit(item,clear,hits):
        if item is None:return None
        kind=item['kind'];building_id=item['building_id'];group_id=item['group_id']
        node=item['node'];position=item['position'];coords=item['coords'];distance=item['distance'];line=item['line']
        name=groups[group_id]['road_class'];name=name[:-5] if name.endswith('_link') else name
        if clear is not True:
            rejected.append({'kind': kind, 'building_id': building_id, 'source_segment': group_id,
                             'reason': 'ACCESS_UNVERIFIED' if clear is None else 'MAPPED_BARRIER_OR_BUILDING',
                             'distance_m': distance, 'geometry': {'type': 'LineString', 'coordinates': coords}, 'barrier_hits': hits})
            return None
        cuts[group_id][node] = position
        value = {'connector_id': ('target' if kind == 'TARGET' else building_id) + '_' + group_id + '_' + node,
                 'kind': kind, 'building_id': building_id, 'node_id': node, 'source_segment': group_id,
                 'status': 'OWNER_ASSUMPTION', 'barrier_clear': True,
                 'evidence_refs': [group_id, 'OWNER_FRONTAGE_ASSUMPTION', 'OSM_MAPPED_BARRIER_CHECK'],
                 'geometry': {'type': 'LineString', 'coordinates': coords}, 'class_rank': ranking[name],
                 'candidate_distance_m': distance, 'connector_distance_m': line.length,
                 'warnings': ['NOT_A_VERIFIED_PHYSICAL_ENTRANCE', 'OSM_ABSENCE_IS_NOT_PROOF_OF_NO_BARRIER']}
        candidates.append(value)
        return value

    geometry=GpuGeometry(device)
    planner=GpuCandidatePlanner(geometry,geometries,group_ids,tree,metrics,alternative_targets,maximum)
    def evaluate(requests):
        items=[prepare(*request) for request in requests]
        barriers=geometry.barrier_batch(items,barrier,epsilon)
        footprint_hits=geometry.footprint_clear_batch(items,footprint_ids,footprints,footprint_tree,inset_geometry)
        results=[]
        for item,(clear,hits),obstacles in zip(items,barriers,footprint_hits):
            if clear is True and obstacles:clear=False;hits=hits+obstacles
            results.append(commit(item,clear,hits))
        return results
    def process(entries):
        pending={}
        for key,kind,bid,point,footprint in entries:
            iterator=iter(planner.ordered(point,maximum if kind=='BUILDING' else None))
            option=next(iterator,None)
            if option is not None:pending[key]=[kind,bid,point,footprint,iterator,option]
        while pending:
            order=sorted(pending,key=lambda key:(group_ids[pending[key][5][1]],key))
            requests=[]
            for key in order:
                kind,bid,point,footprint,iterator,(distance,index)=pending[key]
                requests.append((kind,bid,point,footprint,index,distance))
            answers=evaluate(requests)
            for key,answer in zip(order,answers):
                state=pending[key]
                if answer is not None:
                    if state[0]=='TARGET' and key!='candidate':
                        answer['connector_id']='alternative_'+key+'_'+answer['connector_id'];answer['alternative_store_key']=key
                    del pending[key]
                else:
                    option=next(state[4],None)
                    if option is None:del pending[key]
                    else:state[5]=option
            print('GPU connector batch: '+str(len(order))+' candidates; remaining='+str(len(pending)),flush=True)
    entries=[('candidate','TARGET',None,Point(*metrics['target_xy']),None)]
    entries += [(row['store_key'],'TARGET',None,Point(*row['target_xy']),None) for row in sorted(alternative_targets or [],key=lambda r:r['store_key'])]
    entries += [(b['building_id'],'BUILDING',b['building_id'],Point(*b['representative_point_m']),footprints[b['building_id']]) for b in sorted(metrics['selected_buildings'],key=lambda b:b['building_id'])]
    if not nearest:
        raise ValueError('GPU_CONNECTORS_V2_REQUIRES_FROZEN_NEAREST_PROFILE')
    process(entries)
    diagnostics.update(gpu_geometry=dict(geometry.audit),building_entrance_profile=profile)
    if audit_path is not None:
        from location_intelligent_gpu_runtime import _report
        _report(audit_path,{'stage':'connectors','geometry':dict(geometry.audit)})
    nodes = {n['node_id']: deepcopy(n) for n in graph['nodes']}
    new_edges, new_sources, new_rules, incidents = [], {}, {}, defaultdict(list)
    speed = policy['travel']['reference_constant_speed']['value']*1000/3600
    for group_id in group_ids:
        group = groups[group_id]; line = group['line']
        positions = {group['a']: 0.0, group['b']: line.length, **cuts.get(group_id, {})}
        ordered = sorted(positions, key=lambda n: (positions[n], n))
        for node in ordered:
            point = line.interpolate(positions[node])
            if node not in nodes:
                nodes[node] = {'node_id': node, 'x': point.x, 'y': point.y}
        for parent in group['members']:
            pkey = parent['edge_id']; forward = sources[pkey]['direction'] == 'f'
            path = ordered if forward else list(reversed(ordered))
            for i, (a, b) in enumerate(zip(path, path[1:])):
                start, end = nodes[a], nodes[b]
                coords = [[start['x'], start['y']], [end['x'], end['y']]]
                distance = math.dist(*coords)
                if distance <= 0:
                    continue
                key = pkey + f'_p{i}'
                edge = {**parent, 'edge_id': key, 'u': a, 'v': b, 'key': key, 'length_m': distance,
                        'travel_time_s': distance/speed, 'geometry': {'type': 'LineString', 'coordinates': coords}}
                new_edges.append(edge)
                new_sources[key] = {**deepcopy(sources[pkey]), 'parent_edge_id': pkey}
                new_rules[key] = deepcopy(rules[pkey])
                incidents[(group_id, a)].append(key); incidents[(group_id, b)].append(key)
    new_graph = {**graph, 'nodes': sorted(nodes.values(), key=lambda n: n['node_id']), 'edges': sorted(new_edges, key=lambda e: e['edge_id'])}
    for c in candidates:
        c['road_edge_id'] = min(k for k in incidents[(c['source_segment'], c['node_id'])] if new_rules[k]['allowed'] is True)
    blocked, turn_diagnostics = apply_turns(new_graph, new_sources, new_rules, feature_source,profile=policy['li3'].get('road_rule_profile'))
    # Quarantine inherited by edge rules after split; connector usability is
    # checked again by the existing motor engine, not asserted by this generator.
    diagnostics.update(connectors=len(candidates), rejected_candidates=len(rejected),
                       footprint_buffers_calculated=len(buffered),
                       target_connector_found=any(c['kind'] == 'TARGET' for c in candidates),
                       turn_relations=turn_diagnostics, grade_separation_policy='NO_DIRECT_ENTRY_TO_ELEVATED_OR_TUNNEL_EDGE')
    return {'graph': new_graph, 'edge_sources': new_sources, 'edge_rules': new_rules,
            'blocked_turns': blocked, 'connectors': sorted(candidates, key=lambda c: c['connector_id']),
            'rejected_candidates': rejected, 'diagnostics': diagnostics}
