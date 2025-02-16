from __future__ import annotations
from typing import Any, TypeAlias, Iterable, TextIO
from collections.abc import Callable
import json
import os
from abc import ABC, abstractmethod
import yaml
import difflib


CfgDictT: TypeAlias = dict[str, Any]


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
        cfg.update(self.cfg)


class EnvLoader(CfgLoader):

    def __init__(self, prefix: str = ''):
        self.cfg = {
            k.removeprefix(prefix): v for k, v in os.environ.items()
            if k.startswith(prefix)
        }


LoaderT: TypeAlias = Callable[[TextIO], dict[str, Any]]


FileT: TypeAlias = str  # temporary, will properly define FileT later


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
        include_key:
            A key present in the file that points to other config files to be included
            Included files have a lower priority than the including file
            Value pointed to by include_key must be a list of file paths

    Raises:
        KeyError: Loader specified as string not found
        Propagates any errors raised by file IO or loader callable

    """
    _loaders: dict[str, LoaderT] = {
            'json': json.load,
            'yaml': yaml.safe_load
    }

    def __init__(self, file: FileT,
                 loader: None | str | LoaderT = None,
                 include_key: None | str = None) -> None:

        if loader is None:
            loader = self.guess_loader(file)

        if isinstance(loader, str):
            self.loader = self._loaders[loader]
        else:
            self.loader = loader

        with open(file) as fp:
            self.cfg = self.loader(fp)

        if include_key is not None and include_key in self.cfg:
            self.recursive_update(include_key, self.cfg.get(include_key, ()))

    def recursive_update(self, include_key: str, include_files: Iterable[FileT]) -> None:
        for file in include_files:
            with open(file) as fp:
                new = self.loader(fp)
            self.cfg.update({key: val for key, val in new.items() if key not in self.cfg})
            self.recursive_update(include_key, new.get(include_key, ()))

    def guess_loader(self, file: FileT) -> str:
        match = difflib.get_close_matches(file, self._loaders.keys(), n=1, cutoff=0.2)
        if match:
            return match[0]
        raise ValueError
