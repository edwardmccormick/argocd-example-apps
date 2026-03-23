# Failure Drill: AI Service Internal Application Failure

This drill intentionally degrades the AI document-QA service without taking the pod down. The goal is to exercise detection of an application-behavior failure rather than an infrastructure failure.

## Objective

Validate that the platform can detect when the AI service remains healthy at the HTTP level but stops producing useful grounded answers for normal requests.

This is the more interesting AI reliability case:

- the pod is still running
- readiness and liveness still pass
- `/ask` still returns structured JSON
- but the workflow quality has degraded and the service is no longer doing its intended job well

## Steady-State Hypothesis

Before the drill starts, the system should satisfy these conditions:

- `ai-reliability` is `Synced` and `Healthy` in Argo CD
- the AI service pod is ready and responding on `/healthz`, `/readyz`, and `/ask`
- scheduled or manual baseline traffic is reaching the service
- `Workflow Completion Ratio` is stable and near its normal baseline
- `Structured Output Validity` is stable and near `100%`
- `Insufficient Context Ratio` is low

If those are not true before injection, the drill is mixing an existing reliability problem with the failure you are trying to study.

## Hypothesis

If key corpus documents are removed but the service process stays healthy, the system should continue returning valid HTTP and valid JSON while semantic quality degrades. The main visible change should be a rise in `insufficient_context` outcomes and a fall in workflow-completion signals, not a pod crash or transport outage.

## Preconditions

- `ai-reliability` is healthy and synced in Argo CD
- Prometheus and Grafana are running in the `observability` namespace
- the `AI Doc QA Overview` dashboard is reachable
- the `ai-docqa-load-generator` CronJob has been synced and is generating baseline traffic
- automated sync, prune, and self-heal are enabled for the root app and the AI application

## Failure Injection

Remove the high-value corpus documents from [`platform/ai-reliability/kustomization.yaml`](./platform/ai-reliability/kustomization.yaml#L1) so the mounted corpus no longer contains the material needed to answer the normal evaluation and load-generator questions.

For example, remove these entries from the `ai-reliability-corpus` generator:

```yaml
- corpus/README.md
- corpus/observability-baseline.md
- corpus/failure-drill-guestbook-readiness.md
- corpus/trivy-and-smoketest-notes.md
```

Commit and push the change so Argo CD reconciles it.

This is intentionally an internal application failure:

- the service still starts
- the service still responds
- the response structure remains valid
- but the semantic usefulness of the workflow drops sharply because the corpus no longer supports the normal queries

## Expected Symptoms

- `kubectl get pods -n ai-lab` still shows the AI service pod as ready
- `GET /healthz` and `GET /readyz` still succeed
- `POST /ask` still returns JSON, but most requests now produce `result: insufficient_context`
- the AI load generator continues sending traffic successfully
- `ai_docqa_requests_total{status="insufficient_context"}` increases
- `ai_docqa_workflow_completions_total{result="success"}` drops relative to total requests
- `ai_docqa:workflow_completion_ratio:5m` declines
- `ai_docqa_retrieval_hits_total` may flatten or fall
- Grafana continues to show a live service, but with degraded workflow quality rather than a hard outage

This is precisely the kind of failure mode that matters in AI systems. A healthy pod and a 200 response do not necessarily mean the feature is working.

## Detection Path

1. Check Argo CD application health for `ai-reliability`
2. Confirm the pod in `ai-lab` is still ready
3. Send a manual request:
   ```bash
   curl -H 'Host: ai-lab.localhost' \
     -H 'Content-Type: application/json' \
     -d '{"question":"What does the validation workflow enforce before merge?"}' \
     http://localhost:8080/ask
   ```
4. Confirm the response now reports `insufficient_context`
5. Review Grafana:
   - `Workflow Completion Ratio`
   - `Structured Output Validity`
   - `Request Outcomes`
   - `Citation Throughput`
6. Confirm the Prometheus alert state for AI service degradation

## Recovery Path

1. Restore the removed corpus entries in Git
2. Commit and push the revert
3. Let Argo CD resync automatically, or manually sync if needed
4. Confirm the AI service pod reloads with the restored corpus `ConfigMap`
5. Re-run a known question and confirm the result returns to `success`
6. Confirm the AI workflow metrics recover in Grafana

Do not patch the live deployment directly unless Git reconciliation is broken and the drill has shifted into incident mitigation mode.

## Abort Conditions

Stop the drill and recover immediately if any of these happen:

- the AI pod fails readiness or liveness instead of staying operational
- `/ask` starts returning transport errors rather than semantic degradation
- the service becomes unavailable through ingress or service DNS
- Argo CD or Prometheus is degraded badly enough that you cannot observe the drill

## Follow-Up Hardening

- Add an explicit SLI for `insufficient_context` rate so semantic degradation is easier to see at a glance
- Add an alert tied directly to `ai_docqa:workflow_completion_ratio:5m`
- Expand the replay and eval set so important query categories are better represented
- Distinguish between transport success and semantic success in dashboards and runbooks
- Add a second drill that returns malformed JSON or server-side errors to exercise structured-output and HTTP error signals separately
