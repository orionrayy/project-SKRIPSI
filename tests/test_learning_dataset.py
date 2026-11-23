"""Structural and provenance guards for the public learning dataset."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/learning/academic-background-seven-stage-video-001.json"
SCHEMA = ROOT / "schemas/learning/academic-background-sequence.schema.json"


class AcademicBackgroundLearningDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = json.loads(DATA.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    def test_record_and_schema_are_valid_json(self) -> None:
        self.assertEqual(self.schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(self.record["$schema"], "../../schemas/learning/academic-background-sequence.schema.json")

    def test_exactly_seven_ordered_argument_functions(self) -> None:
        stages = self.record["stages"]
        self.assertEqual(len(stages), 7)
        self.assertEqual([s["ordinal"] for s in stages], list(range(1, 8)))
        self.assertEqual(len({s["stage_id"] for s in stages}), 7)
        self.assertEqual(len({s["function"] for s in stages}), 7)

    def test_stage_windows_are_monotonic_and_within_media_duration(self) -> None:
        duration = self.record["source"]["duration_seconds"]
        previous_end = -1
        for stage in self.record["stages"]:
            window = stage["time_window_seconds"]
            self.assertLessEqual(window["start"], window["end"])
            self.assertGreaterEqual(window["start"], previous_end)
            self.assertLessEqual(window["end"], duration)
            previous_end = window["end"]

    def test_caption_anchors_are_not_misrepresented_as_transcript(self) -> None:
        self.assertFalse(self.record["source"]["audio_stream"]["independent_transcription"])
        self.assertIn("not an independently verified verbatim transcript", self.record["annotation_method"]["caption_status"])
        for stage in self.record["stages"]:
            self.assertTrue(stage["caption_evidence"])
            self.assertTrue(all(a["status"] == "burned_in_caption_fragment" for a in stage["caption_evidence"]))

    def test_publication_boundary_excludes_raw_media(self) -> None:
        distribution = self.record["source"]["public_distribution"]
        self.assertIs(distribution["raw_media_in_repository"], False)
        self.assertIs(distribution["source_rights_verified"], False)

    def test_flexibility_and_phase_boundary_are_explicit(self) -> None:
        governance = self.record["flexibility_and_governance"]
        self.assertIs(governance["not_a_mandatory_template"], True)
        self.assertIn("does not change P0-P9", governance["no_phase_effect"])

    def test_failure_taxonomy_references_only_valid_stages(self) -> None:
        stage_ids = {s["stage_id"] for s in self.record["stages"]}
        failures = self.record["failure_taxonomy"]
        self.assertEqual(len(failures), 20)
        self.assertEqual(len({f["failure_id"] for f in failures}), 20)
        self.assertTrue(all(f["stage"] in stage_ids for f in failures))

    def test_every_stage_has_evidence_and_quality_gate(self) -> None:
        for stage in self.record["stages"]:
            self.assertTrue(stage["evidence_requirements"])
            self.assertTrue(stage["quality_gate"].strip())
            self.assertTrue(stage["failure_modes"])


if __name__ == "__main__":
    unittest.main()
