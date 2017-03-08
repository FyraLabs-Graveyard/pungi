#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import mock
import os
import sys
try:
    import unittest2 as unittest
except ImportError:
    import unittest
import tempfile
import shutil
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi import compose
from pungi import util

from tests.helpers import touch, PungiTestCase


class TestGitRefResolver(unittest.TestCase):

    @mock.patch('pungi.util.run')
    def test_successful_resolve(self, run):
        run.return_value = (0, 'CAFEBABE\tHEAD\n')

        url = util.resolve_git_url('https://git.example.com/repo.git?somedir#HEAD')

        self.assertEqual(url, 'https://git.example.com/repo.git?somedir#CAFEBABE')
        run.assert_called_once_with(['git', 'ls-remote', 'https://git.example.com/repo.git', 'HEAD'])

    @mock.patch('pungi.util.run')
    def test_successful_resolve_branch(self, run):
        run.return_value = (0, 'CAFEBABE\trefs/heads/f24\n')

        url = util.resolve_git_url('https://git.example.com/repo.git?somedir#origin/f24')

        self.assertEqual(url, 'https://git.example.com/repo.git?somedir#CAFEBABE')
        run.assert_called_once_with(['git', 'ls-remote', 'https://git.example.com/repo.git', 'refs/heads/f24'])

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

    @mock.patch('pungi.util.run')
    def test_resolve_keep_empty_query_string(self, run):
        run.return_value = (0, 'CAFEBABE\tHEAD\n')

        url = util.resolve_git_url('https://git.example.com/repo.git?#HEAD')

        run.assert_called_once_with(['git', 'ls-remote', 'https://git.example.com/repo.git', 'HEAD'])
        self.assertEqual(url, 'https://git.example.com/repo.git?#CAFEBABE')

    @mock.patch('pungi.util.run')
    def test_resolve_strip_git_plus_prefix(self, run):
        run.return_value = (0, 'CAFEBABE\tHEAD\n')

        url = util.resolve_git_url('git+https://git.example.com/repo.git#HEAD')

        run.assert_called_once_with(['git', 'ls-remote', 'https://git.example.com/repo.git', 'HEAD'])
        self.assertEqual(url, 'git+https://git.example.com/repo.git#CAFEBABE')


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
                'image_volid_formats': [format],
                'image_volid_layered_product_formats': [],
                'volume_id_substitutions': {},
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


class TestFindOldCompose(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_finds_single(self):
        touch(self.tmp_dir + '/Fedora-Rawhide-20160229.0/STATUS', 'FINISHED')
        old = util.find_old_compose(self.tmp_dir, 'Fedora', 'Rawhide')
        self.assertEqual(old, self.tmp_dir + '/Fedora-Rawhide-20160229.0')

    def test_ignores_in_progress(self):
        touch(self.tmp_dir + '/Fedora-Rawhide-20160229.0/STATUS', 'STARTED')
        old = util.find_old_compose(self.tmp_dir, 'Fedora', 'Rawhide')
        self.assertIsNone(old)

    def test_finds_latest(self):
        touch(self.tmp_dir + '/Fedora-Rawhide-20160228.0/STATUS', 'DOOMED')
        touch(self.tmp_dir + '/Fedora-Rawhide-20160229.0/STATUS', 'FINISHED')
        touch(self.tmp_dir + '/Fedora-Rawhide-20160229.1/STATUS', 'FINISHED_INCOMPLETE')
        old = util.find_old_compose(self.tmp_dir, 'Fedora', 'Rawhide')
        self.assertEqual(old, self.tmp_dir + '/Fedora-Rawhide-20160229.1')

    def test_finds_ignores_other_files(self):
        touch(self.tmp_dir + '/Fedora-Rawhide-20160229.0', 'not a compose')
        touch(self.tmp_dir + '/Fedora-Rawhide-20160228.0/STATUS/file', 'also not a compose')
        touch(self.tmp_dir + '/Fedora-24-20160229.0/STATUS', 'FINISHED')
        touch(self.tmp_dir + '/Another-Rawhide-20160229.0/STATUS', 'FINISHED')
        old = util.find_old_compose(self.tmp_dir, 'Fedora', 'Rawhide')
        self.assertIsNone(old)

    def test_search_in_file(self):
        touch(self.tmp_dir + '/file')
        old = util.find_old_compose(self.tmp_dir + '/file', 'Fedora', 'Rawhide')
        self.assertIsNone(old)

    def test_skips_symlink(self):
        os.symlink(self.tmp_dir, self.tmp_dir + '/Fedora-Rawhide-20160229.0')
        old = util.find_old_compose(self.tmp_dir, 'Fedora', 'Rawhide')
        self.assertIsNone(old)

    def test_finds_layered_product(self):
        touch(self.tmp_dir + '/Fedora-Rawhide-Base-1-20160229.0/STATUS', 'FINISHED')
        old = util.find_old_compose(self.tmp_dir, 'Fedora', 'Rawhide',
                                    base_product_short='Base', base_product_version='1')
        self.assertEqual(old, self.tmp_dir + '/Fedora-Rawhide-Base-1-20160229.0')


class TestHelpers(PungiTestCase):
    def test_process_args(self):
        self.assertEqual(util.process_args('--opt=%s', None), [])
        self.assertEqual(util.process_args('--opt=%s', []), [])
        self.assertEqual(util.process_args('--opt=%s', ['foo', 'bar']),
                         ['--opt=foo', '--opt=bar'])
        self.assertEqual(util.process_args('--opt=%s', 'foo'), ['--opt=foo'])

    def test_makedirs(self):
        util.makedirs(self.topdir + '/foo/bar/baz')
        self.assertTrue(os.path.isdir(self.topdir + '/foo/bar/baz'))

    def test_makedirs_on_existing(self):
        os.makedirs(self.topdir + '/foo/bar/baz')
        try:
            util.makedirs(self.topdir + '/foo/bar/baz')
        except OSError:
            self.fail('makedirs raised exception on existing directory')


RPM_QA_QF_OUTPUT = """
cjkuni-uming-fonts-0.2.20080216.1-56.fc23.noarch
libmount-2.28-1.fc23.x86_64
ed-1.10-5.fc23.x86_64
kbd-2.0.2-8.fc23.x86_64
coreutils-8.24-6.fc23.x86_64
"""

BUILDROOT_LIST = [
    {'arch': 'x86_64',
     'br_type': 0,
     'cg_id': None,
     'cg_name': None,
     'cg_version': None,
     'container_arch': 'x86_64',
     'container_type': 'chroot',
     'create_event_id': 15862222,
     'create_event_time': '2016-04-28 02:37:00.949772',
     'create_ts': 1461811020.94977,
     'extra': None,
     'host_arch': None,
     'host_id': 99,
     'host_name': 'buildhw-01.phx2.fedoraproject.org',
     'host_os': None,
     'id': 5458481,
     'repo_create_event_id': 15861452,
     'repo_create_event_time': '2016-04-28 00:02:40.639317',
     'repo_id': 599173,
     'repo_state': 1,
     'retire_event_id': 15862276,
     'retire_event_time': '2016-04-28 02:58:07.109387',
     'retire_ts': 1461812287.10939,
     'state': 3,
     'tag_id': 315,
     'tag_name': 'f24-build',
     'task_id': 13831904}
]

RPM_LIST = [
    {'arch': 'noarch',
     'build_id': 756072,
     'buildroot_id': 5398084,
     'buildtime': 1461100903,
     'component_buildroot_id': 5458481,
     'epoch': None,
     'external_repo_id': 0,
     'external_repo_name': 'INTERNAL',
     'extra': None,
     'id': 7614370,
     'is_update': True,
     'metadata_only': False,
     'name': 'python3-kickstart',
     'nvr': 'python3-kickstart-2.25-2.fc24',
     'payloadhash': '403723502d27e43955036d2dcd1b09e0',
     'release': '2.fc24',
     'size': 366038,
     'version': '2.25'},
    {'arch': 'x86_64',
     'build_id': 756276,
     'buildroot_id': 5405310,
     'buildtime': 1461165155,
     'component_buildroot_id': 5458481,
     'epoch': None,
     'external_repo_id': 0,
     'external_repo_name': 'INTERNAL',
     'extra': None,
     'id': 7615629,
     'is_update': False,
     'metadata_only': False,
     'name': 'binutils',
     'nvr': 'binutils-2.26-18.fc24',
     'payloadhash': '8ef08c8a64c52787d3559424e5f51d9d',
     'release': '18.fc24',
     'size': 6172094,
     'version': '2.26'},
    {'arch': 'x86_64',
     'build_id': 756616,
     'buildroot_id': 5412029,
     'buildtime': 1461252071,
     'component_buildroot_id': 5458481,
     'epoch': None,
     'external_repo_id': 0,
     'external_repo_name': 'INTERNAL',
     'extra': None,
     'id': 7619636,
     'is_update': False,
     'metadata_only': False,
     'name': 'kernel-headers',
     'nvr': 'kernel-headers-4.5.2-301.fc24',
     'payloadhash': '11c6d70580c8f0c202c28bc6b0fa98cc',
     'release': '301.fc24',
     'size': 1060138,
     'version': '4.5.2'}
]


class TestGetBuildrootRPMs(unittest.TestCase):

    @mock.patch('pungi.wrappers.kojiwrapper.KojiWrapper')
    def test_get_from_koji(self, KojiWrapper):
        compose = mock.Mock(conf={
            'koji_profile': 'koji',
        })

        KojiWrapper.return_value.koji_proxy.listBuildroots.return_value = BUILDROOT_LIST
        KojiWrapper.return_value.koji_proxy.listRPMs.return_value = RPM_LIST

        rpms = util.get_buildroot_rpms(compose, 1234)

        self.assertEqual(KojiWrapper.call_args_list,
                         [mock.call('koji')])
        self.assertEqual(KojiWrapper.return_value.mock_calls,
                         [mock.call.koji_proxy.listBuildroots(taskID=1234),
                          mock.call.koji_proxy.listRPMs(componentBuildrootID=5458481)])

        self.assertItemsEqual(rpms, [
            'python3-kickstart-2.25-2.fc24.noarch',
            'binutils-2.26-18.fc24.x86_64',
            'kernel-headers-4.5.2-301.fc24.x86_64'
        ])

    @mock.patch('pungi.util.run')
    def test_get_local(self, mock_run):
        compose = mock.Mock()

        mock_run.return_value = (0, RPM_QA_QF_OUTPUT)

        rpms = util.get_buildroot_rpms(compose, None)

        self.assertItemsEqual(rpms, [
            'cjkuni-uming-fonts-0.2.20080216.1-56.fc23.noarch',
            'libmount-2.28-1.fc23.x86_64',
            'ed-1.10-5.fc23.x86_64',
            'kbd-2.0.2-8.fc23.x86_64',
            'coreutils-8.24-6.fc23.x86_64',
        ])


class TestLevenshtein(unittest.TestCase):
    def test_edit_dist_empty_str(self):
        self.assertEqual(util.levenshtein('', ''), 0)

    def test_edit_dist_same_str(self):
        self.assertEqual(util.levenshtein('aaa', 'aaa'), 0)

    def test_edit_dist_one_change(self):
        self.assertEqual(util.levenshtein('aab', 'aaa'), 1)

    def test_edit_dist_different_words(self):
        self.assertEqual(util.levenshtein('kitten', 'sitting'), 3)


class TestRecursiveFileList(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_flat_file_list(self):
        """Build a directory containing files and assert they are listed."""
        expected_files = sorted(['file1', 'file2', 'file3'])
        for expected_file in [os.path.join(self.tmp_dir, f) for f in expected_files]:
            touch(expected_file)

        actual_files = sorted(util.recursive_file_list(self.tmp_dir))
        self.assertEqual(expected_files, actual_files)

    def test_nested_file_list(self):
        """Build a directory containing files and assert they are listed."""
        expected_files = sorted(['file1', 'subdir/file2', 'sub/subdir/file3'])
        for expected_file in [os.path.join(self.tmp_dir, f) for f in expected_files]:
            touch(expected_file)

        actual_files = sorted(util.recursive_file_list(self.tmp_dir))
        self.assertEqual(expected_files, actual_files)


class TestTempFiles(unittest.TestCase):
    def test_temp_dir_ok(self):
        with util.temp_dir() as tmp:
            self.assertTrue(os.path.isdir(tmp))
        self.assertFalse(os.path.exists(tmp))

    def test_temp_dir_fail(self):
        with self.assertRaises(RuntimeError):
            with util.temp_dir() as tmp:
                self.assertTrue(os.path.isdir(tmp))
                raise RuntimeError('BOOM')
        self.assertFalse(os.path.exists(tmp))

    def test_temp_dir_in_non_existing_dir(self):
        with util.temp_dir() as playground:
            root = os.path.join(playground, 'missing')
            with util.temp_dir(dir=root) as tmp:
                self.assertTrue(os.path.isdir(tmp))
            self.assertTrue(os.path.isdir(root))
            self.assertFalse(os.path.exists(tmp))


class TestUnmountCmd(unittest.TestCase):

    def _fakeProc(self, ret, err):
        proc = mock.Mock(returncode=ret)
        proc.communicate.return_value = ('', err)
        return proc

    @mock.patch('subprocess.Popen')
    def test_unmount_cmd_success(self, mockPopen):
        cmd = 'unmount'
        mockPopen.side_effect = [self._fakeProc(0, '')]
        util.run_unmount_cmd(cmd)
        self.assertEqual(mockPopen.call_args_list,
                         [mock.call(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)])

    @mock.patch('subprocess.Popen')
    def test_unmount_cmd_fail_other_reason(self, mockPopen):
        cmd = 'unmount'
        mockPopen.side_effect = [self._fakeProc(1, 'It is broken')]
        with self.assertRaises(RuntimeError) as ctx:
            util.run_unmount_cmd(cmd)
        self.assertEqual(str(ctx.exception),
                         "Unhandled error when running 'unmount': 'It is broken'")
        self.assertEqual(mockPopen.call_args_list,
                         [mock.call(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)])

    @mock.patch('time.sleep')
    @mock.patch('subprocess.Popen')
    def test_unmount_cmd_fail_then_retry(self, mockPopen, mock_sleep):
        cmd = 'unmount'
        mockPopen.side_effect = [self._fakeProc(1, 'Device or resource busy'),
                                 self._fakeProc(1, 'Device or resource busy'),
                                 self._fakeProc(0, '')]
        util.run_unmount_cmd(cmd)
        self.assertEqual(mockPopen.call_args_list,
                         [mock.call(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)] * 3)
        self.assertEqual(mock_sleep.call_args_list,
                         [mock.call(0), mock.call(1)])

    @mock.patch('time.sleep')
    @mock.patch('subprocess.Popen')
    def test_unmount_cmd_fail_then_retry_and_fail(self, mockPopen, mock_sleep):
        cmd = 'unmount'
        mockPopen.side_effect = [self._fakeProc(1, 'Device or resource busy'),
                                 self._fakeProc(1, 'Device or resource busy'),
                                 self._fakeProc(1, 'Device or resource busy')]
        with self.assertRaises(RuntimeError) as ctx:
            util.run_unmount_cmd(cmd, max_retries=3)
        self.assertEqual(mockPopen.call_args_list,
                         [mock.call(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)] * 3)
        self.assertEqual(mock_sleep.call_args_list,
                         [mock.call(0), mock.call(1), mock.call(2)])
        self.assertEqual(str(ctx.exception), "Failed to run 'unmount': Device or resource busy.")


if __name__ == "__main__":
    unittest.main()
