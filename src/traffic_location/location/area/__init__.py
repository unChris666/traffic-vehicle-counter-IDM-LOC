"""Versioned Area artifact boundary. Domain migration remains evidence-gated."""
from .facade import freeze, reopen, execute, reopen_result
__all__ = ['freeze', 'reopen', 'execute', 'reopen_result']
