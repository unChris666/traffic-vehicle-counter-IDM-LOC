"""P0 identity isolation over immutable detector-linked measurements.

Research candidate, not verified physical identity. Whole-ID retained group names
are hypotheses only. The B v4 bounded-role/context machinery is reused without
editing its source; positive relations retain exact episode/frame scope. No
appearance features, pixels, detector or tracker are run by this helper.
"""
from __future__ import annotations
from collections import defaultdict
from copy import deepcopy
from statistics import median
from . import identity_core as previous
VEHICLES = previous.VEHICLES

def experimental_identity_policy(*, component_profile='median_temporal_v1'):
    controls = previous.experimental_identity_policy(component_profile=component_profile)
    controls.update(schema_version='phase8_b_v5_identity_policy_v1', historical_unit_policy='HYPOTHESIS_ONLY_ISOLATE_RAW_CONTEXT_UNTIL_SCOPED_POSITIVE_PROOF', same_unit_scope='EXACT_FRAME_PROOF_OR_SOURCE_BOUND_REVIEW_NO_RETROACTIVE_ASSIGNMENT', negative_relation_policy='DISJOINT_COPRESENCE_IS_A_CONSTRAINT_NOT_GLOBAL_PHYSICAL_TRUTH', category_is_identity_gate=False, cross_category_candidate_policy='EXACT_FRAME_HIGH_IOU_HOLDS_WEAK_COVARIATION_AUDIT_ONLY', cross_category_candidate_profile='p0_v2_high_iou_hold_weak_covariation_audit')
    return controls

def _controls(policy):
    value = deepcopy(policy.get('identity', policy))
    previous._require(isinstance(value, dict) and value.get('schema_version') == 'phase8_b_v5_identity_policy_v1', 'Explicit B v5 identity policy required')
    previous._require(value.get('historical_unit_policy') == 'HYPOTHESIS_ONLY_ISOLATE_RAW_CONTEXT_UNTIL_SCOPED_POSITIVE_PROOF', 'Historical unit hypotheses cannot silently become identity proof')
    previous._require(value.get('category_is_identity_gate') is False, 'Category cannot hide cross-category identity candidates')
    previous._require(value.get('cross_category_candidate_policy') == 'EXACT_FRAME_HIGH_IOU_HOLDS_WEAK_COVARIATION_AUDIT_ONLY', 'Explicit supported cross-category conflict policy required')
    previous._require(value.get('cross_category_candidate_profile') == 'p0_v2_high_iou_hold_weak_covariation_audit', 'Unknown cross-category candidate profile')
    previous._require(value.get('same_unit_scope') == 'EXACT_FRAME_PROOF_OR_SOURCE_BOUND_REVIEW_NO_RETROACTIVE_ASSIGNMENT', 'Unknown same-unit scope policy')
    previous._require(value.get('negative_relation_policy') == 'DISJOINT_COPRESENCE_IS_A_CONSTRAINT_NOT_GLOBAL_PHYSICAL_TRUTH', 'Unknown negative relation policy')
    check = deepcopy(value)
    check['schema_version'] = 'phase8_b_v4_identity_policy_v1'
    previous._validate_policy(check)
    return (value, check)

def _review_identity(item):
    """An explicit scoped source assignment is distinct from a group label."""
    refs = list(item.get('review_refs', []))
    if isinstance(item.get('review_ref'), dict):
        refs.append(item['review_ref'])
    unit = str(item['unit_id'])
    generated = unit.startswith(('retained-clique:', 'track:', 'person-track:'))
    return bool(refs) and (not generated)

def _retained_positive_groups(row, controls):
    groups = defaultdict(list)
    for item in row['observations']:
        proof = item.get('source_ref', {}).get('retained_same_vehicle_association', {})
        if item['role'] == 'vehicle' and item.get('association_verified') is True and (item.get('association_id') is not None) and (proof.get('frame_index') == row['frame_index']) and (proof.get('whole_id_support_implied') is False):
            groups[item['association_id']].append(item)
    accepted = set()
    for association, items in groups.items():
        tracks = {o['track_id'] for o in items}
        if len(items) < 2 or any((o.get('identity_conflict') for o in items)):
            continue
        if any((set(o['source_ref']['retained_same_vehicle_association'].get('track_ids', [])) != tracks for o in items)):
            continue
        if any((previous._iou(a['raw_bbox'], b['raw_bbox']) < controls['possible_handoff_min_iou'] for index, a in enumerate(items) for b in items[index + 1:])):
            continue
        accepted.add(association)
    return accepted

def _isolate_hypotheses(frames, controls):
    audit = []
    for row in frames:
        positive = _retained_positive_groups(row, controls)
        for item in row['observations']:
            if item['role'] != 'vehicle':
                continue
            source_unit, source_episode = (item['unit_id'], item['episode_id'])
            item['p0_historical_unit_hypothesis'] = source_unit
            item['p0_historical_episode_hypothesis'] = source_episode
            if _review_identity(item):
                item['p0_identity_basis'] = 'PRESERVED_SOURCE_BOUND_REVIEW_ASSIGNMENT'
                continue
            item['unit_id'] = f"track:{item['track_id']}"
            item['episode_id'] = 'unreviewed-vehicle'
            source_positive = item.get('association_verified') is True and item.get('association_id') in positive
            if not source_positive:
                item['association_verified'] = False
                item.pop('association_id', None)
            item['p0_identity_basis'] = 'EXACT_FRAME_RETAINED_POSITIVE_RELATION' if source_positive else 'ISOLATED_RAW_CONTEXT_PHYSICAL_CONTINUITY_UNVERIFIED'
            if source_unit != item['unit_id']:
                audit.append({'frame_index': row['frame_index'], 'track_id': item['track_id'], 'historical_unit_hypothesis': source_unit, 'independent_raw_context': item['unit_id'], 'exact_frame_positive_proof_present': source_positive, 'whole_id_unification_permitted': False})
    return audit

def _remap_retained_component_parents(frames, relationships):
    """Retain a source-supported rider's exact observed parent after isolation.

    A historical group label is not enough to pick the parent. The old adapter
    has already validated the source measurements; we additionally require its
    retained relation ID, child ID, support frame and actually present raw parent.
    No frame between support observations is filled or relabelled here.
    """
    supported = defaultdict(list)
    for link in (relationships or {}).get('component_links', []):
        for frame in link.get('support_frames', []):
            supported[frame, link.get('component_track_id'), link.get('relation_id')].append(link)
    audit = []
    for row in frames:
        present = {o['track_id']: o for o in row['observations']}
        for child in present.values():
            if child['role'] != 'rider' or child['class_name'] != 'person':
                continue
            key = (row['frame_index'], child['track_id'], child.get('retained_component_relation_id'))
            links = supported.get(key, [])
            parents = {link['vehicle_track_id'] for link in links if link.get('vehicle_track_id') in present and present[link['vehicle_track_id']]['role'] == 'vehicle' and (present[link['vehicle_track_id']]['class_name'] == 'motorcycle')}
            if len(parents) != 1:
                continue
            parent = present[next(iter(parents))]
            child.update(component_of_track_id=parent['track_id'], component_of_unit_id=parent['unit_id'], p0_component_parent_remap_source='EXACT_FRAME_RETAINED_COMPONENT_RELATION')
            audit.append({'frame_index': row['frame_index'], 'component_track_id': child['track_id'], 'vehicle_track_id': parent['track_id'], 'relation_id': key[2], 'physical_unit_id': parent['unit_id'], 'scope_extended': False})
    return audit

def _refine_episode_scopes(frames):
    """Alias adoption starts a new bounded physical-context reference.

    A local association later in the raw-ID history must never give finalizers
    an edge into an earlier independently observed object/context.
    """
    state = {}
    for row in frames:
        for item in row['observations']:
            track = item['track_id']
            base_context = item['physical_episode_id']
            counting_key = (item['unit_id'], item['episode_id'])
            prior = state.get(track)
            vehicle_context = counting_key if item['role'] == 'vehicle' else prior[1] if prior is not None and prior[0] == base_context else None
            changed = prior is None or base_context != prior[0] or (item['role'] == 'vehicle' and prior[1] is not None and (counting_key != prior[1]))
            if changed:
                context = previous._hash('b5-physical-context:', [track, base_context, *counting_key, row['frame_index']])
            else:
                context = prior[2]
            if prior is not None and context != prior[2]:
                item['previous_physical_episode_id'] = prior[2]
            elif 'previous_physical_episode_id' in item:
                item.pop('previous_physical_episode_id')
            item['physical_episode_id'] = context
            state[track] = (base_context, vehicle_context, context)

def _rebind_diagnostic_episodes(result):
    """Keep inherited diagnostics source-addressable after ID refinement."""
    index = {(row['frame_index'], item['track_id']): item['physical_episode_id'] for row in result['frames'] for item in row['observations']}
    for audit in result['handoff_audit']:
        for prefix, frame_key in (('first', 'last_first_frame'), ('second', 'first_second_frame')):
            key = (audit[frame_key], audit[prefix + '_track_id'])
            old = audit[prefix + '_episode_id']
            audit['inherited_' + prefix + '_episode_id'] = old
            audit[prefix + '_episode_id'] = index[key]
        audit['episode_refs_rebound_to_exact_observed_endpoints'] = True
    for audit in result['alias_context_audit']:
        key = (audit['frame_index'], audit['track_id'])
        audit['inherited_physical_episode_id'] = audit['physical_episode_id']
        audit['physical_episode_id'] = index[key]
        audit['episode_ref_rebound_to_exact_observed_frame'] = True

def _relation_rows(frames, controls):
    groups = {}

    def add(kind, first, second, frame, verified, basis):
        if kind != 'COMPONENT_OF' and first['track_id'] > second['track_id']:
            first, second = (second, first)
        key = (kind, first['track_id'], second['track_id'], first['physical_episode_id'], second['physical_episode_id'], verified, basis)
        relation = groups.setdefault(key, {'relation_type': kind, 'type': kind, 'relation_id': previous._hash('b5-relation:', key), 'first_track_id': first['track_id'], 'second_track_id': second['track_id'], 'first_physical_episode_id': first['physical_episode_id'], 'second_physical_episode_id': second['physical_episode_id'], 'first_unit_id': first['unit_id'], 'second_unit_id': second['unit_id'], 'first_episode_id': first['episode_id'], 'second_episode_id': second['episode_id'], 'support_frames': [], 'verified': verified, 'verification_basis': basis, 'claim_type': 'SOURCE_SCOPED_RELATION_NOT_GLOBAL_RAW_ID_OR_GROUND_TRUTH', 'earlier_frames_reassigned': False})
        relation['support_frames'].append(frame)
    for row in frames:
        present = {o['track_id']: o for o in row['observations']}
        vehicles = [o for o in present.values() if o['role'] == 'vehicle']
        for index, first in enumerate(vehicles):
            for second in vehicles[index + 1:]:
                if first.get('association_verified') is True and second.get('association_verified') is True and (first.get('association_id') == second.get('association_id')) and (first.get('association_id') is not None) and ((first['unit_id'], first['episode_id']) == (second['unit_id'], second['episode_id'])):
                    add('SAME_UNIT', first, second, row['frame_index'], True, 'EXACT_FRAME_POSITIVE_ASSOCIATION_OR_BOUNDED_REVIEW')
                elif first.get('p0_historical_unit_hypothesis') == second.get('p0_historical_unit_hypothesis') and first.get('p0_historical_unit_hypothesis', '').startswith('retained-clique:') and (previous._iou(first['raw_bbox'], second['raw_bbox']) == 0):
                    add('DIFFERENT_UNIT', first, second, row['frame_index'], False, 'DISJOINT_COPRESENCE_CONTRADICTS_UNSUPPORTED_GROUP_NAME_ONLY')
        for child in present.values():
            parent = present.get(child.get('component_of_track_id'))
            if child['role'] == 'rider' and parent is not None and (parent['role'] == 'vehicle'):
                add('COMPONENT_OF', child, parent, row['frame_index'], True, 'EXACT_OBSERVED_BOUNDED_ROLE_SUPPORT_NOT_TRAINED_ROLE_TRUTH')
    reviewed = defaultdict(lambda: defaultdict(list))
    for row in frames:
        for item in row['observations']:
            if item['role'] != 'vehicle' or not _review_identity(item):
                continue
            association = item.get('association_id')
            refs = item.get('review_refs', [])
            if item.get('association_verified') is True and association is not None and any((ref.get('review_id') == association for ref in refs)):
                key = (association, item['unit_id'], item['episode_id'])
                reviewed[key][item['track_id'], item['physical_episode_id']].append(item)
    for episodes in reviewed.values():
        members = list(episodes.values())
        for index, first in enumerate(members):
            for second in members[index + 1:]:
                if first[0]['track_id'] == second[0]['track_id']:
                    continue
                for item in first + second:
                    add('SAME_UNIT', first[0], second[0], item['frame_index'], True, 'SOURCE_BOUND_REVIEWED_HANDOFF_SCOPE_NOT_MEASURED_GAP_CROSSING')
    rows = []
    for relation in groups.values():
        relation['support_frames'] = sorted(set(relation['support_frames']))
        relation['start_frame'], relation['end_frame'] = (relation['support_frames'][0], relation['support_frames'][-1])
        rows.append(relation)
    return sorted(rows, key=lambda r: (r['start_frame'], r['relation_type'], r['first_track_id'], r['second_track_id']))

def _cross_category_candidates(frames, controls):
    """Find hypotheses hidden by a class-equality gate; never merge them.

    The existing component controls are reused as explicit research inputs.
    Overlap and covariation do not prove same unit (two adjacent vehicles can
    satisfy them). Weak covariation is audit-only in this versioned ablation.
    Only high-overlap co-observation holds a conflict, never creates an alias.
    """
    pairs = defaultdict(list)
    for row in frames:
        vehicles = [o for o in row['observations'] if o['role'] == 'vehicle']
        for index, first in enumerate(vehicles):
            for second in vehicles[index + 1:]:
                if first['class_name'] == second['class_name']:
                    continue
                if first['track_id'] > second['track_id']:
                    a, b = (second, first)
                else:
                    a, b = (first, second)
                if a.get('association_verified') and b.get('association_verified') and (a.get('association_id') == b.get('association_id')) and ((a['unit_id'], a['episode_id']) == (b['unit_id'], b['episode_id'])):
                    continue
                scale = (previous._diag(a['raw_bbox']) + previous._diag(b['raw_bbox'])) / 2
                distance = previous._distance(previous._center(a['raw_bbox']), previous._center(b['raw_bbox'])) / scale
                if previous._iou(a['raw_bbox'], b['raw_bbox']) <= 0 or distance > controls['component_center_limit']:
                    continue
                key = (a['track_id'], b['track_id'], a['physical_episode_id'], b['physical_episode_id'])
                pairs[key].append((a, b))
    relations, audit = ([], [])
    for key, observations in sorted(pairs.items()):
        runs, current = ([], [])
        for pair in observations:
            if current and pair[0]['frame_index'] != current[-1][0]['frame_index'] + 1:
                runs.append(current)
                current = []
            current.append(pair)
        if current:
            runs.append(current)
        for run in runs:
            offsets = []
            scales = []
            for first, second in run:
                a, b = (previous._center(first['raw_bbox']), previous._center(second['raw_bbox']))
                offsets.append((a[0] - b[0], a[1] - b[1]))
                scales.append((previous._diag(first['raw_bbox']) + previous._diag(second['raw_bbox'])) / 2)
            residuals = [previous._distance(offsets[i], offsets[i - 1]) / ((scales[i] + scales[i - 1]) / 2) for i in range(1, len(run))]
            score = median(residuals) if residuals else None
            temporal_support = len(run) >= controls['min_component_run'] and score is not None and (score <= controls['component_motion_limit'])
            high_overlap = [pair for pair in run if previous._iou(pair[0]['raw_bbox'], pair[1]['raw_bbox']) >= controls['possible_handoff_min_iou']]
            paths = [[((pair[k]['raw_bbox'][0] + pair[k]['raw_bbox'][2]) / 2, pair[k]['raw_bbox'][3]) for pair in run] for k in (0, 1)]
            vectors = [(path[-1][0] - path[0][0], path[-1][1] - path[0][1]) for path in paths]
            monotone = [all(((b[0] - a[0]) * vector[0] + (b[1] - a[1]) * vector[1] > 0 for a, b in zip(path, path[1:]))) for path, vector in zip(paths, vectors)]
            opposite = len(run) >= controls['min_component_run'] and all(monotone) and (vectors[0][0] * vectors[1][0] + vectors[0][1] * vectors[1][1] < 0)
            hold_supported = bool(high_overlap) and (not opposite)
            selected = high_overlap if hold_supported else run if temporal_support or opposite else []
            supported = bool(selected)
            mode = 'EXACT_FRAME_HIGH_IOU_CONFLICT_ONLY' if hold_supported else 'OPPOSITE_OBSERVED_BC_MOTION_AUDIT_ONLY' if opposite else 'WEAK_COVARIATION_AUDIT_ONLY' if temporal_support else 'NO_SUPPORTED_CONFLICT'
            support = [a['frame_index'] for a, _ in selected]
            relation_id = previous._hash('b5-cross-category-hypothesis:', [*key, support, mode])
            audit.append({'relation_id': relation_id, 'first_track_id': key[0], 'second_track_id': key[1], 'first_physical_episode_id': key[2], 'second_physical_episode_id': key[3], 'support_frames': support, 'examined_source_frames': [a['frame_index'] for a, _ in run], 'common_observed_frames': len(run), 'support_mode': mode, 'opposite_observed_bc_motion': opposite, 'hold_supported': hold_supported, 'median_relative_motion_residual_norm': score, 'candidate_supported': supported, 'automatic_alias_created': False, 'claim_type': 'GEOMETRIC_COVARIATION_HYPOTHESIS_NOT_PHYSICAL_IDENTITY_TRUTH'})
            if not supported:
                continue
            first, second = selected[0]
            relations.append({'relation_type': 'SAME_UNIT', 'type': 'SAME_UNIT', 'relation_id': relation_id, 'first_track_id': key[0], 'second_track_id': key[1], 'first_physical_episode_id': key[2], 'second_physical_episode_id': key[3], 'first_unit_id': first['unit_id'], 'second_unit_id': second['unit_id'], 'first_episode_id': first['episode_id'], 'second_episode_id': second['episode_id'], 'support_frames': support, 'start_frame': support[0], 'end_frame': support[-1], 'verified': False, 'candidate_kind': 'POSSIBLE_CROSS_CATEGORY_UNIT_OR_COMPONENT' if hold_supported else 'WEAK_CROSS_CATEGORY_AUDIT_ONLY', 'support_mode': mode, 'verification_basis': 'OVERLAP_CENTER_OR_COVARIATION_REUSE_FROZEN_RESEARCH_CONTROLS', 'claim_type': 'UNRESOLVED_SCOPED_PHYSICAL_UNIT_HYPOTHESIS_NOT_MERGE_PROOF', 'earlier_frames_reassigned': False})
            if hold_supported:
                for a, b in selected:
                    for item in (a, b):
                        reason = 'CROSS_CATEGORY_UNIT_OR_COMPONENT_UNRESOLVED'
                        if reason not in item['identity_timeout_hold']:
                            item['identity_timeout_hold'].append(reason)
    return (relations, audit)

def _assignments(frames):
    rows = []
    fields = ('component_of_unit_id', 'component_of_track_id', 'component_of_episode_id', 'component_parent_context_id', 'physical_episode_id', 'identity_episode_boundary', 'identity_episode_reason', 'previous_physical_episode_id', 'identity_timeout_hold', 'source_bound_episode_id_before_context_split', 'role_scope_id', 'role_source', 'p0_historical_unit_hypothesis', 'p0_identity_basis', 'p0_component_parent_remap_source')
    for row in frames:
        for item in row['observations']:
            rows.append({'frame_index': row['frame_index'], 'track_id': item['track_id'], 'physical_unit_id': item['unit_id'], 'episode_id': item['episode_id'], 'role': item['role'], 'category': item.get('resolved_class_name', item['class_name']), 'raw_category': item['class_name'], 'review_refs': deepcopy(item.get('review_refs', [])), 'association_verified': item.get('association_verified', False), 'association_id': item.get('association_id'), **{key: deepcopy(item[key]) for key in fields if key in item}})
    return rows

def prepare_identity_frames(frames, geometry, policy, relationships=None):
    controls, inherited_controls = _controls(policy)
    copied, _ = previous._validated_frames(frames)
    hypothesis_audit = _isolate_hypotheses(copied, controls)
    parent_remap_audit = _remap_retained_component_parents(copied, relationships)
    result = previous.prepare_identity_frames(copied, geometry, {'identity': inherited_controls}, relationships=relationships)
    _refine_episode_scopes(result['frames'])
    _rebind_diagnostic_episodes(result)
    cross_category_relations, cross_category_audit = _cross_category_candidates(result['frames'], controls)
    result['assignments'] = _assignments(result['frames'])
    result['unit_relations'] = _relation_rows(result['frames'], controls) + cross_category_relations
    result['cross_category_audit'] = cross_category_audit
    result['historical_hypothesis_audit'] = hypothesis_audit
    result['retained_component_parent_remap_audit'] = parent_remap_audit
    result['policy'] = controls
    result['inherited_episode_audit'] = result['episode_audit']
    contexts = defaultdict(list)
    for row in result['frames']:
        for item in row['observations']:
            contexts[item['physical_episode_id']].append(item)
    result['episode_audit'] = [{'physical_episode_id': key, 'track_id': items[0]['track_id'], 'physical_unit_id': items[0]['unit_id'], 'episode_id': items[0]['episode_id'], 'start_frame': items[0]['frame_index'], 'end_frame': items[-1]['frame_index'], 'observed_frames': len(items), 'boundary_reason': items[0].get('identity_episode_reason'), 'claim_type': 'P0_BOUNDED_CONTEXT_NOT_VERIFIED_PHYSICAL_IDENTITY'} for key, items in sorted(contexts.items(), key=lambda pair: (pair[1][0]['frame_index'], pair[1][0]['track_id']))]
    result['provenance'].update(whole_id_historical_groups_used_as_identity=False, current_source_positive_aliases_only=True, disjoint_copresence_is_not_global_physical_truth=True, same_class_gradual_handoff_completely_solved=False, source_bound_reviews_are_preserved_not_new_model_predictions=True)
    return result
