# Codex Brief — Location Intelligence 3 (LI-3)
## Real-World Data Integration, Motorcycle Routing, and Auditable Pilot

### 1. Mission

Continue the existing Location Intelligence project by implementing **LI-3: integration of real-world building data, a motorcycle-accessible road network, access restrictions, building-to-network connectors, and reproducible pilot execution**.

LI-3 must connect the existing LI-1 building selection and reference-capacity calculations with the LI-2 routing workflow using real, versioned, and auditable data sources.

**Do not rebuild LI-1 or LI-2.** Inspect the repository first, identify existing contracts and implementations, and extend them with minimal, well-tested changes.

The primary objective is reliable and explainable data integration—not proving real-world travel-time accuracy or population-capacity accuracy.

### 2. Mandatory First Step: Repository Audit

Before writing or modifying implementation code:

1. Inspect the repository structure, existing documentation, `AGENTS.md`, project specifications, tests, configuration, and previous LI-1/LI-2 implementations.
2. Identify the current building-data adapter, routing engine, graph representation, connector logic, reference-capacity calculations, and output schemas.
3. Identify the existing N1 pilot location and its approved configuration from repository artifacts. Do not invent coordinates or silently substitute another location.
4. Determine which data sources, credentials, cached datasets, and dependencies are already available.
5. Document existing capabilities, missing components, architectural constraints, and implementation risks.
6. Preserve existing working behavior and public interfaces unless a change is necessary and documented.

Produce an initial audit report before proceeding. If a critical prerequisite is missing, report it explicitly and implement independently testable components where possible. Do not fabricate successful data retrieval or pilot results.

### 3. Scope and Execution Order

Implement the following workstreams in order.

#### LI-3.1 — Freeze the N1 Pilot Scope

- Use the existing approved N1 example.
- Define an explicit geographic extraction boundary and data-selection rules.
- Separate LI-3 artifacts from TGDI and other unrelated workflows.
- Freeze a versioned pilot configuration containing the location, extraction boundary, source versions, routing parameters, access policies, and reference-capacity settings.
- Record configuration and schema versions.

The pilot must be reproducible from its stored configuration.

#### LI-3.2 — Complete the Overture Building Adapter

- Retrieve the explicitly selected Overture release using the existing supported access mechanism.
- Normalize building geometries and attributes into the existing LI-1 input contract.
- Preserve source identifiers, source release, original relevant attributes, and geometry provenance.
- Validate coordinate reference systems, geometry validity, duplicate identifiers, missing values, and extraction boundaries.
- Record retrieval time, query parameters, extraction metadata, and checksums.
- Cache the raw source artifacts and normalized outputs.

Data retrieval and normalization must be deterministic where the underlying source permits it. Re-running the adapter must not require hidden manual corrections.

A failed retrieval, incomplete extraction, or missing dataset must produce an explicit failure or incomplete status—not an empty dataset presented as a valid result.

#### LI-3.3 — Build the Real Motorcycle Routing Graph

Start with the existing `drive_service` network acquisition workflow.

Then identify and incorporate road segments that are valid for motorcycles but excluded by the existing motor-vehicle filtering rules.

Requirements:

- Build a directed graph that preserves legal travel direction.
- Preserve source segment identifiers and relevant source attributes.
- Retain connectivity between segments and distinguish missing connectivity from confirmed access restrictions.
- Support motorcycle-relevant road classifications and access permissions.
- Avoid automatically treating every road accessible to cars as accessible to motorcycles, or vice versa.
- Handle missing, contradictory, or insufficient access information explicitly.
- Preserve graph-building provenance and source versions.
- Produce graph diagnostics, including disconnected components, isolated nodes, suspicious gaps, and unresolved restrictions.

Do not silently relax routing filters merely to make buildings reachable.

#### LI-3.4 — Apply Access Restrictions

Implement or extend the routing policy to account for available evidence concerning:

- One-way streets and travel direction.
- Private roads and restricted access.
- Motorcycle prohibitions.
- Gates, portals, and controlled entrances.
- Turn restrictions and prohibited turns.
- Bridges, rivers, tunnels, and elevated roads.
- Road segments whose access permissions are unknown or contradictory.

Apply restrictions only when supported by available source evidence or explicitly configured policy.

Unknown conditions must remain visible in the output and diagnostics. Do not represent unknown access as confirmed permission or confirmed prohibition.

Where the available data cannot reliably establish a restriction, flag the affected segment or route as requiring verification. Document how uncertain restrictions affect route eligibility and result confidence.

A route must not cross a river, fence, or other physical barrier simply because two geometries are geographically close.

#### LI-3.5 — Build Auditable Building and Store Connectors

Connect each building or store to the motorcycle graph using explicit, inspectable connector geometry.

Rules:

- The maximum candidate access-search distance for buildings is **125 meters**.
- Store snapping has **no fixed numerical distance limit**, but must remain within the available graph and follow the defined snapping policy.
- Do not confuse geometric proximity with valid physical access.
- Do not create connectors through rivers, fences, walls, restricted parcels, or other unsupported barriers.
- Record candidate access points, connector geometry, distances, selected graph nodes or edges, and the decision rationale.
- Retain rejected candidates and rejection reasons where practical.
- Distinguish a building with no valid connector from a building with a valid connector but no reachable destination.

Use the existing project conventions for entrance assumptions. When no verified entrance is available, select an assumed entrance facing the highest-ranked valid access-road class that has a feasible route. Fall back to the next eligible class when routing fails.

Document the ranking rules and any tie-breaking logic. Never describe an assumed entrance as a verified physical entrance.

#### LI-3.6 — Integrate LI-1 Selection and Reference Capacity

Feed normalized buildings and valid routing results into the existing LI-1 selection and reference-capacity workflow.

- Preserve the existing LI-1 data contract.
- Keep capacity calculations separated by their original units.
- Never sum or compare incompatible units without an explicit conversion rule.
- Preserve the distinction between source observations, estimates, and assumptions.
- Do not silently change existing capacity formulas.
- Ensure every evaluated building can be traced to its source record, normalized geometry, capacity result, connector, routing result, and configuration.

LI-3 must integrate the existing calculations, not redefine their business logic.

#### LI-3.7 — Implement Motorcycle Routing and Decision Rules

Apply the following approved rules consistently:

| Rule | Required behavior |
|---|---|
| Travel speed | 7 km/h across every eligible route segment |
| Building access search | Maximum 125 meters |
| Store snapping | No fixed numerical distance limit within the available network |
| Access-class selection | Select the highest-ranked valid access class with a reachable route |
| Fallback | Try the next eligible access class when the higher-ranked class is unreachable |
| Same-class tie-break | Select the route with the lowest total travel time |
| Time decision | `round(total_minutes) <= 10` |
| Capacity reference | Preserve separate units |

Use one consistent travel-time calculation and rounding implementation.

Do not replace the approved rounded-time threshold with a raw `total_minutes <= 10` check. Keep the unrounded time, rounded time, and final eligibility decision in the result for auditing.

Define deterministic tie-breaking when routes have identical calculated times.

The 7 km/h speed is a reference assumption, not a claim about observed travel speed.

### 4. Required Decision States

Every evaluated building must receive an explicit status and reason.

At minimum, distinguish:

- `ACCEPTED`
- `OVER_TIME_LIMIT`
- `NO_VALID_CONNECTOR`
- `NO_ROUTE`
- `ACCESS_UNVERIFIED`
- `SOURCE_MISSING`
- `RETRIEVAL_FAILED`
- `INVALID_GEOMETRY`
- `PROCESSING_ERROR`

Adapt these names to existing project conventions if equivalent states already exist, but preserve the distinctions.

Statuses must not be mutually misleading. If the architecture supports it, represent the primary outcome separately from warnings, provenance, and verification requirements.

**Critical rule:** missing data, failed retrieval, invalid geometry, and unverified access must never be converted into a valid zero count or a confirmed rejection without an explicit reason.

### 5. Real-World Pilot and Validation

Execute the full pipeline on the approved N1 pilot:

1. Retrieve and preserve the selected building source.
2. Normalize building records and geometries.
3. Retrieve and construct the motorcycle graph.
4. Apply access restrictions and graph validation.
5. Generate building and store connectors.
6. Run routing and access-class fallback.
7. Apply the approved travel-time decision rule.
8. Integrate reference-capacity results.
9. Produce per-building outputs, diagnostics, and validation reports.

Explicitly inspect representative cases involving:

- One-way streets.
- Narrow alleys and motorcycle-accessible roads.
- Private roads and portals.
- Rivers and bridges.
- Elevated roads and grade-separated crossings.
- Turn restrictions.
- Disconnected graph components.
- Missing connectors and unreachable destinations.
- Unknown or contradictory access permissions.

Create targeted test fixtures for these cases when suitable real-world examples are unavailable. Clearly distinguish synthetic test evidence from observations made during the actual pilot.

Record how many cases were evaluated, accepted, rejected, unreachable, unverified, or affected by missing data. Explain the denominator used for every reported rate.

Do not claim that all edge cases are validated merely because unit tests pass.

### 6. Replayability and Artifact Management

Store all LI-3 outputs under the existing project convention:

`results/location_intelligent/`

Follow established naming and directory conventions where available. A suggested structure, to be adapted after the repository audit, is:

```text
results/location_intelligent/
  li3_pilot/
    config/
    raw/
    normalized/
    graph/
    connectors/
    building_results/
    diagnostics/
    validation/
    manifest.json
    report.md
```

Preserve, at minimum:

- Raw building data and relevant source extracts.
- Normalized building records.
- Road-network source extracts and the generated graph.
- Connector geometries and decision metadata.
- Per-building routing and selection results.
- Frozen pilot configuration.
- Source identifiers, versions, and retrieval timestamps.
- Checksums for stored artifacts.
- Schema and software version information.
- Logs, warnings, validation evidence, and a final report.

The manifest must identify dependencies between artifacts and record the parameters needed to reproduce the run.

Implement replay from saved artifacts without retrieving the underlying sources again. Replay must use the frozen configuration, stored source data, and recorded software or algorithm versions.

Verify determinism by comparing replay outputs against the original run using stable record ordering and canonical serialization. Report any differences rather than hiding them.

A checksum proves artifact integrity, not source accuracy or completeness.

### 7. Testing Requirements

Implement tests that cover:

- Building adapter normalization and schema validation.
- Geometry validity and coordinate reference systems.
- Graph directionality and connectivity.
- Motorcycle access filtering.
- Private access and prohibited movements.
- Connector distance limits and barrier handling.
- Access-class ranking and fallback.
- Lowest-time selection within the same class.
- The exact `round(total_minutes) <= 10` boundary behavior.
- Separate capacity units.
- Missing source data versus valid zero-valued results.
- Retrieval failures and partial data.
- Artifact checksums and manifest completeness.
- Replay equivalence.
- Deterministic output ordering and tie-breaking.

Use unit tests for deterministic logic, integration tests for adapters and graph construction, and pilot-level validation for real-world behavior.

Do not require live network access for ordinary unit tests. Use saved fixtures or mocks, and reserve live source retrieval for explicit integration or pilot commands.

### 8. Engineering and Execution Rules

- Follow existing repository instructions, coding style, dependency management, and architecture.
- Prefer small, reviewable changes over a wholesale rewrite.
- Keep source acquisition, normalization, graph construction, restriction handling, connector generation, routing, capacity integration, reporting, and replay logically separated.
- Make failures explicit and actionable.
- Avoid silent fallbacks, broad exception suppression, fabricated defaults, and unlogged manual corrections.
- Do not commit credentials, tokens, private data, or large source videos.
- Do not run destructive operations against existing artifacts.
- Avoid introducing new dependencies unless they materially improve correctness or maintainability.
- Keep TGDI, UI, Recount, PPAC, and unrelated workflows outside the LI-3 implementation scope.
- Do not claim successful execution, real-source validation, or reproducibility until supported by actual evidence.

### 9. Required Deliverables

Produce:

1. An initial repository audit report.
2. A frozen N1 pilot configuration.
3. A repeatable Overture building-data adapter.
4. A motorcycle routing graph builder.
5. Access-restriction handling and graph diagnostics.
6. Auditable building/store connector generation.
7. Integration with existing LI-1 selection and reference-capacity logic.
8. Motorcycle routing and explicit per-building decision results.
9. Saved raw and normalized source artifacts.
10. A manifest and replay implementation.
11. Unit and integration tests, plus pilot-validation evidence.
12. A final LI-3 report documenting implementation, source provenance, results, limitations, unresolved risks, and next steps.

All deliverables must follow the existing project architecture and be stored in the appropriate repository locations.

### 10. Definition of Done

LI-3 is complete only when:

- Real building data and a real road network have been retrieved and normalized successfully, with evidence.
- The graph supports directed motorcycle routing and exposes unresolved access restrictions.
- Connectors have inspectable geometry and documented decision logic.
- The approved routing and time-threshold rules are implemented and tested.
- Every evaluated building has a traceable outcome and reason.
- Missing data and retrieval failures remain distinguishable from valid zero-valued results.
- Capacity units remain separate.
- A complete pilot can be replayed from saved artifacts without new source retrieval.
- Replay produces equivalent decisions and documented output comparisons.
- The final report distinguishes verified evidence, assumptions, synthetic tests, and unresolved limitations.

**LI-3 does not need to prove actual travel-time accuracy or the accuracy of N1 population-capacity assumptions.** Those remain explicit limitations of the pilot.

### 11. Final Execution Instruction

Work autonomously within the defined scope, but do not guess when a missing decision would affect correctness.

First audit the repository and report the implementation plan. Then execute the workstreams in priority order:

**Motorcycle graph → access restrictions → connectors → replayable pilot → validation and review.**

After each major workstream, run relevant tests and preserve evidence. At completion, report:

- What was implemented.
- Which commands were executed.
- Which tests passed or failed.
- Which real data sources were successfully retrieved.
- Where the artifacts and reports were saved.
- Whether replay equivalence was verified.
- What remains unverified or blocked.
- The recommended next action.

Prioritize correctness, traceability, reproducibility, and honest reporting over superficial completion.