import os
import json
import pathlib
from abc import ABC, abstractmethod
from collections import UserDict


__all__ = ['Loader', 'EnvLoader', 'JSONLoader', 'Config', 'make_config']


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
    get() is called by CfgMgr.get() so values from a loader can be dynamically constructed
    '''
    # TODO: toml loader
    # TODO: dotenv and yaml loaders as optional dependency installs
    # TODO?: Heirarchical loaders

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


@_extension_map.register(".json")
class JSONLoader(Loader):

    def __init__(self, file_path):
        with open(file_path, 'r') as fp:
            self._cfg = json.load(fp)

    def get(self, key, default=None):
        return self._cfg.get(key, default):



class Config:
    # TODO?: Dynamic key value consturction
    # TODO?: Type validation

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
    _loaders = [EnvLoader(prefix=env_prefix)]  # gets all env vars
    if file_path:
        _loaders.extend(_get_file_loader(file_path))
    _loaders.extend(loaders)
    return Config(_loaders, **kwargs)


def find_file_up(basename, extensions=list(_extension_map.keys())):
    for ext in extensions:
        if ext not in _extension_map:
            raise ValueError(f"Item {ext} in {extensions} is not supported")
    p = pathlib.Path(os.getcwd())
    for ancestor in p.parents:
        candidates = [f"{basename}{ext}" for ext in extensions]
        for fname in candidates:
            fpath = os.path.join(ancestor, fname)
            if os.path.isfile(fpath):
                return fpath
    return None

def _get_file_loader(file_path):
    for ext in _extension_map:
        if file_path.endswith(ext):
            return _extension_map[ext](file_path)
    return None


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
