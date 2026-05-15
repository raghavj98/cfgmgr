import unittest
import cfgmgr
import os
import json
import shutil


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

    def tearDown(self):
        os.chdir(self.start_dir)
        shutil.rmtree("tmp_test")


if __name__ == '__main__':
    unittest.main()
