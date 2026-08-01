#!/usr/bin/env python3
"""Unit tests for the layout physical-verification harness.

No PDK and no KLayout required -- these exercise only the two pure
functions in ``layout/harness/drc.py`` that do not touch a subprocess or a
foundry deck: ``parse_report_db`` (XML ``.lyrdb`` parsing) and
``rules_from_log`` (regex extraction over free text).

    python3 -m unittest discover -s layout/tests -t layout/tests -v
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

LAYOUT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAYOUT_DIR))

from harness import drc  # noqa: E402


class ParseReportDbTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def _write(self, name: str, xml: str) -> Path:
        path = self.dir / name
        path.write_text(xml)
        return path

    def test_clean_report_with_no_items_yields_zero_violations(self):
        path = self._write(
            "clean.lyrdb",
            """<?xml version="1.0" encoding="utf-8"?>
<report-database>
  <categories/>
  <items/>
</report-database>
""",
        )
        self.assertEqual(drc.parse_report_db(path), (0, {}))

    def test_multi_category_multi_count_report_is_tallied_per_rule(self):
        path = self._write(
            "dirty.lyrdb",
            """<?xml version="1.0" encoding="utf-8"?>
<report-database>
  <categories>
    <category><name>'poly.1'</name></category>
    <category><name>'metal1.2'</name></category>
  </categories>
  <items>
    <item>
      <category>'poly.1'</category>
      <cell>TOP</cell>
      <multiplicity>3</multiplicity>
    </item>
    <item>
      <category>'poly.1'</category>
      <cell>TOP</cell>
      <multiplicity>2</multiplicity>
    </item>
    <item>
      <category>'metal1.2'</category>
      <cell>TOP</cell>
      <multiplicity>1</multiplicity>
    </item>
  </items>
</report-database>
""",
        )
        count, rule_counts = drc.parse_report_db(path)
        self.assertEqual(count, 6)
        self.assertEqual(rule_counts, {"poly.1": 5, "metal1.2": 1})

    def test_malformed_multiplicity_falls_back_to_one(self):
        path = self._write(
            "malformed.lyrdb",
            """<?xml version="1.0" encoding="utf-8"?>
<report-database>
  <items>
    <item>
      <category>'poly.1'</category>
      <multiplicity>not_an_int</multiplicity>
    </item>
  </items>
</report-database>
""",
        )
        self.assertEqual(drc.parse_report_db(path), (1, {"poly.1": 1}))

    def test_item_without_a_multiplicity_field_defaults_to_one(self):
        path = self._write(
            "no-multiplicity.lyrdb",
            """<?xml version="1.0" encoding="utf-8"?>
<report-database>
  <items>
    <item>
      <category>'poly.1'</category>
    </item>
  </items>
</report-database>
""",
        )
        self.assertEqual(drc.parse_report_db(path), (1, {"poly.1": 1}))

    def test_missing_file_returns_empty_result_without_raising(self):
        missing = self.dir / "does-not-exist.lyrdb"
        self.assertEqual(drc.parse_report_db(missing), (0, {}))


class RulesFromLogTests(unittest.TestCase):
    def test_single_rule_name_is_extracted(self):
        log = "Some preamble\nViolated rules are : {'poly.1'}\nSome trailer\n"
        self.assertEqual(drc.rules_from_log(log), ["poly.1"])

    def test_multiple_rule_names_are_extracted_and_sorted(self):
        log = "Violated rules are : {'metal1.2','poly.1', 'nwell.3'}\n"
        self.assertEqual(drc.rules_from_log(log), ["metal1.2", "nwell.3", "poly.1"])

    def test_no_marker_in_log_returns_empty_list(self):
        log = "Klayout DRC run is clean\nno violated-rules marker here\n"
        self.assertEqual(drc.rules_from_log(log), [])


if __name__ == "__main__":
    unittest.main()
