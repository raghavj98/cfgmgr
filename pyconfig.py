from typing import Any, ClassVar, Callable, TypeAlias, Iterable, TextIO
from pydantic import BaseModel
import json
import os
from abc import ABC, abstractmethod
import yaml


"""TODO
* Make CfgMgr._cfgs immutable outside of load function
* Heirarchical config objects
    * Children inherit all settings from parents
    * Can override inherited settings, or add new
    * Parent-child relation can be defined by the name, same as logging.getLogger()
"""


class CfgLoader(ABC):

    @abstractmethod
    def __init__(self) -> None:
        ...

    @property
    def cfg(self) -> dict[str, Any]:
        if hasattr(self, '_cfg'):
            return self._cfg
        else:
            return {}

    @cfg.setter
    def cfg(self, _cfg: dict[str, Any]) -> None:
        self._cfg = _cfg

    def update(self, cfg: dict[str, Any]) -> None:
        print(f"Update called: {self.__class__}")
        cfg.update(self.cfg)


class EnvLoader(CfgLoader):
    
    def __init__(self, prefix: str = ''):
        self.cfg = {
            k.removeprefix(prefix): v for k, v in os.environ.items()
            if k.startswith(prefix)
        }

CfgSchema: TypeAlias = BaseModel


class CfgMgr[S: CfgSchema]:
    """Static global container for key value pairs
    Loads configuration options from a file, environment and kwargs passed to PyConfig.load()
    """

    _cfgs: dict[str, S] = {}

    def __init__(self):
        raise NotImplmentedError

    @classmethod
    def get(cls, name: str = '') -> S:
        """Get an existing configuration
        Args:
            name: Name passed during load 
        Raises:
            KeyError when config name doesn't exist
        """
        return cls._cfgs[name]

    @classmethod
    def load(cls, schema: type[S],  # schema is the class S itself (not an object of S)
                name: str = '',
                loaders: Iterable[CfgLoader] = (EnvLoader('CFG_'),),  # By default, look for env vars starting with CFG_
                post_load_hook: Callable[[dict], None] = lambda x: None,
                **kwargs) -> S:  # So, this function takes the class S and returns an instance of it
        """Load configuration
        Args:
            schema:
                Pydantic schema to be used for validation
            name:
                A label for the generated config
                To be used with get to fetch the config
            loaders:
                An interable of loader objects to load the config vars
                Defaults to EnvLoader with prefix as "CFG_"
            kwargs:
              Additional key value pairs to store in configuration
        """
        _cfg = cls._load(loaders, **kwargs)
        post_load_hook(_cfg)
        cfg = schema(**_cfg)
        cls._cfgs[name] = cfg
        return cls.get(name)

    @staticmethod
    def _load(loaders: Iterable[CfgLoader],  **kwargs) -> dict[str, Any]:

        _cfg: dict[str, Any] = {}
        for loader in loaders:
            loader.update(_cfg)
        _cfg.update(kwargs)
        return _cfg


class FileLoader(CfgLoader):
    """Loads configuration from a file
    Only meant to be instantiated by the user, to be consumed by CfgMgr

    Args:
        file: 
            Filepath to load the configuration from
        loader: 
            Method used to read the file
            Maybe a string - 'json', 'yaml' indicating the filetype
            Alternatively a custom callable that can read config from the filename specified
    Raises:
        ValueError: If loader is not a valid string
        Propagates any errors raised by file IO or loader callable

    TODO:
        * 'include' directive in config files
            * Files can include other config files
            * Settings from included files should be overwritten by including files
            * Includes can be recursive (check circular includes)
            * Idea: Option to provide an include key,
            *       if this key is present in a config source,
                    it is assumed to point to another config file to be included
    """
    _loaders: dict[str, Callable[[TextIO], dict[str, Any]]] = {
            'json': json.load,
            'yaml': yaml.safe_load
    }

    def __init__(self, file: str, loader: str | Callable[[TextIO], dict[str, Any]] = 'json'):
        if isinstance(loader, str) and loader not in self._loaders:
            raise ValueError(f"Supported loaders are {self._loaders.keys()}")
        with open(file) as fp:
            if isinstance(loader, str):
                self.cfg = self._loaders[loader](fp)
            else:
                self.cfg = loader(fp)
