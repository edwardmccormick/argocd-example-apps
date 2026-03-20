# Guestbook App

This directory is the logical home for the guestbook workload in the GitOps layout.

Current source paths:

- Helm chart: `../../helm-guestbook`
- ArgoCD app manifest: `../../environments/local/apps/guestbook.yaml`

The Helm chart is not complete yet. It currently contains chart metadata and values files, but no `templates/` directory. Finish the chart templates before expecting the ArgoCD Helm application to sync successfully.

Until the Helm-backed guestbook app is ready, keep the existing non-Helm guestbook deployment in mind and avoid enabling automated sync on the Helm application.
