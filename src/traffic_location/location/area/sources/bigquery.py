"""Compatibility boundary; verified baseline algorithms are retained."""
from .._kernel.location_intelligent_map_pilot import load_bq_layers, query_bq_layer
__all__ = ['load_bq_layers', 'query_bq_layer']
