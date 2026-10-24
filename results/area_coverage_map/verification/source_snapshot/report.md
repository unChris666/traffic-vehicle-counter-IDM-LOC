# LI-3 N1 pilot — actual result

Status: **PARTIAL**.

9151 source records; 3597 selected; 9151 rows accounted.

| Selected-building decision | Count |
|---|---:|
| ACCEPTED | 1048 |
| ACCESS_UNVERIFIED | 1083 |
| NO_ROUTE | 88 |
| NO_VALID_CONNECTOR | 740 |
| OVER_TIME_LIMIT | 638 |

Denominator: all selected LI-1 buildings. Source exclusions have separate rows.

- Reference7kmh, not observed ETA
- Owner entrance/alley/gate assumptions, not physical/legal verification
- No mixed-unit capacity/population claim
- Bounded OSM graph, unknown permissions retained
- Conditional and complex restrictions conservatively quarantined, not fully interpreted

Full source/query/provenance and uncertainties: report.json, config/, raw/, diagnostics/.
