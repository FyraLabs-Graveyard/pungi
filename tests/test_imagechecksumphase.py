#!/usr/bin/env python
# -*- coding: utf-8 -*-


import unittest
import mock

import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi.phases.image_checksum import ImageChecksumPhase, dump_checksums
from tests.helpers import DummyCompose, PungiTestCase


class TestImageChecksumPhase(PungiTestCase):

    def test_config_skip_individual_with_multiple_algorithms(self):
        compose = DummyCompose(self.topdir, {
            'media_checksums': ['md5', 'sha1'],
            'media_checksum_one_file': True
        })
        phase = ImageChecksumPhase(compose)
        with self.assertRaises(ValueError) as err:
            phase.validate()
            self.assertIn('media_checksum_one_file', err.message)

    @mock.patch('os.path.exists')
    @mock.patch('kobo.shortcuts.compute_file_checksums')
    @mock.patch('pungi.phases.image_checksum.dump_checksums')
    def test_checksum_one_file(self, dump, cc, exists):
        compose = DummyCompose(self.topdir, {
            'media_checksums': ['sha256'],
            'media_checksum_one_file': True,
        })

        phase = ImageChecksumPhase(compose)

        exists.return_value = True
        cc.return_value = {'sha256': 'cafebabe'}

        phase.run()

        dump.assert_called_once_with(self.topdir + '/compose/Client/i386/iso', 'sha256', {'image.iso': 'cafebabe'}, 'CHECKSUM')
        cc.assert_called_once_with(self.topdir + '/compose/Client/i386/iso/image.iso', ['sha256'])
        compose.image.add_checksum.assert_called_once_with(None, 'sha256', 'cafebabe')

    @mock.patch('os.path.exists')
    @mock.patch('kobo.shortcuts.compute_file_checksums')
    @mock.patch('pungi.phases.image_checksum.dump_checksums')
    def test_checksum_save_individuals(self, dump, cc, exists):
        compose = DummyCompose(self.topdir, {
            'media_checksums': ['md5', 'sha256'],
        })

        phase = ImageChecksumPhase(compose)

        exists.return_value = True
        cc.return_value = {'md5': 'cafebabe', 'sha256': 'deadbeef'}

        phase.run()

        dump.assert_has_calls(
            [mock.call(self.topdir + '/compose/Client/i386/iso', 'md5',
                       {'image.iso': 'cafebabe'}, 'image.iso.MD5SUM'),
             mock.call(self.topdir + '/compose/Client/i386/iso', 'sha256',
                       {'image.iso': 'deadbeef'}, 'image.iso.SHA256SUM'),
             mock.call(self.topdir + '/compose/Client/i386/iso', 'md5',
                       {'image.iso': 'cafebabe'}, 'MD5SUM'),
             mock.call(self.topdir + '/compose/Client/i386/iso', 'sha256',
                       {'image.iso': 'deadbeef'}, 'SHA256SUM')],
            any_order=True
        )
        cc.assert_called_once_with(self.topdir + '/compose/Client/i386/iso/image.iso', ['md5', 'sha256'])
        compose.image.add_checksum.assert_has_calls([mock.call(None, 'sha256', 'deadbeef'),
                                                     mock.call(None, 'md5', 'cafebabe')],
                                                    any_order=True)

    @mock.patch('os.path.exists')
    @mock.patch('kobo.shortcuts.compute_file_checksums')
    @mock.patch('pungi.phases.image_checksum.dump_checksums')
    def test_checksum_one_file_custom_name(self, dump, cc, exists):
        compose = DummyCompose(self.topdir, {
            'media_checksums': ['sha256'],
            'media_checksum_one_file': True,
            'media_checksum_base_filename': '%(release_short)s-%(variant)s-%(version)s-%(date)s%(type_suffix)s.%(respin)s'
        })

        phase = ImageChecksumPhase(compose)

        exists.return_value = True
        cc.return_value = {'sha256': 'cafebabe'}

        phase.run()

        dump.assert_called_once_with(self.topdir + '/compose/Client/i386/iso', 'sha256',
                                     {'image.iso': 'cafebabe'},
                                     'test-Client-1.0-20151203.t.0-CHECKSUM')
        cc.assert_called_once_with(self.topdir + '/compose/Client/i386/iso/image.iso', ['sha256'])
        compose.image.add_checksum.assert_called_once_with(None, 'sha256', 'cafebabe')

    @mock.patch('os.path.exists')
    @mock.patch('kobo.shortcuts.compute_file_checksums')
    @mock.patch('pungi.phases.image_checksum.dump_checksums')
    def test_checksum_save_individuals_custom_name(self, dump, cc, exists):
        compose = DummyCompose(self.topdir, {
            'media_checksums': ['md5', 'sha256'],
            'media_checksum_base_filename': '%(release_short)s-%(variant)s-%(version)s-%(date)s%(type_suffix)s.%(respin)s'
        })

        phase = ImageChecksumPhase(compose)

        exists.return_value = True
        cc.return_value = {'md5': 'cafebabe', 'sha256': 'deadbeef'}

        phase.run()

        dump.assert_has_calls(
            [mock.call(self.topdir + '/compose/Client/i386/iso', 'md5',
                       {'image.iso': 'cafebabe'}, 'image.iso.MD5SUM'),
             mock.call(self.topdir + '/compose/Client/i386/iso', 'sha256',
                       {'image.iso': 'deadbeef'}, 'image.iso.SHA256SUM'),
             mock.call(self.topdir + '/compose/Client/i386/iso', 'md5', {'image.iso': 'cafebabe'},
                       'test-Client-1.0-20151203.t.0-MD5SUM'),
             mock.call(self.topdir + '/compose/Client/i386/iso', 'sha256', {'image.iso': 'deadbeef'},
                       'test-Client-1.0-20151203.t.0-SHA256SUM')],
            any_order=True
        )
        cc.assert_called_once_with(self.topdir + '/compose/Client/i386/iso/image.iso', ['md5', 'sha256'])
        compose.image.add_checksum.assert_has_calls([mock.call(None, 'sha256', 'deadbeef'),
                                                     mock.call(None, 'md5', 'cafebabe')],
                                                    any_order=True)


class TestChecksums(unittest.TestCase):
    def setUp(self):
        _, name = tempfile.mkstemp()
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_dump_checksums(self):
        dump_checksums(self.tmp_dir,
                       'md5',
                       {'file1.iso': 'abcdef', 'file2.iso': 'cafebabe'},
                       'CHECKSUM')

        with open(os.path.join(self.tmp_dir, 'CHECKSUM'), 'r') as f:
            data = f.read().rstrip().split('\n')
            expected = [
                'MD5 (file1.iso) = abcdef',
                'MD5 (file2.iso) = cafebabe',
            ]
            self.assertItemsEqual(expected, data)

if __name__ == "__main__":
    unittest.main()
