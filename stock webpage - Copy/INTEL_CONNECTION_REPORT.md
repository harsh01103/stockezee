# Intel Connection Report

## Summary

The retrieval engine and intelligence UI are now connected to verified document data instead of local placeholder constants.

## Phase 1 - Retrieval Score

Status: Complete.

- `getCompanyIntel()` now computes retrieval score as:
  `base * primary multiplier * freshness * quality * duplicate penalty`
- Scores are persisted on every ranking run into `company_documents.retrieval_score`.
- Scores are also written to `company_document_features.retrieval_score` when the migration has been applied.
- Legacy feature rows without `document_id` are matched back to `company_documents` by symbol/source so existing data can still update document scores.

## Phase 2 - Remove Fallback Intel

Status: Complete.

- Removed UI mock constants from `CompanyIntelPanel`.
- Project search found no remaining code references for the named placeholder sentiment, tone, catalyst, and risk values from the fix request.
- Cleaned 8 legacy Supabase feature rows containing the named placeholder values.
- Empty UI state now renders `NO VERIFIED DOCUMENTS`.

## Phase 3 - Feature Table

Status: Migration prepared.

`server/migrations/06_intel_connection.sql` now ensures `company_document_features` contains:

- `document_id`
- `confidence`
- `tone`
- `risk`
- `evidence`
- `retrieval_score`

It also adds a foreign key to `company_documents`, a unique index for `document_id`, and read policies needed by the UI join.

Important: the live Supabase schema cache currently does not expose the feature-to-document relationship and is missing some feature columns. Run `server/migrations/06_intel_connection.sql` in Supabase SQL Editor, then rerun the pipeline so feature-level scores populate.

## Phase 4 - UI Source Of Truth

Status: Complete in code.

- `CompanyIntelPanel` now queries `company_document_features` joined to `company_documents`.
- It orders by `retrieval_score`.
- It never renders local constants or mock intelligence.
- If the join is unavailable or no ranked verified row exists, it shows `NO VERIFIED DOCUMENTS`.

## Phase 5 - Evidence Mode

Status: Complete.

The UI now shows:

- Document type
- Published date
- Source
- Confidence
- Top evidence

## Phase 6 - Validation

Command run:

```bash
node server/scripts/validate_pipeline.js
```

Result:

- `RELIANCE`: Annual report, score `53.91`, cautious tone, verified RIL annual report source.
- `SBIN`: Filing, score `56.90`, cautious tone, verified BSE financial-results source.
- `WIPRO`: Filing, score `56.90`, neutral tone after placeholder cleanup, verified NSE press-release source.
- Outputs are different.
- No identical catalysts were returned.

## Phase 7 - SQL Validation

Requested query equivalent:

```sql
select
symbol,
origin_type,
content_quality,
retrieval_score
from company_documents
order by retrieval_score desc;
```

Top persisted results after validation:

| symbol | origin_type | content_quality | retrieval_score |
| --- | --- | ---: | ---: |
| SBIN | FILING | 95 | 56.90 |
| WIPRO | FILING | 95 | 56.90 |
| RELIANCE | ANNUAL_REPORT | 90 | 53.91 |
| SBIN | PRESENTATION | 80 | 47.92 |
| WIPRO | TRANSCRIPT | 75 | 44.92 |
| SBIN | NEWS | 0 | 7.49 |
| WIPRO | NEWS | 0 | 7.49 |
| RELIANCE | NEWS | 0 | 7.46 |

Conclusion: `retrieval_score` is no longer all zero.

## Validation Notes

- `node --check server/services/docintel/pipeline.js` passed.
- Focused TypeScript check passed with unrelated unused-symbol rules disabled:
  `npm --prefix app exec tsc -- -p app/tsconfig.app.json --noUnusedLocals false --noUnusedParameters false`
- Full app build is currently blocked by an unrelated existing error:
  `src/features/quality/components/UniverseHealth.tsx(2,1): 'axios' is declared but its value is never read.`
