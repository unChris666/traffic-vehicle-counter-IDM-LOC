# Area graph/routing empty-batch fix — 0.7.4rc1

Owner evidence: Area failed at graph_routing with `TypeError: Array should be of object dtype`. PBF preparation was READY with4398selectedroadways. Traffic continued independently. The supplied excerpt lacks the complete Python traceback; the exact owner call site is not proven from that excerpt alone.

Reproduction in Shapely2.1.2: `STRtree([polygon]).query([])` raises the exact TypeError. NumPy infers float dtype for an empty list; the GEOS spatial query expects an object geometry array. The frozen GPU connector path can produce an empty valid-candidate batch after filtering and calls `resident_footprint_batch`, which unconditionally called `tree.query(lines)` even when lines=[] .

Fix: adapter-level early return for an empty prepared batch in footprint_clear_batch and resident_footprint_batch. Empty candidate batches have no intersections to evaluate. No polygon upload/query or CUDA operation is performed by these empty-batch methods; nonempty calls delegate unchanged to the frozen implementation. Both source build_gpu and market build_market_gpu use a scoped adapter, restored after completion/failure. No global NumPy/Shapely monkeypatch, dependency downgrade, CPU inference fallback, or edits to frozen kernel files.

Allocation, access/rejection rules, Huff, graph topology, candidate selection, PPAC and Traffic counting remain unchanged. An empty batch does not manufacture accepted connectors or convert an unavailable source to zero. New code changes calculation/cache fingerprints; failed attempts are not reused as successful results.

Progress presentation retains seconds. A RUNNING checkpoint whose owner process is observed exited is explicitly marked stale. A process attached to a failed checkpoint may be the live coordinator, not the failed child worker; the display now labels this as the checkpoint-owning process.

Validation: six targeted tests pass in native GIS runtime: empty path cannot access CUDA/tree/inset; direct Shapely reproduction; nonempty CPU intersection/ownership parity; nonempty GPU-method delegation; scoped restoration after exception; source and market runtime scopes. No fresh CUDA/L4 run or owner-location recomputation in this environment.

Retest notebook18 (0.7.4rc1), coordinates from owner failure: latitude -6.11144497343484, longitude106.73812079250304. Allow currently running Traffic to finish before setup changes. Use Area Coverage alone first; check stage beyond graph/routing and final tables/map. Do not silently merge this job with an earlier Traffic job. If still failed, obtain full worker.log/diagnostic ZIP to identify whether the same call path or a different failure remains. Main/foundation not promoted.
