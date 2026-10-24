"""Different authority types for PRE_RESOLVER and POST_COUNTING."""
from dataclasses import dataclass
from enum import Enum
from .source import FrozenDocument

class SourceAction(str, Enum):
    SAME_VEHICLE = 'SAME_VEHICLE'
    SPLIT_IDENTITY = 'SPLIT_IDENTITY'
    COMPONENT_OF = 'COMPONENT_OF'
    PEDESTRIAN_ROLE = 'PEDESTRIAN_ROLE'

class CandidateAction(str, Enum):
    CLOSE_COMPONENT_PLUS_ZERO = 'CLOSE_COMPONENT_PLUS_ZERO'

@dataclass(frozen=True, slots=True)
class SourceContextReview:
    payload: FrozenDocument
    phase: str = 'PRE_RESOLVER'

    def __post_init__(self) -> None:
        if not isinstance(self.payload, FrozenDocument):
            raise TypeError('Immutable review payload required')
        obj = self.payload.object()
        if self.phase != 'PRE_RESOLVER' or obj.get('schema_version') != 'phase8_b_v4_review_overlay_v1':
            raise ValueError('Unsupported source review phase/schema')
        videos = obj.get('videos')
        if set(obj) - {'schema_version', 'donor_manifest_sha256', 'purpose', 'videos'}:
            raise ValueError('Unknown source review fields')
        if not isinstance(videos, list):
            raise ValueError('Source review videos required')
        for video in videos:
            if not isinstance(video, dict) or not isinstance(video.get('reviews'), list):
                raise ValueError('Source review list required')
            reviews = video['reviews']
            assert isinstance(reviews, list)
            for review in reviews:
                if not isinstance(review, dict) or review.get('type') not in {v.value for v in SourceAction} or set(review) - SOURCE_REVIEW_FIELDS:
                    raise ValueError('Unknown source-context action')

@dataclass(frozen=True, slots=True)
class CandidateAdjudication:
    payload: FrozenDocument
    phase: str = 'POST_COUNTING'

    def __post_init__(self) -> None:
        if not isinstance(self.payload, FrozenDocument):
            raise TypeError('Immutable review payload required')
        obj = self.payload.object()
        if self.phase != 'POST_COUNTING' or obj.get('schema_version') != 'phase9_b_v8_pending_adjudications_v1':
            raise ValueError('Unsupported candidate adjudication phase/schema')
        if set(obj) - {'schema_version', 'baseline_result_sha256', 'source_identity', 'decision_origin', 'adjudications'}:
            raise ValueError('Unknown adjudication fields')
        rows = obj.get('adjudications')
        if not isinstance(rows, list):
            raise ValueError('Explicit candidate adjudications required')
        for row in rows:
            if not isinstance(row, dict) or set(row) - CANDIDATE_REVIEW_FIELDS or row.get('final_status', 'resolved_not_eligible') != 'resolved_not_eligible' or any(k in row for k in ('force_accept', 'measured_crossing', 'new_event', 'action')):
                raise ValueError('Adjudication cannot create/accept/promote a passage')


SOURCE_REVIEW_FIELDS = frozenset("""positive_link_to_destination_track_created scope_extent_basis physical_unit_id type required_evidence_grade episode_id claim_type observation reviewer confirmed_frames review_id decision evidence unreviewed_after_confirmation_not_assigned_to_same_identity provenance_boundary scope_extent_note scope_basis human_confirmation_status scope_extent_is_engineering_assumption source_review_is_formal_ground_truth scopes not_a_post_occlusion_alias_to_4874 no_global_raw_id_label reviewed_decision_authority reviewed_result_not_machine_prediction component_of_unit_id resolved_class_name""".split())
CANDIDATE_REVIEW_FIELDS = frozenset("""baseline_source_ref role_scope reviewer_origin proof_artifacts reason reviewed_role adjudication_id scope positive_source_frames records_sha256 baseline_candidate_scope source_video_sha256 related_vehicle_raw_ids source_identity parent_attribution_status final_status previous_status reviewed_decision_authority""".split())
