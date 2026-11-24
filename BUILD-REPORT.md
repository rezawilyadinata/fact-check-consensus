# Build report — FactCheckConsensus

Date: 24 Nov 2026. Built by Muse (subagent) at the user's approval
("Gas, bangun kontraknya"). Local repo only — nothing submitted anywhere,
no GitHub repo created.

## What was built

`~/workspace/genlayer-fact-check-consensus/`

| File | Size | Purpose |
|---|---|---|
| `contract.py` | ~14.7 KB | FactCheckConsensus contract (single file, pinned runner). |
| `README.md` | ~6.2 KB | Purpose, consensus design, Studio deploy steps, test instructions. |
| `tests/test_factcheck.py` | ~9.2 KB | 22 unit tests, stdlib `unittest` only. |
| `tests/genlayer_stub.py` | ~3.2 KB | Fake `genlayer` package so the real contract runs without a chain. |

Contract surface: `submit_claim(claim_text, source_url) -> claim id`,
`resolve_claim(claim_id) -> TRUE | FALSE`, `get_claim(claim_id) -> dict`,
`list_claims(offset, limit) -> dict`. No funds held, no payable methods.

Consensus design: `gl.eq_principle.prompt_comparative` over a bare
verdict token (TRUE / FALSE / UNVERIFIABLE); the verdict is the only
compared field. A one-sentence reason is recorded via
`gl.eq_principle.prompt_non_comparative` (prose, never compared).
Evidence is filtered to claim-relevant lines before judging, so the
judged input is stable across validators. Verdict parsing is
word-boundary based (a substring scan misreads "UNKNOWN" as "NO").

## Runner hash — REAL, not a placeholder

`py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6`

Verified from multiple independent live sources, all using the identical
hash (fetched 24 Nov 2026):

- Periscale "Write Contract" skill — https://periscale.ai/skills/write-contract-internet-court
  (explicitly: "Always pins concrete GenVM runner version hashes", same hash
  in the skeleton and the runner-dependency section).
- GenLayer Studio Explorer contracts (fetched in full):
  - AgentPact (prediction market) — https://explorer-studio.genlayer.com/tx/0x619e74679f0acfa799ac0f9b1f555e52169d96bbd628f46b5ed66b756cde3be4
  - ReleaseCovenant — https://explorer-studio.genlayer.com/tx/0xd586a13d9d6c9826e69642c3da30879db2f3cc46516c157aa6c31af5b98bf3c9
  - Goalpost, ProofBid, Undo402 — same hash in search-result excerpts
    (tx 0x9b933e…, 0x489042…, 0x21451c…).

Caveat: the hash is current as of the fetched pages (crawled 22–23 Nov
2026). If GenLayer ships a newer runner before the user submits, the
portal/Studio will say so at deploy time — the first line is the only
place that would need updating.

## Verification performed (commands + results)

```
$ python3 -m py_compile contract.py tests/test_factcheck.py tests/genlayer_stub.py
PY_COMPILE OK

$ python3 -m unittest discover -s tests -v
Ran 22 tests in 0.001s — OK (22 passed, 0 failed)
```

Test coverage: verdict normalization (bare tokens, verdict inside a
sentence, first-match-wins, unparseable → UNVERIFIABLE, the
UNKNOWN/UNTRUE/FALSEHOOD partial-word traps), evidence filtering
(matching lines only, prefix fallback, 60-line cap), input validation
(claim too short/long, non-http URL, URL too long), submit/get/list
flows (ids increment, pagination, unknown claim), and the full resolve
flow with the stub simulating validator agreement (TRUE and FALSE
recorded with a reason; UNVERIFIABLE leaves the claim OPEN; resolving a
missing or already-resolved claim raises; a failed reason call never
blocks the verdict).

API patterns were verified against the two fully-fetched reference
contracts (AgentPact, ReleaseCovenant): `from genlayer import *`,
`class X(gl.Contract)`, typed storage fields (`TreeMap`, `DynArray`,
`u256`/`u32`/`u64`, `Address`), `@gl.public.write` / `@gl.public.view`,
`gl.nondet.web.render(url, mode="text")`, `gl.nondet.web.get(url)`
(`.status` / `.body`), `gl.nondet.exec_prompt(prompt,
response_format="json")`, `gl.eq_principle.prompt_comparative(fn,
prompt)`, `gl.vm.run_nondet_unsafe(leader_fn, validate)` with the
`gl.vm.Return` / `calldata` check, `gl.vm.UserError`,
`gl.message.sender_address`, `datetime.now(timezone.utc)` pinned to the
transaction timestamp, and zero-initialized storage collections (explicit
`DynArray`/`TreeMap` construction is unsupported by the pinned runner).

## What still needs live GenLayer Studio testing

Docker is NOT installed on this VM, so the multi-validator consensus path
was exercised only through the stub (which simulates agreement). Before
mainnet use, in GenLayer Studio (local 5-validator simulator):

1. Deploy `contract.py` as-is and confirm the pinned runner is accepted.
2. `submit_claim` + `resolve_claim` on a real public source URL; confirm
   the verdict lands as RESOLVED with a reason in `get_claim`.
3. Contradicted claim → FALSE; uncovered claim → call fails, claim stays
   OPEN; second `resolve_claim` on a resolved claim → error.
4. Confirm the `prompt_non_comparative` reason call works as written
   (see flag below).

## Flags a reviewer might raise

1. **`prompt_non_comparative` signature is inferred, not doc-verified.**
   Its use mirrors `prompt_comparative(leader_fn, prompt)`, and the
   semantics ("pipes the leader's output through a second LLM template,
   so the return is prose") come from a comment in the deployed AgentPact
   contract. The official docs page (docs.genlayer.com) failed to fetch
   during research, so this one call needs a Studio confirmation. If the
   signature differs, only the reason step is affected — the verdict path
   is unaffected, and a reason failure falls back to "No reason recorded."
   without blocking the verdict.
2. **Not tested on Studio / mainnet.** See the section above. The
   consensus behavior under real validator disagreement (e.g. what
   `prompt_comparative` returns when validators split) is the framework's
   behavior, not something this repo can prove locally.
3. **Source pages change.** A claim resolved today may not match the same
   URL next month; the recorded verdict is a point-in-time judgment
   (the `created_at` timestamp is stored with each claim). Re-resolution
   of an already-resolved claim is rejected by design — if re-checking
   matters, submit the claim again as a new claim id.
4. **LLM verdict quality is prompt- and model-dependent.** The prompt
   constrains the model to one word and the evidence is pre-filtered, but
   no prompt can guarantee correctness; the verdict is the network's
   consensus judgment, not ground truth.
