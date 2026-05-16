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
from collections import UserDict
from collections.abc import Mapping
from abc import abstractmethod

_log = logging.getLogger(__name__)

# Conditional imports
try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None

try:
    import yaml
except ModuleNotFoundError:
    yaml = None

try:
    import dotenv
except ModuleNotFoundError:
    dotenv = None


__all__ = ['Loader', 'FileLoader', 'EnvLoader', 'JSONLoader', 'TOMLLoader', 'YAMLLoader', 'DotEnvLoader',
           'Config', 'make_config']
_MISSING = object()


class _FileLoaders(UserDict):

    def register(self, extension, enabled=True):
        def wrapper(loader_class):
            if enabled:
                self.data[extension] = loader_class
            return loader_class
        return wrapper


fileloaders = _FileLoaders()


class Loader(Mapping):
    '''Interface for loaders
    Just an alias for Mapping currently, may add stricter constraints in the future
    Override __init__ to load the key value pairs
    Override get to provide value when asked for a key
    get() is called by Config.get() so values from a loader can be dynamically constructed
    '''
    # TODO?: Heirarchical loaders


class EnvLoader(Loader):

    def __init__(self, prefix=""):
        '''Load environment variables into config
        prefix will be stripped from env vars before loading them into the config
        prefix="" to load all env vars
        '''
        self.prefix = prefix

    def __getitem__(self, key):
        env_key = f"{self.prefix}{key}"
        return os.environ[env_key]

    def __iter__(self):
        for key in os.environ:
            if key.startswith(self.prefix):
                yield key.removeprefix(self.prefix)

    def __len__(self):
        return sum(1 for key in os.environ if key.startswith(self.prefix))


class FileLoader(Loader):

    @abstractmethod
    def _parse(self, file_path):
        pass

    def __init__(self, file_path):
        self._cfg = self._parse(file_path)

    def __getitem__(self, key):
        return self._cfg[key]

    def __iter__(self):
        return iter(self._cfg)

    def __len__(self):
        return len(self._cfg)

    # def get(self, key, default=None):
    #     return self._cfg.get(key, default)


@fileloaders.register(".json")
class JSONLoader(FileLoader):

    @staticmethod
    def _parse(file_path):
        with open(file_path, 'r') as fp:
            return json.load(fp)


@fileloaders.register(".toml", enabled=tomllib is not None)
class TOMLLoader(FileLoader):

    @staticmethod
    def _parse(file_path):
        with open(file_path, 'rb') as fp:
            return tomllib.load(fp)


@fileloaders.register(".env", enabled=dotenv is not None)
class DotEnvLoader(FileLoader):

    @staticmethod
    def _parse(file_path):
        return dotenv.dotenv_values(dotenv_path=file_path)


class Config:
    # TODO?: Type validation
    # TODO?: Dynamic key value consturction

    def __init__(self, loaders, **kwargs):
        ''' loaders is an iterable of Loader
        Loader implements the Mapping interface
        Priority order is inverted - a later Loader overrides earlier ones.
        Ex. If you pass in [FileLoader, EnvLoader], values from EnvLoader will override those from FileLoader
        **kwargs has highest priority - overrides everything
        '''
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
