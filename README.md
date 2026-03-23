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

That root app targets [`environments/local`](./environments/local), which creates:

- the `local-lab` Argo CD project
- the Helm-backed guestbook application
- the observability stack application
- the AI reliability application

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

Optional generative mode is also available. The service keeps extractive mode as the default and CI-safe path, but can call an OpenAI-compatible API when a key is provided.

Create the secret from [`platform/ai-reliability/llm-secret.example.yaml`](./platform/ai-reliability/llm-secret.example.yaml) or directly:

```bash
kubectl create secret generic ai-reliability-llm \
  -n ai-lab \
  --from-literal=openai-api-key='replace-me'
```

Then set `OPENAI_MODEL` in [`platform/ai-reliability/rollout.yaml`](./platform/ai-reliability/rollout.yaml) to the model you want, sync `ai-reliability`, and call:

```bash
curl -H 'Host: ai-lab.localhost' \
  -H 'Content-Type: application/json' \
  -d '{"question":"What does the validation workflow enforce before merge?","mode":"generative"}' \
  http://localhost:8080/ask
```

## Implemented Features

### GitOps Delivery

- Argo CD app-of-apps bootstrap in [`platform/argocd`](./platform/argocd)
- environment-managed applications in [`environments/local`](./environments/local)
- automated sync with `prune` and `selfHeal`
- Helm-backed guestbook deployment from [`helm-guestbook`](./helm-guestbook)

### Workloads

- `guestbook-ui`: a simple web workload used to exercise deployment, observability, and failure drills
- `ai-reliability`: a deterministic document-QA service in [`platform/ai-reliability`](./platform/ai-reliability) that supports:
  - grounded retrieval over a curated Markdown corpus
  - structured JSON responses
  - replayable eval cases
  - Prometheus-friendly latency and workflow metrics
  - an optional model-backed `generative` mode behind the same response schema

### Observability

- Prometheus, Grafana, Blackbox Exporter, and OpenTelemetry Collector in [`platform/observability`](./platform/observability)
- guestbook SLIs for availability and latency
- AI service SLIs for workflow completion and structured-output validity
- Argo CD control-plane metrics and dashboarding
- scheduled `k6` traffic for both guestbook and the AI service

More detail lives in [`docs/observability-baseline.md`](./docs/observability-baseline.md).

### Failure Drills

- guestbook readiness regression drill in [`failure-drill-guestbook-readiness.md`](./failure-drill-guestbook-readiness.md)
- AI internal application failure drill in [`failure-drill-ai-internal-application-failure.md`](./failure-drill-ai-internal-application-failure.md)

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
- deterministic AI eval execution
- an ephemeral `kind` smoke test for the guestbook chart

The current validation workflow lives in [`.github/workflows/validate-manifests.yaml`](./.github/workflows/validate-manifests.yaml).

### After Merge

Protected `main` is the deployment source of truth. Argo CD reconciles from Git into the cluster. That means:

- manual cluster changes are not the persistent source of truth
- config changes in observability trigger pod rollouts through hashed Kustomize `ConfigMap` names
- Argo CD sync drift and repo-server failure are themselves observable

### Security And Supply Chain

The pipeline includes Trivy config scanning, but the more useful lesson was operational:

- scanners found real baseline hardening misses
- smoke tests caught runtime regressions that static checks missed
- CI dependency trust is itself a supply-chain problem

Those notes are captured in [`trivy-and-smoketest-notes.md`](./trivy-and-smoketest-notes.md).

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

- testing AI service degradation and recovery
- tightening AI-specific SLI/SLO definitions
- expanding replay and eval coverage
- pushing the AI workload toward richer traces and model-backed behavior without losing deterministic validation

Deferred work is tracked in [`TODO.md`](./TODO.md).
