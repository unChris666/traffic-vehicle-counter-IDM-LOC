"""Execution, evidence, and publication are separate from business estimates."""
from typing import TypedDict, Literal

class AreaArtifactResult(TypedDict):
    schema_version: Literal['area_artifact_result_v1']
    execution_status: Literal['SUCCEEDED']
    data_quality_status: str
    operation: str
    result_version: str
    adapter_sha256: str
    claim_type: Literal['EXPERIMENTAL_SCENARIO']
    source_zip_sha256: str
    native_result_fingerprint: str
    equivalence_status: str
    reproducibility_status: str
    publication_status: str
    rows: list
    summary: dict
    capacity: dict


class AreaExecutionResult(TypedDict):
    schema_version: Literal['area_execution_result_v1']
    execution_status: Literal['SUCCEEDED']
    operation: Literal['replay_recorded', 'compute_gpu_frozen', 'compute_gpu_sources']
    data_quality_status: str
    claim_type: Literal['EXPERIMENTAL_SCENARIO']
    source_zip_sha256: str
    summary: dict
    native_domain_sha256: str
    parity_scope: dict
    environment: dict
    gpu_cpu_equivalence: str
    production_ready: Literal[False]
    result_version: str
    presentation_ref: str | None
