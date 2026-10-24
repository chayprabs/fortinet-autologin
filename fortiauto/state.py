"""Small file the daemon writes on events (not every check) so that
`fortiauto status` can show when you logged in and when the next reset is due.

Plain "key<TAB>value" lines instead of JSON: the json module pulls in re,
which the resident watcher otherwise never needs.
"""

import os
import time


def _encode(value):
    if value is None:
        return "-"
    if isinstance(value, str):
        return "s" + value.replace("\t", " ").replace("\r", " ").replace("\n", " ")
    return repr(value)  # int / float


def _decode(text):
    if text == "-":
        return None
    if text.startswith("s"):
        return text[1:]
    try:
        return int(text)
    except ValueError:
        return float(text)


class State:
    def __init__(self, path):
        self.path = path
        self.data = {}
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    key, sep, value = line.rstrip("\n").partition("\t")
                    if sep:
                        try:
                            self.data[key] = _decode(value)
                        except ValueError:
                            pass
        except OSError:
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
                for key, value in self.data.items():
                    f.write("%s\t%s\n" % (key, _encode(value)))
            os.replace(tmp, self.path)  # atomic: status never reads half a file
        except OSError:
            pass
