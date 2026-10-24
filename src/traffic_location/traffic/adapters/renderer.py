"""Rendering consumes final decisions and cannot run the counting facade."""
def render(*args, **kwargs):
    from ..annotation import render as render_full
    return render_full(*args, **kwargs)

def render_legacy_frame(*args, **kwargs):
    from ..render import frame
    return frame(*args, **kwargs)
