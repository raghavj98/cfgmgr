import unittest
import cfgmgr
import os
import json
import shutil
import logging
from types import MappingProxyType


def setUpModule():
    # Several tests deliberately trigger error-level logs; silence them
    # so the test output stays readable.
    logging.disable(logging.CRITICAL)


def tearDownModule():
    logging.disable(logging.NOTSET)


class DictLoader(cfgmgr.Loader):
    '''Minimal in-memory Loader used to exercise Config directly.'''

    def __init__(self, values):
        self._values = values

    def __getitem__(self, key):
        return self._values[key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)


# --------------------------------------------------------------------------
# EnvLoader
# --------------------------------------------------------------------------

class EnvLoaderClassTest(unittest.TestCase):
    '''Exercises EnvLoader directly, independent of Config/make_config.'''

    def test_prefix_concatenation(self):
        os.environ["CFGMGRTEST_FOO"] = "bar"
        self.addCleanup(os.environ.pop, "CFGMGRTEST_FOO", None)
        loader = cfgmgr.EnvLoader(prefix="CFGMGRTEST_")
        self.assertEqual(loader.get("FOO"), "bar")

    def test_empty_prefix_default(self):
        loader = cfgmgr.EnvLoader()
        self.assertEqual(loader.prefix, "")

    def test_missing_returns_none(self):
        loader = cfgmgr.EnvLoader(prefix="CFGMGRTEST_")
        self.assertIsNone(loader.get("DOES_NOT_EXIST"))

    def test_missing_returns_default(self):
        loader = cfgmgr.EnvLoader(prefix="CFGMGRTEST_")
        self.assertEqual(loader.get("DOES_NOT_EXIST", "fallback"), "fallback")


class EnvLoaderTest(unittest.TestCase):

    def setUp(self):
        cfgmgr.make_config()  # Reset fixture in between test cases

    def test_prefix(self):
        os.environ["CFGMGRTEST_FOO"] = "bar"
        cfgmgr.make_config(env_prefix="CFGMGRTEST_")
        self.assertEqual(cfgmgr.getkey("FOO"), "bar")

    def test_noprefix(self):
        os.environ["CFGMGRTEST_FOO"] = "bar"
        cfgmgr.make_config(env_prefix="")
        self.assertEqual(cfgmgr.getkey("CFGMGRTEST_FOO"), "bar")

    def test_negative_prefix(self):
        os.environ["FOO"] = "bar"
        cfgmgr.make_config(env_prefix="CFGMGRTEST_")
        self.assertEqual(cfgmgr.getkey("FOO"), None)

    def test_negative_noprefix(self):
        os.environ["FOO"] = "bar"
        cfgmgr.make_config()
        self.assertEqual(cfgmgr.getkey("FOO"), None)

    def test_default_for_missing_key(self):
        cfgmgr.make_config(env_prefix="CFGMGRTEST_")
        self.assertEqual(cfgmgr.getkey("MISSING", "fallback"), "fallback")

    def test_dynamic_resolution(self):
        # Values are resolved on each get(), so env changes are reflected.
        cfgmgr.make_config(env_prefix="CFGMGRTEST_")
        self.assertIsNone(cfgmgr.getkey("DYNAMIC"))
        os.environ["CFGMGRTEST_DYNAMIC"] = "now_set"
        self.addCleanup(os.environ.pop, "CFGMGRTEST_DYNAMIC", None)
        self.assertEqual(cfgmgr.getkey("DYNAMIC"), "now_set")


# --------------------------------------------------------------------------
# JSONLoader
# --------------------------------------------------------------------------

class JSONLoaderClassTest(unittest.TestCase):
    '''Exercises JSONLoader directly.'''

    def setUp(self):
        self.start_dir = os.getcwd()
        if os.path.exists("tmp_test"):
            shutil.rmtree("tmp_test")
        os.makedirs("tmp_test")
        with open("tmp_test/good.json", 'w') as fp:
            json.dump({"FOO": "bar", "NUM": 1}, fp)
        with open("tmp_test/bad.json", 'w') as fp:
            fp.write("{not valid json")

    def tearDown(self):
        os.chdir(self.start_dir)
        shutil.rmtree("tmp_test")

    def test_get_existing_key(self):
        loader = cfgmgr.JSONLoader("tmp_test/good.json")
        self.assertEqual(loader.get("FOO"), "bar")

    def test_get_missing_key_default(self):
        loader = cfgmgr.JSONLoader("tmp_test/good.json")
        self.assertEqual(loader.get("MISSING", "fallback"), "fallback")
        self.assertIsNone(loader.get("MISSING"))

    def test_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            cfgmgr.JSONLoader("tmp_test/does_not_exist.json")

    def test_invalid_json(self):
        with self.assertRaises(json.JSONDecodeError):
            cfgmgr.JSONLoader("tmp_test/bad.json")


class JSONLoaderTest(unittest.TestCase):

    def setUp(self):
        self.start_dir = os.getcwd()
        os.makedirs("tmp_test/some/dir")
        with open("tmp_test/some/file1.json", 'w') as fp:
            json.dump({
                "FOO": "bar"
            }, fp)
        os.chdir("tmp_test/some/dir")
        cfgmgr.make_config()

    def test_positive(self):
        cfgmgr.make_config(file_path="file1.json", find_file=True)
        self.assertEqual(cfgmgr.getkey("FOO"), "bar")

    def test_find_file_in_cwd(self):
        with open("local.json", 'w') as fp:
            json.dump({"LOCAL": "value"}, fp)
        cfgmgr.make_config(file_path="local.json", find_file=True)
        self.assertEqual(cfgmgr.getkey("LOCAL"), "value")

    def test_file_path_without_find_file(self):
        # Regression guard: file_path given, find_file omitted.
        with open("local.json", 'w') as fp:
            json.dump({"LOCAL": "value"}, fp)
        cfgmgr.make_config(file_path="local.json")
        self.assertEqual(cfgmgr.getkey("LOCAL"), "value")

    def test_missing_key_returns_default(self):
        cfgmgr.make_config(file_path="file1.json", find_file=True)
        self.assertEqual(cfgmgr.getkey("MISSING", "fallback"), "fallback")

    def tearDown(self):
        os.chdir(self.start_dir)
        shutil.rmtree("tmp_test")


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

class ConfigTest(unittest.TestCase):
    '''Exercises the Config class directly with in-memory loaders.'''

    def test_get_from_single_loader(self):
        cfg = cfgmgr.Config([DictLoader({"a": 1})])
        self.assertEqual(cfg.get("a"), 1)

    def test_get_missing_returns_default(self):
        cfg = cfgmgr.Config([DictLoader({"a": 1})])
        self.assertIsNone(cfg.get("missing"))
        self.assertEqual(cfg.get("missing", "d"), "d")

    def test_no_loaders_returns_default(self):
        cfg = cfgmgr.Config([])
        self.assertIsNone(cfg.get("x"))
        self.assertEqual(cfg.get("x", "d"), "d")

    def test_later_loader_overrides_earlier(self):
        cfg = cfgmgr.Config([
            DictLoader({"shared": "first"}),
            DictLoader({"shared": "second"}),
        ])
        self.assertEqual(cfg.get("shared"), "second")

    def test_later_loader_does_not_clobber_with_default(self):
        # A later loader lacking the key must not overwrite an earlier hit.
        cfg = cfgmgr.Config([
            DictLoader({"only_first": "kept"}),
            DictLoader({"other": "x"}),
        ])
        self.assertEqual(cfg.get("only_first"), "kept")

    def test_overrides_from_kwargs_win(self):
        cfg = cfgmgr.Config([DictLoader({"a": "loader"})], a="override")
        self.assertEqual(cfg.get("a"), "override")

    def test_setitem_overrides_loader(self):
        cfg = cfgmgr.Config([DictLoader({"a": "loader"})])
        cfg["a"] = "set"
        self.assertEqual(cfg.get("a"), "set")

    def test_setitem_new_key(self):
        cfg = cfgmgr.Config([])
        cfg["new"] = "value"
        self.assertEqual(cfg.get("new"), "value")

    def test_getitem_present(self):
        cfg = cfgmgr.Config([DictLoader({"a": 1})])
        self.assertEqual(cfg["a"], 1)

    def test_getitem_missing_raises_keyerror(self):
        cfg = cfgmgr.Config([DictLoader({"a": 1})])
        with self.assertRaises(KeyError):
            cfg["missing"]

    def test_getitem_falsy_values(self):
        # Falsy values are real values, not "missing".
        cfg = cfgmgr.Config([DictLoader({
            "zero": 0, "empty": "", "false": False, "none": None,
        })])
        self.assertEqual(cfg["zero"], 0)
        self.assertEqual(cfg["empty"], "")
        self.assertIs(cfg["false"], False)
        self.assertIsNone(cfg["none"])

    def test_contains_present_and_absent(self):
        cfg = cfgmgr.Config([DictLoader({"a": 1})])
        self.assertIn("a", cfg)
        self.assertNotIn("missing", cfg)

    def test_contains_falsy_value(self):
        cfg = cfgmgr.Config([DictLoader({"zero": 0, "none": None})])
        self.assertIn("zero", cfg)
        self.assertIn("none", cfg)

    def test_contains_override(self):
        cfg = cfgmgr.Config([])
        cfg["k"] = "v"
        self.assertIn("k", cfg)


# --------------------------------------------------------------------------
# make_config
# --------------------------------------------------------------------------

class MakeConfigTest(unittest.TestCase):

    def setUp(self):
        self.start_dir = os.getcwd()
        if os.path.exists("tmp_test"):
            shutil.rmtree("tmp_test")
        os.makedirs("tmp_test")
        with open("tmp_test/config.json", 'w') as fp:
            json.dump({"SHARED": "from_file", "ONLY_FILE": "file_value"}, fp)
        os.chdir("tmp_test")
        cfgmgr.make_config()

    def tearDown(self):
        os.chdir(self.start_dir)
        shutil.rmtree("tmp_test")

    def test_no_args(self):
        cfgmgr.make_config()
        self.assertIsNone(cfgmgr.getkey("anything"))
        self.assertEqual(cfgmgr.getkey("anything", "d"), "d")

    def test_kwargs_overrides(self):
        cfgmgr.make_config(FOO="kwarg_value")
        self.assertEqual(cfgmgr.getkey("FOO"), "kwarg_value")

    def test_kwargs_beat_loaders(self):
        os.environ["CFGMGRTEST_K"] = "env_value"
        self.addCleanup(os.environ.pop, "CFGMGRTEST_K", None)
        cfgmgr.make_config(env_prefix="CFGMGRTEST_", K="kwarg_value")
        self.assertEqual(cfgmgr.getkey("K"), "kwarg_value")

    def test_env_overrides_file(self):
        os.environ["CFGMGRTEST_SHARED"] = "from_env"
        self.addCleanup(os.environ.pop, "CFGMGRTEST_SHARED", None)
        cfgmgr.make_config(env_prefix="CFGMGRTEST_", file_path="config.json")
        self.assertEqual(cfgmgr.getkey("SHARED"), "from_env")

    def test_file_value_survives_when_env_missing(self):
        cfgmgr.make_config(env_prefix="CFGMGRTEST_", file_path="config.json")
        self.assertEqual(cfgmgr.getkey("ONLY_FILE"), "file_value")

    def test_reinit_resets_config(self):
        cfgmgr.make_config(FOO="first")
        cfgmgr.make_config(FOO="second")
        self.assertEqual(cfgmgr.getkey("FOO"), "second")
        cfgmgr.make_config()
        self.assertIsNone(cfgmgr.getkey("FOO"))

    def test_unsupported_extension(self):
        with self.assertRaises(ValueError):
            cfgmgr.make_config(file_path="config.xyz")

    def test_find_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            cfgmgr.make_config(file_path="absent_xyz.json", find_file=True)

    def test_file_not_found_without_find_file(self):
        with self.assertRaises(FileNotFoundError):
            cfgmgr.make_config(file_path="absent_xyz.json")


# --------------------------------------------------------------------------
# Module-level getkey / setkey / get
# --------------------------------------------------------------------------

class GetSetTest(unittest.TestCase):

    def test_setkey_then_getkey(self):
        cfgmgr.make_config()
        cfgmgr.setkey("k", "v")
        self.assertEqual(cfgmgr.getkey("k"), "v")

    def test_getkey_default(self):
        cfgmgr.make_config()
        self.assertEqual(cfgmgr.getkey("missing", "d"), "d")

    def test_setkey_overrides_loader(self):
        os.environ["CFGMGRTEST_X"] = "env_value"
        self.addCleanup(os.environ.pop, "CFGMGRTEST_X", None)
        cfgmgr.make_config(env_prefix="CFGMGRTEST_")
        cfgmgr.setkey("X", "set_value")
        self.assertEqual(cfgmgr.getkey("X"), "set_value")

    def test_getkey_before_make_config(self):
        cfgmgr._config = None
        with self.assertRaises(AttributeError):
            cfgmgr.getkey("k")

    def test_setkey_before_make_config(self):
        cfgmgr._config = None
        with self.assertRaises(AttributeError):
            cfgmgr.setkey("k", "v")

    def test_get_returns_live_config(self):
        cfgmgr.make_config()
        cfg = cfgmgr.get()
        self.assertIsInstance(cfg, cfgmgr.Config)
        self.assertIs(cfg, cfgmgr._config)

    def test_get_reflects_setkey(self):
        cfgmgr.make_config()
        cfgmgr.setkey("k", "v")
        self.assertEqual(cfgmgr.get()["k"], "v")

    def test_get_before_make_config_returns_none(self):
        cfgmgr._config = None
        self.assertIsNone(cfgmgr.get())


# --------------------------------------------------------------------------
# Utility helpers
# --------------------------------------------------------------------------

class FindFileUpTest(unittest.TestCase):

    def setUp(self):
        self.start_dir = os.getcwd()
        os.makedirs("tmp_test/some/dir")
        with open("tmp_test/ancestor.json", 'w') as fp:
            json.dump({}, fp)
        with open("tmp_test/some/dir/local.json", 'w') as fp:
            json.dump({}, fp)
        os.chdir("tmp_test/some/dir")

    def tearDown(self):
        os.chdir(self.start_dir)
        shutil.rmtree("tmp_test")

    def test_finds_in_cwd(self):
        found = cfgmgr.find_file_up("local.json")
        self.assertTrue(found and os.path.isfile(found))

    def test_finds_in_ancestor(self):
        found = cfgmgr.find_file_up("ancestor.json")
        self.assertTrue(found and os.path.isfile(found))

    def test_not_found_returns_none(self):
        self.assertIsNone(cfgmgr.find_file_up("absent_xyz.json"))

    def test_unsupported_extension(self):
        with self.assertRaises(ValueError):
            cfgmgr.find_file_up("config.xyz")


class GetFileLoaderTest(unittest.TestCase):

    def setUp(self):
        self.start_dir = os.getcwd()
        if os.path.exists("tmp_test"):
            shutil.rmtree("tmp_test")
        os.makedirs("tmp_test")
        with open("tmp_test/config.json", 'w') as fp:
            json.dump({}, fp)

    def tearDown(self):
        os.chdir(self.start_dir)
        shutil.rmtree("tmp_test")

    def test_returns_json_loader(self):
        loader = cfgmgr.get_file_loader("tmp_test/config.json")
        self.assertIsInstance(loader, cfgmgr.JSONLoader)

    def test_unsupported_extension(self):
        with self.assertRaises(ValueError):
            cfgmgr.get_file_loader("config.xyz")


# --------------------------------------------------------------------------
# Loader registry and abstract base
# --------------------------------------------------------------------------

class StubLoader(cfgmgr.Loader):
    '''Custom file loader registered for a made-up extension.'''

    def __init__(self, file_path):
        self.file_path = file_path

    def __getitem__(self, key):
        if key == "STUB":
            return "stub_value"
        raise KeyError(key)

    def __iter__(self):
        return iter(["stub_value"])

    def __len__(self):
        return 1


class RegistryTest(unittest.TestCase):

    def tearDown(self):
        cfgmgr.fileloaders.data.pop(".stub", None)

    def test_register_returns_class(self):
        result = cfgmgr.fileloaders.register(".stub")(StubLoader)
        self.assertIs(result, StubLoader)

    def test_registered_loader_used_by_get_file_loader(self):
        cfgmgr.fileloaders.register(".stub")(StubLoader)
        loader = cfgmgr.get_file_loader("anything.stub")
        self.assertIsInstance(loader, StubLoader)

    def test_registered_loader_used_by_make_config(self):
        cfgmgr.fileloaders.register(".stub")(StubLoader)
        cfgmgr.make_config(file_path="anything.stub")
        self.assertEqual(cfgmgr.getkey("STUB"), "stub_value")


class LoaderABCTest(unittest.TestCase):

    def test_cannot_instantiate_loader(self):
        with self.assertRaises(TypeError):
            cfgmgr.Loader()

    def test_subclass_without_get_cannot_instantiate(self):
        class Incomplete(cfgmgr.Loader):
            pass
        with self.assertRaises(TypeError):
            Incomplete()


# --------------------------------------------------------------------------
# Loader Mapping interface
#
# The refactor makes every Loader a collections.abc.Mapping. Subclasses only
# implement __getitem__/__iter__/__len__; get/keys/items/values/__contains__
# come from Mapping. These tests pin that contract.
# --------------------------------------------------------------------------

class FileLoaderMappingTest(unittest.TestCase):
    '''JSONLoader exercised as a full Mapping (JSON is always available).'''

    def setUp(self):
        self.start_dir = os.getcwd()
        if os.path.exists("tmp_test"):
            shutil.rmtree("tmp_test")
        os.makedirs("tmp_test")
        with open("tmp_test/good.json", 'w') as fp:
            json.dump({"FOO": "bar", "NUM": 1}, fp)
        self.loader = cfgmgr.JSONLoader("tmp_test/good.json")

    def tearDown(self):
        os.chdir(self.start_dir)
        shutil.rmtree("tmp_test")

    def test_is_mapping(self):
        from collections.abc import Mapping
        self.assertIsInstance(self.loader, Mapping)

    def test_iter_yields_keys(self):
        self.assertEqual(set(self.loader), {"FOO", "NUM"})

    def test_len(self):
        self.assertEqual(len(self.loader), 2)

    def test_contains(self):
        self.assertIn("FOO", self.loader)
        self.assertNotIn("MISSING", self.loader)

    def test_keys_items_values(self):
        self.assertEqual(set(self.loader.keys()), {"FOO", "NUM"})
        self.assertEqual(set(self.loader.values()), {"bar", 1})
        self.assertEqual(dict(self.loader.items()), {"FOO": "bar", "NUM": 1})

    def test_getitem(self):
        self.assertEqual(self.loader["FOO"], "bar")

    def test_getitem_missing_raises_keyerror(self):
        with self.assertRaises(KeyError):
            self.loader["MISSING"]

    def test_dict_round_trip(self):
        self.assertEqual(dict(self.loader), {"FOO": "bar", "NUM": 1})


class EnvLoaderMappingTest(unittest.TestCase):
    '''EnvLoader exercised as a full Mapping.

    NOTE: these currently fail -- EnvLoader.__iter__/__len__ call the
    non-existent str method `beginswith` (should be `startswith`),
    __len__ calls len() on a generator, and __iter__ does not strip the
    prefix. The tests below encode the intended behaviour.
    '''

    def setUp(self):
        os.environ["CFGMGRITER_A"] = "1"
        os.environ["CFGMGRITER_B"] = "2"
        self.addCleanup(os.environ.pop, "CFGMGRITER_A", None)
        self.addCleanup(os.environ.pop, "CFGMGRITER_B", None)
        self.loader = cfgmgr.EnvLoader(prefix="CFGMGRITER_")

    def test_iter_yields_prefix_stripped_keys(self):
        # Only our keys are checked; the process may hold unrelated env vars.
        keys = set(self.loader)
        self.assertIn("A", keys)
        self.assertIn("B", keys)
        self.assertNotIn("CFGMGRITER_A", keys)  # prefix must be stripped

    def test_len_counts_prefixed_vars(self):
        # Exactly the two we set carry this prefix.
        self.assertEqual(len(self.loader), 2)

    def test_contains_uses_stripped_key(self):
        self.assertIn("A", self.loader)
        self.assertNotIn("CFGMGRITER_A", self.loader)
        self.assertNotIn("MISSING", self.loader)

    def test_dict_round_trip(self):
        # Iterating then indexing each key must resolve back to the value.
        self.assertEqual(dict(self.loader), {"A": "1", "B": "2"})


# --------------------------------------------------------------------------
# FileLoader abstract base
# --------------------------------------------------------------------------

class FileLoaderABCTest(unittest.TestCase):

    def test_cannot_instantiate_fileloader(self):
        # _parse is abstract.
        with self.assertRaises(TypeError):
            cfgmgr.FileLoader("anything")

    def test_subclass_without_parse_cannot_instantiate(self):
        class NoParse(cfgmgr.FileLoader):
            pass
        with self.assertRaises(TypeError):
            NoParse("anything")

    def test_subclass_with_parse_instantiates(self):
        class InMemory(cfgmgr.FileLoader):
            @staticmethod
            def _parse(file_path):
                return {"K": "V"}
        loader = InMemory("ignored")
        self.assertEqual(loader.get("K"), "V")
        self.assertEqual(dict(loader), {"K": "V"})


# --------------------------------------------------------------------------
# Conditional loader registration
# --------------------------------------------------------------------------

class ConditionalRegistrationTest(unittest.TestCase):
    '''Optional loaders register only when their dependency is importable.'''

    def test_toml_registered_iff_tomllib_available(self):
        self.assertEqual(
            ".toml" in cfgmgr.fileloaders,
            cfgmgr.tomllib is not None,
        )

    def test_dotenv_registered_iff_dotenv_available(self):
        self.assertEqual(
            ".env" in cfgmgr.fileloaders,
            cfgmgr.dotenv is not None,
        )

    def test_yaml_registered_iff_pyyaml_available(self):
        # YAMLLoader registers both extensions, gated on PyYAML.
        registered = (".yaml" in cfgmgr.fileloaders
                      and ".yml" in cfgmgr.fileloaders)
        self.assertEqual(registered, cfgmgr.yaml is not None)

    def test_json_always_registered(self):
        self.assertIn(".json", cfgmgr.fileloaders)

    def test_register_disabled_skips_registration(self):
        sentinel = type("Sentinel", (), {})
        returned = cfgmgr.fileloaders.register(".nope", enabled=False)(sentinel)
        self.addCleanup(cfgmgr.fileloaders.data.pop, ".nope", None)
        self.assertIs(returned, sentinel)          # class still returned
        self.assertNotIn(".nope", cfgmgr.fileloaders)  # but not registered


# --------------------------------------------------------------------------
# TOMLLoader  (Python 3.11+ / tomllib)
# --------------------------------------------------------------------------

@unittest.skipUnless(cfgmgr.tomllib is not None, "tomllib not available")
class TOMLLoaderTest(unittest.TestCase):

    def setUp(self):
        self.start_dir = os.getcwd()
        if os.path.exists("tmp_test"):
            shutil.rmtree("tmp_test")
        os.makedirs("tmp_test")
        with open("tmp_test/good.toml", 'w') as fp:
            fp.write('FOO = "bar"\nNUM = 1\n\n[section]\nKEY = "value"\n')
        with open("tmp_test/bad.toml", 'w') as fp:
            fp.write("key =\n")  # value missing -> decode error

    def tearDown(self):
        os.chdir(self.start_dir)
        shutil.rmtree("tmp_test")

    def test_get_existing_key(self):
        loader = cfgmgr.TOMLLoader("tmp_test/good.toml")
        self.assertEqual(loader.get("FOO"), "bar")
        self.assertEqual(loader.get("NUM"), 1)

    def test_get_table_as_nested_mapping(self):
        loader = cfgmgr.TOMLLoader("tmp_test/good.toml")
        self.assertEqual(loader.get("section"), {"KEY": "value"})

    def test_get_missing_key_default(self):
        loader = cfgmgr.TOMLLoader("tmp_test/good.toml")
        self.assertIsNone(loader.get("MISSING"))
        self.assertEqual(loader.get("MISSING", "fallback"), "fallback")

    def test_mapping_interface(self):
        loader = cfgmgr.TOMLLoader("tmp_test/good.toml")
        self.assertEqual(set(loader), {"FOO", "NUM", "section"})
        self.assertEqual(len(loader), 3)

    def test_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            cfgmgr.TOMLLoader("tmp_test/does_not_exist.toml")

    def test_invalid_toml(self):
        with self.assertRaises(cfgmgr.tomllib.TOMLDecodeError):
            cfgmgr.TOMLLoader("tmp_test/bad.toml")

    def test_get_file_loader_returns_toml_loader(self):
        loader = cfgmgr.get_file_loader("tmp_test/good.toml")
        self.assertIsInstance(loader, cfgmgr.TOMLLoader)

    def test_make_config_with_toml(self):
        os.chdir("tmp_test")
        cfgmgr.make_config(file_path="good.toml")
        self.assertEqual(cfgmgr.getkey("FOO"), "bar")


# --------------------------------------------------------------------------
# DotEnvLoader  (requires python-dotenv)
# --------------------------------------------------------------------------

@unittest.skipUnless(cfgmgr.dotenv is not None, "python-dotenv not available")
class DotEnvLoaderTest(unittest.TestCase):

    def setUp(self):
        self.start_dir = os.getcwd()
        if os.path.exists("tmp_test"):
            shutil.rmtree("tmp_test")
        os.makedirs("tmp_test")
        with open("tmp_test/config.env", 'w') as fp:
            fp.write("FOO=bar\nNUM=1\n")

    def tearDown(self):
        os.chdir(self.start_dir)
        shutil.rmtree("tmp_test")

    def test_get_existing_key(self):
        loader = cfgmgr.DotEnvLoader("tmp_test/config.env")
        self.assertEqual(loader.get("FOO"), "bar")

    def test_values_are_strings(self):
        # dotenv does not coerce types -- everything is a string.
        loader = cfgmgr.DotEnvLoader("tmp_test/config.env")
        self.assertEqual(loader.get("NUM"), "1")

    def test_get_missing_key_default(self):
        loader = cfgmgr.DotEnvLoader("tmp_test/config.env")
        self.assertEqual(loader.get("MISSING", "fallback"), "fallback")

    def test_mapping_interface(self):
        loader = cfgmgr.DotEnvLoader("tmp_test/config.env")
        self.assertEqual(set(loader), {"FOO", "NUM"})
        self.assertEqual(len(loader), 2)

    def test_get_file_loader_returns_dotenv_loader(self):
        loader = cfgmgr.get_file_loader("tmp_test/config.env")
        self.assertIsInstance(loader, cfgmgr.DotEnvLoader)

    def test_make_config_with_dotenv(self):
        os.chdir("tmp_test")
        cfgmgr.make_config(file_path="config.env")
        self.assertEqual(cfgmgr.getkey("FOO"), "bar")


# --------------------------------------------------------------------------
# deep_freeze
# --------------------------------------------------------------------------

class DeepFreezeTest(unittest.TestCase):

    def test_dict_becomes_mappingproxy(self):
        frozen = cfgmgr.deep_freeze({"a": 1})
        self.assertIsInstance(frozen, MappingProxyType)

    def test_list_becomes_tuple(self):
        frozen = cfgmgr.deep_freeze([1, 2, 3])
        self.assertEqual(frozen, (1, 2, 3))
        self.assertIsInstance(frozen, tuple)

    def test_nested_recursively_frozen(self):
        frozen = cfgmgr.deep_freeze({"a": [{"b": 1}], "c": {"d": 2}})
        self.assertIsInstance(frozen["a"], tuple)
        self.assertIsInstance(frozen["a"][0], MappingProxyType)
        self.assertIsInstance(frozen["c"], MappingProxyType)

    def test_string_not_split_into_sequence(self):
        self.assertEqual(cfgmgr.deep_freeze("abc"), "abc")
        self.assertEqual(cfgmgr.deep_freeze({"s": "abc"})["s"], "abc")

    def test_scalars_unchanged(self):
        for v in (5, None, True, 1.5):
            self.assertEqual(cfgmgr.deep_freeze(v), v)

    def test_frozen_mapping_rejects_mutation(self):
        frozen = cfgmgr.deep_freeze({"a": 1})
        with self.assertRaises(TypeError):
            frozen["a"] = 2

    def test_frozen_nested_mapping_rejects_mutation(self):
        frozen = cfgmgr.deep_freeze({"outer": {"inner": 1}})
        with self.assertRaises(TypeError):
            frozen["outer"]["inner"] = 2

    def test_frozen_sequence_rejects_mutation(self):
        frozen = cfgmgr.deep_freeze({"list": [1]})
        with self.assertRaises(AttributeError):
            frozen["list"].append(2)


# --------------------------------------------------------------------------
# deep_merge   (deep_merge(prim, sec) -- prim wins)
# --------------------------------------------------------------------------

class DeepMergeTest(unittest.TestCase):

    def test_disjoint_keys_union(self):
        self.assertEqual(
            dict(cfgmgr.deep_merge({"a": 1}, {"b": 2})),
            {"a": 1, "b": 2},
        )

    def test_shared_scalar_primary_wins(self):
        self.assertEqual(cfgmgr.deep_merge({"a": 1}, {"a": 2})["a"], 1)

    def test_nested_mapping_recursive_merge(self):
        merged = cfgmgr.deep_merge(
            {"d": {"x": 1}},
            {"d": {"x": 9, "y": 2}},
        )
        # x: primary wins; y: only in secondary, preserved.
        self.assertEqual(dict(merged["d"]), {"x": 1, "y": 2})

    def test_three_levels_deep(self):
        merged = cfgmgr.deep_merge(
            {"a": {"b": {"c": "new"}}},
            {"a": {"b": {"c": "old", "d": "keep"}}},
        )
        self.assertEqual(dict(merged["a"]["b"]), {"c": "new", "d": "keep"})

    def test_list_overrides_not_extends(self):
        # Conventional behaviour: lists replace, they don't concatenate.
        merged = cfgmgr.deep_merge({"l": [1, 2]}, {"l": [3, 4, 5]})
        self.assertEqual(merged["l"], [1, 2])

    def test_type_mismatch_primary_wins(self):
        self.assertEqual(
            cfgmgr.deep_merge({"k": {"a": 1}}, {"k": "scalar"})["k"],
            {"a": 1},
        )
        self.assertEqual(
            cfgmgr.deep_merge({"k": "scalar"}, {"k": {"a": 1}})["k"],
            "scalar",
        )

    def test_non_mapping_returns_primary(self):
        self.assertEqual(cfgmgr.deep_merge("x", "y"), "x")
        self.assertEqual(cfgmgr.deep_merge(5, {"a": 1}), 5)

    def test_result_is_frozen(self):
        merged = cfgmgr.deep_merge({"d": {"x": 1}}, {"d": {"x": 2}})
        self.assertIsInstance(merged, MappingProxyType)
        self.assertIsInstance(merged["d"], MappingProxyType)

    def test_inputs_not_mutated(self):
        prim = {"d": {"x": 1}}
        sec = {"d": {"x": 2, "y": 3}}
        cfgmgr.deep_merge(prim, sec)
        self.assertEqual(prim, {"d": {"x": 1}})
        self.assertEqual(sec, {"d": {"x": 2, "y": 3}})


# --------------------------------------------------------------------------
# IncludeLoader
# --------------------------------------------------------------------------

class StaticDictLoader(cfgmgr.Loader):
    '''In-memory Loader that advertises itself as static (frozen).'''
    static = True

    def __init__(self, values):
        self._values = cfgmgr.deep_freeze(values)

    def __getitem__(self, key):
        return self._values[key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)


class IncludeLoaderTest(unittest.TestCase):

    def test_key_in_including_only(self):
        il = cfgmgr.IncludeLoader(StaticDictLoader({"a": "inc"}),
                                  StaticDictLoader({"b": "base"}))
        self.assertEqual(il["a"], "inc")

    def test_key_in_included_only(self):
        il = cfgmgr.IncludeLoader(StaticDictLoader({"a": "inc"}),
                                  StaticDictLoader({"b": "base"}))
        self.assertEqual(il["b"], "base")

    def test_shared_scalar_including_wins(self):
        il = cfgmgr.IncludeLoader(StaticDictLoader({"k": "including"}),
                                  StaticDictLoader({"k": "included"}))
        self.assertEqual(il["k"], "including")

    def test_shared_nested_mapping_merged(self):
        il = cfgmgr.IncludeLoader(
            StaticDictLoader({"d": {"x": "new"}}),
            StaticDictLoader({"d": {"x": "old", "y": "keep"}}),
        )
        self.assertEqual(dict(il["d"]), {"x": "new", "y": "keep"})

    def test_missing_key_raises_keyerror(self):
        il = cfgmgr.IncludeLoader(StaticDictLoader({"a": 1}),
                                  StaticDictLoader({"b": 2}))
        with self.assertRaises(KeyError):
            il["missing"]

    def test_contains_is_union(self):
        il = cfgmgr.IncludeLoader(StaticDictLoader({"a": 1}),
                                  StaticDictLoader({"b": 2}))
        self.assertIn("a", il)
        self.assertIn("b", il)
        self.assertNotIn("c", il)

    def test_iter_dedups_shared_keys(self):
        il = cfgmgr.IncludeLoader(StaticDictLoader({"a": 1, "shared": 1}),
                                  StaticDictLoader({"b": 2, "shared": 2}))
        self.assertEqual(set(il), {"a", "b", "shared"})
        self.assertEqual(len(il), 3)

    def test_rejects_nonstatic_including(self):
        with self.assertRaises(TypeError):
            cfgmgr.IncludeLoader(DictLoader({"a": 1}),
                                 StaticDictLoader({"b": 2}))

    def test_rejects_nonstatic_included(self):
        with self.assertRaises(TypeError):
            cfgmgr.IncludeLoader(StaticDictLoader({"a": 1}),
                                 DictLoader({"b": 2}))

    def test_chained_includes(self):
        # An IncludeLoader is itself static, so it can be nested.
        inner = cfgmgr.IncludeLoader(StaticDictLoader({"a": "mid"}),
                                     StaticDictLoader({"a": "base", "b": "base"}))
        outer = cfgmgr.IncludeLoader(StaticDictLoader({"a": "top"}), inner)
        self.assertEqual(outer["a"], "top")
        self.assertEqual(outer["b"], "base")

    def test_getitem_memoized(self):
        il = cfgmgr.IncludeLoader(StaticDictLoader({"d": {"x": 1}}),
                                  StaticDictLoader({"d": {"y": 2}}))
        self.assertIs(il["d"], il["d"])


# --------------------------------------------------------------------------
# FileLoader strip_keys / _stripped
# --------------------------------------------------------------------------

class FileLoaderStripKeysTest(unittest.TestCase):

    def setUp(self):
        self.start_dir = os.getcwd()
        if os.path.exists("tmp_test"):
            shutil.rmtree("tmp_test")
        os.makedirs("tmp_test")
        with open("tmp_test/cfg.json", 'w') as fp:
            json.dump({"include-cfg": "other.json", "A": 1, "B": 2}, fp)

    def tearDown(self):
        os.chdir(self.start_dir)
        shutil.rmtree("tmp_test")

    def test_stripped_key_absent_from_config(self):
        loader = cfgmgr.JSONLoader("tmp_test/cfg.json",
                                   strip_keys=("include-cfg",))
        self.assertNotIn("include-cfg", loader)
        self.assertEqual(loader["A"], 1)

    def test_stripped_values_recorded(self):
        loader = cfgmgr.JSONLoader("tmp_test/cfg.json",
                                   strip_keys=("include-cfg",))
        self.assertEqual(loader._stripped, {"include-cfg": "other.json"})

    def test_no_strip_keys_keeps_everything(self):
        loader = cfgmgr.JSONLoader("tmp_test/cfg.json")
        self.assertIn("include-cfg", loader)
        self.assertEqual(loader._stripped, {})

    def test_strip_key_not_present_is_noop(self):
        loader = cfgmgr.JSONLoader("tmp_test/cfg.json",
                                   strip_keys=("not-there",))
        self.assertEqual(loader._stripped, {})
        self.assertIn("include-cfg", loader)


# --------------------------------------------------------------------------
# Config as a MutableMapping  (__delitem__, __iter__, __len__)
# --------------------------------------------------------------------------

class ConfigMutableMappingTest(unittest.TestCase):

    def test_is_mutablemapping(self):
        from collections.abc import MutableMapping
        self.assertIsInstance(cfgmgr.Config([]), MutableMapping)

    def test_delitem_override_key(self):
        cfg = cfgmgr.Config([], k="v")
        del cfg["k"]
        self.assertNotIn("k", cfg)

    def test_delitem_loader_key(self):
        # Regression guard: deleting a key that lives only in a loader
        # must not raise (it is masked, not popped from _overrides).
        cfg = cfgmgr.Config([DictLoader({"a": 1})])
        del cfg["a"]
        self.assertNotIn("a", cfg)
        self.assertEqual(cfg.get("a", "default"), "default")

    def test_delitem_absent_raises(self):
        cfg = cfgmgr.Config([DictLoader({"a": 1})])
        with self.assertRaises(KeyError):
            del cfg["missing"]

    def test_delitem_twice_raises(self):
        cfg = cfgmgr.Config([DictLoader({"a": 1})])
        del cfg["a"]
        with self.assertRaises(KeyError):
            del cfg["a"]

    def test_set_after_delete_resurrects(self):
        cfg = cfgmgr.Config([DictLoader({"a": "loader"})])
        del cfg["a"]
        cfg["a"] = "new"
        self.assertEqual(cfg["a"], "new")

    def test_iter_includes_overrides_and_loaders(self):
        cfg = cfgmgr.Config([DictLoader({"a": 1, "b": 2})], c=3)
        self.assertEqual(set(cfg), {"a", "b", "c"})

    def test_iter_dedups_across_loaders(self):
        cfg = cfgmgr.Config([DictLoader({"x": 1}), DictLoader({"x": 2})])
        self.assertEqual(list(cfg).count("x"), 1)

    def test_iter_excludes_deleted_keys(self):
        cfg = cfgmgr.Config([DictLoader({"a": 1, "b": 2})])
        del cfg["a"]
        self.assertEqual(set(cfg), {"b"})

    def test_len_counts_distinct_live_keys(self):
        cfg = cfgmgr.Config([DictLoader({"a": 1, "b": 2})], c=3)
        self.assertEqual(len(cfg), 3)
        del cfg["a"]
        self.assertEqual(len(cfg), 2)


# --------------------------------------------------------------------------
# Includes:  resolve_includes / find_relative_file / make_config(include_key=)
# --------------------------------------------------------------------------

class _IncludeTreeTestCase(unittest.TestCase):
    '''Builds a tree of JSON config files wired together by `include-cfg`.'''

    def setUp(self):
        self.start_dir = os.getcwd()
        if os.path.exists("tmp_test"):
            shutil.rmtree("tmp_test")
        os.makedirs("tmp_test/sub")

        def write(path, data):
            with open(os.path.join("tmp_test", path), 'w') as fp:
                json.dump(data, fp)

        write("base.json", {"A": "base", "B": "base",
                            "deep": {"x": "base", "y": "base"}})
        write("mid.json", {"include-cfg": "base.json", "B": "mid",
                           "deep": {"y": "mid", "z": "mid"}})
        write("entry.json", {"include-cfg": "mid.json", "A": "entry",
                             "deep": {"x": "entry"}})
        write("noinc.json", {"A": "solo"})
        write("selfref.json", {"include-cfg": "selfref.json", "A": 1})
        write("cyc_a.json", {"include-cfg": "cyc_b.json", "A": 1})
        write("cyc_b.json", {"include-cfg": "cyc_a.json", "B": 2})
        write("badref.json", {"include-cfg": "nonexistent.json"})
        write("entry_sub.json", {"include-cfg": "sub/child.json",
                                 "A": "entry_sub"})
        write("sub/child.json", {"include-cfg": "../base.json", "C": "child"})
        os.chdir("tmp_test")

    def tearDown(self):
        os.chdir(self.start_dir)
        shutil.rmtree("tmp_test")


class ResolveIncludesTest(_IncludeTreeTestCase):

    def test_single_file_no_include(self):
        loader = cfgmgr.resolve_includes("noinc.json")
        self.assertIsInstance(loader, cfgmgr.JSONLoader)
        self.assertEqual(loader["A"], "solo")

    def test_two_file_chain(self):
        loader = cfgmgr.resolve_includes("mid.json")
        self.assertIsInstance(loader, cfgmgr.IncludeLoader)
        self.assertEqual(loader["B"], "mid")    # including wins
        self.assertEqual(loader["A"], "base")   # only in included

    def test_three_file_chain(self):
        # Exercises nested IncludeLoader (IncludeLoader must be static).
        loader = cfgmgr.resolve_includes("entry.json")
        self.assertEqual(loader["A"], "entry")
        self.assertEqual(loader["B"], "mid")

    def test_nested_value_merged_across_chain(self):
        loader = cfgmgr.resolve_includes("entry.json")
        self.assertEqual(
            dict(loader["deep"]),
            {"x": "entry", "y": "mid", "z": "mid"},
        )

    def test_directive_key_is_stripped(self):
        loader = cfgmgr.resolve_includes("entry.json")
        self.assertNotIn("include-cfg", loader)

    def test_merged_values_are_frozen(self):
        loader = cfgmgr.resolve_includes("entry.json")
        self.assertIsInstance(loader["deep"], MappingProxyType)

    def test_cycle_detected(self):
        with self.assertRaises(cfgmgr.IncludeCycleError):
            cfgmgr.resolve_includes("cyc_a.json")

    def test_self_include_detected(self):
        with self.assertRaises(cfgmgr.IncludeCycleError):
            cfgmgr.resolve_includes("selfref.json")

    def test_missing_include_target_raises(self):
        with self.assertRaises(FileNotFoundError):
            cfgmgr.resolve_includes("badref.json")

    def test_relative_include_resolved_from_subdir(self):
        loader = cfgmgr.resolve_includes("entry_sub.json")
        self.assertEqual(loader["A"], "entry_sub")
        self.assertEqual(loader["C"], "child")    # tmp_test/sub/child.json
        self.assertEqual(loader["B"], "base")     # via sub/child -> ../base.json


class FindRelativeFileTest(_IncludeTreeTestCase):

    def test_none_target_returns_none(self):
        base = os.path.realpath("entry.json")
        self.assertIsNone(cfgmgr.find_relative_file(base, None))

    def test_relative_target_found(self):
        base = os.path.realpath("entry.json")
        found = cfgmgr.find_relative_file(base, "base.json")
        self.assertTrue(os.path.isfile(found))

    def test_relative_target_missing_raises(self):
        base = os.path.realpath("entry.json")
        with self.assertRaises(FileNotFoundError):
            cfgmgr.find_relative_file(base, "nonexistent.json")

    def test_absolute_target_found(self):
        base = os.path.realpath("entry.json")
        target = os.path.realpath("base.json")
        self.assertEqual(cfgmgr.find_relative_file(base, target), target)

    def test_absolute_target_missing_raises(self):
        base = os.path.realpath("entry.json")
        with self.assertRaises(FileNotFoundError):
            cfgmgr.find_relative_file(base, "/no/such/path/xyz.json")


class MakeConfigIncludeTest(_IncludeTreeTestCase):

    def test_include_chain_merged(self):
        cfgmgr.make_config(file_path="entry.json", include_key="include-cfg")
        self.assertEqual(cfgmgr.getkey("A"), "entry")
        self.assertEqual(cfgmgr.getkey("B"), "mid")

    def test_nested_value_merged(self):
        cfgmgr.make_config(file_path="entry.json", include_key="include-cfg")
        self.assertEqual(
            dict(cfgmgr.getkey("deep")),
            {"x": "entry", "y": "mid", "z": "mid"},
        )

    def test_include_key_requires_file_path(self):
        with self.assertRaises(ValueError):
            cfgmgr.make_config(include_key="include-cfg")

    def test_cycle_propagates(self):
        with self.assertRaises(cfgmgr.IncludeCycleError):
            cfgmgr.make_config(file_path="cyc_a.json",
                               include_key="include-cfg")

    def test_env_overrides_included_config(self):
        os.environ["CFGMGRINC_A"] = "from_env"
        self.addCleanup(os.environ.pop, "CFGMGRINC_A", None)
        cfgmgr.make_config(file_path="entry.json", include_key="include-cfg",
                           env_prefix="CFGMGRINC_")
        self.assertEqual(cfgmgr.getkey("A"), "from_env")


if __name__ == '__main__':
    unittest.main()
