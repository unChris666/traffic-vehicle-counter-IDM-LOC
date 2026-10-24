"""Final native reconciliation; never accepts pending candidates by wrapper policy."""
from ..results import validate_native
from .._kernel import review_metadata

def finalize(native, *, request, branch, resolved, overlay=None):
    native.update(video_id=request['video_id'], source_identity=request['source_identity'], branch=branch,
                  frame_assignments=resolved['assignments'], component_links=resolved.get('component_links', []))
    if overlay is not None:
        review_metadata._decision_provenance(native, overlay, finalization_frame=request['frame_count'] - 1,
            overlay_sha256=request['artifacts']['review_overlay']['sha256'])
        native = review_metadata._rename_event_ids(native)
        native['report'].update(version='b_v8_p1_review_assisted_v1', reviewed_branch_not_machine_model_improvement=True)
    return validate_native(native)
