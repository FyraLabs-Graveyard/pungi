# -*- coding: utf-8 -*-

try:
    import unittest2 as unittest
except ImportError:
    import unittest
import tempfile

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi.wrappers import fus

from .helpers import touch


class TestGetCmd(unittest.TestCase):
    def test_minimum_command(self):
        cmd = fus.get_cmd("x86_64", [], [], [], [], [])
        self.assertEqual(cmd, ["fus", "--verbose", "--arch", "x86_64"])

    def test_full_command(self):
        cmd = fus.get_cmd(
            "x86_64",
            ["/tmp/first", "/tmp/second"],
            ["/tmp/fst", "/tmp/snd"],
            ["pkg"],
            ["mod:1.0"],
            platform="f29",
        )
        self.assertEqual(
            cmd,
            [
                "fus",
                "--verbose",
                "--arch",
                "x86_64",
                "--repo=repo-0,repo,/tmp/first",
                "--repo=repo-1,repo,/tmp/second",
                "--repo=lookaside-0,lookaside,/tmp/fst",
                "--repo=lookaside-1,lookaside,/tmp/snd",
                "--platform=f29",
                "module(mod:1.0)",
                "pkg",
            ],
        )


class TestParseOutput(unittest.TestCase):
    def setUp(self):
        _, self.file = tempfile.mkstemp(prefix="test-parse-fus-out-")

    def tearDown(self):
        os.remove(self.file)

    def test_skips_debug_line(self):
        touch(self.file, "debug line\n")
        packages = fus.parse_output(self.file)
        self.assertItemsEqual(packages, [])

    def test_separates_arch(self):
        touch(self.file, "pkg-1.0-1.x86_64@repo-0\npkg-1.0-1.i686@repo-0\n")
        packages = fus.parse_output(self.file)
        self.assertItemsEqual(
            packages,
            [("pkg-1.0-1", "x86_64", frozenset()), ("pkg-1.0-1", "i686", frozenset())],
        )

    def test_marks_modular(self):
        touch(self.file, "*pkg-1.0-1.x86_64@repo-0\n")
        packages = fus.parse_output(self.file)
        self.assertItemsEqual(
            packages,
            [("pkg-1.0-1", "x86_64", frozenset(["modular"]))],
        )
