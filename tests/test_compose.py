#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import mock
import unittest
import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi.compose import Compose


class ComposeTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    @mock.patch('pungi.compose.ComposeInfo')
    def test_can_fail(self, ci):
        conf = {
            'failable_deliverables': [
                ('^.*$', {
                    '*': ['buildinstall'],
                    'i386': ['buildinstall', 'live', 'iso'],
                }),
            ]
        }
        compose = Compose(conf, self.tmp_dir)
        variant = mock.Mock(uid='Server')

        self.assertTrue(compose.can_fail(variant, 'x86_64', 'buildinstall'))
        self.assertFalse(compose.can_fail(variant, 'x86_64', 'live'))
        self.assertTrue(compose.can_fail(variant, 'i386', 'live'))

        self.assertFalse(compose.can_fail(None, 'x86_64', 'live'))
        self.assertTrue(compose.can_fail(None, 'i386', 'live'))


if __name__ == "__main__":
    unittest.main()
