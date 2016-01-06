#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import mock
import os
import sys
import unittest
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi import compose
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


class TestGetVariantData(unittest.TestCase):
    def test_get_simple(self):
        conf = {
            'foo': {
                '^Client$': 1
            }
        }
        result = util.get_variant_data(conf, 'foo', mock.Mock(uid='Client'))
        self.assertEqual(result, [1])

    def test_get_make_list(self):
        conf = {
            'foo': {
                '^Client$': [1, 2],
                '^.*$': 3,
            }
        }
        result = util.get_variant_data(conf, 'foo', mock.Mock(uid='Client'))
        self.assertItemsEqual(result, [1, 2, 3])

    def test_not_matching_arch(self):
        conf = {
            'foo': {
                '^Client$': [1, 2],
            }
        }
        result = util.get_variant_data(conf, 'foo', mock.Mock(uid='Server'))
        self.assertItemsEqual(result, [])

    def test_handle_missing_config(self):
        result = util.get_variant_data({}, 'foo', mock.Mock(uid='Client'))
        self.assertItemsEqual(result, [])


class TestVolumeIdGenerator(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    @mock.patch('pungi.compose.ComposeInfo')
    def test_get_volid(self, ci):
        all_keys = [
            (['arch', 'compose_id', 'date', 'disc_type'], 'x86_64-compose_id-20160107-'),
            (['label', 'label_major_version', 'release_short', 'respin'], 'RC-1.0-1-rel_short2-2'),
            (['type', 'type_suffix', 'variant', 'version'], 'nightly-.n-Server-6.0')
        ]
        for keys, expected in all_keys:
            format = '-'.join(['%(' + k + ')s' for k in keys])
            conf = {
                'release_short': 'rel_short2',
                'release_version': '6.0',
                'release_is_layered': False,
                'image_volid_formats': [format]
            }
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

            c = compose.Compose(conf, self.tmp_dir)

            volid = util.get_volid(c, 'x86_64', variant, escape_spaces=False, disc_type=False)

            self.assertEqual(volid, expected)


if __name__ == "__main__":
    unittest.main()
