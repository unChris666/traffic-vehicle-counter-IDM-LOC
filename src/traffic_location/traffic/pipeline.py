"""Compatibility entry point; all counting now goes through the versioned facade."""
from .application.pipeline import run, process_video, implementation_hash
__all__ = ['run', 'process_video', 'implementation_hash']
