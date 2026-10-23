from collections import Counter, defaultdict
from copy import deepcopy
import math
from .support import require, records, bbox, iter_json_array
VEHICLES = {'motorcycle', 'car', 'truck', 'bus'}

def retained_relationships(path):
    """Reuse supported old relations; no new appearance/spatial association.

    Whole-ID grouping is explicitly experimental: supported raw-ID graph
    components must be cliques and must not have an unresolved internal pair.
    Ambiguous SAME_VEHICLE support is retained locally as a count conflict.
    """
    components, edges, ambiguous = ([], set(), set())
    conflicts = defaultdict(set)
    for relation in iter_json_array(path):
        kind, status = (relation.get('type'), relation.get('status'))
        if kind not in ('COMPONENT_OF', 'SAME_VEHICLE') or status not in ('SUPPORTED', 'UNRESOLVED'):
            continue
        first, second = (relation['first_track_id'], relation['second_track_id'])
        frames = relation.get('features', {}).get('common_frame_indices', [])
        require(type(first) is int and type(second) is int and (first > 0) and (second > 0) and (first != second) and isinstance(frames, list) and frames and all((type(f) is int and f >= 0 for f in frames)), 'Invalid retained relation support')
        if kind == 'COMPONENT_OF' and status == 'SUPPORTED':
            components.append({'type': 'COMPONENT_OF', 'relation_id': relation['relation_id'], 'vehicle_track_id': second, 'component_track_id': first, 'support_frames': sorted(set(frames))})
        elif kind == 'SAME_VEHICLE':
            pair = frozenset((first, second))
            if status == 'SUPPORTED':
                edges.add(pair)
            else:
                ambiguous.add(pair)
                for frame in frames:
                    conflicts[frame].update((first, second))
    graph = defaultdict(set)
    for pair in edges - ambiguous:
        first, second = sorted(pair)
        graph[first].add(second)
        graph[second].add(first)
    visited, units, groups = (set(), {}, [])
    for first in sorted(graph):
        if first in visited:
            continue
        todo, members = ([first], set())
        while todo:
            current = todo.pop()
            if current in members:
                continue
            members.add(current)
            todo.extend(graph[current] - members)
        visited.update(members)
        if any((frozenset((a, b)) not in edges - ambiguous for a in members for b in members if a < b)):
            continue
        group = sorted(members)
        unit = 'retained-clique:' + ','.join(map(str, group))
        units.update({track: unit for track in group})
        groups.append(group)
    return {'component_links': components, 'unit_by_track': units, 'unit_groups': groups, 'identity_conflicts_by_frame': dict(conflicts)}

def relationship_evidence(path):
    result = retained_relationships(path)
    pairs, supported, relation_ids = (defaultdict(list), defaultdict(list), defaultdict(dict))
    for row in iter_json_array(path):
        if row.get('type') != 'SAME_VEHICLE' or row.get('status') not in ('SUPPORTED', 'UNRESOLVED'):
            continue
        pair = tuple(sorted((row['first_track_id'], row['second_track_id'])))
        target = pairs if row['status'] == 'UNRESOLVED' else supported
        for frame in row.get('features', {}).get('common_frame_indices', []):
            target[frame].append(pair)
            if row['status'] == 'SUPPORTED':
                relation_ids[frame].setdefault(pair, []).append(row['relation_id'])
    result.update(identity_pairs_by_frame=dict(pairs), supported_pairs_by_frame=dict(supported), supported_relation_ids_by_frame=dict(relation_ids))
    return result

def _family(category):
    return 'vehicle' if category in VEHICLES else 'person' if category == 'person' else 'other'

def _scope_matches(scope, track, frame, category):
    return scope['track_id'] == track and scope['start_frame'] <= frame <= scope['end_frame'] and (scope['raw_family'] == _family(category))

def _review_at(reviews, track, frame, category):
    return [(review, scope) for review in reviews for scope in review['scopes'] if _scope_matches(scope, track, frame, category)]

def _same_reviewed_pair(reviews, pair, frame):
    for review in reviews:
        if review['type'] != 'SAME_VEHICLE':
            continue
        active = {s['track_id'] for s in review['scopes'] if s['raw_family'] == 'vehicle' and s['start_frame'] <= frame <= s['end_frame']}
        if set(pair) <= active:
            return True
    return False

def _local_retained_associations(links, present, frame, identity):
    """Verify only an exact-frame complete positive co-observation clique.

    The retained whole-ID unit name is an operational grouping assumption. It
    does not verify every observation, fill support gaps, or authorize a chain
    merge. A future/earlier positive relation cannot verify this source frame.
    """
    units = links.get('unit_by_track', {})
    groups = defaultdict(list)
    for track, observation in present.items():
        if observation.get('class_name') in VEHICLES and track in units:
            groups[units[track]].append(track)
    positive = {tuple(sorted(pair)) for pair in links.get('supported_pairs_by_frame', {}).get(frame, [])}
    unresolved = {tuple(sorted(pair)) for pair in links.get('identity_pairs_by_frame', {}).get(frame, [])}
    verified = {}
    for unit, members in groups.items():
        members = sorted(members)
        if len(members) < 2:
            continue
        required = {(first, second) for index, first in enumerate(members) for second in members[index + 1:]}
        if not required <= positive - unresolved:
            continue
        relation_ids = sorted({rid for pair in required for rid in links.get('supported_relation_ids_by_frame', {}).get(frame, {}).get(pair, [])})
        for track in members:
            verified[track] = {'association_id': 'retained-local:' + identity['records_sha256'] + ':' + unit, 'association_evidence': {'claim_type': 'RETAINED_SUPPORTED_SAME_VEHICLE_EXACT_SOURCE_FRAME', 'frame_index': frame, 'track_ids': members, 'relation_ids': relation_ids, 'records_sha256': identity['records_sha256'], 'whole_id_support_implied': False}}
    return verified

def adapted_frames(path, identity, frame_count, *, relationships=None, reviews=None, reviews_sha256=None, assignments=None, application_proof=None):
    """Validate every emitted/raw link; attach explicit roles without editing it."""
    links, reviews = (relationships or {}, reviews or [])
    units = links.get('unit_by_track', {})
    components = defaultdict(dict)
    for link in links.get('component_links', []):
        for frame in link['support_frames']:
            components[frame][link['component_track_id']] = link
    proof = application_proof if application_proof is not None else {}
    counts, anchors, coexistence, count = (Counter(), set(), [], 0)
    for record in records(path):
        frame = record.get('frame_index')
        require(type(frame) is int and frame == count, 'B v3 frames must start at zero and be continuous')
        require(all((record.get(key) == identity.get(key) for key in ('video_sha256', 'parent_run_id', 'variant', 'width', 'height'))), 'Source cache identity differs')
        raw, tracks = (record.get('raw_detections'), record.get('emitted_tracks'))
        require(isinstance(raw, list) and isinstance(tracks, list), 'Missing retained source links')
        seen, indices, observations = (set(), set(), [])
        present = {o['track_id']: o for o in tracks}
        local_associations = _local_retained_associations(links, present, frame, identity)
        for review in reviews:
            anchor = review.get('_pixel_anchor_proofs', {}).get(frame)
            if not anchor:
                continue
            require(record.get('detector_input_frame_pixel_sha256') == anchor['raw_bgr_pixel_sha256'], 'Reviewed pedestrian frame differs from actual retained detector input')
            targets = {s['track_id'] for s in review['scopes']}
            for source in anchor['observations']:
                if source['track_id'] not in targets:
                    continue
                actual = present.get(source['track_id'], {})
                require(all((actual.get(key) == source[key] for key in ('class_name', 'raw_bbox', 'original_detection_index'))), 'Reviewed pedestrian source measurement differs')
        for original in tracks:
            track, index = (original.get('track_id'), original.get('original_detection_index'))
            require(type(track) is int and track > 0 and (track not in seen) and (type(index) is int) and (0 <= index < len(raw)) and (index not in indices), 'Repeated or invalid emitted source link')
            seen.add(track)
            indices.add(index)
            require(original.get('frame_index') == frame and original.get('emitted') is True and (original.get('measurement_provenance') == 'retained_phase_8_detection'), 'Only raw measured emitted source observations may enter replay')
            box, detection = (bbox(original.get('raw_bbox')), raw[index])
            require(0 <= box[0] < box[2] <= identity['width'] and 0 <= box[1] < box[3] <= identity['height'], 'BBox outside source image')
            require(box == detection.get('bbox_xyxy_pixels') and all((original.get(key) == detection.get(key) for key in ('class_name', 'class_id', 'confidence'))), 'Measurement differs from original detection')
            confidence = original.get('confidence')
            require(isinstance(confidence, (int, float)) and (not isinstance(confidence, bool)) and math.isfinite(confidence), 'Missing finite source confidence')
            category = original['class_name']
            if _family(category) == 'other':
                continue
            item = deepcopy(original)
            item.update(observed=True, role='unknown_person' if category == 'person' else 'vehicle', unit_id=f'person-track:{track}' if category == 'person' else units.get(track, f'track:{track}'), episode_id='unreviewed-person' if category == 'person' else 'unreviewed-vehicle', association_verified=False)
            association = local_associations.get(track)
            if association is not None:
                item.update(association_verified=True, association_id=association['association_id'])
                original_ref = deepcopy(item.get('source_ref'))
                item['source_ref'] = {'retained_same_vehicle_association': association['association_evidence']}
                if original_ref is not None:
                    item['source_ref']['original_source_ref'] = original_ref
            pairs = [pair for pair in links.get('identity_pairs_by_frame', {}).get(frame, []) if track in pair]
            item['identity_conflict'] = any((not _same_reviewed_pair(reviews, pair, frame) for pair in pairs))
            if not links.get('identity_pairs_by_frame'):
                item['identity_conflict'] = track in links.get('identity_conflicts_by_frame', {}).get(frame, set())
            local = components.get(frame, {}).get(track)
            if category == 'person' and local and (local['vehicle_track_id'] in present):
                parent = present[local['vehicle_track_id']]
                if parent['class_name'] == 'motorcycle':
                    item.update(role='rider', component_of_unit_id=units.get(local['vehicle_track_id'], f"track:{local['vehicle_track_id']}"), retained_component_relation_id=local['relation_id'])
            applied = _review_at(reviews, track, frame, category)
            for review, scope in applied:
                rid, kind = (review['review_id'], review['type'])
                counts[rid] += 1
                if frame in review['confirmed_frames']:
                    anchors.add((rid, track, frame))
                item.setdefault('review_refs', []).append({'review_id': rid, 'reviews_sha256': reviews_sha256, 'source_frame': frame, 'track_id': track, 'claim_type': review.get('claim_type', 'USER_REVIEW'), 'scope_extent_is_engineering_assumption': True})
                if kind in ('SAME_VEHICLE', 'SPLIT_IDENTITY'):
                    item.update(unit_id=scope.get('physical_unit_id', review.get('physical_unit_id')), episode_id=scope.get('episode_id', review.get('episode_id')))
                    if kind == 'SAME_VEHICLE':
                        item.update(association_verified=True, association_id=rid)
                elif kind == 'COMPONENT_OF':
                    item.update(role='rider', component_of_unit_id=review['component_of_unit_id'])
                elif kind == 'PEDESTRIAN_ROLE':
                    item.update(role='pedestrian', resolved_class_name='pedestrian', unit_id=review.get('physical_unit_id', f'reviewed-pedestrian:{track}'), episode_id=review.get('episode_id', f'reviewed-role:{rid}'))
                resolved = scope.get('resolved_class_name', review.get('resolved_class_name'))
                if resolved:
                    item['resolved_class_name'] = resolved
            observations.append(item)
            if assignments is not None:
                assignments.append({'frame_index': frame, 'track_id': track, 'physical_unit_id': item['unit_id'], 'episode_id': item['episode_id'], 'role': item['role'], 'category': item.get('resolved_class_name', category), 'raw_category': category, 'review_refs': deepcopy(item.get('review_refs', [])), 'association_verified': item['association_verified'], 'association_id': item.get('association_id'), **({'component_of_unit_id': item['component_of_unit_id']} if 'component_of_unit_id' in item else {})})
        simultaneous = defaultdict(list)
        for item in observations:
            if item['role'] == 'vehicle' and item.get('association_verified'):
                simultaneous[item['unit_id'], item['episode_id']].append(item)
        for (unit, episode), items in simultaneous.items():
            if len(items) < 2:
                continue
            for index, first in enumerate(items):
                for second in items[index + 1:]:
                    a, b = (first['raw_bbox'], second['raw_bbox'])
                    overlap = max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3])
                    coexistence.append({'frame_index': frame, 'physical_unit_id': unit, 'episode_id': episode, 'track_ids': [first['track_id'], second['track_id']], 'raw_bboxes': [a, b], 'boxes_overlap_with_positive_area': overlap, 'association_basis': 'SOURCE_FRAME_BOUND_REVIEWED_CLAIM_NOT_AUTOMATIC_IDENTITY_PROOF' if first.get('review_refs') or second.get('review_refs') else 'RETAINED_SUPPORTED_SAME_VEHICLE_EXACT_SOURCE_FRAME'})
        yield {'frame_index': frame, 'observations': observations}
        count += 1
    require(count == frame_count, 'Full B v3 source cache frame count differs')
    require(all((counts[r['review_id']] > 0 for r in reviews)), 'Review did not match any measured source')
    proof.update(applied_measurements=dict(counts), matched_reviewed_anchors=[{'review_id': r, 'track_id': t, 'frame_index': f} for r, t, f in sorted(anchors)], source_links_checked=True, no_source_observations_modified=True, all_source_frames_retained=count, simultaneous_reviewed_vehicle_measurements=coexistence)
