import os
import json
import itertools
from abc import ABC, abstractmethod


class Loader(ABC):
    '''Interface for loaders
    Override __init__ to load the key value pairs
    Override get to provide value when asked for a key
    get() is called by CfgMgr.get() so values from a loader can be dynamically constructed
    '''

    @abstractmethod
    def __init__(self, *args, **kwargs):
        pass

    @abstractmethod
    def get(self, key, default=None):
        pass


class EnvLoader(Loader):

    def __init__(self, prefix=None):
        self.prefix = prefix

    def get(self, key, default=None):
        if self.prefix:
            return os.getenv(key.removeprefix(self.prefix), default)
        return os.getenv(key, default)


class JSONLoader(Loader):

    def __init__(self, file_path):
        with open(file_path, 'r') as fp:
            self._cfg = json.load(fp)

    def get(self, key, default=None):
        return self._cfg.get(key, default):


# TODO: toml loader
# TODO: dotenv and yaml loaders as optional dependency installs


class Config:

    def __init__(loaders, **kwargs):
        self.loaders = loaders
        self._overrides = dict()
        for key, value in kwargs.items():
            self._overrides[key] = value

    def get(key, default=None):
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
        raise KeyErorr(key)

    def __setitem__(self, key, val):
        self._overrides[key] = val


def make_config(env_prefix=None, file_path=None, loaders=list(), **kwargs):
    env_loader = EnvLoader(prefix=env_prefix)  # gets all env vars
    file_loader = _get_file_loader(file_path)
    if file_loader:
        _loaders = itertools.chain([env_loader, file_loader], loaders)
    else:
        _loaders = itertools.chain([env_loader], loaders)
    return Config(_loaders, **kwargs)


def _get_file_loader(file_path):
    _ext_map = _build_extension_map()
    if file_path is None:
        # TODO: Implement upwards crawl to find a config.<extension>
        return None
    for ext in _ext_map:
        if file_path.endswith(ext):
            return _ext_map[ext](file_path)
    return None


def _build_extension_map():
    _extension_map = {
        ".json": JSONLoader,
    }
    # TODO: build _extension_map based on availability of toml, yaml, dotenv parsers
    return _extension_map

#########################################################################

# Intended usage

import cfgmgr

# Sensible default usage
some_val = cfgmgr.Config.get('key')
some_val = cfgmgr.Config['key']  # Should have __getitem__ and __setitem__

# Dynamically override values
cfgmgr.Config.set('key', 'new_val')
new_val = cfgmgr.Config.get('key')

# Allow config variants?
test_val = cfgmgr.OtherConfig.get('key')
