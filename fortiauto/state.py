"""Small JSON file the daemon writes on events (not every check) so that
`fortiauto status` can show when you logged in and when the next reset is due."""

import json
import os
import time


class State:
    def __init__(self, path):
        self.path = path
        self.data = {}
        try:
            with open(path, encoding="utf-8") as f:
                self.data = json.load(f)
        except (OSError, ValueError):
            pass

    def get(self, key, default=None):
        return self.data.get(key, default)

    def update(self, **changes):
        """Merge changes and write only if something actually changed."""
        if all(self.data.get(k) == v for k, v in changes.items()):
            return
        self.data.update(changes)
        self.data["updated_at"] = time.time()
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=1)
            os.replace(tmp, self.path)  # atomic: status never reads half a file
        except OSError:
            pass
