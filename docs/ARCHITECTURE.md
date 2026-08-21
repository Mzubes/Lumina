# Private Markets OS — Technical Architecture

## System flow

```text
Documents / User Input
        |
        v
Ingestion API -> Object Storage
        |
        v
Classification + OCR/Layout Parsing
        |
        v
Extraction Pipeline -> Structured Facts + Evidence
        |
        +--------------------+
        |                    |
        v                    v
Canonical PostgreSQL     Vector / Semantic Index
        |                    |
        +---------+----------+
                  |
                  v
        Validation / Reconciliation
                  |
          +-------+-------+
          |               |
          v               v
      Workflow        AI Copilot/RAG
          |               |
          +-------+-------+
                  |
                  v
             User UI / API
                  |
                  v
       Export / Webhook / Downstream
```

## Service boundaries
- `web`: Next.js application and workflow UI.
- `api`: FastAPI service exposing domain and ingestion APIs.
- `worker`: asynchronous document/extraction/validation jobs.
- `db`: PostgreSQL + pgvector.
- `storage`: original files and derived artifacts.

## AI boundaries
AI is used for classification, extraction, summarization, comparison and reasoning. Deterministic code owns identifiers, financial calculations, validation rules, state transitions and approvals.

## Security direction
Design for tenant isolation, least privilege, encryption in transit/at rest, immutable audit events, document access controls and configurable retention. Do not place production investor documents or secrets in source control.

## Initial API concepts
- `POST /documents`
- `GET /documents/{id}`
- `POST /documents/{id}/process`
- `GET /facts?entity_id=`
- `GET /facts/{id}/evidence`
- `POST /diligence/{manager_id}/run`
- `POST /ic-memos`
- `POST /commitments`
- `POST /capital-calls`
- `POST /validations/run`
- `GET /exceptions`
- `POST /exceptions/{id}/resolve`
- `GET /portfolio`
- `POST /exports`

## Build sequence
1. Domain schema + seed data.
2. Document upload/storage.
3. Extraction pipeline with evidence.
4. Pre-trade diligence workspace.
5. IC memo generation.
6. Commitment and allocation state.
7. Capital call ingestion.
8. Validation/reconciliation.
9. Portfolio view.
10. Export layer.
