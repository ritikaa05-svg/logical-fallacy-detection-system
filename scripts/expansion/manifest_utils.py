import datetime
import json
import os


def update_manifest(batch_info):
    manifest_path = "data/generation_manifest.json"
    manifest = []

    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            manifest = json.load(f)

    batch_info["timestamp"] = datetime.datetime.now().isoformat()
    manifest.append(batch_info)

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)


# Example usage:
# update_manifest({
#     "generator": "generate_hard_negatives",
#     "target_class": "appeal_to_authority",
#     "sample_count": 20,
#     "accepted_count": 16,
#     "rejected_count": 4,
#     "duplicate_count": 4
# })
