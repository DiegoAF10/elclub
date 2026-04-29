# IMP-R2-R6 Plans · Peer Review

**Date:** 2026-04-28 ~18:30
**Reviewer:** subagent (peer review run in parallel with execution)
**Plans reviewed:** 5 (R2, R3, R4, R5, R6)
**Spec reference:** `2026-04-27-importaciones-design.md` sec 4.2-4.6
**Reference impl plan:** `2026-04-28-importaciones-IMP-R1.5.md`
**Schema verified against:** `C:/Users/Diego/el-club-imp/erp/elclub.db` (snapshot)

---

## Summary

- **Critical findings: 3** (1 schema mismatch with hard fail at runtime · 1 in-progress edit incoherence in R2 body · 1 cross-plan divergence in stock-pendiente cost source)
- **Major findings: 6**
- **Minor findings: 7**
- **Plans approved as-is:** R5
- **Plans needing changes before execution:** R2 (mid-edit · finish), R3 (schema column verification + jerseys cost source), R4 (idempotency + state guard tweaks), R6 (apply order + script-runs-on-main-DB risk)

---

## Critical findings (BLOCK execution if any)

### C1 · `sale_items.customer_id` does NOT exist in production schema · R2 will hard-fail at runtime
- **Plan:** R2
- **Section:** Task 6 — `impl_promote_wishlist_to_batch` body (lines 1471-1484)
- **Issue:** The plan INSERT statement reads `INSERT INTO sale_items (sale_id, family_id, jersey_id, size, unit_cost_usd, import_id, customer_id, personalization_json) VALUES (...)`. Verified against actual DB at `C:/Users/Diego/el-club-imp/erp/elclub.db` — the `sale_items` table has these columns: `item_id, sale_id, family_id, jersey_id, team, season, variant_label, version, personalization_json, unit_price, unit_cost, notes, import_id, item_type, unit_cost_usd`. **`customer_id` is NOT among them.** The R2 test fixture (lines 875-895) defines its own custom CREATE TABLE with `customer_id`, so the test will pass — but the production code path will hit `Error: no such column: customer_id` at the very first promote call.
- **Recommendation:** Per Diego's split decision (assigned → sale_items, stock-future → jerseys), assigned items in `sale_items` already track the customer link via `sale_id` once a sale is created. Until then, the customer association must live elsewhere (notes? personalization_json? a new column?). Two options:
  1. ADD COLUMN `customer_id` to `sale_items` via R6 schema script (preferred — keeps the data model clean for the assigned-but-not-yet-sold state).
  2. Stuff `customer_id` into `personalization_json` (preserves the data without ALTER, but breaks JOIN-friendliness for R3 queries).
  Pick option 1 and add the ALTER to `apply_imp_schema.py` in R6.

### C2 · R2 plan body is mid-edit and internally inconsistent · execution will produce wrong code
- **Plan:** R2
- **Section:** Task 6 (impl_promote_wishlist_to_batch · ~lines 1264-1511)
- **Issue:** The Goal/Architecture preamble (line 5-7), the doc comment (lines 1264-1291), the validators (lines 1303-1334), and the test cases (lines 990-1009) all reflect the NEW Diego decisions:
  - status default = 'paid' with toggle to 'draft'
  - split sale_items vs jerseys based on `customer_id`
  - new `cmd_mark_in_transit` command
  
  But the **actual transactional body** (lines 1441-1495) still contains the OLD logic:
  - hardcodes `'draft'` in the INSERT (line 1445)
  - has a single INSERT path into sale_items only (no split)
  - includes `customer_id` in the sale_items INSERT (which compounds C1)
  
  The plan has been partially edited (header and tests) but the implementation body wasn't yet updated. If executed as-is, the executor will write code that contradicts both Diego's resolved decisions and the plan's own test fixtures (tests will FAIL because they expect the split behaviour).
- **Recommendation:** Finish the R2 edit before the executor reaches Task 6. Specifically: replace the single INSERT loop (line 1457-1495) with the split logic per the doc comment at line 1268, parameterize status/paid_at from input, and add `cmd_mark_in_transit` impl + cmd as a sibling of promote (currently only mentioned in the Goal/Architecture/file-list, but no Task in the body actually creates it). The test file at line 1024 also references `imp_r2_mark_in_transit_test.rs` but no Task creates it.

### C3 · R3 stock-pendiente cost source assumes `imports.unit_cost` per-unit shared; jerseys.cost not populated by close_import for stock-future items
- **Plan:** R3 (cross-plan with R4 close_import modification)
- **Section:** R3 Task 2 `compute_batch_summary` (lines 264-271)
- **Issue:** R3 computes `valor_stock_pendiente_gtq = unit_cost_landed × n_pendiente` where `unit_cost_landed = imports.unit_cost`. The comment correctly notes "jerseys table doesn't have unit_cost populated (only sale_items get unit_cost set during close_import_proportional)". But the existing `cmd_close_import_proportional` at lib.rs:2693 *does* `UPDATE jerseys SET cost = ? WHERE rowid = ?` — so jerseys DO get a cost set. However, this only runs for jerseys that EXISTED at close time. Per R2 split decision, stock-future items will be inserted into `jerseys` BEFORE the import closes (at promote-to-batch time, when status=paid/draft). When close_import runs, those jerseys SHOULD get cost prorated alongside sale_items — but the existing close logic may iterate only sale_items (verify lib.rs:2620-2730). If it doesn't iterate jerseys, then post-close, `jerseys.cost` for stock-future items will remain NULL, AND `imports.unit_cost` is the per-unit landed (a single number) which is the right proxy. Either approach works numerically (D2=B says proportional to USD, but if all stock-future items have the same `expected_usd`, they share the same unit_cost). **The bug is**: R3's stock pendiente uses `imports.unit_cost` (per-unit landed) which is correct ONLY if all items in the batch share the same USD value. Per D2=B, they generally don't. This means stock pendiente value is approximate, not exact.
- **Recommendation:** Two paths:
  1. Have R4's close_import modification ALSO update `jerseys.cost` for jerseys with `import_id=this_import` using the same prorrateo loop. Then R3's query becomes `SUM(COALESCE(si.unit_cost, j.cost))` — accurate per-item.
  2. Accept the approximation and document it explicitly in `BatchMargenSummary.valor_stock_pendiente_gtq` as "promedio per-unit · no exacto si items tienen distinto unit_cost_usd" so Diego knows.
  Path 1 is preferred. The R4 close modification (Task 5) needs to be expanded to also iterate `jerseys WHERE import_id=X` and apply prorrateo. This is a CROSS-PLAN dependency that neither R3 nor R4 currently call out.

---

## Major findings (integrate before that plan executes)

### M1 · `inbox_events` table EXISTS in production · R2/R6 incorrectly assert it doesn't
- **Plan:** R2 (line 3098), R6
- **Issue:** R2 line 3098 says "Schema nueva (tabla `inbox_events`) — NO está en R1 schema additions" as a reason to defer Inbox events. R6 line 1597 punts inbox event consumption to Comercial. But verified against real DB: **`inbox_events` table EXISTS already** (it's a Comercial-shipped table). The deferral reasoning is wrong. Inbox events COULD be implemented in R2/R4 by INSERT-ing into the existing `inbox_events` table.
- **Recommendation:** This may be intentional (don't expand R2 scope), but the PRETEXT is wrong. Either: (a) keep deferral but update justification ("not because table missing, but because cron/trigger mechanism not yet defined"), or (b) reconsider whether spec sec 4.2's three Inbox events should at least INSERT into `inbox_events` synchronously when the wishlist insert/promote happens (cheap and aligns with spec).

### M2 · R3 references `sale_items.created_at` which DOES NOT EXIST
- **Plan:** R3
- **Section:** Task 4 `impl_get_batch_margen_breakdown` line 444 — `SELECT s.sale_id, s.created_at, s.customer_id, s.total_gtq` (this is `sales.created_at` so OK). But line 540 commit message refers to `items by item_id` (OK, item_id exists). However: **`sales` table actual columns:** `sale_id, ref, occurred_at, modality, origin, customer_id, payment_method, fulfillment_status, shipping_method, tracking_code, subtotal, shipping_fee, discount, total, source_vault_ref, notes, created_at, shipped_at, shipping_address`. So `sales.created_at` exists ✓ AND `sales.customer_id` exists ✓. But the R3 SELECT uses `s.total_gtq` — **the actual column is `total`, NOT `total_gtq`**. The query will fail with `no such column: total_gtq`.
- **Recommendation:** Update R3 Task 4 SELECT (line 444) and Task 5 (lines 567-575 if applicable) to use `s.total` instead of `s.total_gtq`. The struct field can still be `total_gtq` (mapping `s.total AS total_gtq` works in SELECT alias). Same correction applies to the smoke script at line 1607 which INSERTs `total_gtq` into a sales test table — verify the test schema matches production schema.

### M3 · R3 references `sale_items.sku` and `sale_items.variant` which DO NOT EXIST in production schema
- **Plan:** R3
- **Section:** Task 4 `impl_get_batch_margen_breakdown` line 463-466 SELECT pending items uses `sku` and `variant`. Production `sale_items` columns are: `family_id, jersey_id, team, season, variant_label, version, ...`. There is NO `sku` and NO `variant` column. The closest equivalents would be `family_id` (canonical SKU) and `variant_label` (display variant).
- **Recommendation:** Update R3 Task 4 SELECT to: `SELECT item_id, family_id AS sku, variant_label AS variant, unit_cost, unit_price`. The plan's own Step 2 verification command actually flags this risk ("Si distintos · ajustar SELECT en lib.rs antes de commit") — good defensive note, but the executor needs to act on it. Make the SELECT correct upfront.

### M4 · `cmd_mark_in_transit` listed in R2 architecture and file structure but NO Task implements it
- **Plan:** R2
- **Section:** R2 file structure (line 21-25) lists `MarkInTransitModal.svelte` and `imp_r2_mark_in_transit_test.rs`. R2 architecture line 5 says "Adicional: nuevo `cmd_mark_in_transit`". But the Task numbering goes 1-16 and there is no Task implementing the Rust impl/cmd for `mark_in_transit`. The generate_handler! wire-up (Task 7) only adds 5 commands (cmd_list_wishlist, cmd_create_wishlist_item, cmd_update_wishlist_item, cmd_cancel_wishlist_item, cmd_promote_wishlist_to_batch). cmd_mark_in_transit is missing from the macro list too.
- **Recommendation:** Add a new Task (between Task 6 and Task 7) for `cmd_mark_in_transit`: TDD light, state guard (only paid → in_transit accepted), optional `tracking_code` COALESCE update, sets `imports.tracking_code` and `imports.status='in_transit'`. Then update Task 7 to wire 6 commands instead of 5. Also add the Svelte modal task.

### M5 · R2 jerseys INSERT has no `status='pending'` value enforced; jerseys.status CHECK constraint may reject
- **Plan:** R2
- **Section:** R2 doc comment line 1268 says stock-future items go to `jerseys (import_id=new, status='pending')`. Production jerseys table HAS a `status` column. The current production schema for jerseys.status (verify: I did not check the CHECK constraint, only column existence) needs to allow 'pending'. If jerseys.status has a CHECK constraint that doesn't include 'pending', the INSERT will fail.
- **Recommendation:** Before R2 ships, run `python -c "import sqlite3; print(sqlite3.connect(r'C:/Users/Diego/el-club-imp/erp/elclub.db').execute(\"SELECT sql FROM sqlite_master WHERE name='jerseys'\").fetchone()[0])"` to inspect the actual CHECK constraint on jerseys.status. If 'pending' is not allowed, either: (a) add it via R6 schema script ALTER, or (b) use an existing valid status value like 'draft' or 'unpublished'.

### M6 · R4 close_import modification stores free units WITHOUT family_id/jersey_id linkage
- **Plan:** R4
- **Section:** Task 5 (line 951-960) inserts free units as `INSERT INTO import_free_unit (import_id, created_at) VALUES (?, ?)` — no family_id, no jersey_id. The spec sec 4.4 line 252 ("`import_id · sku_placeholder · player_spec · created_at · status · destination · notes`") implies free units carry SOME identifier hints. Per D-FREE=A (unassigned default · Diego decides destino caso a caso), the destination is null OK — but the plan doesn't even pick a SKU placeholder.
- **Recommendation:** Either (a) accept that free units are anonymous at creation (Diego links them to a SKU later via assign), document this in the spec; or (b) at close time, pick the cheapest item from the batch (or N/A) as the placeholder family_id. Option (a) is fine — but ensure the assign flow lets Diego SET family_id post-creation. Currently the AssignFreeUnitInput has optional `familyId` (R4 line 1037), so this works — just confirm the UI surfaces it.

---

## Minor findings (polish · defer)

### m1 · R3 best/worst batch O(N×helpers) loop is wasteful
- **Plan:** R3
- **Section:** Task 5 `impl_get_margen_pulso` lines 593-603 iterates all closed batches and runs `compute_batch_summary` per batch just to get `margen_pct`. This is O(N) DB roundtrips × ~5 sub-queries each = 5N queries for what could be a single GROUP BY query.
- **Recommendation:** For an MVP with ~2-10 closed batches the cost is trivial. Accept as-is for v0.4.0. Optimize in a follow-up if N grows >50.

### m2 · R3 destination CHECK constraint mismatch · spec includes 'unassigned' but R6 schema script CHECK allows it, R4 plan does NOT allow it as a valid input value
- **Plan:** R4 + R6
- **Section:** R6 `apply_imp_schema.py` line 173: `CHECK(destination IN ('unassigned','vip','mystery','garantizada','personal'))`. R4 valid destinations input list (line 1033): `'vip' | 'mystery' | 'garantizada' | 'personal'` (no 'unassigned'). The R4 Rust constant (not shown in my reads but referenced in test line 388) likely matches the input typing and rejects 'unassigned' as input — which is correct (Diego doesn't assign-to-unassigned, that's the default). But R4 plan also has `cmd_unassign_free_unit` that sets destination back to NULL (line 603), not 'unassigned'. The schema CHECK says destination IN ('unassigned',...) but the R4 plan stores NULL. **Inconsistency**: schema permits NULL (CHECK only fires when destination IS NOT NULL · per SQLite semantics), but the schema's CHECK list suggests the convention is the string 'unassigned' instead of NULL.
- **Recommendation:** Pick one. Either (a) use NULL throughout and remove 'unassigned' from the CHECK enum, or (b) use 'unassigned' string and have R4 unassign set destination='unassigned' instead of NULL. Option (a) is cleaner. Update apply_imp_schema.py CHECK to omit 'unassigned'.

### m3 · R6 apply_imp_schema.py default DB path is `C:/Users/Diego/el-club/erp/elclub.db` (MAIN db) — script will run against PRODUCTION DB by default
- **Plan:** R6
- **Section:** Task 1 line 140-143 `DEFAULT_DB = ... r"C:/Users/Diego/el-club/erp/elclub.db"`.
- **Risk:** If Diego runs `python apply_imp_schema.py --apply` from any working directory without `--db-path`, it writes to MAIN production DB. The script DOES backup first (good), but the order-of-operations (apply BEFORE merge so the new code finds the new schema) creates a window where MSI v0.4.0 isn't installed yet but main DB already has new schema. If something goes wrong with v0.4.0 build/install, the main DB has uncommitted-from-codebase schema state.
- **Recommendation:** Two safety nets: (1) Add a confirmation prompt when `--apply` is used and `--db-path` resolves to the MAIN production DB (not the worktree DB). (2) Document the apply order explicitly in starter docs: `apply_imp_schema.py --apply` runs ONLY after `git merge --no-ff` succeeds AND MSI v0.4.0 is built. Before merge, only `--dry-run` is allowed.

### m4 · R6 `imp_settings` table is created but free_ratio default is hardcoded in R4 (spec divergence noted but not migrated)
- **Plan:** R6
- **Section:** R6 line 16 explicitly says "free_ratio default queda HARDCODED en 10 en R4 · NO se cablea a `imp_settings` en v0.4.0". Per spec sec 4.6 ("Free unit ratio (default 1/10)") this is a Settings field. Hardcoding it in R4 (close_import) means Settings UI shows the value but changing it in Settings has no effect on actual close_import behavior.
- **Recommendation:** Acceptable for v0.4.0 (deferred to v0.5 per the plan). Make sure the Settings UI flags this clearly: show a "Read-only · cableado en v0.5" indicator on the free_ratio field, otherwise Diego will be surprised when changing it doesn't change actual behavior.

### m5 · R5 `next_expected_arrival` calc rounds avg lead time to nearest day · could be slightly off
- **Plan:** R5
- **Section:** Task 3 line 357 `chrono::Duration::days(avg.round() as i64)` rounds 8.4 → 8 days. With n=1 batch closed (current state, only IMP-2026-04-07 with 8d lead), the calc is fine. With more samples, half-day rounding may matter very little.
- **Recommendation:** Accept as-is. Document in struct comment that the projection is `±1 day`.

### m6 · R3 `valor_free_units_gtq` is hardcoded `None` with TODO · UI must handle null gracefully
- **Plan:** R3
- **Section:** Task 2 line 305 `valor_free_units_gtq: None, // TBD per spec ambiguity (open question for Diego)`. The R3 BatchMarginCard.svelte (Task 10 line 1027) renders this as `{fmtGtq(summary.valorFreeUnitsGtq)}` which returns 'Q—' for null — OK.
- **Recommendation:** Acceptable. Add a tooltip on the value clarifying "valor pendiente cuando se asigne destino" so Diego doesn't think it's a bug.

### m7 · R4 modal `customers` lookup uses `adapter.listCustomers?.()?.then(...)` — defensive optional chain may hide a real bug
- **Plan:** R4
- **Section:** Task 9 `AssignDestinationModal.svelte` line 1244. The `listCustomers` adapter method may not exist (it's a Comercial method, not an IMP method). The optional chain swallows the absence silently and the UI shows "manual input fallback" without telling the user why.
- **Recommendation:** Verify `adapter.listCustomers` is defined in `Adapter` interface (it should be — Comercial has it). If yes, drop the `?.()?` and use straight `adapter.listCustomers()`. If no, import the method explicitly. Silent fallbacks make debugging harder.

---

## Cross-plan consistency check

### Naming consistency
- ✅ Command naming follows convention: all R2-R6 commands use `cmd_X` + `impl_X` split per lib.rs:2730-2742.
- ✅ Adapter method names are camelCase mirrors of cmd_X (e.g. `cmd_list_wishlist` ↔ `listWishlist`).
- ⚠️ Status pill spelling: R2/R3/R4 all use `'cancelled'` (British) — good consistency with existing spec.

### Type drift
- ⚠️ R3 uses `total_gtq` field name on `LinkedSale` struct (line 142-145) but the production sales table uses `total`. The Rust struct can keep the camelCase `totalGtq` for TS compat, but the SELECT must alias `s.total AS total_gtq`. Currently it doesn't.
- ✅ R3 `BatchMargenSummary.valorFreeUnitsGtq: number | null` is consistent across Rust struct + TS interface + Svelte card.
- ⚠️ R4 `FreeUnit.destination` typed as `Option<String>` in Rust (line 121) but TS interface (line 1021) is `'vip' | 'mystery' | 'garantizada' | 'personal' | null`. Discriminated union vs string is a non-issue at runtime but means TS callers can't pass arbitrary strings — fine for production code.

### Data flow R2 → R3 (sale_items + jerseys)
- ⚠️ Per Diego's split decision (R2 architecture), assigned items go to sale_items, stock-future to jerseys. R3 `compute_batch_summary` (line 254-262) UNIONs both tables for n_pendiente. ✅ Correct.
- ⚠️ R3 revenue calc (line 245-249) reads `SUM(unit_price) FROM sale_items WHERE import_id=X AND sale_id IS NOT NULL`. Stock-future items in jerseys never have unit_price (jerseys uses `price`, not `unit_price`). When a jersey gets sold (Comercial creates a sale), a `sale_item` is inserted with the sold jersey's data — so the revenue calc IS correct, AS LONG AS Comercial's sale-creation flow inserts a sale_items row with the matching `import_id` carried over from the jersey. **Cross-module dependency on Comercial behavior**: confirm that when Comercial sells a jersey, the resulting sale_item carries the jersey's `import_id`. If not, R3 revenue calc will undercount.

### Data flow R4 → R3 (free_units)
- ✅ R4 stores free units in `import_free_unit`. R3 reads `import_free_unit` for `n_free_units` count. Independent of close_import internals.
- ⚠️ R3's `valor_free_units_gtq` is None always (per m6). Once Diego decides the valuation rule (cost? price? avg unit_cost?), R3 needs a follow-up patch.

### Schema migration coverage (R6 apply_imp_schema.py)
- ✅ Creates `import_wishlist`, `import_free_unit`, `imp_settings` (idempotent).
- ✅ Creates 4 indexes per spec sec 7 line 532-535.
- ✅ Seeds 7 default settings.
- ❌ Does NOT add `sale_items.customer_id` (which we identified as needed in C1).
- ❌ Does NOT verify or add `jerseys.status='pending'` to existing CHECK constraint (M5).
- ❌ The script DEFAULT_DB points at MAIN db (m3), risk of accidental main-db write.
- ⚠️ The `notes_extra` ALTER mentioned in master overview line 70 is commented out — accept as deferred per R6 line 287-296 documentation.

---

## Per-plan summary

### R2 (Wishlist + Promote-to-batch)
- **Spec coverage:** ~90% (all spec sec 4.2 items in plan structure · gaps: cmd_mark_in_transit unimplemented · split logic wrong in body · sale_items.customer_id schema gap)
- **Strengths:** TDD MANDATORY for promote-to-batch with 7+ edge cases · catalog_family_exists D7=B server-side · self-clean modal pattern · clear cross-module risk callouts in self-review.
- **Risks:** **Plan body is in mid-edit (C2)** — task6 impl will produce wrong code if executed before edit completes. Schema gap C1 will cause runtime failure on first promote. M4 missing task for new command.
- **Verdict:** **REVISE before execution starts on Task 6**. Tasks 1-5 (helpers, list, create, update, cancel) are safe to execute now — they don't touch the broken parts.

### R3 (Margen real cross-Comercial)
- **Spec coverage:** ~95% (all sec 4.3 items covered)
- **Strengths:** Clean separation of impl/cmd · single helper for summary computation · pulso command with best/worst tracking · color-coded margen card per spec mockup.
- **Risks:** M2/M3 (column name mismatch) will cause runtime failure on first call. C3 stock-pendiente value is approximate (acceptable but document it).
- **Verdict:** **REVISE column references in SELECT statements** (sales.total → AS total_gtq · sale_items.sku → family_id AS sku · sale_items.variant → variant_label AS variant). Then approve.

### R4 (Free units + close_import modification)
- **Spec coverage:** ~92%
- **Strengths:** **EXCELLENT regression test discipline** (canary test BEFORE modification · explicit STOP condition if canary fails · 4 idempotency cases for free unit creation). This is the right pattern for modifying production code.
- **Risks:** M5/m2 destination enum/CHECK inconsistency. M6 free units have no SKU placeholder at creation (but assign UI surfaces it · OK). C3 cross-plan: jerseys.cost not updated by close (impacts R3).
- **Verdict:** **APPROVE with M5/m2 cleanup** — pick NULL or 'unassigned' string convention and stick to it across schema CHECK + R4 unassign behavior.

### R5 (Supplier scorecard)
- **Spec coverage:** ~98% (defers cost_accuracy and disputes_log per spec)
- **Strengths:** Clean Rust-side percentile (no SQL gymnastics) · inline tests for percentile helper · Bond constants as hardcoded (avoids premature suppliers table per spec) · multi-supplier scaffold via DISTINCT supplier query.
- **Risks:** None significant. m5 minor rounding artifact. cost_accuracy_pct is intentionally None.
- **Verdict:** **APPROVE AS-IS**.

### R6 (Settings + polish + apply_imp_schema.py)
- **Spec coverage:** ~88% (Settings tab · schema script · polish pass — DOES NOT close C1 gap by adding sale_items.customer_id)
- **Strengths:** Idempotent script with backup obligation · dry-run mode · clean separation Settings UI vs schema script · polish pass per-tab.
- **Risks:** m3 (default DB path is MAIN) · m4 (free_ratio not actually wired). Should add the `sale_items.customer_id` ALTER to fix C1.
- **Verdict:** **REVISE to address C1 (add ALTER) + m3 (safety prompt for main DB) + m4 (UI flag for read-only setting)**.

---

## Final verdict

**Status: NEEDS REVISION before Wave 1 R2 execution proceeds past Task 5.**

**Blocking issues for Wave 1 (R2):**
- C1 schema gap (sale_items.customer_id missing) — fix via R6 ALTER OR change R2 to NOT insert customer_id directly
- C2 R2 body mid-edit — finish the edit so Task 6 produces the correct split logic + new cmd_mark_in_transit
- M4 missing task for cmd_mark_in_transit
- M5 verify jerseys.status CHECK allows 'pending' before R2 jerseys INSERT path executes

**Blocking issues for Wave 2 R3:**
- M2/M3 column name corrections (`total` not `total_gtq`, `family_id` not `sku`, `variant_label` not `variant`)
- C3 cross-plan: decide whether R4 close also updates jerseys.cost (preferred) or R3 documents approximation

**Recommended sequencing:**
1. Pause R2 executor BEFORE Task 6
2. Strategy author finishes R2 plan edit (split logic + cmd_mark_in_transit task + Svelte modal task + handler wiring)
3. Add ALTER `sale_items` ADD COLUMN `customer_id` to R6 apply_imp_schema.py
4. Fix R3 column references (3 lines)
5. Decide C3 path (extend R4 close to also iterate jerseys, or document R3 approximation)
6. Resume R2 → R3 → R4 → R5 → R6

R5 can ship as-is. R4 and R6 need the small cleanup but are otherwise solid.
