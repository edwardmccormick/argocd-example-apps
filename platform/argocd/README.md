# ArgoCD Bootstrap

These manifests bootstrap ArgoCD against the repository structure in this repo.

`root-application.yaml` points ArgoCD at `environments/local`, which in turn defines:

- the `AppProject` for the lab
- the Helm-backed guestbook `Application`

Once the legacy guestbook app is removed and the Helm chart is complete, enable automated sync in `environments/local/apps/guestbook.yaml`.
