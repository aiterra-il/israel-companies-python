from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

import israel_companies
from israel_companies import (
    CompanyLookupError,
    build_name_query,
    check_company_number,
    clean_text,
    entity_of,
    get_company,
    is_valid_israeli_id,
    search_companies,
    status_info,
    to_company,
    type_info,
)
from israel_companies import _rank_by_name, _search_url_for

FIXTURES = json.loads(Path(__file__).with_name("fixtures.json").read_text(encoding="utf-8"))
LIVE = os.environ.get("LIVE") == "1"


class ParityTest(unittest.TestCase):
    def test_numbers(self):
        self.assertGreater(len(FIXTURES["numbers"]), 200)
        for case in FIXTURES["numbers"]:
            value = case["value"]
            self.assertEqual(is_valid_israeli_id(value), case["valid_id"], repr(value))
            self.assertEqual(entity_of(value), case["entity"], repr(value))
            self.assertEqual(check_company_number(value), case["check"], repr(value))

    def test_clean_text(self):
        for value, expected in FIXTURES["clean_text"]:
            self.assertEqual(clean_text(value), expected, repr(value))

    def test_catalogs(self):
        for status, expected in FIXTURES["status_info"]:
            self.assertEqual(status_info(status), expected)
        for type_name, expected in FIXTURES["type_info"]:
            self.assertEqual(type_info(type_name), expected)

    def test_name_query(self):
        for name, expected in FIXTURES["name_query"]:
            self.assertEqual(build_name_query(name), expected, repr(name))

    def test_records_become_companies(self):
        self.assertGreater(len(FIXTURES["companies"]), 200)
        for case in FIXTURES["companies"]:
            self.assertEqual(to_company(case["record"]), case["company"], case["record"])

    def test_search_url_and_ranking(self):
        for search, url in zip(FIXTURES["searches"], FIXTURES["search_urls"]):
            self.assertEqual(_search_url_for(search["name"], search["limit"]), url)
            companies = [to_company(record) for record in search["records"]]
            ranked = _rank_by_name(companies, search["name"])[: search["limit"]]
            self.assertEqual([company["number"] for company in ranked], search["result"], search["name"])

    def test_ranking_of_generated_names(self):
        pool = [record for search in FIXTURES["searches"] for record in search["records"]]
        self.assertGreater(len(FIXTURES["rankings"]), 200)
        for case in FIXTURES["rankings"]:
            self.assertEqual(_search_url_for(case["name"], case["limit"]), case["url"], case["name"])
            if case["url"] is None:
                self.assertEqual(case["result"], [])
                continue
            companies = [to_company(pool[index]) for index in case["indices"]]
            ranked = _rank_by_name(companies, case["name"])[: case["limit"]]
            self.assertEqual([company["number"] for company in ranked], case["result"], case["name"])


class PackageTest(unittest.TestCase):
    def test_invalid_number_is_rejected_before_the_network(self):
        with self.assertRaises(CompanyLookupError) as raised:
            get_company("123")
        self.assertEqual(raised.exception.code, "invalid-number")

    def test_package_is_typed_and_versioned(self):
        self.assertTrue(Path(israel_companies.__file__).with_name("py.typed").exists())
        self.assertRegex(israel_companies.__version__, r"^\d+\.\d+\.\d+$")


@unittest.skipUnless(LIVE, "set LIVE=1 to call data.gov.il")
class LiveTest(unittest.TestCase):
    def test_company_by_number(self):
        company = get_company("520025636")
        self.assertEqual(company["number"], "520025636")

    def test_search_by_name(self):
        self.assertTrue(search_companies("טבע", limit=5))


if __name__ == "__main__":
    unittest.main()
