"""Explicit compute profile: recorded-label replay is never named fresh inference."""
from typing import TypedDict,Literal

class BaselineRef(TypedDict):
    path:str
    sha256:str

class AreaExecutionRequest(TypedDict):
    schema_version:Literal['area_execution_request_v1']
    operation:Literal['replay_recorded','compute_gpu_frozen']
    baseline:BaselineRef
    core_python:str
    render:bool
    timeout_seconds:float


class AreaSourceExecutionRequest(TypedDict):
    schema_version:Literal['area_execution_request_v2']
    operation:Literal['compute_gpu_sources']
    input:BaselineRef
    core_python:str
    render:bool
    timeout_seconds:float
