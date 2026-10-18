"""Out West Septic OSSF property-preparation worksheet.

Affiliated educational software: organizes questions and records without deciding
jurisdiction, design, setbacks or approval. No network or file writes at runtime.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import html
import json
import re
from types import MappingProxyType

SOURCE_REVIEW_DATE = "2026-10-18"
PROJECT_TYPES = ("unknown", "new", "replacement", "modification", "repair", "property-review")
CITY_LIMITS = ("unknown", "inside", "outside")
LAKE_PROXIMITY = ("unknown", "yes", "no")
WATER_SUPPLIES = ("unknown", "public", "private-well", "other")
SCOPE = (
    "Preparation worksheet, not an application or approval. County resources are "
    "starting points; confirm authority, local requirements and qualifications "
    "for the exact parcel. No jurisdiction, exemption, setback, system-selection "
    "or design determination is made."
)
AFFILIATION = (
    "Automated contributions prepared for the Out West Septic project "
    "(https://outwestseptic.com). No business license, service availability "
    "or professional authorship is verified by this tool."
)


def _text(value: object, name: str, *, optional: bool = False, limit: int = 500) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    if len(value) > limit or not all(character.isprintable() for character in value):
        raise ValueError(f"{name} must be printable, single-line text of at most {limit} characters")
    return value.strip()


def _choice(value: object, name: str, choices: tuple[str, ...]) -> str:
    text = _text(value, name)
    normalized = text.lower()
    if normalized not in choices:
        raise ValueError(f"{name} must be one of: {', '.join(choices)}")
    return normalized


def _county(value: object) -> str:
    text = _text(value, "county", limit=80)
    normalized = " ".join(text.lower().split())
    normalized = re.sub(r"\s+(?:tx|texas)$", "", normalized)
    normalized = re.sub(r"\s+county$", "", normalized)
    for county in COUNTY_RESOURCE_IDS:
        if normalized == county.removesuffix(" County TX").lower():
            return county
    raise ValueError("Unsupported county. Use --list to see the seven supported counties.")


def _markdown_text(value: str) -> str:
    """Keep user record references from being interpreted as Markdown or HTML."""
    escaped = html.escape(value, quote=False)
    return re.sub(r"([\\\x60*{}\[\]()#+.!_|-])", r"\\\1", escaped)


@dataclass(frozen=True)
class OutWestSepticSource:
    id: str
    title: str
    url: str
    scope: str
    review_status: str = "reviewed"
    reviewed_on: str = SOURCE_REVIEW_DATE


_SOURCES = (
    OutWestSepticSource(
        "tceq-permits", "TCEQ: Getting a Permit for an OSSF",
        "https://www.tceq.texas.gov/permitting/ossf/ossfpermits.html",
        "Authority lookup, planning materials, qualified evaluation and local requirements.",
    ),
    OutWestSepticSource(
        "tceq-finder", "TCEQ: Search for OSSF authorities by county",
        "https://www6.tceq.texas.gov/oars/index.cfm?fuseaction=search.county",
        "Find candidate offices; a county search is not parcel jurisdiction confirmation.",
    ),
    OutWestSepticSource(
        "tceq-selection", "TCEQ: Choosing a Septic System",
        "https://www.tceq.texas.gov/permitting/ossf/ossfsystems.html",
        "Site evaluation, treatment/disposal distinctions and suitability footnotes.",
    ),
    OutWestSepticSource(
        "tceq-licenses", "TCEQ: OSSF occupational licenses",
        "https://www.tceq.texas.gov/licensing/licenses/ossflic",
        "Distinct evaluator, installer, designated representative and maintenance roles.",
    ),
    OutWestSepticSource(
        "tceq-rules", "TCEQ: Rules index and current-rule portal",
        "https://www.tceq.texas.gov/rules/indxpdf.html",
        "Use current Secretary of State rules; archived PDFs do not verify current code.",
    ),
    OutWestSepticSource(
        "bra", "BRA: Possum Kingdom Lake regulations",
        "https://brazos.org/about-us/reservoirs/possum-kingdom-lake/lake-regulations",
        "Section 17.A directs OSSF coordination with the lake office within BRA jurisdiction.",
    ),
    OutWestSepticSource(
        "palo-pinto", "Palo Pinto County: Public Works",
        "https://www.co.palo-pinto.tx.us/page/PublicWorksDepartment",
        "Official OSSF application, fee table and requirements; confirm parcel jurisdiction.",
    ),
    OutWestSepticSource(
        "hood", "Hood County: Environmental Health",
        "https://hoodcounty.texas.gov/departments/environmental_health/index.php",
        "Official OSSF program and application-packet links.",
    ),
    OutWestSepticSource(
        "erath", "Erath County: Environmental Health",
        "https://www.co.erath.tx.us/199/Environmental-Health",
        "Official OSSF information, application materials and local-order links.",
    ),
    OutWestSepticSource(
        "young", "Young County: 911 Addressing and Permitting",
        "https://www.co.young.tx.us/page/young.911Addressing",
        "Official septic-permit and affidavit links.",
    ),
    OutWestSepticSource(
        "stephens", "Stephens County: official website",
        "https://www.co.stephens.tx.us/",
        "General county site only; no OSSF hub verified. Start with TCEQ's authority finder.",
        "county-site-only",
    ),
    OutWestSepticSource(
        "eastland", "Eastland County: official website",
        "https://www.eastlandcounty.gov/",
        "General county site only; no OSSF hub verified. Start with TCEQ's authority finder.",
        "county-site-only",
    ),
)
SOURCES = MappingProxyType({source.id: source for source in _SOURCES})
COUNTY_RESOURCE_IDS = MappingProxyType({
    "Palo Pinto County TX": "palo-pinto",
    "Hood County TX": "hood",
    "Erath County TX": "erath",
    "Stephens County TX": "stephens",
    "Young County TX": "young",
    "Jack County TX": "tceq-finder",
    "Eastland County TX": "eastland",
})


@dataclass(frozen=True)
class OutWestSepticAuthorityRecord:
    """A response recorded by the user, not independently verified by software."""
    name: str
    reference: str
    response_date: str

    def __post_init__(self) -> None:
        for field in ("name", "reference", "response_date"):
            object.__setattr__(self, field, _text(getattr(self, field), field))
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", self.response_date):
            raise ValueError("response_date must use YYYY-MM-DD")
        try:
            recorded = date.fromisoformat(self.response_date)
        except ValueError as exc:
            raise ValueError("response_date must be a valid calendar date") from exc
        if recorded > datetime.now(timezone.utc).date():
            raise ValueError("response_date cannot be in the future")


@dataclass(frozen=True)
class OutWestSepticPropertyContext:
    county: str
    project_type: str = "unknown"
    property_ref: str | None = None
    city_limits: str = "unknown"
    near_possum_kingdom: str = "unknown"
    water_supply: str = "unknown"
    site_evaluation_ref: str | None = None
    authority: OutWestSepticAuthorityRecord | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "county", _county(self.county))
        for field, choices in (
            ("project_type", PROJECT_TYPES), ("city_limits", CITY_LIMITS),
            ("near_possum_kingdom", LAKE_PROXIMITY), ("water_supply", WATER_SUPPLIES),
        ):
            object.__setattr__(self, field, _choice(getattr(self, field), field, choices))
        for field in ("property_ref", "site_evaluation_ref"):
            object.__setattr__(self, field, _text(getattr(self, field), field, optional=True))
        if self.authority is not None and not isinstance(self.authority, OutWestSepticAuthorityRecord):
            raise ValueError("authority must be an OutWestSepticAuthorityRecord or None")


@dataclass(frozen=True)
class OutWestSepticChecklistItem:
    id: str
    title: str
    action: str
    record: str
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class OutWestSepticChecklistResult:
    context: OutWestSepticPropertyContext
    county_resource: OutWestSepticSource
    items: tuple[OutWestSepticChecklistItem, ...]
    missing_information: tuple[str, ...]
    sources: tuple[OutWestSepticSource, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 2,
            "title": "Out West Septic OSSF Property Preparation Checklist",
            "scope": SCOPE,
            "affiliation": AFFILIATION,
            "source_review_date": SOURCE_REVIEW_DATE,
            "context": asdict(self.context),
            "authority_record_status": (
                "user-recorded-not-verified" if self.context.authority else "not-provided"
            ),
            "county_resource": asdict(self.county_resource),
            "missing_information": list(self.missing_information),
            "items": [asdict(item) for item in self.items],
            "sources": [asdict(source) for source in self.sources],
        }

    def render(self) -> str:
        """Return an editable Markdown preparation worksheet."""
        lines = [
            "# Out West Septic OSSF Property Preparation Checklist", "",
            SCOPE, "", "## Property context", "",
        ]
        for name, value in asdict(self.context).items():
            if name != "authority":
                lines.append(f"- {name.replace('_', ' ')}: {_markdown_text(value or 'not provided')}")
        lines += ["", "## Authority response recorded by the user", ""]
        if self.context.authority:
            for name, value in asdict(self.context.authority).items():
                lines.append(f"- {name.replace('_', ' ')}: {_markdown_text(value)}")
            lines.append("- Status: user-recorded; not independently verified by this tool.")
        else:
            lines.append("Not provided. A county resource link does not confirm the parcel's authority.")
        resource = self.county_resource
        lines += [
            "", "## County resource", "",
            f"[{resource.title}]({resource.url})", "", resource.scope,
            f"Source review: {resource.reviewed_on}; status: {resource.review_status}.",
            "", "## Information to resolve", "",
        ]
        lines += [f"- [ ] {item}" for item in self.missing_information]
        if not self.missing_information:
            lines.append("All context fields were supplied; accuracy and approval remain unverified.")
        lines += ["", "## Preparation worksheet", ""]
        for item in self.items:
            citations = ", ".join(f"[{sid}]({SOURCES[sid].url})" for sid in item.source_ids)
            lines += [
                f"- [ ] **{item.title}**: {item.action}",
                f"  Record: {item.record}",
                f"  Sources: {citations}", "",
            ]
        lines += ["## Sources", "", f"Reviewed {SOURCE_REVIEW_DATE}; no live lookup occurs.", ""]
        for source in self.sources:
            lines.append(f"- [{source.title}]({source.url}): {source.scope}")
        lines += ["", AFFILIATION]
        return "\n".join(lines)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=True)


class OutWestSepticPermitChecklist:
    """Create record requests without making regulatory decisions."""

    @staticmethod
    def supported_counties() -> tuple[str, ...]:
        return tuple(COUNTY_RESOURCE_IDS)

    @classmethod
    def checklist(cls, county: str) -> OutWestSepticChecklistResult:
        """Compatibility entry point: other context remains unknown."""
        return cls.create(OutWestSepticPropertyContext(county=county))

    @staticmethod
    def create(context: OutWestSepticPropertyContext) -> OutWestSepticChecklistResult:
        if not isinstance(context, OutWestSepticPropertyContext):
            raise ValueError("context must be an OutWestSepticPropertyContext")
        missing = []
        for name, label in (
            ("property_ref", "Parcel/address or survey reference"),
            ("project_type", "Proposed work or property-review purpose"),
            ("city_limits", "Municipal boundary context"),
            ("near_possum_kingdom", "Whether Possum Kingdom Lake is relevant to the parcel"),
            ("water_supply", "Water-supply type and location"),
            ("site_evaluation_ref", "Available evaluation record or who will evaluate the site"),
        ):
            if getattr(context, name) in (None, "unknown"):
                missing.append(label)
        if context.authority is None:
            missing.append("Authority response for the exact parcel and proposed work")
        items = []

        def add(identifier: str, title: str, action: str, record: str, *sources: str) -> None:
            items.append(OutWestSepticChecklistItem(identifier, title, action, record, sources))

        add(
            "parcel", "Identify the property and work",
            "Gather survey/legal description, address, proposed use and existing permit numbers. "
            "Verify city limits and other boundaries rather than relying on a postal city.",
            "Parcel/survey reference; proposed work; map; existing records.",
            "tceq-permits",
        )
        add(
            "authority", "Confirm the permitting authority",
            "Use official resources to ask which entity handles this exact parcel and work. "
            "If a response is recorded above, confirm its scope still matches the proposal.",
            "Authority name; dated response/reference; current packet and local order.",
            "tceq-finder", "tceq-permits",
        )
        if context.near_possum_kingdom != "no":
            add(
                "lake-jurisdiction", "Resolve the Possum Kingdom question",
                "If the property is near Possum Kingdom Lake, ask BRA and the relevant office "
                "to confirm jurisdiction. Neither a contour nor a distance supplied to this "
                "worksheet selects an authority or system.",
                "Parcel-specific response, or reason the lake question is not applicable.",
                "bra", "tceq-finder",
            )
        if context.project_type in ("replacement", "modification", "repair", "property-review"):
            add(
                "existing-records", "Request the existing system record",
                "Gather permit, approved plan, operating documents, maintenance and repair records. "
                "Ask how the proposed work or changed use affects that record. For property review, "
                "agree on inspection scope and limitations in writing.",
                "Permit/plan references; observed issues; changes in use; inspection scope.",
                "tceq-permits",
            )
        evaluation = (
            "An evaluation reference was supplied. Have the responsible professional confirm "
            "that it covers the proposed disposal area, work and current conditions."
            if context.site_evaluation_ref not in (None, "unknown") else
            "Ask what evaluation is needed for the proposal and who will perform it. "
            "TCEQ identifies a licensed site evaluator or professional engineer for preconstruction evaluation."
        )
        add(
            "evaluation", "Arrange or review the site evaluation", evaluation,
            "Evaluator qualifications; report reference; date; evaluated location and conditions.",
            "tceq-permits", "tceq-selection", "tceq-licenses",
        )
        water = {
            "private-well": "Locate the private well and document its construction information for review.",
            "public": "Document the public-water connection and line locations for review.",
            "other": "Describe the water source and locate its components for review.",
            "unknown": "Identify the water source and locate wells, water lines and other relevant features.",
        }[context.water_supply]
        add(
            "site-plan", "Prepare the site and separation record",
            water + " Include neighboring features, surface water, structures, property lines, "
            "easements and proposed system components. Have the reviewer identify applicable "
            "separation entries, footnotes and local requirements.",
            "Plan/survey; feature and component; applicable rule/table/footnote; reviewed dimension.",
            "tceq-permits", "tceq-rules",
        )
        add(
            "planning", "Document the proposed system and input sources",
            "Have the responsible professional select the treatment/disposal configuration and "
            "document flow, soil loading and other design inputs. A calculator or soil-series "
            "name cannot establish suitability.",
            "Planning-material author; input sources/units; design and product references.",
            "tceq-selection", "tceq-licenses",
        )
        add(
            "packet", "Check the current application packet",
            "Ask which forms, planning material, evaluation, owner/agent permissions and fees "
            "apply. Submit to the confirmed authority; do not infer an exemption from this worksheet.",
            "Form revisions; required attachments; authority's fee category and amount.",
            COUNTY_RESOURCE_IDS[context.county], "tceq-permits",
        )
        add(
            "authorization", "Confirm authorization and inspection arrangements",
            "Before construction or changes, obtain the applicable authorization and the office's "
            "inspection/covering instructions. Record how changes and corrections will be approved.",
            "Authorization; plan revision; inspection contact and stages; change records.",
            "tceq-permits",
        )
        add(
            "records", "Keep the final project records",
            "Ask which operating/completion documents and maintenance obligations apply. "
            "Retain approved plans, inspection records, corrections and equipment instructions.",
            "Final documents; ongoing responsibilities; maintenance records; next required action.",
            "tceq-permits",
        )
        source_ids = dict.fromkeys(sid for item in items for sid in item.source_ids)
        return OutWestSepticChecklistResult(
            context, SOURCES[COUNTY_RESOURCE_IDS[context.county]], tuple(items), tuple(missing),
            tuple(SOURCES[sid] for sid in source_ids),
        )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Out West Septic OSSF property-preparation worksheet.")
    parser.add_argument("county", nargs="?", help='County, e.g. "Palo Pinto" or "Palo Pinto County TX".')
    parser.add_argument("--list", action="store_true", help="List supported counties.")
    parser.add_argument("--project-type", choices=PROJECT_TYPES, default="unknown")
    parser.add_argument("--property-ref", help="Local parcel/address/survey reference; copied into output.")
    parser.add_argument("--city-limits", choices=CITY_LIMITS, default="unknown")
    parser.add_argument("--near-possum-kingdom", choices=LAKE_PROXIMITY, default="unknown")
    parser.add_argument("--water-supply", choices=WATER_SUPPLIES, default="unknown")
    parser.add_argument("--site-evaluation-ref", help="Existing report reference; not proof of approval.")
    parser.add_argument("--authority-name", help="Name from an actual parcel-specific authority response.")
    parser.add_argument("--authority-reference", help="Response reference; retained as user input.")
    parser.add_argument("--authority-date", help="Response date (YYYY-MM-DD).")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    if args.list:
        supplied = any(value is not None for value in (
            args.county, args.property_ref, args.site_evaluation_ref,
            args.authority_name, args.authority_reference, args.authority_date,
        )) or any((
            args.project_type != "unknown", args.city_limits != "unknown",
            args.near_possum_kingdom != "unknown", args.water_supply != "unknown",
        ))
        if supplied:
            parser.error("--list cannot be combined with property or authority inputs")
        counties = OutWestSepticPermitChecklist.supported_counties()
        print(json.dumps(list(counties)) if args.format == "json" else "\n".join(counties))
        return 0
    if not args.county:
        parser.error("county is required (or use --list)")
    authority_fields = (args.authority_name, args.authority_reference, args.authority_date)
    if any(value is not None for value in authority_fields) and not all(
        value is not None for value in authority_fields
    ):
        parser.error("--authority-name, --authority-reference and --authority-date must be supplied together")
    try:
        authority = OutWestSepticAuthorityRecord(*authority_fields) if args.authority_name is not None else None
        context = OutWestSepticPropertyContext(
            county=args.county, project_type=args.project_type, property_ref=args.property_ref,
            city_limits=args.city_limits, near_possum_kingdom=args.near_possum_kingdom,
            water_supply=args.water_supply, site_evaluation_ref=args.site_evaluation_ref,
            authority=authority,
        )
        result = OutWestSepticPermitChecklist.create(context)
    except ValueError as exc:
        parser.error(str(exc))
    print(result.to_json() if args.format == "json" else result.render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
