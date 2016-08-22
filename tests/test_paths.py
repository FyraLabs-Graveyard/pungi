#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import mock
import unittest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi import paths


class TranslatePathTestCase(unittest.TestCase):
    def test_does_nothing_without_config(self):
        compose = mock.Mock(conf={'translate_paths': []})
        ret = paths.translate_path(compose, '/mnt/koji/compose/rawhide/XYZ')
        self.assertEqual(ret, '/mnt/koji/compose/rawhide/XYZ')

    def test_translates_prefix(self):
        compose = mock.Mock(conf={
            'translate_paths': [('/mnt/koji', 'http://example.com')]
        })
        ret = paths.translate_path(compose, '/mnt/koji/compose/rawhide/XYZ')
        self.assertEqual(ret, 'http://example.com/compose/rawhide/XYZ')

    def test_does_not_translate_not_matching(self):
        compose = mock.Mock(conf={
            'translate_paths': [('/mnt/koji', 'http://example.com')]
        })
        ret = paths.translate_path(compose, '/mnt/fedora_koji/compose/rawhide/XYZ')
        self.assertEqual(ret, '/mnt/fedora_koji/compose/rawhide/XYZ')


if __name__ == "__main__":
    unittest.main()
