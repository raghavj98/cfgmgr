from typing import Any, ClassVar, Callable
import json
import os


"""TODO
* Make PyConfig._cfg immutable outside of load function
* Test how it works when used in imported modules
* Heirarchical config files
    * Files can include other config files
    * Settings from included files should be overwritten by main files
    * Includes can be recursive (check circular includes)
"""


class PyConfig:
    """Static global container for key value pairs
    Loads configuration options from a file, environment and kwargs passed to PyConfig.load()
    """

    _cfg: ClassVar[dict[str, Any]]
    _post_load_hook: ClassVar[Callable[[dict], None]] = lambda x: None

    @classmethod
    def load(cls, cfg_json: str | None, env: bool = False, env_prefix: str = '', **kwargs) -> None:
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
            kwargs:
              Additional key value pairs to store in configuration
        """
        cls._cfg = {}  # Clear any existing config

        if cfg_json is not None:
            cls._cfg.update(cls._load_json(cfg_json))

        if env:
            cls._cfg.update(cls._load_from_env(env_prefix))

        cls._cfg.update(kwargs)
        _post_load_hook = getattr(cls, '_post_load_hook')
        _post_load_hook(cls._cfg)

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
