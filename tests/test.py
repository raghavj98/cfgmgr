import unittest
import cfgmgr
import os
import json
import shutil
import logging


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
        self.assertEqual(cfgmgr.get("FOO"), "bar")

    def test_noprefix(self):
        os.environ["CFGMGRTEST_FOO"] = "bar"
        cfgmgr.make_config(env_prefix="")
        self.assertEqual(cfgmgr.get("CFGMGRTEST_FOO"), "bar")

    def test_negative_prefix(self):
        os.environ["FOO"] = "bar"
        cfgmgr.make_config(env_prefix="CFGMGRTEST_")
        self.assertEqual(cfgmgr.get("FOO"), None)

    def test_negative_noprefix(self):
        os.environ["FOO"] = "bar"
        cfgmgr.make_config()
        self.assertEqual(cfgmgr.get("FOO"), None)

    def test_default_for_missing_key(self):
        cfgmgr.make_config(env_prefix="CFGMGRTEST_")
        self.assertEqual(cfgmgr.get("MISSING", "fallback"), "fallback")

    def test_dynamic_resolution(self):
        # Values are resolved on each get(), so env changes are reflected.
        cfgmgr.make_config(env_prefix="CFGMGRTEST_")
        self.assertIsNone(cfgmgr.get("DYNAMIC"))
        os.environ["CFGMGRTEST_DYNAMIC"] = "now_set"
        self.addCleanup(os.environ.pop, "CFGMGRTEST_DYNAMIC", None)
        self.assertEqual(cfgmgr.get("DYNAMIC"), "now_set")


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
        self.assertEqual(cfgmgr.get("FOO"), "bar")

    def test_find_file_in_cwd(self):
        with open("local.json", 'w') as fp:
            json.dump({"LOCAL": "value"}, fp)
        cfgmgr.make_config(file_path="local.json", find_file=True)
        self.assertEqual(cfgmgr.get("LOCAL"), "value")

    def test_file_path_without_find_file(self):
        # Regression guard: file_path given, find_file omitted.
        with open("local.json", 'w') as fp:
            json.dump({"LOCAL": "value"}, fp)
        cfgmgr.make_config(file_path="local.json")
        self.assertEqual(cfgmgr.get("LOCAL"), "value")

    def test_missing_key_returns_default(self):
        cfgmgr.make_config(file_path="file1.json", find_file=True)
        self.assertEqual(cfgmgr.get("MISSING", "fallback"), "fallback")

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
        self.assertIsNone(cfgmgr.get("anything"))
        self.assertEqual(cfgmgr.get("anything", "d"), "d")

    def test_kwargs_overrides(self):
        cfgmgr.make_config(FOO="kwarg_value")
        self.assertEqual(cfgmgr.get("FOO"), "kwarg_value")

    def test_kwargs_beat_loaders(self):
        os.environ["CFGMGRTEST_K"] = "env_value"
        self.addCleanup(os.environ.pop, "CFGMGRTEST_K", None)
        cfgmgr.make_config(env_prefix="CFGMGRTEST_", K="kwarg_value")
        self.assertEqual(cfgmgr.get("K"), "kwarg_value")

    def test_env_overrides_file(self):
        os.environ["CFGMGRTEST_SHARED"] = "from_env"
        self.addCleanup(os.environ.pop, "CFGMGRTEST_SHARED", None)
        cfgmgr.make_config(env_prefix="CFGMGRTEST_", file_path="config.json")
        self.assertEqual(cfgmgr.get("SHARED"), "from_env")

    def test_file_value_survives_when_env_missing(self):
        cfgmgr.make_config(env_prefix="CFGMGRTEST_", file_path="config.json")
        self.assertEqual(cfgmgr.get("ONLY_FILE"), "file_value")

    def test_reinit_resets_config(self):
        cfgmgr.make_config(FOO="first")
        cfgmgr.make_config(FOO="second")
        self.assertEqual(cfgmgr.get("FOO"), "second")
        cfgmgr.make_config()
        self.assertIsNone(cfgmgr.get("FOO"))

    def test_unsupported_extension(self):
        with self.assertRaises(ValueError):
            cfgmgr.make_config(file_path="config.yaml")

    def test_find_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            cfgmgr.make_config(file_path="absent_xyz.json", find_file=True)

    def test_file_not_found_without_find_file(self):
        with self.assertRaises(FileNotFoundError):
            cfgmgr.make_config(file_path="absent_xyz.json")


# --------------------------------------------------------------------------
# Module-level get / set
# --------------------------------------------------------------------------

class GetSetTest(unittest.TestCase):

    def test_set_then_get(self):
        cfgmgr.make_config()
        cfgmgr.set("k", "v")
        self.assertEqual(cfgmgr.get("k"), "v")

    def test_get_default(self):
        cfgmgr.make_config()
        self.assertEqual(cfgmgr.get("missing", "d"), "d")

    def test_set_overrides_loader(self):
        os.environ["CFGMGRTEST_X"] = "env_value"
        self.addCleanup(os.environ.pop, "CFGMGRTEST_X", None)
        cfgmgr.make_config(env_prefix="CFGMGRTEST_")
        cfgmgr.set("X", "set_value")
        self.assertEqual(cfgmgr.get("X"), "set_value")

    def test_get_before_make_config(self):
        cfgmgr._config = None
        with self.assertRaises(AttributeError):
            cfgmgr.get("k")

    def test_set_before_make_config(self):
        cfgmgr._config = None
        with self.assertRaises(AttributeError):
            cfgmgr.set("k", "v")


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
            cfgmgr.find_file_up("config.yaml")


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
            cfgmgr.get_file_loader("config.yaml")


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
        self.assertEqual(cfgmgr.get("STUB"), "stub_value")


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

    def test_yaml_not_registered(self):
        # No YAMLLoader class exists yet, so .yaml/.yml stay unsupported
        # regardless of whether PyYAML is installed.
        self.assertNotIn(".yaml", cfgmgr.fileloaders)
        self.assertNotIn(".yml", cfgmgr.fileloaders)

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
        self.assertEqual(cfgmgr.get("FOO"), "bar")


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
        self.assertEqual(cfgmgr.get("FOO"), "bar")


if __name__ == '__main__':
    unittest.main()
