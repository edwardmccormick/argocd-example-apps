# TODO

This file is the forward-looking roadmap for the lab. The goal is not to collect every good idea. The goal is to keep the next steps aligned with the current shape of the repo: local, GitOps-driven, reliability-focused, and interview-useful.

## Completed

### Progressive Delivery With Real Quality Gates

Done. Argo Rollouts canary is running with a multi-stage promotion sequence (20% → 50% → 100%) gated on Prometheus analysis metrics: workflow completion rate ≥ 95%, insufficient-context rate ≤ 10%, and functional QA checks against known questions. Metrics that were "observed after deploy" are now "used during deploy."

### AI Replay / Analysis Against A Live Candidate

Done in initial form. `replay_cases.json` captures known-input / expected-output cases. The canary analysis template uses live `/ask` calls against specific questions as promotion gates. The foundation is in place; expanding the case set is the next layer (see below).

---

## Next Up

### LLM Backend Integration (Thin Wrapper)

Add an optional generative mode to the AI service alongside the existing extractive mode. The extractive engine stays — it is fast, local, and deterministic. The generative mode adds a real LLM call (Claude or OpenAI) so that the AI-specific reliability patterns the lab demonstrates (hallucination monitoring, grounding checks, token accounting, model degradation) apply to a probabilistic output substrate, not just a retrieval engine.

Why it matters:

- the extractive service demonstrates the right vocabulary (SLIs, structured output validity, workflow completion rate) but the failure modes are deterministic — there is no hallucination risk, no model drift, no prompt regression
- a technical interviewer asking about AI reliability will expect those terms to map to generative outputs; "the service is extractive" is an accurate answer but not the strongest one
- the generative mode is the substrate that makes LangSmith tracing, adversarial probes, and regression prompt suites meaningful

Target shape:

- `?mode=generative` query param (or request body field) routes to an LLM call instead of the extractive engine
- same response schema — `grounded`, `result`, `citations`, `token_usage` — so existing metrics and dashboards require no changes
- grounding check: does the response cite something present in the retrieved chunks? flag `grounded: false` if not
- `token_usage` switches from estimated to actual (from API response metadata)
- extractive mode remains the default and the CI smoke test target (no API key required in CI)

Priority note:

- this is the highest-value next item because it unlocks everything below it — adversarial probes, LangSmith traces, and real cost modeling all require generative outputs
- it does not require replacing or rewriting anything that exists

### Expand and Deepen the Eval Suite

The current eval suite has three cases. Expand it to 15–20 curated cases covering the full range of failure modes the service should handle.

Why it matters:

- three cases proves the service boots and returns a result; it does not prove the retrieval logic is robust or that the grounding check is meaningful
- a 15–20 case suite with structured categories reads as an "LLM evaluation pipeline" in an interview; three cases does not
- the categories matter as much as the count — see target shape below

Target shape:

- **Retrieval relevance cases** — questions with a clearly correct source document; verify the right chunk is ranked first
- **Grounding accuracy cases** — questions where the answer must cite retrieved context; verify `grounded: true` and that the citation excerpt contains the answer
- **Structured output validity cases** — verify the response schema is always populated correctly, even on edge-case inputs
- **Insufficient context cases** — questions that are deliberately out of scope; verify `result: insufficient_context` rather than a hallucinated answer
- **Adversarial / robustness cases** — malformed input, empty question string, very long question, prompt injection attempt; verify the service returns a valid schema rather than crashing or leaking internal state
- pass/fail threshold per category surfaced in CI output (not just aggregate pass rate)

Priority note:

- once the generative mode exists, run the same suite against both modes and compare grounding accuracy rates — that comparison is a strong interview artifact

### Add Steady-State Hypothesis Structure to Failure Drills

The failure drill documents describe how to induce and observe specific failures. Add a structured preamble to each drill so they read as game day designs rather than break-fix runbooks.

Why it matters:

- the gap between "here is how to break it" and "here is a chaos engineering exercise" is mostly framing — the steady-state hypothesis, the SLO being observed during failure, and the expected recovery behavior
- an interviewer asking about chaos engineering experience can be answered with these documents; they need the right structure to support that answer

Target shape for each drill document:

```
## Steady-State Hypothesis
[What does normal look like: P99 latency target, error rate, workflow completion rate, ArgoCD sync status]

## Failure Injection
[What to change and how]

## Expected Behavior During Failure
[What signals should degrade, what should not]

## Recovery Procedure
[Runbook steps]

## SLO Impact
[Which SLIs are affected, what the error budget cost is, what the expected recovery time is]

## What This Drill Validates
[What confidence this gives us about the system]
```

Priority note:

- low effort, high interview value — the content already exists; this is a restructuring exercise

### Feed CI Eval Scores Into Grafana

The eval runner produces pass/fail output in CI. Surface that signal in the AI DocQA Grafana dashboard as a time-series of eval pass rate by commit or by day.

Why it matters:

- "quality dashboards surfacing AI evaluation scores to leadership" is a named JD requirement
- the eval infrastructure exists; the wiring to a visible dashboard does not
- a screenshot of a Grafana panel showing eval pass rate over time is a stronger artifact than describing the CI output in words

Target shape:

- on each CI run, push a metric to a Prometheus pushgateway or write a line to a time-series store
- Grafana panel: eval pass rate (%) over time, broken down by category if feasible
- threshold line at the gate value so regressions are visually obvious

Priority note:

- depends on eval suite expansion above — worth doing together rather than as two separate efforts

---

## Good Follow-On Work

### Event-Driven Scaling

Add a queue-backed workload and autoscale it with KEDA.

Why it matters:

- demonstrates asynchronous workload behavior instead of only request/response services
- creates a stronger scaling story than replica counts alone
- gives the lab a realistic way to discuss lag, backlog, throughput, and scaling signals

Target shape:

- lightweight producer / consumer pair
- visible queue depth or lag metric
- KEDA-driven scaling policy
- Grafana view that correlates load, lag, and replica count

Priority note:

- valuable, but less directly aligned to the current AI quality thread than the items above

### ApplicationSet Expansion

Add an `ApplicationSet` example for multi-service or multi-environment generation.

Why it matters:

- useful for talking about scale beyond a single app or cluster
- good way to discuss templated onboarding and Git-driven fleet management
- relevant to real Argo CD usage in larger organizations

Target shape:

- generate multiple child Applications from a Git directory or cluster list
- optionally show environment fan-out such as local / staging / prod
- keep the example narrow enough that it does not overwhelm the repo

Priority note:

- strong interview topic
- not the best immediate implementation target unless the repo is intentionally moving toward multi-app fleet management

### Secret Management

Add an external secret pattern instead of assuming low-secret local operation.

Why it matters:

- GitOps secret handling is a real platform question
- this repo currently avoids most secrets rather than demonstrating how to manage them well
- it creates a good discussion about separation of desired state from secret values

Possible target shape:

- External Secrets Operator pattern
- local secret store simulation or documented cloud-backed reference design
- Argo CD manages secret references, not literal secret values

Priority note:

- valuable as an interview talking point
- harder to make clean and local than the items above

---

## Useful Discussion Topics Even If Not Implemented

These are worth understanding and being able to speak to, even if the repo never grows far enough to implement them all.

### LangSmith Tracing

Once the generative mode exists, instrument it with LangSmith: one span per request capturing the prompt sent, retrieved chunks, model response, token count, and latency at each step. A single LangSmith trace screenshot changes "I understand LLM observability" to "here is the trace."

### AI Cost Modeling

With real token usage from a generative mode, build a cost-per-query model: at current token prices, what does each workflow run cost? What does a 10% reduction in average token count save at scale? That framing is the model routing strategy conversation — when do you use a smaller model?

### Multi-Environment Promotion

- environment branches or promotion repos
- immutable artifact promotion between stages
- separation of CI validation from production deployment decisions

### Policy As Code

- enforce probes, security context, resource requests/limits
- reject mutable image tags
- encode cluster standards instead of relying on review discipline

### Supply Chain Hardening

- pinning actions by SHA
- verifying checksums or signatures
- internal artifact mirrors
- minimizing privileged CI workflows and secrets

### Control Plane Hardening

- Git-manage more of the Argo CD install itself
- remove live-only patches where practical
- continue reducing restart-time brittleness and reconciliation blind spots

---

## What To Avoid Right Now

- adding too many controllers at once without a clear story
- turning the lab into a generic platform zoo
- implementing features that are mechanically interesting but not tied to current service metrics or reliability goals
- building LangSmith / adversarial probes / cost modeling before the generative mode exists — those features require probabilistic outputs to be meaningful

Short version:

1. Add a thin LLM backend so the AI-specific reliability patterns apply to generative outputs.
2. Expand the eval suite to 15–20 cases with structured failure mode categories.
3. Add steady-state hypothesis framing to the failure drill documents.
4. Wire eval pass rate into Grafana.
5. Treat event-driven scaling, ApplicationSets, and secret management as the next layer after those four are done.
