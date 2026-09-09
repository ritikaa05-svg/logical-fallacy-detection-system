# LogiScan Reliability Audit

## High Risk Areas
- **Z3 Translation (Regex Fallback)**: The regex fallback uses heuristic stemming and variable mapping which can still fail on linguistically diverse premises (e.g., "The sun is shining" vs "Sunshine is occurring").
- **LLM Synthesis Quality**: SmollM-1.7B is compact but prone to shorter outputs or format divergence. The `[len(prompt):]` slicing is now safer but still relies on deterministic behavior from the model.

## Medium Risk Areas
- **Unified Model Shape Mismatch**: Partially mitigated — `ignore_mismatched_sizes=True` allows loading despite shape differences. Full resolution requires weight re-export.
- **Inference Latency**: Synthesis on CPU is ~1.5–3s per call (down from ~20s). Cold-start caching reduces first-run overhead.

## Low Risk Areas
- **API Contracts**: Pydantic v2 migration is complete and stable.
- **Caching**: Redis integration is verified and robust against service downtime.

## Recommended Future Work
1. **Z3 Predicate Logic**: Move the regex fallback toward a basic predicate logic parser to handle syllogisms like "All A are B".
2. **Synthesis Fine-Tuning**: Fine-tune SmolLM2-1.7B on fallacy-correction pairs to reduce prompt sensitivity and improve output quality.
3. **Unified Model Export**: Re-export the multi-head classifier weights to resolve remaining shape mismatch issues.
