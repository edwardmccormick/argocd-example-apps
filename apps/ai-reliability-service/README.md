# AI Reliability Service

This directory is a lightweight entry point for the AI reliability workload.

The canonical deployable implementation now lives in [`platform/ai-reliability`](../../platform/ai-reliability).

That workload intentionally starts small:

- corpus-backed retrieval over this repository's own operational notes
- deterministic, structured JSON responses
- Prometheus-friendly service metrics for latency, workflow completion, and structured-output validity
- a small deterministic eval dataset that can run in CI without external model access

The initial deployment mode is extractive rather than generative. That is deliberate. It gives the lab a grounded workload that can be evaluated and observed locally before introducing a remote LLM dependency.
