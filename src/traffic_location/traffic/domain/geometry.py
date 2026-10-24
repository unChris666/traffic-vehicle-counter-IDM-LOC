"""Geometry algorithms, retained exactly; input file I/O belongs to application."""
from .._kernel.geometry import Geometry, GeometryStateMachine, point_in_polygon, segment_intersection, signed_distance
__all__ = ['Geometry', 'GeometryStateMachine', 'point_in_polygon', 'segment_intersection', 'signed_distance']
