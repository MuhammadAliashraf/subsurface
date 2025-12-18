import json
from os import path
from .globals import globals

if not globals.get("testrun", False):
    from .redis import redis
else:
    class MockRedis:
        def get(self, name): return None
        def set(self, name, value, nx=False, ex=None): return True
        def delete(self, name): pass
    redis = MockRedis()


# The Env class uses both a flat file and Redis to store values
# This ensures that we stay consistent across the different workers,
# but also have a file storage backend across unexpected reboots or
# other issues that might prevent Redis from staying consistent across
# restarts.
class Env:
    def __init__(
        self,
        name: str,
        default: any = None,
    ):
        # Let's make sure we have an env file
        if not path.isfile(globals.get("env_file_path")):
            open(globals.get("env_file_path"), "w").close()
        self._name = name
        # check if we have a value in backing store, otherwise use the default
        # if redis.get(name=self._name) == None:
        # get the value from the file and write either that or the default to Redis
        value_in_file = self._get_value_from_file()
        if value_in_file is not None:
            self.value = value_in_file
        else:
            self.value = default
        # redis.set(name=self._name, value=json.dumps(self.value)) # Handled by setter

    def _get_values_from_file(self):
        ret = {}
        try:
            with open(globals.get("env_file_path"), "r") as f:
                for line in f.readlines():
                    if line.strip().startswith("#"):
                        continue
                    key, var = line.partition("=")[::2]
                    if key is not None and var is not None:
                        ret[key.strip()] = json.loads(var)
        except (json.JSONDecodeError, FileNotFoundError):
            pass

        return ret

    def _get_value_from_file(self):
        return self._get_values_from_file().get(self._name, None)

    def _write_value_to_file(self, new_value):
        if (self._name == "lrelease" or self._name == "crelease") and new_value == "":
            return
        values = self._get_values_from_file()
        values[self._name] = new_value
        with open(globals.get("env_file_path"), "w") as f:
            for key, value in values.items():
                if key:
                    f.write(f"{key}={json.dumps(value)}\n")

    def __str__(self):
        return f"Env({self._name}, {self.value})"

    @property
    def name(self):
        return self._name

    @property
    def value(self):
        # v = redis.get(name=self._name)
        # In testrun, we rely on file or memory.
        # But for simplicity, let's just use the file logic or simple pass-through if redis is mocked.
        # The original code preferred Redis.
        # If redis is mocked to return None, we fall back to file?
        # Original code:
        v = redis.get(name=self._name)
        result = None
        if v is not None:
            try:
                result = json.loads(v)
            except json.JSONDecodeError:
                pass
        
        if result is None:
             # Fallback to file if redis returns None (which MockRedis does)
             return self._get_value_from_file()
        return result

    @value.setter
    def value(self, value):
        if value != self.value:
            redis.set(name=self._name, value=json.dumps(value))

            value_in_file = self._get_value_from_file()
            if value == value_in_file:
                return  # do not write to file if value is the same
            if value is None or value == "None":
                self._write_value_to_file("")
            else:
                self._write_value_to_file(value)


env = {
    "lrelease": Env("lrelease", default="6.0.5217"),
    "lrelease_date": Env("lrelease_date", default="2024-06-16"),
    "crelease": Env("crelease", default="6.0.5214"),
    "crelease_date": Env("crelease_date", default="2024-06-16"),
    "release_ids": Env("release_ids", default=[]),
    "pr_summary": Env("pr_summary", default=""),
}
