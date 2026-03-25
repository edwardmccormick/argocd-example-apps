from __future__ import annotations

import argparse
from pathlib import Path

import yaml
from ruamel.yaml import YAML


rt_yaml = YAML(typ="rt")
rt_yaml.preserve_quotes = True

def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return rt_yaml.load(handle)


def dump_yaml(path: Path, payload: dict) -> None:
    with path.open("w", encoding="utf-8") as handle:
        rt_yaml.dump(payload, handle)


def update_rollout(rollout_path: Path, image_ref: str) -> bool:
    rollout = load_yaml(rollout_path)
    container = rollout["spec"]["template"]["spec"]["containers"][0]
    changed = False

    if container.get("image") != image_ref:
        container["image"] = image_ref
        changed = True

    original_mounts = container.get("volumeMounts", [])
    filtered_mounts = [mount for mount in original_mounts if mount.get("name") != "app"]
    if filtered_mounts != original_mounts:
        container["volumeMounts"] = filtered_mounts
        changed = True

    pod_spec = rollout["spec"]["template"]["spec"]
    original_volumes = pod_spec.get("volumes", [])
    filtered_volumes = [volume for volume in original_volumes if volume.get("name") != "app"]
    if filtered_volumes != original_volumes:
        pod_spec["volumes"] = filtered_volumes
        changed = True

    if changed:
        dump_yaml(rollout_path, rollout)
    return changed


def update_kustomization(kustomization_path: Path) -> bool:
    kustomization = load_yaml(kustomization_path)
    generators = kustomization.get("configMapGenerator", [])
    filtered_generators = [generator for generator in generators if generator.get("name") != "ai-reliability-app"]

    if filtered_generators == generators:
        return False

    kustomization["configMapGenerator"] = filtered_generators
    dump_yaml(kustomization_path, kustomization)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Update ai-reliability rollout to use a pinned image reference.")
    parser.add_argument("--image-ref", required=True)
    parser.add_argument("--rollout-file", default="platform/ai-reliability/rollout.yaml")
    parser.add_argument("--kustomization-file", default="platform/ai-reliability/kustomization.yaml")
    args = parser.parse_args()

    rollout_changed = update_rollout(Path(args.rollout_file), args.image_ref)
    kustomization_changed = update_kustomization(Path(args.kustomization_file))

    print(
        {
            "rollout_changed": rollout_changed,
            "kustomization_changed": kustomization_changed,
            "image_ref": args.image_ref,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
