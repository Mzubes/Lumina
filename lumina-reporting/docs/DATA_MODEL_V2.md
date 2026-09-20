# Lumina data model v2

Status: **designed and tested, not yet wired in.** Lives at
`backend/schema_v2/`, exercised by `backend/tests/test_schema_v2.py` (27
tests). It has its own declarative `Base` and metadata, so it can be created
alongside today's schema and cut over deliberately.

---

## The decision this is built around

**Lumina is a reporting system downstream of an already-reconciled book of
record.** It does not reconcile. It records that reconciliation happened
upstream, and refuses to publish numbers carrying no attestation.

That single choice removes a lot — no break tables, no custodian-vs-internal
comparison, no break-resolution workflow — and adds one thing: a publishing
gate. See [Reconciliation as a contract](#reconciliation-as-a-contract).

---

## What was wrong with v1

| Problem | Consequence |
|---|---|
| `Client` and `FundData` are unrelated roots; `client_id` / `fund_id` both nullable on every fact | A client cannot hold two mandates in the same strategy. Level is implied by which FK is set, so every query branches. |
| No Account/Portfolio layer | Nothing sits between "who owns it" and "what it holds". |
| No client↔fund relationship exists anywhere | Client-level AUM reads $0 whenever the feed is fund-scoped. |
| `security_id` is a bare string; no instrument table | The same security from two feeds becomes two rows that never aggregate — duplicate names in a top-ten list. |
| `benchmark_return_pct` is a bare `Numeric` | A report says "vs +8.1% bench" and cannot name the index. Not GIPS-defensible. |
| No transactions | Cost basis, realised gain/loss and money-weighted return are all unanswerable. |
| No provenance; `DataSource.last_sync_*` is one mutable row | No way to say which book a number came from, or to reproduce a report sent last year. |
| No tenant column | Single-firm only. |

---

## Shape

```
                          Firm  ─── tenant boundary, on every table
                            │
        ┌───────────────────┼────────────────────┬──────────────────┐
        │                   │                    │                  │
  ClientGroup           Strategy             Benchmark          Composite
        │                   │                    │                  │
     Client                 │            BenchmarkComponent   CompositeMembership
     │    │                 │                    │                  │
  Contact └────────┐        │                    │                  │
                   ▼        ▼                    │                  │
              ╔═══════════════════╗              │                  │
              ║    PORTFOLIO      ║◄─ PortfolioBenchmark ───────────┘
              ║ separate_account  ║
              ║ pooled_fund       ║──► ShareClass ──► Instrument
              ║ model             ║──► CustodialAccount
              ╚═════════╤═════════╝
                        │  every fact hangs here, portfolio_id NOT NULL
   ┌────────┬───────────┼───────────┬────────────┬──────────────┐
   ▼        ▼           ▼           ▼            ▼              ▼
Position Transaction Valuation  CashFlow  PerformanceReturn  (FxRate)
   │        │           │           │            │
   └────────┴───────────┴───────────┴────────────┴──► DataLoad ──► DataSource
                                                        │
                                            reconciliation attestation
```

`CompositeReturn` and `BenchmarkReturn` attach to `Composite` and `Benchmark`
respectively, not to `Portfolio`.

---

## The five decisions that matter

### 1. Every pool of assets is a Portfolio — including funds

One axis, not two. A separate account, a commingled fund and a model
portfolio are all rows in `portfolio`, distinguished by `portfolio_type`.
Positions, valuations, transactions and returns all carry
`portfolio_id NOT NULL`.

A check constraint keeps ownership unambiguous: a `separate_account` must
have a `client_id`, a `pooled_fund` or `model` must not.

**A client's stake in a fund is not a special case.** It is an ordinary
`Position` in the client's own portfolio whose `instrument` is the fund's
share class — which is what actually happens economically. Fund look-through
becomes a join rather than a rule.

### 2. Facts are append-only and carry their provenance

Every fact row has:
- `as_of_date` — the business date it describes (valid time)
- `data_load_id` → `DataLoad.loaded_at` — when Lumina learned it (transaction time)

A correction is a **new load** for the same `as_of_date` with
`supersedes_id` pointing at the old one. Rows are never updated or deleted.

This is what makes a distributed report reproducible: re-render it in three
years and the numbers are identical, because the rows it read are still
exactly as they were. It is bitemporality's useful half without its weight.

### 3. Benchmarks and composites are entities

`Benchmark` carries name, provider, currency and — importantly —
`return_variant` (net vs gross of withholding tax), because comparing a
net-of-tax portfolio return to a gross index overstates performance.

`PortfolioBenchmark` is **effective-dated**, so a mandate that changes
benchmark doesn't retro-point old reports at the new one.

`CompositeMembership` is effective-dated with inclusion and exclusion
reasons. A portfolio that leaves stays on record for the periods it was
managed — GIPS exists to prevent exactly the rewrite that deleting a
membership row would perform.

`CompositeReturn` carries the GIPS statistics (`portfolio_count`,
`composite_assets`, `firm_assets`, `dispersion_pct`,
`three_year_std_dev_pct`) that otherwise get typed into a template by hand
and go stale.

### 4. Returns are taken as delivered, not computed

`method` (`twr` / `mwr` / `simple`) and `return_basis` (`gross` / `net`) are
per-row, because one client pack legitimately shows several at once.
Mislabelling one as another is a compliance problem, not a display bug.

Lumina does not calculate returns. The firm's performance system owns the
methodology, the flow timing and the large-flow policy; a second
implementation inside a reporting tool would eventually disagree with the
numbers the client was already sent.

### 5. Tenant on every table

`firm_id NOT NULL` everywhere except `firm` itself — never inferred through a
join, because a row-level-security policy that has to traverse a join is a
policy that gets bypassed. A test asserts no table is missing it.

---

## Reconciliation as a contract

Because reconciliation is upstream, `DataLoad` records the **attestation**:

| Column | Meaning |
|---|---|
| `reconciliation_status` | `reconciled` / `unreconciled` / `waived` |
| `reconciled_at`, `reconciled_by_system`, `reconciliation_reference` | Which system asserted it, and its run id, so an auditor can follow the claim back |
| `waiver_reason`, `waived_by_user_id` | Only when waived — who accepted unreconciled data and why |

One rule follows:

```python
DataLoad.is_publishable  # reconciliation_status in ('reconciled','waived') and is_current
```

Report generation checks every load it intends to read and refuses if any
answers `False`. A database check constraint requires a waiver to carry a
reason, because an unexplained override would make the gate meaningless.

**This is the point.** Without it, "we reconcile upstream" is a sentence in a
runbook. With it, unreconciled data physically cannot reach a client.

`DataSource.book` (`ibor` / `abor` / `custodian` / `manual`) records which
book a feed speaks for. The same portfolio on the same date legitimately has
different positions in each — an IBOR reflects trade-date intent, an ABOR
settled accounting — so "does this tie to my custodian?" becomes answerable
rather than assumed.

---

## What is deliberately not here

- **No reconciliation engine.** Per the decision above.
- **No derived positions.** Lumina takes positions and transactions as given.
- **No return calculation.** See decision 4.
- **No NAV derivation.** `Valuation.total_market_value` is the administrator's
  struck number. It is stored beside the positions, and a variance between
  them is a signal Lumina can surface — never one it resolves.
- **No group-of-groups.** `ClientGroup` is one level deep. A `parent_id` is
  additive if it's ever needed; recursion in every roll-up query is not free.
- **No attribution model.** Sector/factor attribution is a larger schema of
  its own and nobody has asked for it yet.

---

## Carried over unchanged

The reporting and workflow tables in `models.py` are good and are not
replaced: `report_templates`, `workflow_diagrams`, `workflow_groups`,
`workflow_group_memberships`, `report_step_instances`, `report_transitions`,
`component_reviews`, `distribution_links`, `disclosures`, `users`.

They **re-parent**, though:

| Today | v2 |
|---|---|
| `reports.client_id` + `reports.fund_id` | `reports.portfolio_id` (or `composite_id` for a composite factsheet) |
| — | `reports.firm_id` |
| — | `report_data_binding` (report_id, data_load_id) — the exact loads a report was rendered from, which is what makes it reproducible |

---

## Cutover sequence

Each step is independently shippable and reversible.

1. **Stand up v2 alongside v1.** Tables created, nothing reads them. *(Done — this commit.)*
2. **Backfill.** `Client` → `client`; `FundData` → `strategy` + a `pooled_fund` portfolio; each existing `client_id`-scoped set of holdings → a `separate_account` portfolio. Every backfilled row gets a synthetic `DataLoad` marked `waived` with reason "v1 backfill, pre-dates attestation" — honest about what is and isn't attested.
3. **Dual-write.** New ingestion writes both schemas. Compare outputs.
4. **Move reads.** `report_content.py` resolvers onto v2 first (they are the narrowest surface), then `book.py`, `production_metrics.py`, `risk_status.py`.
5. **Re-parent `reports`** onto `portfolio_id`, add `report_data_binding`.
6. **Drop v1 fact tables.** `holdings`, `performance_snapshots`, `fund_data`.

Step 2 is where the honest accounting happens: today's data has no
provenance, and marking it `waived` rather than `reconciled` says so out loud
instead of laundering it.

---

## Open questions for you

1. **Are you the book of record, or downstream of one?** This design assumes
   downstream. If some prospects have no IBOR and expect Lumina to *be* the
   book, that's a materially different product and this schema is the wrong
   shape for it.
2. **Do you need attribution?** Deliberately omitted. If client packs need
   sector or factor attribution, that's its own schema and worth scoping
   before cutover rather than after.
3. **One firm per deployment, or true multi-tenant?** `firm_id` is present
   either way. If it's one firm per deployment, you never need the RLS
   policies and the column is just cheap insurance.
