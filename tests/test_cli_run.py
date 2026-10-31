import unittest
from unittest import mock

import _bootstrap

import psicotest.cli

ARGS = ["run", "--base-url", "http://fake/v1", "--model", "fake-model", "--seed", "7"]


class TestCliRun(unittest.TestCase):
    def test_run_requires_base_url(self):
        argv = ["run", "--model", "fake-model", "--seed", "7"]
        with mock.patch("sys.stderr"), self.assertRaises(SystemExit) as caught:
            psicotest.cli.main(argv)
        self.assertEqual(caught.exception.code, 2)

    def test_run_requires_model(self):
        argv = ["run", "--base-url", "http://fake/v1", "--seed", "7"]
        with mock.patch("sys.stderr"), self.assertRaises(SystemExit) as caught:
            psicotest.cli.main(argv)
        self.assertEqual(caught.exception.code, 2)

    def test_run_requires_seed(self):
        argv = ["run", "--base-url", "http://fake/v1", "--model", "fake-model"]
        with mock.patch("sys.stderr"), self.assertRaises(SystemExit) as caught:
            psicotest.cli.main(argv)
        self.assertEqual(caught.exception.code, 2)

    def test_run_missing_key_exit3(self):
        with mock.patch.dict("os.environ", {}, clear=True), mock.patch("sys.stderr"):
            code = psicotest.cli.main(ARGS)
        self.assertEqual(code, 3)


if __name__ == "__main__":
    unittest.main()
