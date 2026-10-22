# LI-3 N1 pilot — actual result

Status: **PARTIAL**.

2623 source records; 1322 selected; 2623 rows accounted.

| Selected-building decision | Count |
|---|---:|
| ACCEPTED | 641 |
| ACCESS_UNVERIFIED | 620 |
| NO_VALID_CONNECTOR | 54 |
| OVER_TIME_LIMIT | 7 |

Denominator: all selected LI-1 buildings. Source exclusions have separate rows.

- Reference7kmh, not observed ETA
- Owner entrance/alley/gate assumptions, not physical/legal verification
- No mixed-unit capacity/population claim
- Bounded OSM graph, unknown permissions retained
- Conditional and complex restrictions conservatively quarantined, not fully interpreted

Full source/query/provenance and uncertainties: report.json, config/, raw/, diagnostics/.
