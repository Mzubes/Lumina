# Private Markets OS — MVP Blueprint

## Objective
Build a demonstrable end-to-end operational bridge for private-market allocators, spanning pre-trade manager diligence through post-trade document processing and downstream data delivery.

## MVP demo journey
1. Upload GP/fund materials (PPM, DDQ, track record, financials, team bios).
2. Classify and parse documents.
3. Extract structured manager/fund facts with source citations and confidence.
4. Run diligence checks, identify missing information and contradictions.
5. Generate an investment thesis and draft IC memo.
6. Record an allocation/commitment decision.
7. Upload a post-trade document such as a capital call, distribution or quarterly statement.
8. Extract transaction/portfolio facts.
9. Validate against canonical fund, commitment and portfolio records.
10. Surface exceptions for human approval.
11. Update portfolio state.
12. Export normalized data through API/CSV/webhook abstractions.

## Core product modules

### Pre-trade
- Opportunity / GP intake
- Document ingestion
- GP and fund profile extraction
- DDQ extraction
- Track-record extraction
- Team/person extraction
- Strategy and mandate analysis
- Fees and terms extraction
- ESG / operational diligence extraction
- Missing-data detection
- Contradiction detection
- Evidence/citation viewer
- GP risk flags
- Benchmarking and peer comparison
- Investment thesis workspace
- IC memo generation
- IC red-team / challenge mode
- Allocation recommendation
- Decision log

### Post-trade
- Capital call ingestion
- Distribution ingestion
- Quarterly statement ingestion
- Investor-letter ingestion
- Valuation / NAV extraction
- Portfolio company / asset extraction
- Commitment and transaction ledger
- Validation rules
- Reconciliation
- Exception queue
- Human approval workflow
- Portfolio position updates
- Historical document/versioning
- Audit trail
- Downstream export/API/webhook layer

### Cross-cutting intelligence
- OCR and layout-aware parsing
- Structured extraction
- Entity resolution
- Canonical data model
- Confidence scoring
- Provenance for every material fact
- Semantic search / RAG
- Natural-language copilot
- Workflow orchestration
- Role-based approvals

## Canonical entities
Organization, User, Manager, Fund, Vehicle, Investment, Commitment, Transaction, CapitalCall, Distribution, Valuation, PortfolioPosition, Document, DocumentVersion, ExtractedFact, Validation, Workflow, WorkflowTask, InvestmentThesis, ICMemo, SourceCitation.

## Data provenance requirement
Every material extracted fact should retain: value, source document, page/section when available, source location/bounding box when available, confidence, extraction method, timestamps and approval state.

## Initial architecture
- Frontend: Next.js + TypeScript
- API: Python + FastAPI
- Database: PostgreSQL
- Vector search: pgvector initially
- Object storage: S3-compatible storage
- Document intelligence: managed OCR/layout extraction initially
- LLM: structured extraction + reasoning + RAG
- Validation: deterministic rules first, LLM-assisted checks second
- Background processing: queue/worker architecture
- Auth: managed authentication
- Deployment: Vercel + managed backend infrastructure
- CI/CD: GitHub Actions

## MVP principles
1. Build a vertical slice, not a monolith.
2. The LLM is not the system of record.
3. Deterministic validation must sit alongside probabilistic AI extraction.
4. Every important AI-derived fact needs evidence.
5. Start with sample documents; integrations come later.
6. Optimize for a compelling allocator workflow and measurable accuracy.

## First acceptance criteria
- A GP document bundle can be uploaded and processed.
- At least 50–100 useful fields can be extracted into a canonical schema.
- Users can inspect the evidence supporting extracted facts.
- Contradictions and missing fields are surfaced.
- A diligence summary and draft IC memo can be generated.
- A capital call can be ingested and linked to the correct fund/commitment.
- Basic validation can flag a mismatch.
- Approved post-trade data changes portfolio state.
- A normalized export can be generated.
