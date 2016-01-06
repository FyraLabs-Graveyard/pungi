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

    @mock.patch('pungi.compose.ComposeInfo')
    def test_get_image_name(self, ci):
        conf = {}
        variant = mock.Mock(uid='Server', type='variant')
        ci.return_value.compose.respin = 2
        ci.return_value.compose.id = 'compose_id'
        ci.return_value.compose.date = '20160107'
        ci.return_value.compose.type = 'nightly'
        ci.return_value.compose.type_suffix = '.n'
        ci.return_value.compose.label = 'RC-1.0'
        ci.return_value.compose.label_major_version = '1'

        ci.return_value.release.version = '3.0'
        ci.return_value.release.short = 'rel_short'

        compose = Compose(conf, self.tmp_dir)

        keys = ['arch', 'compose_id', 'date', 'disc_num', 'disc_type',
                'label', 'label_major_version', 'release_short', 'respin',
                'suffix', 'type', 'type_suffix', 'variant', 'version']
        format = '-'.join(['%(' + k + ')s' for k in keys])
        name = compose.get_image_name('x86_64', variant, format=format,
                                      disc_num=7, disc_type='live', suffix='.iso')

        self.assertEqual(name, '-'.join(['x86_64', 'compose_id', '20160107', '7', 'live',
                                         'RC-1.0', '1', 'rel_short', '2', '.iso', 'nightly',
                                         '.n', 'Server', '3.0']))


if __name__ == "__main__":
    unittest.main()
