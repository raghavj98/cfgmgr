'''Usage

import cfgmgr

cfgmgr.make_config(env_prefix="CFG_", file_path="config.json", find_file=True)
some_val = cfgmgr.get('key')
cfgmgr.set('key', 'new_val')
'''

import os
import json
import pathlib
import logging
from abc import ABC, abstractmethod
from collections import UserDict


__all__ = ['Loader', 'EnvLoader', 'JSONLoader', 'Config', 'make_config']
_MISSING = object()

_log = logging.getLogger(__name__)


class _FileLoaders(UserDict):

    def register(self, extension):
        def wrapper(loader_class):
            self.data[extension] = loader_class
            return loader_class
        return wrapper


fileloaders = _FileLoaders()


class Loader(ABC):
    '''Interface for loaders
    Override __init__ to load the key value pairs
    Override get to provide value when asked for a key
    get() is called by Config.get() so values from a loader can be dynamically constructed
    '''
    # TODO: toml loader
    # TODO: dotenv and yaml loaders as optional dependency installs
    # TODO?: Heirarchical loaders

    @abstractmethod
    def get(self, key: str, default=None):
        pass


class EnvLoader(Loader):

    def __init__(self, prefix=""):
        '''Load environment variables into config
        prefix will be stripped from env vars before loading them into the config
        prefix="" to load all env vars
        '''
        self.prefix = prefix

    def get(self, key, default=None):
        return os.getenv(f"{self.prefix}{key}", default)


@fileloaders.register(".json")
class JSONLoader(Loader):

    def __init__(self, file_path):
        with open(file_path, 'r') as fp:
            self._cfg = json.load(fp)

    def get(self, key, default=None):
        return self._cfg.get(key, default)


class Config:
    # TODO?: Dynamic key value consturction
    # TODO?: Type validation

    def __init__(self, loaders, **kwargs):
        self.loaders = loaders
        self._overrides = dict(kwargs)

    def get(self, key, default=None):
        if key in self._overrides:
            return self._overrides[key]
        candidate = default
        for loader in self.loaders:
            # Let each loader override the candidate
            candidate = loader.get(key, candidate)
        return candidate

    def set(self, key, value):
        self._overrides[key] = value

    def __getitem__(self, key):
        val = self.get(key, _MISSING)
        if val is _MISSING:
            raise KeyError(key)
        return val

    def __setitem__(self, key, val):
        self._overrides[key] = val

    def __contains__(self, key):
        val = self.get(key, _MISSING)
        return val is not _MISSING


# Primary public interface

_config = None


def make_config(env_prefix=None, file_path=None, find_file=False, **kwargs):
    global _config
    _loaders = []
    if file_path:
        target = find_file_up(file_path) if find_file else file_path
        if not target:
            raise FileNotFoundError(file_path)
        _loaders.append(get_file_loader(target))
    if env_prefix is not None:
        _loaders.append(EnvLoader(prefix=env_prefix))
    _config = Config(_loaders, **kwargs)


def get(key, default=None):
    # Intentionally not exposed in __all__ to prevent namespace collisions
    if not _config:
        # Log, and let _config.get raise
        _log.error("get called on uninitialized config, did you call make_config?")
    return _config.get(key, default)


def set(key, value):
    # Intentionally not exposed in __all__ to prevent namespace collisions
    if not _config:
        # Log, and let _config.set raise
        _log.error("set called on uninitialized config, did you call make_config?")
    _config.set(key, value)


# Utility

def find_file_up(basename):
    # Try to parse extension
    for ext in fileloaders:
        if basename.endswith(ext):
            break
    else:
        _unsupported_ext(basename)

    p = pathlib.Path(os.getcwd())
    for ancestor in [p, *p.parents]:
        fpath = os.path.join(ancestor, basename)
        if os.path.isfile(fpath):
            return fpath
    return None


def get_file_loader(file_path):
    for ext in fileloaders:
        if file_path.endswith(ext):
            return fileloaders[ext](file_path)
    _unsupported_ext(file_path)


def _unsupported_ext(fname):
    _log.error(f"Can't detect a supported extension for {fname}")
    _log.debug(f"Supported extensions: {list(fileloaders.keys())}")
    raise ValueError(fname)
