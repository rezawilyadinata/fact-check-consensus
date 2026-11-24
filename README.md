# FactCheckConsensus — a GenLayer Intelligent Contract

A standalone, reusable **fact-checking primitive**: anyone submits a factual
claim plus a source URL, the GenLayer validator network independently
verifies the claim against that source, and the consensus verdict
(TRUE / FALSE / UNVERIFIABLE) is recorded on-chain.

Other contracts and apps can build on it — dispute resolution, content
moderation queues, prediction-market settlement, or any flow that needs a
trust-minimized "is this claim true?" answer — without re-implementing the
fetch → judge → consensus pipeline.

This builds on the "Validating LLM Outputs" documentation pattern: the
compared field is a single verdict token, and free-text reasons are never
part of what validators must agree on.

## Files

| File | What it is |
|---|---|
| `contract.py` | The contract. Single file, pinned runner (see below). |
| `tests/test_factcheck.py` | 22 unit tests, stdlib only, run without a chain. |
| `tests/genlayer_stub.py` | Minimal fake `genlayer` package the tests run against. |
| `BUILD-REPORT.md` | What was verified, what still needs live Studio testing. |

## How consensus works

```
submit_claim("GenLayer launched mainnet in Q4 2026.",
             "https://example.com/news")
  -> claim-1, status OPEN

resolve_claim("claim-1")
  -> leader fetches the source, filters it to the lines that mention the
     claim's key terms, and asks an LLM for exactly one word:
     TRUE / FALSE / UNVERIFIABLE
  -> every validator independently re-runs the same check on its own
     fetch and compares its verdict with the leader's
     (gl.eq_principle.prompt_comparative)
  -> agreement on TRUE or FALSE  -> status RESOLVED, verdict on-chain
  -> agreement on UNVERIFIABLE  -> claim stays OPEN, retry later
```

**What is compared:** the verdict token only. Two validators will word the
same conclusion differently, so free-text reasons are never part of the
compared fields — comparing prose would starve consensus. A one-sentence
reason is recorded alongside the verdict via
`gl.eq_principle.prompt_non_comparative`, which reconciles the leader's
prose instead of demanding exact agreement. The reason is informational;
the verdict is the authoritative on-chain outcome.

**Why the evidence is filtered:** validators each fetch the source
themselves, and a raw slice of a large, frequently-edited page differs
between fetches. Filtering to lines that mention the claim's key terms
makes the judged input stable across validators, which is what lets the
equivalence principle agree. (Same technique as the reference AgentPact
contract.)

**Why verdict parsing is word-boundary based:** a naive substring scan
misreads "UNKNOWN" as containing "NO" and "UNTRUE" as containing "TRUE".
Anything unparseable becomes UNVERIFIABLE, which leaves the claim OPEN
instead of recording a verdict nobody actually reached.

## Public methods

| Method | Type | Purpose |
|---|---|---|
| `submit_claim(claim_text, source_url)` | write | Store a claim. Returns `claim-1`, `claim-2`, … Claim 10–1000 chars, URL must be http(s), max 2000 chars. Deterministic — no AI involved. |
| `resolve_claim(claim_id)` | write | Verify through consensus. Returns `TRUE` or `FALSE`. Raises (claim stays OPEN) when the source does not settle it. Anyone may call it. |
| `get_claim(claim_id)` | view | Full record as a JSON dict (`exists: false` when unknown). |
| `list_claims(offset, limit)` | view | Paginated list (limit clamped to 50) with total count. |

The contract holds no funds and has no payable methods.

## Deploy / test with GenLayer Studio

GenLayer Studio is the local 5-validator simulator (needs Docker). Exact
commands live in the official docs — https://docs.genlayer.com — because
the Studio CLI changes between releases; the flow is:

1. Open GenLayer Studio and create a new Intelligent Contract.
2. Paste the contents of `contract.py` (first line pins the runner — do
   not remove or change it).
3. Deploy to the local simulator.
4. Call `submit_claim` with a real claim + a public source URL.
5. Call `resolve_claim` and confirm the verdict lands as `RESOLVED`
   with a reason in `get_claim`.
6. Try the edge cases: a claim the source contradicts (expect FALSE),
   a claim the source does not cover (expect the call to fail and the
   claim to stay OPEN), and a second `resolve_claim` on a resolved claim
   (expect an error).

## Run the unit tests (no chain needed)

```bash
python3 -m unittest discover -s tests -v
```

22 tests, stdlib only. They import the real `contract.py` against a fake
`genlayer` package (`tests/genlayer_stub.py`), so the code under test is
the code that will be deployed. Covered: verdict normalization (including
the UNKNOWN/UNTRUE traps), evidence filtering and its cap, input
validation, submit/get/list flows, the full resolve flow (TRUE, FALSE,
UNVERIFIABLE-stays-open), double-resolve guards, and the guarantee that a
failed reason call never blocks the verdict.

## What was verified here

- Runner hash `py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6`
  is the hash used by live example contracts on the GenLayer Studio
  Explorer (AgentPact, ReleaseCovenant, Goalpost, ProofBid, Undo402) and by
  the Periscale "Write Contract" skill. See BUILD-REPORT.md for sources.
- API patterns verified against those deployed contracts:
  `from genlayer import *`, `gl.Contract`, `@gl.public.write` /
  `@gl.public.view`, `gl.nondet.web.render`, `gl.nondet.exec_prompt`,
  `gl.eq_principle.prompt_comparative`, `gl.vm.UserError`,
  `gl.message.sender_address`, zero-initialized `TreeMap`/`DynArray`.
- `python3 -m py_compile contract.py` — clean.
- `python3 -m unittest discover -s tests -v` — 22 passed, 0 failed.

## Known limits (see BUILD-REPORT.md)

- **Not yet tested on GenLayer Studio.** Docker is not available in the
  build environment, so the multi-validator consensus path has only been
  exercised through the stub (which simulates agreement). Live Studio
  testing is required before mainnet use.
- The `prompt_non_comparative` call signature is inferred from its
  comparative twin and from the AgentPact contract's comment; confirm it
  in Studio.
