#!/usr/bin/python
# -*- coding: utf-8 -*-


import unittest
import mock

import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi.phases.image_checksum import (ImageChecksumPhase,
                                         dump_checksums,
                                         dump_individual)


class _DummyCompose(object):
    def __init__(self, config):
        self.conf = config
        self.paths = mock.Mock(
            compose=mock.Mock(
                topdir=mock.Mock(return_value='/a/b')
            )
        )
        self.image = mock.Mock(
            path='Client/i386/iso/image.iso',
        )
        self.im = mock.Mock(images={'Client': {'i386': [self.image]}})


class TestImageChecksumPhase(unittest.TestCase):

    def test_config_skip_individual_with_multiple_algorithms(self):
        compose = _DummyCompose({
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
        compose = _DummyCompose({
            'media_checksums': ['sha256'],
            'media_checksum_one_file': True,
        })

        phase = ImageChecksumPhase(compose)

        exists.return_value = True
        cc.return_value = {'sha256': 'cafebabe'}

        phase.run()

        dump.assert_called_once_with('/a/b/Client/i386/iso', {'image.iso': 'cafebabe'})
        cc.assert_called_once_with('/a/b/Client/i386/iso/image.iso', ['sha256'])
        compose.image.add_checksum.assert_called_once_with(None, 'sha256', 'cafebabe')

    @mock.patch('os.path.exists')
    @mock.patch('kobo.shortcuts.compute_file_checksums')
    @mock.patch('pungi.phases.image_checksum.dump_checksums')
    @mock.patch('pungi.phases.image_checksum.dump_individual')
    def test_checksum_save_individuals(self, indiv_dump, dump, cc, exists):
        compose = _DummyCompose({
            'media_checksums': ['md5', 'sha256'],
        })

        phase = ImageChecksumPhase(compose)

        exists.return_value = True
        cc.return_value = {'md5': 'cafebabe', 'sha256': 'deadbeef'}

        phase.run()

        indiv_dump.assert_has_calls(
            [mock.call('/a/b/Client/i386/iso/image.iso', 'cafebabe', 'md5'),
             mock.call('/a/b/Client/i386/iso/image.iso', 'deadbeef', 'sha256')],
            any_order=True
        )
        dump.assert_has_calls(
            [mock.call('/a/b/Client/i386/iso', {'image.iso': 'cafebabe'}, 'MD5SUM'),
             mock.call('/a/b/Client/i386/iso', {'image.iso': 'deadbeef'}, 'SHA256SUM')],
            any_order=True
        )
        cc.assert_called_once_with('/a/b/Client/i386/iso/image.iso', ['md5', 'sha256'])
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
        dump_checksums(self.tmp_dir, {'file1.iso': 'abcdef', 'file2.iso': 'cafebabe'})

        with open(os.path.join(self.tmp_dir, 'CHECKSUM'), 'r') as f:
            data = f.read().rstrip().split('\n')
            expected = [
                'abcdef *file1.iso',
                'cafebabe *file2.iso',
            ]
            self.assertItemsEqual(expected, data)

    def test_dump_individual(self):
        base_path = os.path.join(self.tmp_dir, 'file.iso')
        dump_individual(base_path, 'cafebabe', 'md5')

        with open(base_path + '.MD5SUM', 'r') as f:
            data = f.read()
            self.assertEqual('cafebabe *file.iso\n', data)

if __name__ == "__main__":
    unittest.main()
