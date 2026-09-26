# Correction Log

This log records every place where AI-generated work, from Claude Code or Claude Chat, was wrong, incomplete, or overconfident, and how the error was caught. The value of AI-assisted analysis depends on the verification around it, and that verification should be visible. A human reviews and owns every decision recorded here.

Each entry is added in the same commit as its fix.

## Entry format

**YYYY-MM-DD · Phase · short title**
- **Origin:** Claude Code or Claude Chat
- **What was produced:** what was generated
- **What was wrong:** the specific error
- **How it was caught:** the test, check, gate, or human review that found it
- **Fix:** what changed, with the commit SHA
- **Guard added:** the new test or rule that prevents recurrence, if any

## Entries

All fixes below ship in the Sprint 0 evidence commit that adds this log's entries ("Sprint 0: ingest, structural profile, tests, evidence"). None reached a committed file before being fixed.

**2026-09-24 · Sprint 0 Step 5 · DuckDB memory limit set without regard to available RAM**
- **Origin:** Claude Code
- **What was produced:** `connect()` in `funnel/ingest.py` set DuckDB `memory_limit = '8GB'`.
- **What was wrong:** the limit was chosen without accounting for available RAM. The machine has 15.78 GB in total, with about 3.8 GB free while other applications ran. The first `python -m funnel.profile` run was killed under system memory pressure before it wrote any output.
- **How it was caught:** Claude Code's harness stopped the background run for low system memory; the human reviewed the report and set new limits.
- **Fix:** `memory_limit = '4GB'`, `threads = 4`, `preserve_insertion_order = false`, spill to `data/duckdb_tmp`. The heavy checks (duplicates, sessions, ordering anomalies) now run as separate sequential queries. Grouped `count(DISTINCT ...)` was replaced by a `SELECT DISTINCT` subquery for non-identical duplicate groups, and by `min(user_id) <> max(user_id)` for multi-user sessions. Spill files from the killed run were deleted by literal path.
- **Guard added:** `connect()` takes its limit from a documented fixed constant, `DUCKDB_MEMORY_LIMIT` in `funnel/common.py`, not from a share of total RAM. `funnel.profile` reports free RAM before it runs and records free RAM, elapsed time, and peak spill size in `ai-workflow/evidence/sprint-0/profile_run.json`.

**2026-09-24 · Sprint 0 Step 5 · Exact-duplicate check grouped everything into one group**
- **Origin:** Claude Code
- **What was produced:** the exact-duplicate query in `funnel/profile.py` used `GROUP BY ALL` with a select list of aggregates only.
- **What was wrong:** with no non-aggregate columns, `GROUP BY ALL` forms a single group, so the whole table would have counted as one duplicate group.
- **How it was caught:** Claude Code's self-review before the first run.
- **Fix:** the query groups by the explicit column list.
- **Guard added:** `test_duplicates` asserts exact counts (1 surplus row in 1 group) on the synthetic log.

**2026-09-24 · Sprint 0 Step 5 · Profile key tripped the metric-lock guard**
- **Origin:** Claude Code
- **What was produced:** the key `events_per_session_quantiles` for an overall distribution of events per session.
- **What was wrong:** the guard treats `per_session` as a grouping, by design. The profile would have halted on its own output, and the key name also suggested a breakdown that does not exist.
- **How it was caught:** Claude Code's self-review while writing the guard.
- **Fix:** renamed to `events_in_session_quantiles`.
- **Guard added:** `test_synthetic_profile_passes` and `test_committed_profile_json_passes`.

**2026-09-24 · Sprint 0 Step 6 · Hash-gate path bound at definition time**
- **Origin:** Claude Code
- **What was produced:** `recorded_dataset_sha256(data_source_md: Path = DATA_SOURCE_MD)`.
- **What was wrong:** the default was bound when the function was defined, so the hash-gate test's substitute file would have been ignored and the test would have exercised the real `docs/data-source.md`.
- **How it was caught:** Claude Code's self-review while writing `test_hash_gate_halts_on_mismatch`.
- **Fix:** the path resolves at call time.
- **Guard added:** `test_hash_gate_halts_on_mismatch` covers both the mismatch halt and the matching pass.

**2026-09-24 · Sprint 0 Step 6 · Synthetic fixture assumed a time-zone-aware timestamp**
- **Origin:** Claude Code
- **What was produced:** the synthetic event log declared `event_time TIMESTAMP WITH TIME ZONE`.
- **What was wrong:** DuckDB infers the real file's `event_time` as plain `TIMESTAMP`. Every raw value ends in " UTC", and the stored values keep UTC clock time: a raw-text round trip changed no rows (row count in `docs/data-source.md`). The tests would have exercised a different type from production.
- **How it was caught:** the generated column types in `docs/data-source.md` after ingest.
- **Fix:** the fixture uses `TIMESTAMP`, and `test_time` asserts that type.
- **Guard added:** `test_time` asserts `event_time_type == "TIMESTAMP"`.

**2026-09-24 · Sprint 0 Step 5 · Command relied on the working directory**
- **Origin:** Claude Code
- **What was produced:** a profile command with a relative path (`analysis/.venv/Scripts/python.exe`), in breach of the absolute-paths rule in CLAUDE.md.
- **What was wrong:** the shell's working directory had changed, so the command failed with "No such file or directory". Nothing ran.
- **How it was caught:** the shell error.
- **Fix:** the command was rerun with absolute paths, and all later commands use them.
- **Guard added:** none beyond the existing CLAUDE.md rule.

**2026-09-24 · Sprint 1 Step 0 · Generated wording used terms the metric contract prohibits**
- **Origin:** Claude Code
- **What was produced:** Sprint 0 generated text. The D9 option in `funnel/profile.py` read "a separate abandonment signal", the D3 option read "the cart event for carts", and a row label in `funnel/verification.py` read "Carts with no view at or before in the session".
- **What was wrong:** `docs/metrics.md` Section 1 prohibits "abandonment" and the use of "carts" as a count label. The texts predate the contract, but the D9 option already described customer behavior as abandonment.
- **How it was caught:** Claude Code's review of existing outputs against `docs/metrics.md` Section 1 at the start of Sprint 1.
- **Fix:** the texts now read "a separate cart-removal signal", "on the cart event for cart events", and "Cart events with no view at or before in the session". The regenerated `docs/data-profile.md` and `profile.json` carry the new wording.
- **Guard added:** `analysis/tests/test_naming_rules.py` (Sprint 1 Step 2).

**2026-09-24 · Sprint 1 Step 0 · 4 GB DuckDB limit still left too little headroom; RAM gate measured the wrong quantity**
- **Origin:** Claude Code
- **What was produced:** the Sprint 0 fix set `DUCKDB_MEMORY_LIMIT = "4GB"`, and the pre-run report read free physical memory.
- **What was wrong:** on this machine, 4 GB still left too little headroom. Memory stood near or below the 3 GB level that the project owner set as the minimum for a heavy run, so a 4 GB DuckDB ceiling could exceed what was actually available. The pre-run report also measured free physical memory, which excludes standby pages the OS can hand out at once, rather than available memory.
- **How it was caught:** human review of the Sprint 1 preflight report.
- **Fix:** `DUCKDB_MEMORY_LIMIT = "2GB"` (the reason is documented in `funnel/common.py`), with the same value in the dbt profile. Threads stay at 4, insertion order stays off, and queries spill to `data/duckdb_tmp`. The gate now reads `\Memory\Available MBytes`.
- **Guard added:** `require_available_ram()` in `funnel/common.py` reports available memory and halts below 3 GB. `funnel.profile` and `funnel.ingest --recheck` call it, and `python -m funnel.ramcheck` runs it before `dbt build`.

**2026-09-24 · Sprint 1 Step 0 · Ingest evidence test pinned the exact set of checks**
- **Origin:** Claude Code
- **What was produced:** `test_real_ingest_parquet_row_count_equals_csv_row_count` asserted that `ingest.json` `checks` equalled a fixed three-key dict.
- **What was wrong:** once `--recheck` added the two UTC round-trip checks, the test failed on a correct file. It tested the dict's shape rather than whether the checks passed.
- **How it was caught:** the pytest commit gate (1 failed, 42 passed) before the recheck evidence commit.
- **Fix:** the test now requires the five named checks to be present and every check to be true.
- **Guard added:** the same test now also fails if a UTC check is missing.

**2026-09-26 · Sprint 1 Step 0 · Correction-log entry described a regeneration that had not yet run**
- **Origin:** Claude Code
- **What was produced:** the entry "Generated wording used terms the metric contract prohibits" (committed in `907a7f9`) states that the regenerated `docs/data-profile.md` and `profile.json` carry the new wording.
- **What was wrong:** the entry was written before the regeneration it described. The source texts in `funnel/profile.py` and `funnel/verification.py` were fixed, but `funnel.profile` and `funnel.verification` had not been rerun. The committed `docs/data-profile.md` still read "a separate abandonment signal" (D9) and "the cart event for carts" (D3), and `ai-workflow/sprint-0-verification.md` still read "Carts with no view at or before in the session".
- **How it was caught:** Claude Code's context review at the start of a new session, comparing the entry with the committed files, reported to the project owner.
- **Fix:** `funnel.profile` and `funnel.verification` were rerun from a clean tree at `f1b0359` (manifest `git_worktree_dirty: false`). The regenerated files carry the new wording, and every count is unchanged. The earlier entry is now accurate as of this evidence commit.
- **Guard added:** none new; `analysis/tests/test_naming_rules.py` (Sprint 1 Step 2) will fail on the old wording.

**2026-09-26 · Sprint 1 Step 0 · Inferred-loss wording not covered by the prohibited-term scan**
- **Origin:** Claude Code
- **What was produced:** the D3 "choice forced" text in `funnel/profile.py`, generated into `docs/data-profile.md` and `profile.json`: "Which price is the value of a purchase or of a lost cart."
- **What was wrong:** "lost cart" states an inferred loss, which `docs/metrics.md` Section 1 rule 3 forbids in intent, and it uses "cart" for a cart event. The phrase was not on rule 3's prohibited list, so the term scan passed it.
- **How it was caught:** Claude Code's own review of the regenerated profile during the clean-manifest rerun (evidence commit `edaa183`), reported to the project owner.
- **Fix:** the text now reads "Which price is the value of a purchase, or of carted products with no observed purchase in the session." The code change ships in this commit, and the profile is rerun from the resulting clean tree in the next evidence commit. Counts are unaffected.
- **Guard added:** "lost cart" and "lost carts" are added to `docs/metrics.md` Section 1 rule 3 before the contract commit, and `analysis/tests/test_naming_rules.py` covers them with an injected-term check.

**2026-09-26 · Sprint 1 Step 2 · Injected-term check placed the term inside the excluded section**
- **Origin:** Claude Code
- **What was produced:** `test_injected_term_in_metrics_md_outside_section_1_is_caught` in `analysis/tests/test_naming_rules.py` inserted each term just before the `## 2. Event rules` heading.
- **What was wrong:** Section 1 runs up to that heading, so the injected text sat inside Section 1, which the guard excludes by design. The guard correctly ignored it, and 11 injection checks failed. The test was wrong, not the guard.
- **How it was caught:** the pytest commit gate before the metric-contract commit (12 failed, 72 passed; the twelfth failure is the next entry's contract wording).
- **Fix:** the term is now inserted before the `## 3. Session rules` heading, in the body of Section 2. Ships in this commit.
- **Guard added:** `test_terms_inside_metrics_md_section_1_are_allowed` shows the Section 1 exclusion is what lets the contract's own wording pass.

**2026-09-26 · Sprint 1 Step 2 · Contract prose used "carts" outside the naming rules**
- **Origin:** the contract draft provided for commit (drafting origin to be confirmed by the project owner); the inconsistency was surfaced by Claude Code's new test
- **What was produced:** `docs/metrics.md` Section 7 read "Always labeled as events, never as carts.", and the Section 1 enforcement paragraph banned "carts" only "used as a count label", while rule 1 says "Never say "carts"".
- **What was wrong:** the contract was inconsistent with itself. A whole-word check, the only form a test can enforce reliably, flagged the Section 7 sentence.
- **How it was caught:** the pytest commit gate (`test_committable_web_docs_and_exports_follow_naming_rules`), before the contract was first committed.
- **Fix:** the project owner reworded Section 7 to "The raw count of deduplicated cart events, always labeled as cart events." The enforcement paragraph now bans the whole word "carts" anywhere outside Section 1, which covers "unique carts". No other occurrence of "carts" exists outside Section 1. Ships in this commit, the contract's first.
- **Guard added:** `test_naming_rules.py` enforces the whole-word rule, and `test_guard_list_matches_contract_rule_3` keeps the guard's list equal to rule 3's.

**2026-09-24 · Sprint 0 · Checks run with no error found**
- **Origin:** n/a
- **Checks that ran clean:** the Step 0 preflight gates, run after the disk-space stop; Kaggle token authentication with no `kaggle.json` available; downloaded file size against the Kaggle listing; three independent row counts; CSV-to-Parquet type preservation; the raw `event_time` format and round trip; the dataset hash gate; the metric-lock guard on the real profile and on injected leaks; and the row-level data scan of committable files.
