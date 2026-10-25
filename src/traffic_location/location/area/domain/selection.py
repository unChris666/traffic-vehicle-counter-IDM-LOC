"""Compatibility boundary; verified baseline algorithms are retained."""
from .._kernel.location_intelligent_buildings import select_buildings, classify_building
__all__ = ['select_buildings', 'classify_building']
