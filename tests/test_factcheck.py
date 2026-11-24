"""Unit tests for the FactCheckConsensus contract's pure logic and flows.

Runs WITHOUT a chain: the tests import the real ``contract.py`` against
the ``genlayer_stub`` fake package (see genlayer_stub.py), so the code
under test is the code that will be deployed — not a copy of it.

Run:  python3 -m unittest discover -s tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import genlayer_stub  # noqa: F401  (installs the fake genlayer module)
from genlayer import gl
import contract

SENDER = "0x1111111111111111111111111111111111111111"
CLAIM = "GenLayer launched mainnet in Q4 2026."
URL = "https://example.com/news"
PAGE = (
    "GenLayer launched its mainnet in Q4 2026 according to the official "
    "announcement published today on the project website."
)


class TestNormalizeVerdict(unittest.TestCase):
    def test_bare_tokens(self):
        self.assertEqual(contract._normalize_verdict("TRUE"), "TRUE")
        self.assertEqual(contract._normalize_verdict("false"), "FALSE")
        self.assertEqual(contract._normalize_verdict("Unverifiable"), "UNVERIFIABLE")

    def test_verdict_inside_a_sentence(self):
        self.assertEqual(
            contract._normalize_verdict("The answer is TRUE."), "TRUE"
        )
        self.assertEqual(
            contract._normalize_verdict(
                "I find this UNVERIFIABLE given the source."
            ),
            "UNVERIFIABLE",
        )

    def test_first_match_wins(self):
        self.assertEqual(
            contract._normalize_verdict("TRUE, not FALSE"), "TRUE"
        )
        self.assertEqual(
            contract._normalize_verdict("FALSE - the claim is not TRUE"),
            "FALSE",
        )

    def test_unparseable_becomes_unverifiable(self):
        self.assertEqual(contract._normalize_verdict("UNKNOWN"), "UNVERIFIABLE")
        self.assertEqual(contract._normalize_verdict(""), "UNVERIFIABLE")
        self.assertEqual(contract._normalize_verdict(None), "UNVERIFIABLE")
        self.assertEqual(contract._normalize_verdict(42), "UNVERIFIABLE")

    def test_no_partial_word_matches(self):
        # A substring scan would misread both of these; word boundaries must not.
        self.assertEqual(contract._normalize_verdict("UNTRUE"), "UNVERIFIABLE")
        self.assertEqual(
            contract._normalize_verdict("FALSEHOOD"), "UNVERIFIABLE"
        )


class TestFilterEvidence(unittest.TestCase):
    def test_keeps_only_matching_lines(self):
        page = (
            "The quick brown fox jumps over the lazy dog today.\n"
            "Water is wet and the sky is blue over the hills.\n"
            "GenLayer launched mainnet in Q4 2026 today.\n"
        )
        out = contract._filter_evidence(page, "GenLayer mainnet launch date")
        self.assertIn("GenLayer launched mainnet", out)
        self.assertNotIn("quick brown fox", out)
        self.assertNotIn("Water is wet", out)

    def test_falls_back_to_page_prefix_when_nothing_matches(self):
        page = "x" * 5000
        out = contract._filter_evidence(page, "something entirely different")
        self.assertEqual(out, page[: contract.MAX_EVIDENCE_CHARS])

    def test_caps_the_number_of_lines(self):
        page = "\n".join(
            f"GenLayer line number {i} with enough words here" for i in range(200)
        )
        out = contract._filter_evidence(page, "GenLayer")
        self.assertLessEqual(len(out.splitlines()), 60)


class TestValidateClaim(unittest.TestCase):
    def test_valid_input_is_trimmed_and_returned(self):
        text, url = contract._validate_claim("  " + CLAIM + "  ", URL)
        self.assertEqual(text, CLAIM)
        self.assertEqual(url, URL)

    def test_too_short_claim(self):
        with self.assertRaises(ValueError):
            contract._validate_claim("Too short", URL)

    def test_too_long_claim(self):
        with self.assertRaises(ValueError):
            contract._validate_claim("x" * 1001, URL)

    def test_non_http_url(self):
        with self.assertRaises(ValueError):
            contract._validate_claim(CLAIM, "ftp://example.com/news")

    def test_url_too_long(self):
        with self.assertRaises(ValueError):
            contract._validate_claim(CLAIM, "https://example.com/" + "a" * 2000)


class TestContractFlow(unittest.TestCase):
    def setUp(self):
        # Real __init__ plus explicit storage, simulating GenVM's
        # zero-initialized persistent collections.
        self.c = contract.FactCheckConsensus()
        self.c.c_submitter = {}
        self.c.c_text = {}
        self.c.c_source = {}
        self.c.c_status = {}
        self.c.c_verdict = {}
        self.c.c_reason = {}
        self.c.c_created_at = {}
        self.c.claim_order = []
        gl.message.sender_address = SENDER
        gl.nondet.web.render_result = PAGE
        gl.nondet.prompt_result = "TRUE"

    def test_submit_and_read(self):
        claim_id = self.c.submit_claim(CLAIM, URL)
        self.assertEqual(claim_id, "claim-1")
        rec = self.c.get_claim(claim_id)
        self.assertTrue(rec["exists"])
        self.assertEqual(rec["status"], "OPEN")
        self.assertEqual(rec["verdict"], "")
        self.assertEqual(rec["reason"], "")
        self.assertEqual(rec["claim"], CLAIM)
        self.assertEqual(rec["source_url"], URL)
        self.assertEqual(rec["submitter"], SENDER)
        self.assertEqual(self.c.get_claim("claim-999"), {"exists": False})

    def test_submit_rejects_bad_input_with_user_error(self):
        with self.assertRaises(gl.vm.UserError):
            self.c.submit_claim("short", URL)
        with self.assertRaises(gl.vm.UserError):
            self.c.submit_claim(CLAIM, "ftp://example.com")

    def test_submit_increments_ids(self):
        first = self.c.submit_claim(CLAIM, URL)
        second = self.c.submit_claim("Another claim about GenLayer here.", URL)
        self.assertEqual((first, second), ("claim-1", "claim-2"))

    def test_list_claims_paginates(self):
        for i in range(3):
            self.c.submit_claim(f"Claim number {i} about GenLayer news.", URL)
        page = self.c.list_claims(contract.u256(0), contract.u256(2))
        self.assertEqual(page["total"], 3)
        self.assertEqual(len(page["claims"]), 2)
        self.assertEqual(page["claims"][0]["claim_id"], "claim-1")
        page2 = self.c.list_claims(contract.u256(2), contract.u256(2))
        self.assertEqual(len(page2["claims"]), 1)
        self.assertEqual(page2["claims"][0]["claim_id"], "claim-3")
        empty = self.c.list_claims(contract.u256(10), contract.u256(5))
        self.assertEqual(empty["claims"], [])

    def test_resolve_records_consensus_verdict_and_reason(self):
        claim_id = self.c.submit_claim(CLAIM, URL)
        # Script the two LLM calls: verdict first, reason second.
        gl.nondet.prompt_result = [
            "TRUE",
            "The source states the launch plainly.",
        ]
        verdict = self.c.resolve_claim(claim_id)
        self.assertEqual(verdict, "TRUE")
        rec = self.c.get_claim(claim_id)
        self.assertEqual(rec["status"], "RESOLVED")
        self.assertEqual(rec["verdict"], "TRUE")
        self.assertIn("launch", rec["reason"])

    def test_resolve_false_verdict(self):
        claim_id = self.c.submit_claim(CLAIM, URL)
        gl.nondet.prompt_result = ["FALSE", "The source contradicts it."]
        self.assertEqual(self.c.resolve_claim(claim_id), "FALSE")
        self.assertEqual(self.c.get_claim(claim_id)["verdict"], "FALSE")

    def test_resolve_unverifiable_stays_open(self):
        claim_id = self.c.submit_claim(CLAIM, URL)
        gl.nondet.prompt_result = ["UNVERIFIABLE", "No reason."]
        with self.assertRaises(gl.vm.UserError):
            self.c.resolve_claim(claim_id)
        rec = self.c.get_claim(claim_id)
        self.assertEqual(rec["status"], "OPEN")
        self.assertEqual(rec["verdict"], "")

    def test_resolve_missing_or_already_resolved_raises(self):
        with self.assertRaises(gl.vm.UserError):
            self.c.resolve_claim("claim-999")
        claim_id = self.c.submit_claim(CLAIM, URL)
        gl.nondet.prompt_result = ["FALSE", "The source contradicts it."]
        self.c.resolve_claim(claim_id)
        with self.assertRaises(gl.vm.UserError):
            self.c.resolve_claim(claim_id)

    def test_reason_failure_does_not_block_the_verdict(self):
        claim_id = self.c.submit_claim(CLAIM, URL)

        calls = {"n": 0}

        def flaky_prompt(prompt, response_format=None):
            calls["n"] += 1
            if calls["n"] == 1:
                return "TRUE"
            raise RuntimeError("LLM unavailable")

        gl.nondet.exec_prompt = flaky_prompt
        try:
            verdict = self.c.resolve_claim(claim_id)
        finally:
            # Restore the stub method for other tests.
            del gl.nondet.exec_prompt
        self.assertEqual(verdict, "TRUE")
        rec = self.c.get_claim(claim_id)
        self.assertEqual(rec["status"], "RESOLVED")
        self.assertEqual(rec["reason"], "No reason recorded.")


if __name__ == "__main__":
    unittest.main()
