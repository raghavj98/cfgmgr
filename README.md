# cfgmgr
Simple out of the box configurations for python projects

## Basic usage
```python3

import cfgmgr

cfgmgr.make_config(env_prefix="CFG_", file_path="config.json", find_file=True)
some_val = cfgmgr.getkey('key')
cfgmgr.setkey('key', 'new_val')
config = cfgmgr.get()          # the global Config object itself
```

### `make_config`
- Initializes a global `Config` as per args specified
- Pass in `env_prefix` to read values from environment variables
    - `env_prefix` will be prefixed to the keys before reading the environment variable
    - Ex. `env_prefix="CFG_"` will effectively translate `cfgmgr.getkey('foo')` to `os.getenv('CFG_foo')`
- Values are resolved dynamically, so `cfgmgr.getkey` will respect environment variables set via `os.environ` (Useful in test cases)
- `file_path` attempts to resolve the extension and defers to the corresponding loader
    - JSON and env are always supported. TOML is supported on Python 3.11+ (`tomllib`).
      YAML and dotenv are supported when their packages are installed — `pip install cfg-mgr[yaml]` / `cfg-mgr[dotenv]`.
    - Custom Loaders can be implemented and registered via a decorator `cfgmgr.fileloaders.register('.extension')`
- `find_file`, if `True`, will crawl upwards from `cwd` until it finds a match for `file_path`
- `include_key`, if given, enables config includes: a config file may name another file under that key
  to be pulled in as a base. The including file overrides the included one; nested mappings are deep-merged.
  Include chains are followed recursively and cycles raise `IncludeCycleError`.

### `getkey` and `setkey`
- Getter and setter for individual keys on the global default `Config` object
- `getkey(key, default=None)` returns the resolved value, or `default` if absent
- `setkey(key, value)` sets an override (highest priority)
- Both `raise AttributeError` if `make_config` has not been called prior to the call

### `get`
- Returns the global default `Config` object itself (a `MutableMapping`), or `None` if `make_config`
  has not been called
- Use it for mapping-style access: `cfgmgr.get()['key']`, `'key' in cfgmgr.get()`, iteration, etc.

## Documentation
https://raghavj98.github.io/cfgmgr/
