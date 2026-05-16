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


if __name__ == '__main__':
    unittest.main()
