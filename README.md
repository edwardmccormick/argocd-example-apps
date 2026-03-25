# Local Reliability Lab

This repository is a local GitOps and reliability-engineering lab built around `k3d/k3s`, Argo CD, Helm, Prometheus, Grafana, and a small AI document-QA service. It is meant to show how platform changes are validated, deployed, observed, and recovered through Git rather than through manual cluster drift.

## Run Locally

### Prerequisites

- Docker or Docker Desktop with enough resources to run `k3d` and Argo CD
- `kubectl`
- `k3d`
- optional but useful: `argocd` CLI

### Create The Cluster

Run from WSL or a Linux shell:

```bash
k3d cluster create my-practice-cluster -p "8080:80@loadbalancer" --agents 2
```

This exposes Traefik on `localhost:8080`.

### Install Argo CD

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl apply -f argocd-ingress.yaml
```

Initial admin password:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
```

### Bootstrap The Lab

Apply the root Argo CD application:

```bash
kubectl apply -f platform/argocd/root-application.yaml
```

That bootstrap manifest also patches `argocd-server` to run with `--insecure` so local HTTP routing on `localhost:8080` works without manual Argo CD patching.

That root app targets [`environments/local`](./environments/local), which creates:

- the `local-lab` Argo CD project
- the `argo-rollouts` controller application
- the Helm-backed guestbook application
- the observability stack application
- the AI reliability application

Repo-backed Argo CD applications track the protected `main` branch rather than the repo default branch implicitly.

Optional but recommended for CI-eval metric polling reliability (or private forks): create a GitHub token secret in `observability` using [`platform/observability/ci-eval-metrics-secret.example.yaml`](./platform/observability/ci-eval-metrics-secret.example.yaml) or directly:

```bash
kubectl create secret generic ai-ci-eval-metrics \
  -n observability \
  --from-literal=github-token='replace-me' \
  --dry-run=client -o yaml | kubectl apply -f -
```

This token is optional for public repositories but helps avoid unauthenticated API rate limits. The polling path runs inside the cluster as the `ai-ci-eval-metrics` CronJob and pushes to `pushgateway` for Prometheus scraping.

If you want the AI image pinning workflow to commit directly to `main` while keeping PR-required protections for normal users, create a private GitHub App, install it on this repository, add that app to the `main` ruleset bypass list, and set:

- repository variable `AI_IMAGE_PINNER_APP_ID` (preferred) or repository secret `AI_IMAGE_PINNER_APP_ID`
- repository secret `AI_IMAGE_PINNER_PRIVATE_KEY`

This lab keeps that app intentionally narrow: it only needs write access to [`platform/ai-reliability/kustomization.yaml`](./platform/ai-reliability/kustomization.yaml) and [`platform/ai-reliability/rollout.yaml`](./platform/ai-reliability/rollout.yaml), plus read access to actions, commit statuses, and metadata. That is enough for the post-merge image pin without giving automation broad repo write access.

That narrow scope is a deliberate tradeoff. It is safer for the current repo shape, but future refactors need to preserve or consciously expand those paths if the image-pin workflow ever needs to touch different files.

For the helper action in [`.github/workflows/build-ai-image.yaml`](./.github/workflows/build-ai-image.yaml), `AI_IMAGE_PINNER_APP_ID` should be the numeric GitHub App ID, not the client ID.

### Access

Traefik routes everything through `localhost:8080` by host header:

- `http://argocd.localhost:8080`
- `http://guestbook.localhost:8080`
- `http://grafana.localhost:8080`
- `http://prometheus.localhost:8080`
- `http://ai-lab.localhost:8080`

If local hostname resolution is awkward on Windows, you can still test directly with curl:

```bash
curl -H 'Host: ai-lab.localhost' http://localhost:8080/
```

The AI service is an API, not a browser UI. Its primary route is:

```bash
curl -H 'Host: ai-lab.localhost' \
  -H 'Content-Type: application/json' \
  -d '{"question":"What does the validation workflow enforce before merge?"}' \
  http://localhost:8080/ask
```

Optional generative mode is also available. The service keeps extractive mode as the default and CI-safe path, but can call the Gemini API when a key is provided.

Create the secret from [`platform/ai-reliability/llm-secret.example.yaml`](./platform/ai-reliability/llm-secret.example.yaml) or directly:

```bash
kubectl create secret generic ai-reliability-llm \
  -n ai-lab \
  --from-literal=gemini-api-key='replace-me' \
  --dry-run=client -o yaml | kubectl apply -f -
```

If you also want LangSmith tracing, create or update that same secret with the LangSmith values as well:

```bash
kubectl create secret generic ai-reliability-llm \
  -n ai-lab \
  --from-literal=gemini-api-key='replace-me' \
  --from-literal=langsmith-api-key='replace-me' \
  --from-literal=langsmith-workspace-id='optional-workspace-id' \
  --dry-run=client -o yaml | kubectl apply -f -
```

Then set `GEMINI_MODEL` in [`platform/ai-reliability/rollout.yaml`](./platform/ai-reliability/rollout.yaml) to the model you want, sync `ai-reliability`, and call:

```bash
curl -H 'Host: ai-lab.localhost' \
  -H 'Content-Type: application/json' \
  -d '{"question":"What does the validation workflow enforce before merge?","mode":"generative"}' \
  http://localhost:8080/ask
```

The generative path includes a short bounded retry/backoff policy for transient provider saturation (`429`/`503`/similar upstream failures). The defaults are configured in [`platform/ai-reliability/rollout.yaml`](./platform/ai-reliability/rollout.yaml) through `GEMINI_MAX_ATTEMPTS` and `GEMINI_RETRY_BASE_DELAY_SECONDS`.

Canary analysis burst traffic defaults to extractive mode. To include a generative slice during canary analysis, set `canary-generative-ratio` in [`platform/ai-reliability/analysis-template.yaml`](./platform/ai-reliability/analysis-template.yaml) to a value such as `0.1`.

An opt-in generative eval pack also lives in [`platform/ai-reliability/app/generative_eval_cases.json`](./platform/ai-reliability/app/generative_eval_cases.json). It is intentionally not part of CI because it needs a live Gemini key and the outputs are probabilistic rather than exact-string deterministic.

Run it locally with:

```bash
python3 ./platform/ai-reliability/app/run_eval.py \
  --corpus-dir ./platform/ai-reliability/corpus \
  --eval-file ./platform/ai-reliability/app/generative_eval_cases.json \
  --mode generative
```

Optional LangSmith tracing is also wired into the AI service. It is off by default and remains completely optional so the deterministic local path stays secret-free.

To enable it, populate `langsmith-api-key` in the same `ai-reliability-llm` Kubernetes secret and set `LANGSMITH_TRACING` to `"true"` in [`platform/ai-reliability/rollout.yaml`](./platform/ai-reliability/rollout.yaml). Optionally add `langsmith-workspace-id` if your account requires it.

This implementation emits:

- one root trace per `/ask` request
- one child retriever run containing retrieved documents and chunk ids
- one child LLM run for Gemini calls in generative mode

The trace captures the question, mode, top-k retrieval setting, selected chunks, answer preview, grounded/result status, citation ids, token usage, and latency. It uses a small direct HTTP client in [`platform/ai-reliability/app/tracing.py`](./platform/ai-reliability/app/tracing.py) so it fits the repo’s current no-packaging model.

## Implemented Features

### GitOps Delivery

- Argo CD app-of-apps bootstrap in [`platform/argocd`](./platform/argocd)
- environment-managed applications in [`environments/local`](./environments/local)
- automated sync with `prune` and `selfHeal`
- Helm-backed guestbook deployment from [`helm-guestbook`](./helm-guestbook)
- AI service image build-and-pin workflow in [`.github/workflows/build-ai-image.yaml`](./.github/workflows/build-ai-image.yaml), which builds to GHCR on `main` and commits a pinned digest back into Git using a GitHub App installation token

### Progressive Delivery

- Argo Rollouts canary delivery for `ai-reliability` with staged traffic (`20%` -> `50%` -> `100%`)
- analysis-gated promotion using readiness checks, grounded `/ask` checks, insufficient-context behavior, and canary metrics
- rollout-triggered canary burst traffic via analysis jobs so low-traffic environments still produce evaluable sample sizes
- minimum canary request-volume gating before semantic quality ratios are accepted

### Workloads

- `guestbook-ui`: a simple web workload used to exercise deployment, observability, and failure drills
- `ai-reliability`: a deterministic-by-default document-QA service in [`platform/ai-reliability`](./platform/ai-reliability) that supports:
  - grounded retrieval over a curated Markdown corpus
  - structured JSON responses
  - replayable eval cases
  - Prometheus-friendly latency and workflow metrics
  - an optional model-backed `generative` mode behind the same response schema
  - optional LangSmith traces for request, retrieval, and model steps

### Autoscaling

- `ai-reliability` scales horizontally through an HPA targeting the Rollout resource
- scale-up and scale-down behavior are tuned explicitly in [`platform/ai-reliability/hpa.yaml`](./platform/ai-reliability/hpa.yaml)
- repeatable local load generation for scale testing lives in [`scripts/trigger-ai-scale.sh`](./scripts/trigger-ai-scale.sh)

### Observability

- Prometheus, Grafana, Blackbox Exporter, and OpenTelemetry Collector in [`platform/observability`](./platform/observability)
- guestbook SLIs for availability and latency
- AI service SLIs for workflow completion and structured-output validity
- mode-split AI visibility for extractive versus generative behavior
- canary gate panels for request volume, workflow completion, and insufficient-context ratio
- Argo CD control-plane metrics and dashboarding
- CI deterministic eval pass-rate trends pulled from GitHub Actions into Prometheus and Grafana
- scheduled `k6` traffic for both guestbook and the AI service

More detail lives in [`platform/ai-reliability/corpus/observability-baseline.md`](./platform/ai-reliability/corpus/observability-baseline.md).

### Failure Drills

- guestbook readiness regression drill in [`docs/failure-drill-guestbook-readiness.md`](./docs/failure-drill-guestbook-readiness.md)
- AI internal application failure drill in [`docs/failure-drill-ai-internal-application-failure.md`](./docs/failure-drill-ai-internal-application-failure.md)
- AI canary semantic regression drill in [`docs/failure-drill-ai-canary-semantic-regression.md`](./docs/failure-drill-ai-canary-semantic-regression.md)

These drills are intentionally GitOps-oriented: the failure is introduced through Git, detected through metrics and dashboards, and recovered by reverting Git.

## Reliability And Quality In The Operational Flow

This repo is designed so reliability and QA are part of the normal delivery path, not a separate afterthought.

### Before Merge

GitHub Actions validates infrastructure and runtime behavior through:

- `helm lint`
- `helm template`
- Kustomize rendering
- YAML parsing
- Kubernetes schema validation
- Trivy config scanning
- AI service Docker image build validation
- deterministic AI eval execution
- deterministic AI eval summary artifact upload for downstream in-cluster polling
- an ephemeral `kind` smoke test for the guestbook chart
- an ephemeral `kind` smoke test for the AI service, including `/healthz`, `/readyz`, and `/ask`

The current validation workflow lives in [`.github/workflows/validate-manifests.yaml`](./.github/workflows/validate-manifests.yaml).

### After Merge

Protected `main` is the deployment source of truth. Argo CD reconciles from Git into the cluster. That means:

- manual cluster changes are not the persistent source of truth
- the AI service image is built after merge and then pinned back into the rollout manifest by digest, so the cluster deploys an immutable reviewed artifact rather than `latest`
- config changes in observability trigger pod rollouts through hashed Kustomize `ConfigMap` names
- Argo CD sync drift and repo-server failure are themselves observable

### Security And Supply Chain

The pipeline includes Trivy config scanning, but the more useful lesson was operational:

- scanners found real baseline hardening misses
- smoke tests caught runtime regressions that static checks missed
- CI dependency trust is itself a supply-chain problem

Those notes are captured in [`docs/trivy-and-smoketest-notes.md`](./docs/trivy-and-smoketest-notes.md).

## Repository Layout

- [`helm-guestbook`](./helm-guestbook): Helm chart for the guestbook workload
- [`platform/argocd`](./platform/argocd): Argo CD bootstrap manifest
- [`platform/observability`](./platform/observability): Prometheus, Grafana, OTEL collector, load generation, and dashboards
- [`platform/ai-reliability`](./platform/ai-reliability): AI reliability service, corpus, and deployment manifests
- [`environments/local`](./environments/local): Argo CD-managed local environment definitions
- [`apps/guestbook`](./apps/guestbook): guestbook notes
- [`apps/ai-reliability-service`](./apps/ai-reliability-service): lightweight entry point for the AI workload

## Current Focus

The lab is now far enough along that the next valuable work is less about basic cluster setup and more about service behavior:

- adding queue-backed event-driven scaling and backlog-aware autoscaling signals
- adding a practical external secret pattern for GitOps-managed secret references
- improving upstream model resilience with bounded retry/backoff and fallback behavior
- turning the generative eval path into a scheduled or promotion-aware signal rather than a purely manual one

Deferred work is tracked in [`TODO.md`](./TODO.md).
