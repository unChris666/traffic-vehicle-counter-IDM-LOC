#!/usr/bin/env python3
"""Read-only arithmetic in supplied scaled-image coordinates; no pixel mapping.

Inputs are the user's four points in their listed order and the selected line.
Fraction arithmetic preserves all supplied decimal values exactly. This script
computes ordinary segment intersections and polygon signed area only. It does
not run a crossing state machine, accept events/geometry, or inspect models.
"""
from fractions import Fraction as Q
from pathlib import Path
import json, math

SPACE = 'SUPPLIED_SCALED_IMAGE_COORDINATES_ONLY; image dimensions/crop/native transform UNKNOWN'
coords = [('4.5', '516.5'), ('4.5', '348.2'), ('936.6', '305.8'), ('557.5', '165.3')]
points = [tuple(Q(v) for v in pair) for pair in coords]
line = [tuple(Q(v) for v in pair) for pair in [('4.5','516.5'), ('936.4','305.4')]]

def sub(a,b): return (a[0]-b[0],a[1]-b[1])
def cross(a,b): return a[0]*b[1]-a[1]*b[0]
def orient(a,b,c): return cross(sub(b,a),sub(c,a))
def numeric(q): return float(q)
def xy(point): return [numeric(v) for v in point]
def exact(q): return str(q)
def intersect(a,b,c,d):
    ab=sub(b,a); cd=sub(d,c); den=cross(ab,cd)
    if den == 0: return None
    t=cross(sub(c,a),cd)/den; u=cross(sub(c,a),ab)/den
    if 0<=t<=1 and 0<=u<=1:
        p=(a[0]+t*ab[0],a[1]+t*ab[1])
        return {'intersection':xy(p), 'intersection_exact_fraction':[exact(v) for v in p], 'first_segment_parameter':numeric(t), 'second_segment_parameter':numeric(u), 'proper_interior_intersection':0<t<1 and 0<u<1}
    return None

def topology(order):
    poly=[points[i] for i in order]
    hits=[]
    n=len(poly)
    for i in range(n):
        for j in range(i+1,n):
            if j==(i+1)%n or i==(j+1)%n: continue
            hit=intersect(poly[i],poly[(i+1)%n],poly[j],poly[(j+1)%n])
            if hit:
                hits.append({'edges_by_supplied_point_indices':[[order[i]+1,order[(i+1)%n]+1],[order[j]+1,order[(j+1)%n]+1]],**hit})
    area2=sum(cross(poly[i],poly[(i+1)%n]) for i in range(n))
    turns=[orient(poly[i],poly[(i+1)%n],poly[(i+2)%n]) for i in range(n)]
    return {'order_by_supplied_point_index':[i+1 for i in order], 'coordinates':list(map(xy,poly)), 'nonadjacent_edge_intersections':hits, 'signed_area_scaled_coordinate_units2':numeric(area2/2), 'convex_turn_cross_products':list(map(numeric,turns)), 'convex_all_nonzero_turns_same_sign':all(v>0 for v in turns) or all(v<0 for v in turns)}

selected=[0,1,3,2]
poly=[points[i] for i in selected]
delta=sub(line[1],points[2])
line_hits=[]
for i in range(len(poly)):
    hit=intersect(line[0],line[1],poly[i],poly[(i+1)%len(poly)])
    if hit:
        line_hits.append({'polygon_edge_by_supplied_point_indices':[selected[i]+1,selected[(i+1)%len(poly)]+1],**hit})
endpoint_cross=[orient(poly[i],poly[(i+1)%len(poly)],line[1]) for i in range(len(poly))]
report={
    'scope':'ACTUAL_READ_ONLY_STATIC_COORDINATE_ARITHMETIC_NOT_GEOMETRY_ACCEPTANCE_OR_CROSSING_TEST',
    'coordinate_space':SPACE,
    'input_provenance':'latest user G2 reply; all four polygon points labelled P1 in user text; indices below are helper aliases only',
    'listed_points': [{'supplied_point_index':i+1,'supplied_label':'P1','coordinate':xy(p)} for i,p in enumerate(points)],
    'line_endpoints_supplied_coordinates':list(map(xy,line)),
    'listed_order_topology':topology([0,1,2,3]),
    'simple_perimeter_reorder_proposal':topology(selected),
    'reorder_status':'PROPOSAL_ONLY_NOT_USER_APPROVED; swaps listed points3/4; all coordinates preserved exactly',
    'P2_minus_supplied_polygon_point3':xy(delta),
    'P2_distance_to_supplied_polygon_point3_scaled_units':math.hypot(*xy(delta)),
    'P2_is_exact_polygon_vertex':line[1] in points,
    'P2_orientations_against_proposed_perimeter_edges':list(map(numeric,endpoint_cross)),
    'P2_is_outside_proposed_convex_polygon':not(all(v>=0 for v in endpoint_cross) or all(v<=0 for v in endpoint_cross)),
    'selected_line_boundary_intersections_for_proposed_reorder':line_hits,
    'offset_status':'KEEP_EXACT_VALUES; no snap, extrapolation, tolerance or native-pixel offset selected',
    'limitations':['source display width/height unknown','resize/crop/rotation/letterbox transform unknown','listed point order not explicitly confirmed','polygon reorder unapproved','static arithmetic only; no crossing acceptance, state or event','no source/model/tracker/encoder execution','relative template selected by user does not establish all-video reliability'],
    'repository_modified':False,
    'geometry_contract_accepted':False,
    'native_pixel_conversion_executed':False,
    'model_tracker_encoder_rerun':False,
    'synthetic_crossing_tests_executed':False,
}
output=Path('/tmp/phase5_scaled_polygon_coordinate_check.json')
output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
