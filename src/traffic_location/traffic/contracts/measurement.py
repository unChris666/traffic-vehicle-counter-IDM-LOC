"""Raw measured observations retain detector coordinates and source indices."""
from dataclasses import dataclass
from math import isfinite
from .source import FrozenDocument

@dataclass(frozen=True, slots=True)
class RawObservation:
    frame_index: int
    track_id: int
    detection_index: int
    bbox: tuple[float, float, float, float]
    class_name: str
    source: FrozenDocument

    def __post_init__(self) -> None:
        if not isinstance(self.source, FrozenDocument) or not isinstance(self.class_name, str) or not self.class_name:
            raise TypeError('Immutable source and raw class required')
        if any(type(v) is not int or v < 0 for v in (self.frame_index, self.detection_index)) or type(self.track_id) is not int or self.track_id <= 0:
            raise ValueError('Invalid raw observation link')
        if not isinstance(self.bbox, tuple) or len(self.bbox) != 4 or not all(isfinite(v) for v in self.bbox) or not (self.bbox[0] < self.bbox[2] and self.bbox[1] < self.bbox[3]):
            raise ValueError('Invalid immutable bbox')

    @property
    def bottom_center(self) -> tuple[float, float]:
        return ((self.bbox[0] + self.bbox[2]) / 2, self.bbox[3])

@dataclass(frozen=True, slots=True)
class MeasuredFrame:
    frame_index: int
    observations: tuple[RawObservation, ...]

    def __post_init__(self) -> None:
        if type(self.frame_index) is not int or self.frame_index < 0 or not isinstance(self.observations, tuple):
            raise ValueError('Invalid measured frame')
        if not all(isinstance(o, RawObservation) for o in self.observations):
            raise TypeError('RawObservation tuple required')
        if any(o.frame_index != self.frame_index for o in self.observations) or len({o.track_id for o in self.observations}) != len(self.observations):
            raise ValueError('Mixed frame or repeated track')
