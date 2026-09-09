# Generation Specifications

## Pipeline: Two-Stage Structured Reasoning
1. **Stage A (Structured Reasoning)**: Generate argument via LLM in specific JSON schema (`reasoning_type`, `premise_1`, `premise_2`, `conclusion`, `validity_explanation`).
2. **Stage B (Natural Language Realization)**: Convert to text only AFTER validation of structural components.

## Validation Criteria
- Schema integrity (all required reasoning fields present).
- Argument length > 10 words.
- Presence of explicit inferential markers (e.g., "Therefore").
- Exclusion of bare citations or isolated factual statements.
- Diversity tracking for `reasoning_type` (Max 30% per type).
