# Repository Guidelines

## Project Structure & Module Organization
This repository is a small Argo CD example app repo with two main parts:

- `helm-guestbook/`: Helm chart metadata and environment values for the guestbook app.
- `argocd-ingress.yaml`: Traefik `IngressRoute` for exposing the Argo CD server.

Within `helm-guestbook/`, keep chart metadata in `Chart.yaml`, shared defaults in `values.yaml`, and environment-specific overrides in files such as `value-production.yaml`.

## Build, Test, and Development Commands
Use Helm to validate changes before committing:

- `helm lint .\helm-guestbook`: checks chart structure and values.
- `helm template guestbook .\helm-guestbook`: renders manifests locally for review.
- `helm template guestbook .\helm-guestbook -f .\helm-guestbook\value-production.yaml`: verifies the production override.
- `kubectl apply --dry-run=client -f .\argocd-ingress.yaml`: validates the ingress manifest syntax against your local client.

Run commands from the repository root.

## Coding Style & Naming Conventions
Use 2-space indentation in YAML and keep keys grouped logically: image, service, ingress, then scheduling or resource settings. Prefer descriptive lowercase names with hyphens for Kubernetes resources and files. Add new environment overrides as `value-<environment>.yaml`.

Keep Helm values minimal and explicit. If a value differs by environment, place the default in `values.yaml` and override only the changed keys in the environment file.

## Testing Guidelines
There is no automated test suite in this repository today. Treat manifest validation as the required test baseline:

- lint the chart with `helm lint`
- render manifests with `helm template`
- dry-run standalone manifests with `kubectl apply --dry-run=client`

When adding templates later, keep template names aligned with Kubernetes kinds and verify both default and override renders.

## Commit & Pull Request Guidelines
Recent history uses short, informal subject lines. Prefer concise imperative commits instead, for example: `Add production service override` or `Update Argo CD ingress host`.

Pull requests should include:

- a brief summary of the change
- affected paths, such as `helm-guestbook/values.yaml`
- validation commands you ran and their result
- any cluster-specific assumptions, especially hostnames, namespaces, or ingress controller requirements
