"""Simple interface for loading and using configurations.

Usage::

    import cfgmgr

    cfgmgr.make_config(env_prefix="CFG_", file_path="config.json")
    val = cfgmgr.getkey("KEY")  # Reads os.environ["CFG_KEY"]
    cfgmgr.setkey("KEY", 'a')
    cfgmgr.get()["KEY"]  # 'a'
"""
import os
import json
import pathlib
import logging
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


__all__ = [
        # Primary public interface
        'make_config', 'getkey', 'setkey', 'get', 'Config', 'IncludeCycleError',
        # Loaders
        'Loader', 'FileLoader', 'EnvLoader', 'JSONLoader', 'TOMLLoader', 'YAMLLoader', 'DotEnvLoader', 'IncludeLoader',
        # Utility
        "deep_merge", "deep_freeze", "resolve_includes", "find_relative_file", "find_file_up", "get_file_loader"
]

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
    """Abstract interface for configuration data sources.

    A Loader is a Mapping over a data source for a configuration.
    """

    static = False
    """bool: True if the underlying data source is immutable.

    A loader itself is always immutable, but the underlying data source may
    still be mutable through other means (like EnvLoader via os.environ),
    in which case static is False.
    """


class EnvLoader(Loader):
    """Loader for environment variables."""

    def __init__(self, prefix=""):
        """Initialize with environment variables beginning with ``prefix``.

        Only variables beginning with ``prefix`` are exposed through this loader
        Ex. ``prefix = ""`` to load all env vars
        """
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
    """Abstract base class for loaders reading from a file.

    `FileLoader` has ``static = True`` since the stored internal state is immutable.
    """
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
    """Load JSON files.

    Uses stdlib ``json`` module.
    """

    @staticmethod
    def _parse(file_path):
        with open(file_path, 'r') as fp:
            return json.load(fp)


@fileloaders.register(".toml", enabled=tomllib is not None)
class TOMLLoader(FileLoader):
    """Load TOML files.

    Requires python>=3.11 since it uses stdlib ``tomllib``.
    """

    @staticmethod
    def _parse(file_path):
        with open(file_path, 'rb') as fp:
            return tomllib.load(fp)


@fileloaders.register(".env", enabled=dotenv is not None)
class DotEnvLoader(FileLoader):
    """Load .env files.

    Uses python-dotenv. (``dotenv.dotenv_values``, so ``os.environ`` is not modified)
    """

    @staticmethod
    def _parse(file_path):
        return dotenv.dotenv_values(dotenv_path=file_path)


@fileloaders.register(".yaml", enabled=yaml is not None)
@fileloaders.register(".yml", enabled=yaml is not None)
class YAMLLoader(FileLoader):
    """Load YAML files.

    Uses PyYAML. (``yaml.safe_load``)
    """

    @staticmethod
    def _parse(file_path):
        with open(file_path, 'r') as fp:
            return yaml.safe_load(fp)


class IncludeLoader(Loader):
    """Composite `Loader` subclass for files that includes another file."""
    static = True

    def __init__(self, including, included):
        """Construct a composite loader out of two static `Loader` instances.

        Args:
            including (Loader): Loader for file that includes the other
            included  (Loader): Loader for the file being included

        Raises:
            TypeError: If either ``including`` or ``included`` are non static
        """
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
    """Primary interface for configuration access.

    Composed of an ordered set of loaders. Implements ``MutableMapping``.
    Contained loaders shadow each others' keys.
    Setting a key using MutableMapping methods shadows all loaders.

    Performance warning: ``len`` on a `Config` instance iterates over it (albeit non exhausting)
    """
    def __init__(self, loaders, **kwargs):
        """Construct a Config from multiple loaders

        Args:
            loaders (iterable[Loader]): Source loaders for this config
                Priority order: later loaders override the ones before them.
                Ex. If you pass in [FileLoader, EnvLoader], values from EnvLoader will override those from FileLoader
            **kwargs: Highest priority key value pairs in the config - overrides everything
        """
        self.loaders = list(loaders)
        self._deleted = set()
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
        seen = set(self._deleted)
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
    """Initialize a global default `Config` instance.

    Args:
        env_prefix (str): If provided, used to construct an `EnvLoader` instance for the default config.
        file_path (str): If provided, used to construct a `FileLoader` instance for the default config.
            `make_config` will try to auto detect the appropriate `FileLoader` subclass via the file extension.
        find_file (bool): If ``True``, crawl upwards from current working directory until ``file_path`` is found.
        include_key (str): Can only be given alongside a ``file_path``.
            If given, the value corresponding to it will be treated as another file to load, recursively.
        **kwargs: Passed to ``Config.__init__``, overrides values from all loaders.

    Raises:
        ValueError: ``include_key`` given without ``file_path``.
        FileNotFoundError: ``file_path`` or any files inferred from ``include_key`` cannot be found.
        IncludeCycleError: Cyclical includes detected

    Returns:
        None
    """
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


def get():
    """Get the current global default config.

    Returns:
        The current global default `Config` instance.
        Future `make_config` calls will create a new global config.
        Can be used to "store" configs created by `make_config`.
    """
    return _config


def getkey(key, default=None):
    """Get a value from the current global default config.

    Args:
        key (str): Passed to `Config.get`.
        default (Optional): If ``key`` is not found, return this instead.

    Returns:
        The value corresponding to ``key`` in the current global default config.

    Raises:
        AttributeError: If no global default config is initialized (via `make_config`)
    """
    if _config is None:
        # Log, and let _config.get raise
        _log.error("get called on uninitialized config, did you call make_config?")
    return _config.get(key, default)


def setkey(key, value):
    """Set a value in the current global default config.

    Args:
        key (str): key to set the value for
        value (Any): The value to store

    Returns:
        None

    Raises:
        AttributeError: If no global default config is initialized (via `make_config`)
    """
    if _config is None:
        # Log, and let _config.__setitem__ raise
        _log.error("set called on uninitialized config, did you call make_config?")
    _config.__setitem__(key, value)


class IncludeCycleError(ValueError):
    """Raised when a file's include directives form a cycle."""


# Utility

def deep_merge(prim, sec):
    """Recursively merge two mappings, with ``prim`` taking priority.

    Where both mappings contain the same key and both values are themselves
    mappings, the values are merged recursively. Otherwise the value from
    ``prim`` wins. If either argument is not a mapping, ``prim`` is returned as-is.

    Args:
        prim (Any): The higher-priority value.
        sec (Any): The lower-priority value.

    Returns:
        The merged result. A read-only ``MappingProxyType`` when a merge
        occurred, otherwise ``prim`` unchanged.
    """
    if not isinstance(prim, Mapping) or not isinstance(sec, Mapping):
        return prim
    _merged = dict(sec)
    for k, v in prim.items():
        _merged[k] = deep_merge(v, _merged[k]) if k in _merged else v
    return MappingProxyType(_merged)


def deep_freeze(val):
    """Recursively convert a value into an immutable structure.

    Mappings become read-only ``MappingProxyType``\\ s and sequences (other than
    ``str``, ``bytes``, and ``bytearray``) become tuples, applied recursively.
    Any other value is returned unchanged.

    Args:
        val (Any): The value to freeze.

    Returns:
        An immutable copy of `val`.
    """
    if isinstance(val, Mapping):
        return MappingProxyType({k: deep_freeze(v) for k, v in val.items()})
    if isinstance(val, Sequence) and not isinstance(val, (str, bytes, bytearray)):
        return tuple(deep_freeze(v) for v in val)
    return val


def resolve_includes(entry_file, include_key='include-cfg'):
    """Recursively construct loaders for a file with an include directive

    Args:
        entry_file (str): Path of the entry point file
        include_key (str): Include key that specifies the files to include.
            Defaults to 'include-cfg'.

    Returns:
        A `Loader` instance representing the merged data from all found files

    Raises:
        IncludeCycleError: If the include directives form a cycle.
        FileNotFoundError: If ``entry_file`` or any included file cannot be found.
    """
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
    """Find a file path relative to another.

    Args:
        base (str): File path of the base file.
        target (str): Path of the target relative to base.

    Returns:
        Canonical path of the target.

    Raises:
        FileNotFoundError: If no file can be found.
    """
    if target is None:
        return None
    if os.path.isabs(target) and os.path.isfile(target):
        return target
    ret = os.path.join(os.path.dirname(base), target)
    if os.path.isfile(ret):
        return ret
    raise FileNotFoundError(target if os.path.isabs(target) else ret)


def find_file_up(basename):
    """Find a file crawling up from the current working directory

    Args:
        basename (str): Name of the file to find

    Returns:
        Path of the found file, or None if no such file can be found.

    Raises:
        ValueError: If the file extension is not registered to a corresponding `Loader`.
    """
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
    """Get a constructed loader for a file

    Attempts to find a registered loader for the extension of the given file

    Args:
        file_path (str): File path to construct a loader from

    Returns:
        Constructed `Loader` instance for the file

    Raises:
        ValueError: If the extension is not supported.
    """
    for ext in fileloaders:
        if file_path.endswith(ext):
            return fileloaders[ext](file_path, **kwargs)
    _unsupported_ext(file_path)


def _unsupported_ext(fname):
    _log.error(f"Can't detect a supported extension for {fname}")
    _log.debug(f"Supported extensions: {list(fileloaders.keys())}")
    raise ValueError(fname)
