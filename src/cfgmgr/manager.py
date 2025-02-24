from typing import Any, TypeAlias, Iterable
from collections.abc import Callable
from pydantic import BaseModel
from .loaders import EnvLoader, CfgLoader, CfgDictT


"""TODO
* Make CfgMgr._cfgs immutable outside of load function
* Heirarchical config objects
    * Children inherit all settings from parents
    * Can override inherited settings, or add new
    * Parent-child relation can be defined by the name, same as logging.getLogger()
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
             loaders: Iterable[CfgLoader] = (EnvLoader('CFG_'),),
             post_load_hook: Callable[[CfgDictT], None] = lambda x: None,
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
    def _load(loaders: Iterable[CfgLoader],  **kwargs) -> CfgDictT:

        _cfg: CfgDictT = {}
        for loader in loaders:
            loader.update(_cfg)
        _cfg.update(kwargs)
        return _cfg
