# cfgmgr
Simple out of the box configurations for python projects

## Basic usage
```python3

import cfgmgr

cfgmgr.make_config(env_prefix="CFG_", file_path="config.json", find_file=True)
some_val = cfgmgr.get('key')
cfgmgr.set('key', 'new_val')
```

### `make_config`
- Initializes a global `Config` as per args specified
- Pass in `env_prefix` to read values from environment variables
    - `env_prefix` will be prefixed to the keys before reading the environment variable
    - Ex. `env_prefix="CFG_"` will effectively translate `cfgmgr.get('foo')` to `os.getenv('CFG_foo')`
- Values are resolved dynamically, so `cfgmgr.get` will respect environment variables set via `os.environ` (Useful in test cases)
- `file_path` attempts to resolve the extension and defers to the corresponding loader
    - JSON support is present. TOML, YAML and dotenv are planned.
    - Custom Loaders can be implemented and registered via a decorator `cfgmgr.fileloaders.register('.extension')`
- `find_file`, if `True`, will crawl upwards from `cwd` until it finds a match for `file_path`

### `get` and `set`
- Getter and Setter for the global default `Config` object
- `raise AttributeError` if `make_config` has not been called prior to a `get`/`set` call
