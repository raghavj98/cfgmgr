from typing import Any, ClassVar, Callable
import json
import os


"""TODO
* Make PyConfig._cfg immutable outside of load function
* Test how it works when used in imported modules
* Test post_load_hook
* Heirarchical config files
    * Files can include other config files
    * Settings from included files should be overwritten by main files
    * Includes can be recursive (check circular includes)
* Add a validator class
    * Validator will be called after post_load_hook
    * Field type validation
    * Mandatory field check
    * ...
"""


class PyConfig:
    """Static global container for key value pairs
    Loads configuration options from a file, environment and kwargs passed to PyConfig.load()
    """

    _cfg: ClassVar[dict[str, Any]]
    _post_load_hook: ClassVar[Callable[[dict], None]] = lambda x: None

    def __init__(self) -> None:
        raise NotImplementedError("PyConfig cannot be instantiated")
    
    @classmethod
    def load(cls, cfg_json: str | None = None,
             env: bool = False,
             env_prefix: str = '', 
             loading_order: str = 'fek',
             **kwargs) -> None:
        """Load configuration
        Priority order: kwargs > env > file
        Args:
            env:
              Load from env vars
            env_prefix:
              Look only for env vars starting with env_prefix
              Strip env_prefix from configuration keys
              Defaults to empty strings (all env vars are stored)
              No effect if env == False
            loading_order:
              Define the priority order of where to pick config vals from
              'k' -> kwargs as passed to .load()
              'e' -> environment (as returned by os.environ())
              'f' -> file as passed to .load()
              Must be a string formed by the letters 'k', 'e', 'f' in any order
              Later positon in the string indicates higher priority
              Example: fek (default) will 
                1) load from file
                2) load from environment overriding previous cfg
                3) load from kwargs overriding previous cfg
            kwargs:
              Additional key value pairs to store in configuration
        """
        cls._cfg = {}  # Clear any existing config

        cls._load(cfg_json, env, env_prefix, **kwargs)

        _post_load_hook = getattr(cls, '_post_load_hook')
        _post_load_hook(cls._cfg)

    @classmethod
    def _load(cls, cfg_json: str | None = None,
             env: bool = False,
             env_prefix: str = '', 
             loading_order: str = 'fek',
             **kwargs) -> None:

        for method in loading_order:
            if method == 'f' and cfg_json is not None:
                cls._cfg.update(cls._load_json(cfg_json))
            if method == 'e' and env:
                cls._cfg.update(cls._load_from_env(env_prefix))
            if method == 'k':
                cls._cfg.update(kwargs)

    @classmethod
    def _load_from_env(cls, env_prefix: str) -> dict[str, str]:
        _ret = {
                k.removeprefix(env_prefix): v for k, v in os.environ.items()
                if k.startswith(env_prefix)
        }
        return _ret

    @classmethod
    def _load_json(cls, fpath: str) -> dict:
        with open(fpath) as fp:
            return json.load(fp)

    @classmethod
    def get(cls, key: str) -> Any:
        """Return value associated with key
        """
        return cls._cfg.get(key)

    @classmethod
    def to_dict(cls) -> dict:
        """ Return a dict of loaded configuration options
        """
        return cls._cfg

    @classmethod
    def post_load[F: Callable[[dict], None]](cls, func: F) -> F:
        """Hook called after configuration is loaded
        This can be used to validate and modify values, create inferred keys
        To be used as a decorator on a function that takes in a dict of config key value pairs
        """
        cls._post_load_hook = func
        return func
