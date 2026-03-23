# Failure Drill: AI Canary Semantic Regression

This drill intentionally introduces a semantic regression into the canary path for the AI document-QA service while keeping the service healthy at the HTTP and pod levels. The goal is to validate that progressive delivery blocks promotion when AI workflow quality drops, even if transport-level health still looks fine.

## Objective

Validate that the Argo Rollouts canary analysis rejects a new AI release when the canary remains operational but starts returning low-value `insufficient_context` responses for normal grounded questions.

This is the exact failure mode progressive delivery is supposed to catch:

- the canary pod starts and becomes ready
- `/healthz` and `/readyz` still pass
- `/ask` still returns valid JSON
- but semantic usefulness degrades enough that promotion should stop

## Steady-State Hypothesis

Before the drill starts, the system should satisfy these conditions:

- `ai-reliability` is `Synced` and `Healthy` in Argo CD
- the Rollout is fully promoted, with no active `AnalysisRun`
- both stable and canary metrics are present in Prometheus when traffic is generated
- `Workflow Completion Ratio` is stable near its baseline
- `Structured Output Validity` is stable near `100%`
- `Insufficient Context Ratio` is low for normal traffic
- the canary analysis template is passing on ordinary deploys

If those conditions are not true before injection, the drill is testing a noisy baseline rather than a controlled regression.

## Hypothesis

If the canary version loses access to the key corpus material needed for normal grounded questions, Argo Rollouts should keep the new version from promoting. Transport-level checks should remain green, but canary-only quality signals such as workflow completion and insufficient-context ratio should fail the analysis.

## Preconditions

- `argo-rollouts` is healthy in Argo CD
- `ai-reliability` is healthy and managed as a `Rollout`
- Prometheus is scraping `ai-docqa-stable` and `ai-docqa-canary`
- the `AI Doc QA Overview` dashboard is reachable
- the `ai-docqa-load-generator` CronJob is running or you are prepared to generate manual AI traffic

## Failure Injection

Introduce a canary-only semantic regression by changing the mounted corpus or application behavior in a way that preserves transport health but harms grounding.

The cleanest version in this lab is:

1. Modify the AI workload so the new release omits one or more high-value corpus documents used by the canary analysis questions.
2. Keep the server process, readiness, and response schema unchanged.
3. Commit and push the change so Argo CD starts a new rollout.

A realistic example would be removing these corpus entries from the new release payload:

```yaml
- corpus/README.md
- corpus/observability-baseline.md
- corpus/trivy-and-smoketest-notes.md
```

That should preserve startup and HTTP behavior while making the canary materially worse at answering the rollout-analysis questions.

## Expected Behavior During Failure

- the new canary ReplicaSet starts normally
- canary `/readyz` remains healthy
- Argo Rollouts creates an `AnalysisRun`
- the web checks may still pass if the service remains structurally healthy
- one or more quality gates should fail:
  - `canary-workflow-completion`
  - `canary-insufficient-context`
  - grounded `/ask` checks against known questions
- rollout promotion should pause or fail before full traffic shift
- stable traffic should continue serving through `ai-reliability-stable`
- stable metrics should remain normal while canary metrics degrade

This is the key distinction the drill is meant to prove: the release is blocked for quality reasons, not because Kubernetes could not keep the pod alive.

## Detection Path

1. Check rollout status:
   ```bash
   kubectl get rollout -n ai-lab ai-reliability
   kubectl argo rollouts get rollout ai-reliability -n ai-lab
   ```
2. Inspect the active analysis:
   ```bash
   kubectl get analysisruns -n ai-lab
   kubectl describe analysisrun -n ai-lab <analysisrun-name>
   ```
3. Compare stable and canary traffic manually:
   ```bash
   curl -sS -H 'Content-Type: application/json' \
     -d '{"question":"What operational value did the Trivy and smoke-test notes describe?"}' \
     http://ai-reliability-stable.ai-lab.svc.cluster.local:8080/ask

   curl -sS -H 'Content-Type: application/json' \
     -d '{"question":"What operational value did the Trivy and smoke-test notes describe?"}' \
     http://ai-reliability-canary.ai-lab.svc.cluster.local:8080/ask
   ```
4. Review Grafana and compare:
   - stable vs canary request outcomes
   - stable vs canary workflow completion
   - stable vs canary insufficient-context rate
   - stable vs canary latency
5. Confirm Argo Rollouts did not fully promote the canary

## SLO Impact

- Transport-level availability should remain largely unaffected because stable continues serving traffic.
- AI workflow quality for canary traffic should degrade.
- Error-budget impact should be limited to the canary slice rather than the full service.
- The drill is successful if promotion is blocked before the degraded behavior becomes the stable version.

## Recovery Procedure

1. Revert the corpus or behavior change in Git.
2. Commit and push the fix.
3. Let Argo CD reconcile automatically, or manually sync if needed.
4. Confirm a new rollout starts from the corrected desired state.
5. Verify the next `AnalysisRun` passes.
6. Confirm the rollout fully promotes and stable/canary metrics converge again.

Do not patch the live rollout or services directly unless Git reconciliation is broken and the drill has shifted into incident mitigation mode.

## Abort Conditions

Stop the drill and recover immediately if any of these happen:

- stable traffic is impacted instead of only canary traffic
- the stable service becomes unavailable
- rollout analysis stops functioning because Prometheus or Rollouts is degraded
- the canary fails for transport reasons rather than semantic-quality reasons

## What This Drill Validates

- Argo Rollouts is enforcing AI-quality promotion gates rather than only transport checks
- stable and canary metrics are separated well enough to make promotion decisions defensibly
- the system can absorb a bad AI release without turning it into the new stable version
- GitOps recovery remains the operational path even during progressive-delivery failure handling

## Follow-Up Hardening

- Add explicit Grafana panels comparing stable and canary workflow completion and insufficient-context ratio side by side
- Expand the canary analysis question set so it covers more than two grounded business questions
- Add a replay-based live canary probe that runs a small eval bundle instead of only single-question checks
- Add alerting for stalled rollouts caused by failed semantic analysis
