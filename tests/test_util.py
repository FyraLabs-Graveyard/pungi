#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import mock
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi import util


class TestGitRefResolver(unittest.TestCase):

    @mock.patch('pungi.util.run')
    def test_successful_resolve(self, run):
        run.return_value = (0, 'CAFEBABE\tHEAD\n')

        url = util.resolve_git_url('https://git.example.com/repo.git?somedir#HEAD')

        self.assertEqual(url, 'https://git.example.com/repo.git?somedir#CAFEBABE')
        run.assert_called_once_with(['git', 'ls-remote', 'https://git.example.com/repo.git', 'HEAD'])

    @mock.patch('pungi.util.run')
    def test_resolve_missing_spec(self, run):
        url = util.resolve_git_url('https://git.example.com/repo.git')

        self.assertEqual(url, 'https://git.example.com/repo.git')
        self.assertEqual(run.mock_calls, [])

    @mock.patch('pungi.util.run')
    def test_resolve_non_head_spec(self, run):
        url = util.resolve_git_url('https://git.example.com/repo.git#some-tag')

        self.assertEqual(url, 'https://git.example.com/repo.git#some-tag')
        self.assertEqual(run.mock_calls, [])

    @mock.patch('pungi.util.run')
    def test_resolve_ambiguous(self, run):
        run.return_value = (0, 'CAFEBABE\tF11\nDEADBEEF\tF10\n')

        with self.assertRaises(RuntimeError):
            util.resolve_git_url('https://git.example.com/repo.git?somedir#HEAD')

        run.assert_called_once_with(['git', 'ls-remote', 'https://git.example.com/repo.git', 'HEAD'])


if __name__ == "__main__":
    unittest.main()
