# Correction Log

This log records every place where AI-generated work, from Claude Code or Claude Chat, was wrong, incomplete, or overconfident, and how the error was caught. The value of AI-assisted analysis depends on the verification around it, and that verification should be visible. A human reviews and owns every decision recorded here. From Sprint 2, it also records errors in the project owner's own specifications when a check catches them (origin "Project owner").

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
- **Origin:** Claude Chat (`docs/metrics.md` was drafted in Claude Chat; its decisions were approved by the project owner). Claude Code's new test surfaced the inconsistency. The origin was confirmed by the project owner after the contract commit `8d4093f` and recorded in the next commit.
- **What was produced:** `docs/metrics.md` Section 7 read "Always labeled as events, never as carts.", and the Section 1 enforcement paragraph banned "carts" only "used as a count label", while rule 1 says "Never say "carts"".
- **What was wrong:** the contract was inconsistent with itself. A whole-word check, the only form a test can enforce reliably, flagged the Section 7 sentence.
- **How it was caught:** the pytest commit gate (`test_committable_web_docs_and_exports_follow_naming_rules`), before the contract was first committed.
- **Fix:** the project owner reworded Section 7 to "The raw count of deduplicated cart events, always labeled as cart events." The enforcement paragraph now bans the whole word "carts" anywhere outside Section 1, which covers "unique carts". No other occurrence of "carts" exists outside Section 1. Ships in this commit, the contract's first.
- **Guard added:** `test_naming_rules.py` enforces the whole-word rule, and `test_guard_list_matches_contract_rule_3` keeps the guard's list equal to rule 3's.
- **Public title:** Contract prose used a prohibited count label outside the naming rules

**2026-09-26 · Sprint 1 Step 3 · Edit command used `cd` and a bare `python`, and hung**
- **Origin:** Claude Code
- **What was produced:** a shell command to add `price_amount` to the dbt models. It began with `cd` into `pipeline/`, in breach of the CLAUDE.md absolute-paths rule, and ran an inline script through a bare `python` with an ill-formed heredoc fallback, instead of the project venv or the Edit tool.
- **What was wrong:** the bare `python` did not return, so the command hung until the harness timeout and was stopped. It changed no files (checked afterwards).
- **How it was caught:** the harness's 120-second command timeout, then Claude Code's review of the stopped command.
- **Fix:** the edits were made with the Edit tool. Nothing was committed from the failed command.
- **Guard added:** none beyond the existing CLAUDE.md rules (absolute paths, no `cd`, temporary scripts only in the scratchpad).

**2026-09-26 · Sprint 1 Step 3 · DuckDB settings in the dbt profile were re-applied per cursor**
- **Origin:** Claude Code
- **What was produced:** `pipeline/profiles.yml` set memory_limit, threads, preserve_insertion_order, temp_directory, and TimeZone under dbt-duckdb `settings`.
- **What was wrong:** dbt-duckdb applies `settings` as `SET` statements on every new cursor. After `stg_dedup_audit` spilled, the next cursor's `SET temp_directory` failed with "Cannot switch temporary directory after the current one has been used". `stg_events` and every later node errored.
- **How it was caught:** the first `python -m funnel.build --select staging` run (dbt exit code 2, recorded in `ai-workflow/evidence/sprint-1/dbt_build_runs.json`).
- **Fix:** the same values move to `config_options`, which dbt-duckdb passes once to `duckdb.connect(config=...)`.
- **Guard added:** the reason is documented in `pipeline/profiles.yml`. Every build goes through `funnel.build`, which records the dbt exit code.

**2026-09-26 · Sprint 1 Step 3 · Contract gave an impossible basis for two data-quality metrics**
- **Origin:** Claude Chat (drafting of `docs/metrics.md`)
- **What was produced:** Section 10 of the contract committed in `8d4093f` said that all data-quality metrics except exact duplicate rows are counted "on deduplicated events in valid sessions".
- **What was wrong:** null-session events and multi-user sessions are excluded from valid sessions by definition (Section 3), so they cannot be counted on that basis. `mart_data_quality` could not be built as written.
- **How it was caught:** Claude Code's review of the contract against the Step 3 model specs, before `mart_data_quality` was written, reported to the project owner.
- **Fix:** a dated Changes entry in `docs/metrics.md` (2026-09-26) counts those two metrics on deduplicated events before session exclusions. The same entry records the project owner's decisions on two gaps: what the category funnel publishes (Section 9) and the timing reading of the cart-session purchase rate (Section 6). Ships in this commit, before either affected mart is built.
- **Guard added:** Step 3 stops at any model whose logic the contract does not define clearly.

**2026-09-26 · Sprint 1 Step 3 · Tie tests silently skipped by the build's test selection**
- **Origin:** Claude Code
- **What was produced:** build 2 ran `python -m funnel.build --select intermediate --indirect-selection cautious`.
- **What was wrong:** cautious selection runs a test only when all of its parents are selected. The three tie tests also reference `stg_events`, which was not in the selection, so they did not run. The build still reported `PASS=27`, which read as full coverage of the intermediate layer.
- **How it was caught:** Claude Code's own review of the build 2 log (no `assert_no_tied` line) before any mart was built. The three tests were then run on their own (`PASS=3`) before build 3.
- **Fix:** the tie tests ran and passed before the marts were built. The final Step 3 evidence is a full `dbt build` with no selection.
- **Guard added:** `funnel.build` reads dbt's manifest and run results after every build. It records tests run against tests expected (every test that depends on a model built in the run), and it fails the run if any expected test did not run or was skipped. `analysis/tests/test_build_coverage.py` covers the guard, including this case.

**2026-09-26 · Sprint 1 Step 3 · Build record's dbt summary was always empty**
- **Origin:** Claude Code
- **What was produced:** `summary_lines()` in `funnel/build.py` kept dbt's result lines by stripping a leading timestamp when a line began with digits.
- **What was wrong:** dbt colours its log output, so every line begins with an ANSI escape code, not a digit. No line matched, and every record in `ai-workflow/evidence/sprint-1/dbt_build_runs.json` up to and including the clean-tree full build at `6f8045b` has `"dbt_summary": []`. The exit codes, elapsed times, spill figures, and test-coverage counts in those records are unaffected.
- **How it was caught:** Claude Code's review of the final Step 3 evidence record before committing it.
- **Fix:** ANSI codes are stripped before the timestamp. The record also stores the `Done.` line's counts as `dbt_done_counts`. The full build is rerun from a clean tree, so the Step 3 evidence record is complete. Earlier records are left as written.
- **Guard added:** `funnel.build` fails a run whose output has no `Done. PASS=` line. `test_summary_lines_strip_colour_codes_and_timestamps` uses real dbt output, including the escape codes.

**2026-09-26 · Sprint 1 Step 5 · `.gitignore` also ignored the committed exports folder**
- **Origin:** Claude Code (Sprint 0 Step 1 `.gitignore`)
- **What was produced:** the ignore rule `data/`, meant for the top-level `data/` folder (raw CSV, Parquet, warehouse).
- **What was wrong:** an unanchored `data/` matches a folder named `data` at any depth, including `web/public/data/`, where CLAUDE.md says the JSON exports are committed. The exports could not have been committed. Also, `test_no_row_level_data.py` and `test_naming_rules.py` scan committable files only, so they would never have scanned the exports.
- **How it was caught:** Claude Code's check after the first `python -m funnel.export`. Every manifest read `git_worktree_dirty: false` while six new files existed; `git check-ignore -v` showed `.gitignore:8:data/`.
- **Fix:** the rule is anchored as `/data/`. `git check-ignore` confirms the raw CSV and warehouse are still ignored and the exports are not. The row-level and naming guards passed on the exports the first time they were in scope (95 passed).
- **Guard added:** `analysis/tests/test_export_files.py` requires each export to exist and carry a manifest. A file the guards cannot see would now also be absent from git and fail that test on a fresh checkout.

**2026-09-26 · Sprint 1 Step 5 · Export manifest taken per file, after earlier writes**
- **Origin:** Claude Code
- **What was produced:** `funnel/export.py` built each file's manifest inside the write loop.
- **What was wrong:** once the first export is written, the tree is dirty, so every later file would record `git_worktree_dirty: true` even on a clean run. The ignore bug above hid this in the first run.
- **How it was caught:** Claude Code's review while diagnosing the ignore bug, before any export was committed.
- **Fix:** one manifest is taken for the run before the first write. The exports from the first run were deleted and regenerated from a clean tree.
- **Guard added:** `test_export_files.py` asserts that all exports share one manifest and that it records a clean tree.

**2026-09-26 · Sprint 1 Step 6 · Site text stated facts not read from the exports**
- **Origin:** Claude Code
- **What was produced:** first drafts of three page sentences. `/data` said "It has no order or transaction ID" as fixed text. `/funnel` said the largest drop is between a view and a cart event as fixed text. `/data-quality` said long sessions do not change any headline figure "materially".
- **What was wrong:** CLAUDE.md rule 2 requires interpretation to rest on exported fields. The first two would have stayed on the page if the data said otherwise, and "materially" was an unstated judgement.
- **How it was caught:** Claude Code's own review of each page against rule 2, before the first render.
- **Fix:** each sentence is now chosen by a condition on the exported fields (`contents.order_or_transaction_id_exists`, the two step rates, the largest relative sensitivity shift), and the sensitivity sentence states its 1% threshold.
- **Guard added:** none automated; every interpretive sentence carries a Sources line naming its fields.

**2026-09-26 · Sprint 1 Step 6 · Daily chart ticks ran past the data and overflowed at 390 px**
- **Origin:** Claude Code
- **What was produced:** the home page's daily charts took x-axis ticks from a rounded scale (0 to 40) over days 1 to 31, dropping day 1.
- **What was wrong:** a "day 40" tick was drawn outside the plot, which pushed the page 47 px wider than a 390 px screen. The last tick label also wrapped onto the axis caption.
- **How it was caught:** Claude Code's 390 px screenshot pass, which also measures horizontal overflow per page.
- **Fix:** weekly ticks from the first day, kept inside the data range, and tick labels that do not wrap. Every page now measures 0 px overflow at 390 px and at desktop width.
- **Guard added:** the screenshot pass reports overflow per page (Step 7 evidence).

**2026-09-26 · Sprint 1 Step 6 · Correction-log titles exported to the site unscreened**
- **Origin:** Claude Code
- **What was produced:** `workflow.json` (for `/how-its-built`) exported every correction-log entry title as written.
- **What was wrong:** one title quotes the whole word that metrics.md Section 1 prohibits in any web file or export, to describe the error it records.
- **How it was caught:** the pytest commit gate (`test_committable_web_docs_and_exports_follow_naming_rules`) on the first development export of `workflow.json`.
- **Fix:** the log stays append-only. The affected entry gains a `Public title` line, and the export uses an entry's Public title when present. The original title and body are unchanged, and the guard and contract are unchanged (project owner's decision).
- **Guard added:** `test_correction_log_titles_safe_for_export` fails if any entry whose title would fail the naming guard lacks a Public title, or if a Public title would itself fail.

**2026-09-26 · Sprint 1 Step 6 · Delete command used unguarded variables in its path**
- **Origin:** Claude Code
- **What was produced:** a commit sequence that removed the development `workflow.json` with `rm "$R/$D/workflow.json"`.
- **What was wrong:** CLAUDE.md rule 10 requires a literal path or `${VAR:?}` guards for any delete on a variable path. With `R` or `D` unset, the command would have targeted a different path.
- **How it was caught:** human review at the permission prompt; the project owner declined the command before it ran. Nothing was deleted.
- **Fix:** the delete is written as a literal path, `rm "/c/Dev/ecommerce-funnel-analytics/web/public/data/workflow.json"`.
- **Guard added:** none beyond CLAUDE.md rule 10 and the permission check.

**2026-09-26 · Sprint 1 Step 7 · Wide tables clipped at 390 px on the first production deploy**
- **Origin:** Claude Code
- **What was produced:** the `/funnel` category tables (six columns) and the home page's daily table (full dates and full revenue figures).
- **What was wrong:** the pages did not overflow, but these tables scrolled sideways inside their boxes at 390 px, so part of each row was off-screen. Step 6's own check measured page overflow only, not clipped scroll boxes.
- **How it was caught:** the Step 7 screenshot script, adopted from the first project, which also fails a page with a clipped scroll box (4 of 12 page-theme combinations failed on the first production deploy).
- **Fix:** below the `sm` breakpoint, the three category funnel columns fold into a line under the category name, so no figure is hidden, and long codes wrap. The daily table uses short UTC day labels and compact revenue. All 12 combinations pass before the redeploy.
- **Guard added:** `npm run screenshots` fails on page overflow or any clipped scroll box. `test_evidence_images_within_size_limit` holds committed evidence images to 300 KB.

**2026-09-26 · v1.0.1 · Patch item specified from a text rendering of the page**
- **Origin:** Claude Chat
- **What was produced:** a v1.0.1 patch item asking for the home page's daily table to be collapsed.
- **What was wrong:** the table was already a closed disclosure. The item was specified from a text rendering of the page, which shows collapsed content expanded, not from the rendered page.
- **How it was caught:** Claude Code's review of the patch list against the committed page source (`web/app/page.tsx`, a `<details>` element), before any change was made; confirmed by the project owner.
- **Fix:** no change to the daily table.
- **Guard added:** page review uses rendered screenshots (`npm --prefix web run screenshots`), not text renderings.

**2026-09-26 · v1.0.1 · Git Bash rewrote leading-slash arguments into Windows paths**
- **Origin:** Claude Code
- **What was produced:** two commands passed arguments beginning with `/` through Git Bash: `vercel api /v9/projects/...` (Sprint 1 Step 7) and `SCREENSHOT_PAGES=/funnel npm run screenshots` (v1.0.1).
- **What was wrong:** Git Bash's path conversion rewrote them to `C:/Program Files/Git/...`, so the API call was rejected and the screenshot run navigated to a malformed URL. No output was written or committed from either.
- **How it was caught:** the command errors ("Invalid arguments" from the Vercel CLI; a navigation error naming the rewritten URL).
- **Fix:** the API call was rerun with `MSYS_NO_PATHCONV=1`, and the screenshot check was run from PowerShell.
- **Guard added:** none automated; arguments that begin with `/` are passed from PowerShell or with path conversion disabled.

**2026-09-26 · Sprint 2 Step 0 · `.env.example` left out of the last direct commit to main**
- **Origin:** Claude Code
- **What was produced:** the Step 0 commit `03c1eed`, pushed to `main`. Its command ran `git add` on a list of paths that included `.env.example`, then committed and pushed, gating only on `git commit`'s exit code.
- **What was wrong:** the Sprint 0 rule `.env*` in `.gitignore` also matches `.env.example`, so `git add` refused that path ("The following paths are ignored") and staged the others. The commit went out without `.env.example`, and its message lists it. The env-drift test passed locally only because the file exists in the working tree; on a fresh clone or in CI it would have failed.
- **How it was caught:** Claude Code's review of the command output immediately after the push.
- **Fix:** `.gitignore` gains `!.env.example`, and the file is committed on the Step 1 branch `sprint-2/governed-setup`, so it reaches `main` through the first PR. `03c1eed` is left as pushed; history is not rewritten.
- **Guard added:** `test_env_example_is_committable_not_ignored` in `analysis/tests/test_env_drift.py` fails if git ignores `.env.example` (checked by running it against the old `.gitignore`: 1 failed). Commit sequences now check `git status --short` after staging, and every listed path must be staged before the commit.

**2026-09-26 · Sprint 2 Step 3 · Export test pinned that no Changes entry touches decision D4**
- **Origin:** Claude Code (Sprint 1 Step 5, `analysis/tests/test_export.py`)
- **What was produced:** `test_decisions_link_to_the_changes_entries_that_apply` asserted `linked["D4"] == []`.
- **What was wrong:** the assertion recorded the Sprint 1 state of the contract rather than the linking rule. The Sprint 2 Changes entry lists Section 4 in its heading because it decomposes the D4 revenue difference, so `/data` correctly links D4 to it, and the test failed on a correct contract.
- **How it was caught:** the pytest commit gate before the Changes-entry commit (1 failed, 120 passed). Nothing was committed.
- **Fix:** the test asserts that D4 links to exactly the Sprint 2 entry and that D1 still links to none. The owner-approved entry text is unchanged. Ships in this commit.
- **Guard added:** none new; the test now checks the rule's output for the current contract.

**2026-09-26 · Sprint 2 Step 4 · Wording guard could pass on nothing and did not check its injections**
- **Origin:** Claude Code (`analysis/tests/test_wording_guard.py`, Sprint 2 Step 3, commit `7a73028`)
- **What was produced:** a guard that scanned the `/investigations` pages only `if INVESTIGATIONS.exists()`, and a boundary test that injected a phrase by `str.replace` on a heading and then checked the findings.
- **What was wrong:** with no pages, the investigations surface was silently absent and the test still passed, so the guard reported green on a surface it never read. It also did not scan the exported files those pages render from. If a heading were renamed, the injection's `replace` would change nothing, and the "inside Section 1" half would pass vacuously.
- **How it was caught:** human review by the project owner of the merged test (`76467d3..7a73028`), before Step 4.
- **Fix:** each surface is a parametrized case that must find all its files. The investigations surface is skipped, with the reason stated, only while no page exists; afterwards it also scans `investigation*.json` exports and `metrics_index.json`. Both injections assert that the text changed. Ships in this commit, before any Step 4 computation.
- **Guard added:** the per-surface file assertions and the injection-changed assertions themselves.

**2026-09-26 · Sprint 2 Step 4 · Added wording-guard term `prove\w*` was over-broad**
- **Origin:** Project owner (the Step 4 instruction to extend the phrase list, the owner's own specification), implemented as given by Claude Code
- **What was produced:** the phrase `prove\w*` in the wording guard.
- **What was wrong:** at a word boundary it also matches "provenance", a project rule term (CLAUDE.md rule 5), which appears twice in `README.md`. The guard would have failed on correct text.
- **How it was caught:** Claude Code's pre-commit check against the stop condition in the same instruction: before committing, any new term matching existing guarded text was reported to the owner rather than resolved by rephrasing or dropping it. The test run showed `wording guard: {'README.md': ['provenance']}` (1 failed, 13 passed, 1 skipped). Nothing was committed.
- **Fix:** the project owner chose to list the word forms `prove|proves|proved|proven|proving`. The README is unchanged. Ships in this commit.
- **Guard added:** "provenance", "improve", and "approve" are in the legitimate-wording assertion, so widening the term back to `prove\w*`, or dropping the word boundary, fails the test (checked: the wide pattern flags "provenance", and the unanchored pattern also flags "improve" and "approve").

**2026-09-26 · Sprint 2 Step 4 · Correction-log entry written outside the log's classification rules**
- **Origin:** Claude Code
- **What was produced:** the entry above on the over-broad `prove\w*` term, with an Origin line that named the owner's specification in prose and a "How it was caught" line with no classifier keyword.
- **What was wrong:** the `/how-its-built` statistics classify each entry by its Origin line (only "Claude Code" or "Claude Chat") and by keywords in "How it was caught". The entry fell into "Other" on both counts.
- **How it was caught:** the pytest commit gate (`test_every_correction_log_entry_is_classified`: 1 failed, 133 passed). Nothing was committed.
- **Fix:** `funnel/export.py` gains the origin "Project owner" (`ORIGINS`), with the displayed rule updated. The log's opening paragraph states that owner-specification errors are recorded. The entry's lines now read "Project owner" and "Claude Code's pre-commit check". Ships in this commit.
- **Guard added:** none new; the existing classification test caught it.

**2026-09-24 · Sprint 0 · Checks run with no error found**
- **Origin:** n/a
- **Checks that ran clean:** the Step 0 preflight gates, run after the disk-space stop; Kaggle token authentication with no `kaggle.json` available; downloaded file size against the Kaggle listing; three independent row counts; CSV-to-Parquet type preservation; the raw `event_time` format and round trip; the dataset hash gate; the metric-lock guard on the real profile and on injected leaks; and the row-level data scan of committable files.
