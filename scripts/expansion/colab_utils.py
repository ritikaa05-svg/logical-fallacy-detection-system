import json
import os


class ExpansionState:
    def __init__(self, manifest_path="data/generation_manifest.json"):
        self.manifest_path = manifest_path
        self.state = self._load_state()

    def _load_state(self):
        if os.path.exists(self.manifest_path):
            with open(self.manifest_path) as f:
                return json.load(f)
        return []

    def get_last_batch_id(self):
        return len(self.state)

    def save_checkpoint(self, batch_info):
        self.state.append(batch_info)
        with open(self.manifest_path, "w") as f:
            json.dump(self.state, f, indent=2)
        print(f"Checkpoint saved: Batch {len(self.state)}")
