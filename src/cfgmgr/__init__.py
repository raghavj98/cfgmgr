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
import builtins
import functools
import itertools
from collections import UserDict
from collections.abc import Mapping, MutableMapping, Sequence
from types import MappingProxyType
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
    static = False


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
    static = True

    @abstractmethod
    def _parse(self, file_path):
        pass

    def __init__(self, file_path, strip_keys=()):
        data = self._parse(file_path)
        self._stripped = {k: data.pop(k) for k in strip_keys if k in data}
        self._cfg = deep_freeze(data)

    def __getitem__(self, key):
        return self._cfg[key]

    def __iter__(self):
        return iter(self._cfg)

    def __len__(self):
        return len(self._cfg)


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


@fileloaders.register(".yaml", enabled=yaml is not None)
@fileloaders.register(".yml", enabled=yaml is not None)
class YAMLLoader(FileLoader):

    @staticmethod
    def _parse(file_path):
        with open(file_path, 'r') as fp:
            return yaml.safe_load(fp)


class IncludeLoader(Loader):
    static = True

    def __init__(self, including, included):
        if not getattr(including, 'static', False):
            raise TypeError(including)
        if not getattr(included, 'static', False):
            raise TypeError(included)
        self.including = including
        self.included = included
        self._get_cached = functools.cache(self._get_helper)

    def _get_helper(self, key):
        in_including = key in self.including
        in_included = key in self.included
        if in_including and in_included:
            return deep_merge(self.including[key], self.included[key])
        if in_including:
            return self.including[key]
        if in_included:
            return self.included[key]
        raise KeyError(key)

    def __getitem__(self, key):
        return self._get_cached(key)

    def __iter__(self):
        return iter(dict.fromkeys([*self.included, *self.including]))

    def __len__(self):
        return sum(1 for _ in self)

    def __contains__(self, key):
        return key in self.including or key in self.included


class Config(MutableMapping):
    # TODO?: Type validation
    def __init__(self, loaders, **kwargs):
        '''loaders is an iterable of Loader
        Loader implements the Mapping interface
        Config implements the MutableMapping interface
        Priority order is inverted - a later Loader overrides earlier ones.
        Ex. If you pass in [FileLoader, EnvLoader], values from EnvLoader will override those from FileLoader
        **kwargs has highest priority - overrides everything
        '''
        self.loaders = list(loaders)
        self._deleted = builtins.set()
        self._overrides = dict(kwargs)

    def get(self, key, default=None):
        if key in self._deleted:
            return default
        if key in self._overrides:
            return self._overrides[key]
        candidate = default
        for loader in self.loaders:
            # Let each loader override the candidate
            candidate = loader.get(key, candidate)
        return candidate

    def __getitem__(self, key):
        val = self.get(key, _MISSING)
        if val is _MISSING:
            raise KeyError(key)
        return val

    def __setitem__(self, key, val):
        self._deleted.discard(key)
        self._overrides[key] = val

    def __delitem__(self, key):
        if self.get(key, _MISSING) is _MISSING:
            raise KeyError(key)
        self._overrides.pop(key, None)
        self._deleted.add(key)

    def __iter__(self):
        loader_chain = itertools.chain.from_iterable(reversed(self.loaders))
        seen = builtins.set(self._deleted)
        for key in itertools.chain(self._overrides, loader_chain):
            if key not in seen:
                seen.add(key)
                yield key

    def __len__(self):
        # Warning, expensive!
        return sum(1 for _ in self)


# Primary public interface

_config = None


def make_config(env_prefix=None, file_path=None, find_file=False, include_key=None, **kwargs):
    global _config
    _loaders = []
    if include_key:
        if file_path is None:
            raise ValueError("file_path must be given when using an include_key")
        _loaders.append(resolve_includes(file_path, include_key=include_key))
    elif file_path:
        target = find_file_up(file_path) if find_file else file_path
        if not target:
            raise FileNotFoundError(file_path)
        _loaders.append(get_file_loader(target))
    if env_prefix is not None:
        _loaders.append(EnvLoader(prefix=env_prefix))
    _config = Config(_loaders, **kwargs)


def get(key, default=None):
    # Intentionally not exposed in __all__ to prevent namespace collisions
    if _config is None:
        # Log, and let _config.get raise
        _log.error("get called on uninitialized config, did you call make_config?")
    return _config.get(key, default)


def set(key, value):
    # Intentionally not exposed in __all__ to prevent namespace collisions
    if _config is None:
        # Log, and let _config.set raise
        _log.error("set called on uninitialized config, did you call make_config?")
    _config.__setitem__(key, value)


class IncludeCycleError(ValueError):
    pass


# Utility

def deep_merge(prim, sec):
    if not isinstance(prim, Mapping) or not isinstance(sec, Mapping):
        return prim
    _merged = dict(sec)
    for k, v in prim.items():
        _merged[k] = deep_merge(v, _merged[k]) if k in _merged else v
    return MappingProxyType(_merged)


def deep_freeze(val):
    if isinstance(val, Mapping):
        return MappingProxyType({k: deep_freeze(v) for k, v in val.items()})
    if isinstance(val, Sequence) and not isinstance(val, (str, bytes, bytearray)):
        return tuple(deep_freeze(v) for v in val)
    return val


def resolve_includes(entry_file, include_key='include-cfg'):
    included = list()
    loaders = list()
    curr = find_file_up(entry_file)
    while curr is not None:
        curr = os.path.realpath(curr)
        if curr in included:
            raise IncludeCycleError(curr)
        included.append(curr)
        loader = get_file_loader(curr, strip_keys=(include_key,))
        loaders.append(loader)
        _next = loader._stripped.get(include_key)
        curr = find_relative_file(curr, _next)
    if not loaders:
        raise FileNotFoundError(entry_file)
    ret = loaders[-1]
    for loader in reversed(loaders[:-1]):
        ret = IncludeLoader(including=loader, included=ret)
    return ret


def find_relative_file(base, target):
    if target is None:
        return None
    if os.path.isabs(target) and os.path.isfile(target):
        return target
    ret = os.path.join(os.path.dirname(base), target)
    if os.path.isfile(ret):
        return ret
    raise FileNotFoundError(target if os.path.isabs(target) else ret)


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


def get_file_loader(file_path, /, **kwargs):
    for ext in fileloaders:
        if file_path.endswith(ext):
            return fileloaders[ext](file_path, **kwargs)
    _unsupported_ext(file_path)


def _unsupported_ext(fname):
    _log.error(f"Can't detect a supported extension for {fname}")
    _log.debug(f"Supported extensions: {list(fileloaders.keys())}")
    raise ValueError(fname)
