import os
import json
import pathlib
import logging
from abc import ABC, abstractmethod
from collections import UserDict


__all__ = ['Loader', 'EnvLoader', 'JSONLoader', 'Config', 'make_config']

_log = logging.getLogger(__name__)


class _Loaders(UserDict):

    def register(self, extension):
        def wrapper(loader_class):
            self.data[extension] = loader_class
            return loader_class
        return wrapper


_extension_map = _Loaders()


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
    def __init__(self, *args, **kwargs):
        pass

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


@_extension_map.register(".json")
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
        self._overrides = dict()
        for key, value in kwargs.items():
            self._overrides[key] = value

    def get(self, key, default=None):
        if key in self._overrides:
            return self._overrides[key]
        candidate = default
        for loader in self.loaders:
            # Let each loader override the candidate
            candidate = loader.get(key, default)
        return candidate

    def __getitem__(self, key):
        if val := self.get(key):
            return val
        raise KeyError(key)

    def __setitem__(self, key, val):
        self._overrides[key] = val


# Primary public interface

_config = None


def make_config(env_prefix=None, file_path=None, find_file=False, loaders=list(), **kwargs):
    global _config
    _loaders = []
    if env_prefix or env_prefix == "":
        _loaders.append(EnvLoader(prefix=env_prefix))
    if file_path:
        if find_file:
            file_path = find_file_up(file_path)
        _loaders.append(get_file_loader(file_path))
    _loaders.extend(loaders)
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
    for ext in _extension_map:
        if basename.endswith(ext):
            break
    else:
        _unsupported_ext(basename)

    p = pathlib.Path(os.getcwd())
    for ancestor in p.parents:
        fpath = os.path.join(ancestor, basename)
        if os.path.isfile(fpath):
            return fpath
    return None


def get_file_loader(file_path):
    for ext in _extension_map:
        if file_path.endswith(ext):
            return _extension_map[ext](file_path)
    _unsupported_ext(file_path)


def _unsupported_ext(fname):
    _log.error(f"Can't detect a supported extension for {fname}")
    _log.debug(f"Supported extensions: {list(_extension_map.keys())}")
    raise ValueError(fname)


'''Intended usage

import cfgmgr

# Sensible default usage
cfgmgr.make_config(env_prefix="CFG_", file_path="config.json", find_file=True)
some_val = cfgmgr.get('key')
cfgmgr.set('key', 'new_val')
'''
