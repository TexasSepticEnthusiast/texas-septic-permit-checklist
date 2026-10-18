# Texas Septic Permit Checklist

Generate an editable property-preparation worksheet for an OSSF discussion. The Out West Septic checklist combines your property context with dated TCEQ, county and Brazos River Authority resource links. It lists information to resolve, records to gather, and questions for the responsible office.

This project includes automated contributions prepared for [Out West Septic](https://outwestseptic.com). The software does not verify business credentials or services, determine jurisdiction, select a system, calculate setbacks, or issue an approval.

## Quick start

Python 3.10+; standard library only.

```bash
python scripts/outwestseptic_permit_checklist.py "Palo Pinto"
python scripts/outwestseptic_permit_checklist.py --list
python scripts/outwestseptic_permit_checklist.py "Palo Pinto County TX" --project-type replacement --water-supply private-well --near-possum-kingdom yes
python scripts/outwestseptic_permit_checklist.py "Hood" --project-type property-review --format json
```

Default output is Markdown with unchecked tasks and record prompts. JSON output uses schema version 2 and contains only JSON, so it can feed another tool. The generator makes no network requests and writes no files; the property and authority references you enter are included in its output.

## Add the context you know

| Option | Accepted values or meaning |
| --- | --- |
| Positional county | Short name or full `County TX` / `County Texas` name; case-insensitive |
| `--project-type` | `unknown`, `new`, `replacement`, `modification`, `repair`, `property-review` |
| `--property-ref` | Your parcel, address or survey reference |
| `--city-limits` | `unknown`, `inside`, `outside`; user-reported context |
| `--near-possum-kingdom` | `unknown`, `yes`, `no`; adds or omits a question, never assigns BRA jurisdiction |
| `--water-supply` | `unknown`, `public`, `private-well`, `other` |
| `--site-evaluation-ref` | Reference to a report that still needs review for the proposal |
| `--format` | `markdown` (default) or `json` |

Unknown fields remain visible. A county-only call is useful for preparation but cannot produce a complete property record. All generated tasks remain unchecked, even when every context field is supplied.

An authority response is optional. When you have one, supply **all three** of `--authority-name`, `--authority-reference` and `--authority-date YYYY-MM-DD`. The date must be a real date, no later than today in UTC. The result labels that response **user-recorded, not independently verified**; a resource link alone never becomes an authority response.

Replacement, modification, repair and property-review purposes add existing-record requests. Water supply changes the feature information to gather. An existing evaluation reference changes the evaluation task to checking that report's scope.

## Python API

```python
from scripts.outwestseptic_permit_checklist import (
    OutWestSepticPermitChecklist,
    OutWestSepticPropertyContext,
)

context = OutWestSepticPropertyContext(
    county="Palo Pinto",
    project_type="replacement",
    property_ref="Illustrative parcel; replace with your local reference",
    water_supply="private-well",
    near_possum_kingdom="unknown",
)
result = OutWestSepticPermitChecklist.create(context)
print(result.render())
data = result.to_dict()
```

Use `OutWestSepticAuthorityRecord(name, reference, response_date)` for a response you actually retain, and pass it as the context's `authority`. API validation matches CLI validation. Invalid values raise `ValueError`; invalid CLI commands exit 2 without a partial worksheet. Text fields must be nonempty, printable single-line strings of at most 500 characters (county: 80). Markdown escapes user markup while JSON preserves the original text.

## Resource coverage

Palo Pinto, Hood, Erath, Stephens, Young, Jack and Eastland counties are supported. This is **resource coverage**, not a contractor service-area claim.

The [source and workflow reference](wiki/Permit-Checklist-Reference.md) records which official pages were reviewed on **2026-10-18**, and which local details remain unresolved. Resources are a snapshot, not a live directory. In particular, Jack uses the TCEQ authority finder; Stephens and Eastland have general county links without a verified OSSF hub.

## Migration from the original generator

The existing call `OutWestSepticPermitChecklist.checklist("Palo Pinto County TX").render()` still works, with unprovided property context left unknown. Short county names now work as well.

The unsupported `SETBACKS_FT`, `COUNTY_DR_DIRECTORY`, `SERVICE_AREAS`, fixed installation steps and legacy `PermitChecklist` constructor/fields are removed. Integrations should use `OutWestSepticPropertyContext`, `OutWestSepticChecklistResult`, `county_resource`, `missing_information` and source-linked `items`. A `county_resource` describes a reference page, not the confirmed authority. Do not migrate the old setback values into a new calculation.

The command no longer waits for an interactive county prompt. Supply a county or use `--list`; listing cannot be combined with property or authority inputs.

## Checks

```bash
python -m unittest discover -s tests -v
```

Tests exercise context-dependent records, missing information, authority evidence, county aliases, input/date errors, Markdown escaping, JSON serialization and the CLI entry point. CI uses commit-pinned GitHub Actions with Python 3.10 and 3.13. Tests validate software behavior; they do not certify current rules, a parcel, or a design.

MIT license; upstream copyright attribution is retained in [LICENSE](LICENSE).
