# -*- coding: utf-8 -*-

import mock
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi.wrappers import iso

CORRECT_OUTPUT = '''dummy.iso:   31ff3e405e26ad01c63b62f6b11d30f6
Fragment sums: 6eb92e7bda221d7fe5f19b4d21468c9bf261d84c96d145d96c76444b9cbc
Fragment count: 20
Supported ISO: no
'''

INCORRECT_OUTPUT = '''This should never happen: File not found'''


class TestIsoUtils(unittest.TestCase):
    @mock.patch('pungi.wrappers.iso.run')
    def test_get_implanted_md5_correct(self, mock_run):
        mock_run.return_value = (0, CORRECT_OUTPUT)
        logger = mock.Mock()
        self.assertEqual(iso.get_implanted_md5('dummy.iso', logger=logger),
                         '31ff3e405e26ad01c63b62f6b11d30f6')
        self.assertEqual(mock_run.call_args_list,
                         [mock.call(['/usr/bin/checkisomd5', '--md5sumonly', 'dummy.iso'])])
        self.assertEqual(logger.mock_calls, [])

    @mock.patch('pungi.wrappers.iso.run')
    def test_get_implanted_md5_incorrect(self, mock_run):
        mock_run.return_value = (0, INCORRECT_OUTPUT)
        logger = mock.Mock()
        self.assertIsNone(iso.get_implanted_md5('dummy.iso', logger=logger))
        self.assertEqual(mock_run.call_args_list,
                         [mock.call(['/usr/bin/checkisomd5', '--md5sumonly', 'dummy.iso'])])
        self.assertGreater(len(logger.mock_calls), 0)

    @mock.patch('pungi.util.run_unmount_cmd')
    @mock.patch('pungi.wrappers.iso.run')
    def test_mount_iso(self, mock_run, mock_unmount):
        mock_run.return_value = (0, '')
        with iso.mount('dummy') as temp_dir:
            self.assertTrue(os.path.isdir(temp_dir))
        self.assertEqual(len(mock_run.call_args_list), 1)
        self.assertEqual(len(mock_unmount.call_args_list), 1)
        self.assertFalse(os.path.isdir(temp_dir))

    @mock.patch('pungi.util.run_unmount_cmd')
    @mock.patch('pungi.wrappers.iso.run')
    def test_mount_iso_always_unmounts(self, mock_run, mock_unmount):
        mock_run.return_value = (0, '')
        try:
            with iso.mount('dummy') as temp_dir:
                self.assertTrue(os.path.isdir(temp_dir))
                raise RuntimeError()
        except RuntimeError:
            pass
        self.assertEqual(len(mock_run.call_args_list), 1)
        self.assertEqual(len(mock_unmount.call_args_list), 1)
        self.assertFalse(os.path.isdir(temp_dir))

    @mock.patch('pungi.util.run_unmount_cmd')
    @mock.patch('pungi.wrappers.iso.run')
    def test_mount_iso_raises_on_error(self, mock_run, mock_unmount):
        log = mock.Mock()
        mock_run.return_value = (1, 'Boom')
        with self.assertRaises(RuntimeError):
            with iso.mount('dummy', logger=log) as temp_dir:
                self.assertTrue(os.path.isdir(temp_dir))
        self.assertEqual(len(mock_run.call_args_list), 1)
        self.assertEqual(len(mock_unmount.call_args_list), 0)
        self.assertEqual(len(log.mock_calls), 1)
