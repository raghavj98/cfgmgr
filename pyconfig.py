from typing import Any, ClassVar, Callable, TypeAlias, Iterable
from pydantic import BaseModel
import json
import os


"""TODO
* Make CfgMgr._cfgs immutable outside of load function
* Introduce a loader class
    * Instead of taking in args for env, files and kwargs, have a loader class manage this
    * Loader instances should provide an update method which takes in a dict and updates it with all their keys
    * Multiple loaders can be provided, will be consumed in order - last one is highest priority
* Heirarchical config objects
    * Children inherit all settings from parents
    * Can override inherited settings, or add new
    * Parent-child relation can be defined by the name, same as logging.getLogger()
* 'include' directive in config files
    * Files can include other config files
    * Settings from included files should be overwritten by including files
    * Includes can be recursive (check circular includes)
    * Idea: Option to provide an include key,
    *       if this key is present in a config source,
            it is assumed to point to another config file to be included
"""


CfgSchema: TypeAlias = BaseModel


class CfgMgr[S: CfgSchema]:
    """Static global container for key value pairs
    Loads configuration options from a file, environment and kwargs passed to PyConfig.load()
    """

    _cfgs: dict[str, S] = {}

    def __init__(self):
        raise NotImplmentedError

    @classmethod
    def getCfg(cls, name: str = '') -> S:
        """Get an existing configuration
        Args:
            name: Name passed during loadCfg 
        Raises:
            KeyError when config name doesn't exist
        """
        return cls._cfgs[name]

    @classmethod
    def loadCfg(cls, schema: type[S],  # schema is the class S itself (not an object of S)
                name: str = '',
                file: str | Iterable[str] | None = None,
                env: bool = False,
                env_prefix: str = '', 
                loading_order: str = 'fek',
                post_load_hook: Callable[[dict], None] = lambda x: None,
                **kwargs) -> S:  # So, this function takes the class S and returns an instance of it
        """Load configuration
        Args:
            schema:
                Pydantic schema to be used for validation
            name:
                A label for the generated config
                To be used with getCfg to fetch the config
            cfg_json:
                Config files to read the config from

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
        _cfg = cls._load(file, env, env_prefix, loading_order, **kwargs)
        post_load_hook(_cfg)
        cfg = schema(**_cfg)
        cls._cfgs[name] = cfg
        return cls.getCfg(name)

    @staticmethod
    def _load(file: str | Iterable[str] | None = None,
             env: bool = False,
             env_prefix: str = '', 
             loading_order: str = 'fek',
              **kwargs) -> dict[str, Any]:

        _cfg: dict[str, Any] = {}
        for method in loading_order:
            if method == 'f' and file is not None:
                if isinstance(file, str):
                    CfgMgr._update_from_files(_cfg, [file])
                else:
                    CfgMgr._update_from_files(_cfg, file)
            if method == 'e' and env:
                _cfg.update(CfgMgr._load_from_env(env_prefix))
            if method == 'k':
                _cfg.update(kwargs)
        return _cfg

    @staticmethod
    def _update_from_files(cfg: dict[str, Any], files: Iterable[str]) -> None:
        for file in files:
            cfg.update(CfgMgr._load_json(file))

    @staticmethod
    def _load_from_env(env_prefix: str) -> dict[str, str]:
        _ret = {
                k.removeprefix(env_prefix): v for k, v in os.environ.items()
                if k.startswith(env_prefix)
        }
        return _ret

    @staticmethod
    def _load_json(fpath: str) -> dict[str, Any]:
        with open(fpath) as fp:
            return json.load(fp)
