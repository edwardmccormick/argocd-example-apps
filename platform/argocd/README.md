# ArgoCD Bootstrap

These manifests bootstrap ArgoCD against the repository structure in this repo.

`root-application.yaml` includes two bootstrap resources:

- a patch for `argocd-server` to run with `--insecure` for local HTTP ingress through Traefik on `localhost:8080`
- an app-of-apps `Application` that points ArgoCD at `environments/local`

That environment definition in turn creates:

- the `AppProject` for the lab
- the Helm-backed guestbook `Application`

Once the legacy guestbook app is removed and the Helm chart is complete, enable automated sync in `environments/local/apps/guestbook.yaml`.
