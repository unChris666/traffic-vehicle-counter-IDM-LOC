"""Compatibility boundary; verified baseline algorithms are retained."""
from .._kernel.location_intelligent_market import allocate_building, huff, classify_store
__all__ = ['allocate_building', 'huff', 'classify_store']
