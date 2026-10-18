"""Behavioral tests for the public permit-preparation API and CLI."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import FrozenInstanceError
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest

from scripts.outwestseptic_permit_checklist import (
    OutWestSepticAuthorityRecord,
    OutWestSepticPermitChecklist,
    OutWestSepticPropertyContext,
    main,
)


class PropertyContextTests(unittest.TestCase):
    def test_county_aliases_preserve_the_existing_full_name(self):
        for county in ("Palo Pinto", "palo pinto county", "PALO PINTO COUNTY TX",
                       "  Palo   Pinto County Texas  ", "Palo Pinto TX"):
            with self.subTest(county=county):
                context = OutWestSepticPropertyContext(county)
                self.assertEqual(context.county, "Palo Pinto County TX")

    def test_rejects_unsupported_counties_and_invalid_county_values(self):
        for county in ("Hamilton", "Bosque", "", "  ", 12, None, True, "Palo Pinto\n"):
            with self.subTest(county=county), self.assertRaises(ValueError):
                OutWestSepticPropertyContext(county)

    def test_rejects_invalid_context_choices_through_api(self):
        fields = ("project_type", "city_limits", "near_possum_kingdom", "water_supply")
        for field in fields:
            for value in ("invented", "", None, True, 4):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    OutWestSepticPropertyContext("Hood", **{field: value})

    def test_api_normalizes_known_choices(self):
        context = OutWestSepticPropertyContext(
            "Hood", project_type=" REPAIR ", city_limits=" INSIDE ",
            near_possum_kingdom=" NO ", water_supply=" PUBLIC ",
        )
        self.assertEqual(context.project_type, "repair")
        self.assertEqual(context.city_limits, "inside")
        self.assertEqual(context.water_supply, "public")

    def test_rejects_empty_multiline_and_non_text_references(self):
        for field in ("property_ref", "site_evaluation_ref"):
            for value in ("", " ", "x\n# approved", "x\rnew", "\x1b[31m", "x\x7f",
                          "x\u2028y", "a" * 501, False, 34):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    OutWestSepticPropertyContext("Erath", **{field: value})

    def test_authority_must_be_an_explicit_record(self):
        for value in ("County", {}, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                OutWestSepticPropertyContext("Young", authority=value)

    def test_context_is_immutable(self):
        context = OutWestSepticPropertyContext("Young")
        with self.assertRaises(FrozenInstanceError):
            context.county = "Changed"


class AuthorityRecordTests(unittest.TestCase):
    def test_record_requires_name_reference_and_real_iso_date(self):
        invalid = [
            ("", "letter", "2020-01-01"), ("Office", "", "2020-01-01"),
            ("Office", "letter", "2020-02-30"), ("Office", "letter", "20200101"),
            ("Office", "letter", "tomorrow"), ("Office", "letter", "9999-01-01"),
            ("Office\napproved", "letter", "2020-01-01"),
            ("Office", True, "2020-01-01"),
        ]
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(ValueError):
                OutWestSepticAuthorityRecord(*values)

    def test_leap_day_is_valid_and_record_preserves_its_reference(self):
        record = OutWestSepticAuthorityRecord(" Example office ", " Local record A ", "2020-02-29")
        self.assertEqual(record.name, "Example office")
        self.assertEqual(record.reference, "Local record A")


class ChecklistTests(unittest.TestCase):
    @staticmethod
    def create(**kwargs):
        return OutWestSepticPermitChecklist.create(OutWestSepticPropertyContext("Palo Pinto", **kwargs))

    def test_county_only_api_leaves_authority_and_other_context_unresolved(self):
        result = OutWestSepticPermitChecklist.checklist("Palo Pinto County TX")
        self.assertIsNone(result.context.authority)
        self.assertEqual(len(result.missing_information), 7)
        self.assertEqual(result.to_dict()["authority_record_status"], "not-provided")
        self.assertIn("Palo Pinto County: Public Works", result.render())
        self.assertNotIn("Permitting office:", result.render())

    def test_only_the_seven_supported_counties_are_listed(self):
        self.assertEqual(OutWestSepticPermitChecklist.supported_counties(), (
            "Palo Pinto County TX", "Hood County TX", "Erath County TX",
            "Stephens County TX", "Young County TX", "Jack County TX", "Eastland County TX",
        ))

    def test_each_county_has_sources_but_no_automatic_authority(self):
        for county in OutWestSepticPermitChecklist.supported_counties():
            with self.subTest(county=county):
                result = OutWestSepticPermitChecklist.checklist(county)
                self.assertTrue(result.county_resource.url.startswith("https://"))
                self.assertIsNone(result.context.authority)
                source_ids = {source.id for source in result.sources}
                self.assertIn(result.county_resource.id, source_ids)
                self.assertIn("tceq-finder", source_ids)
                self.assertIn("authority", {item.id for item in result.items})

    def test_incomplete_directory_entries_do_not_claim_verified_local_offices(self):
        jack = OutWestSepticPermitChecklist.checklist("Jack")
        self.assertEqual(jack.county_resource.id, "tceq-finder")
        for county in ("Stephens", "Eastland"):
            result = OutWestSepticPermitChecklist.checklist(county)
            self.assertEqual(result.county_resource.review_status, "county-site-only")
            self.assertIn("no OSSF hub verified", result.county_resource.scope)

    def test_lake_context_adds_a_question_without_assigning_bra(self):
        for proximity in ("unknown", "yes"):
            result = self.create(near_possum_kingdom=proximity)
            self.assertIn("lake-jurisdiction", {item.id for item in result.items})
            self.assertIn("bra", {source.id for source in result.sources})
            self.assertIsNone(result.context.authority)
        no_lake = self.create(near_possum_kingdom="no")
        self.assertNotIn("lake-jurisdiction", {item.id for item in no_lake.items})
        self.assertIn("authority", {item.id for item in no_lake.items})
        self.assertIsNone(no_lake.context.authority)

    def test_existing_work_requests_records_and_new_work_does_not_invent_them(self):
        for purpose in ("replacement", "modification", "repair", "property-review"):
            with self.subTest(purpose=purpose):
                self.assertIn("existing-records", {item.id for item in self.create(project_type=purpose).items})
        self.assertNotIn("existing-records", {item.id for item in self.create(project_type="new").items})

    def test_water_supply_changes_the_information_to_gather(self):
        for supply, phrase in (
            ("private-well", "private well"), ("public", "public-water connection"),
            ("other", "Describe the water source"), ("unknown", "Identify the water source"),
        ):
            with self.subTest(supply=supply):
                action = next(item.action for item in self.create(water_supply=supply).items if item.id == "site-plan")
                self.assertIn(phrase, action)

    def test_supplied_evaluation_is_reviewed_not_treated_as_approval(self):
        result = self.create(site_evaluation_ref="Report A")
        step = next(item for item in result.items if item.id == "evaluation")
        self.assertIn("confirm", step.action)
        self.assertIn("proposed disposal area", step.action)
        self.assertFalse(any("Available evaluation" in label for label in result.missing_information))

    def test_unknown_evaluation_reference_keeps_evaluation_unresolved(self):
        authority = OutWestSepticAuthorityRecord("Example office", "Local response", "2020-01-01")
        for reference in ("unknown", " unknown "):
            with self.subTest(reference=reference):
                result = self.create(site_evaluation_ref=reference, authority=authority)
                step = next(item for item in result.items if item.id == "evaluation")
                self.assertTrue(any("Available evaluation" in label for label in result.missing_information))
                self.assertIn("Ask what evaluation is needed", step.action)
                self.assertNotIn("An evaluation reference was supplied", step.action)
                self.assertEqual(result.context.site_evaluation_ref, "unknown")
                self.assertEqual(result.context.authority, authority)
                self.assertEqual(result.to_dict()["authority_record_status"], "user-recorded-not-verified")

    def test_complete_context_never_becomes_a_verified_or_approved_result(self):
        result = self.create(
            property_ref="Example parcel", project_type="new", city_limits="outside",
            near_possum_kingdom="no", water_supply="public", site_evaluation_ref="Report A",
            authority=OutWestSepticAuthorityRecord("Example office", "Local response", "2020-01-01"),
        )
        self.assertEqual(result.missing_information, ())
        self.assertEqual(result.to_dict()["authority_record_status"], "user-recorded-not-verified")
        self.assertIn("accuracy and approval remain unverified", result.render())
        self.assertIn("authority", {item.id for item in result.items})
        self.assertNotIn("- [x]", result.render())

    def test_no_unsafe_legacy_decisions_in_result_structure_or_output(self):
        result = self.create(near_possum_kingdom="yes")
        data = result.to_dict()
        for removed in ("setbacks_ft", "office", "dr_notes", "verification"):
            self.assertNotIn(removed, data)
        for false_claim in ("50 ft", "2,000 ft", "1,000 ft contour", "TCEQ-accepted perc",
                            "OS0041298", "940.452", "installs conventional", "aerobic required"):
            self.assertNotIn(false_claim, result.render())

    def test_every_step_has_resolvable_primary_sources_and_record_prompt(self):
        result = self.create()
        sources = {source.id for source in result.sources}
        self.assertEqual(len(sources), len(result.sources))
        for step in result.items:
            self.assertTrue(step.record)
            self.assertTrue(step.source_ids)
            self.assertTrue(set(step.source_ids) <= sources)
        self.assertEqual(len({item.id for item in result.items}), len(result.items))

    def test_json_preserves_data_and_returns_independent_copies(self):
        result = self.create(property_ref="Parcel A")
        data = result.to_dict()
        self.assertEqual(json.loads(result.to_json()), json.loads(json.dumps(data)))
        data["context"]["county"] = "changed"
        data["items"][0]["action"] = "changed"
        self.assertEqual(result.context.county, "Palo Pinto County TX")
        self.assertNotEqual(result.items[0].action, "changed")
        self.assertEqual(data["schema_version"], 2)

    def test_markdown_escapes_user_markup_but_json_preserves_the_record(self):
        reference = "Parcel [A](https://example.test) <tag> *text*"
        result = self.create(property_ref=reference)
        self.assertNotIn("<tag>", result.render())
        self.assertNotIn("[A](https://example.test)", result.render())
        self.assertEqual(json.loads(result.to_json())["context"]["property_ref"], reference)

    def test_create_rejects_non_context_values(self):
        for value in (None, "Palo Pinto", {}, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                OutWestSepticPermitChecklist.create(value)


class CliTests(unittest.TestCase):
    @staticmethod
    def run_cli(*args):
        output, error = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            try:
                code = main(list(args))
            except SystemExit as exc:
                code = exc.code
        return code, output.getvalue(), error.getvalue()

    def test_cli_json_can_be_consumed_without_banner_noise(self):
        code, output, error = self.run_cli("Palo Pinto", "--project-type", "repair", "--format", "json")
        self.assertEqual(code, 0)
        self.assertEqual(error, "")
        self.assertEqual(json.loads(output)["context"]["project_type"], "repair")

    def test_cli_records_authority_only_when_all_fields_are_present(self):
        code, output, error = self.run_cli(
            "Hood", "--authority-name", "Example office", "--authority-reference", "Local letter",
            "--authority-date", "2020-01-01", "--format", "json",
        )
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(json.loads(output)["authority_record_status"], "user-recorded-not-verified")

    def test_invalid_commands_fail_without_partial_output_or_traceback(self):
        bad = [
            (), ("Nowhere",), ("Palo Pinto", "--authority-name", "Office"),
            ("Palo Pinto", "--authority-reference", "A"),
            ("Palo Pinto", "--authority-date", "2020-01-01"),
            ("Palo Pinto", "--property-ref", ""),
            ("Palo Pinto", "--project-type", "permit-approved"),
            ("--list", "Palo Pinto"), ("--list", "--authority-name", "Office"),
            ("--list", "--property-ref", ""),
        ]
        for args in bad:
            with self.subTest(args=args):
                code, output, error = self.run_cli(*args)
                self.assertEqual(code, 2)
                self.assertEqual(output, "")
                self.assertIn("error:", error)
                self.assertNotIn("Traceback", error)

    def test_json_list_is_a_clean_seven_county_list(self):
        code, output, error = self.run_cli("--list", "--format", "json")
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(json.loads(output), list(OutWestSepticPermitChecklist.supported_counties()))

    def test_entrypoint_runs_from_an_unrelated_working_directory(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "outwestseptic_permit_checklist.py"
        process = subprocess.run(
            [sys.executable, str(script), "Palo Pinto", "--format", "json"],
            cwd=script.parent, capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)["context"]["county"], "Palo Pinto County TX")


if __name__ == "__main__":
    unittest.main()
