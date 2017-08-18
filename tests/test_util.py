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

    @mock.patch('pungi.util.run')
    def test_resolve_no_branch_in_remote(self, run):
        run.return_value = (0, '')

        with self.assertRaises(RuntimeError) as ctx:
            util.resolve_git_url('https://git.example.com/repo.git?somedir#origin/my-branch')

        run.assert_called_once_with(
            ['git', 'ls-remote', 'https://git.example.com/repo.git', 'refs/heads/my-branch'])
        self.assertIn('ref does not exist in remote repo', str(ctx.exception))

    @mock.patch('time.sleep')
    @mock.patch('pungi.util.run')
    def test_retry(self, run, sleep):
        run.side_effect = [RuntimeError('Boom'), (0, 'CAFEBABE\tHEAD\n')]

        url = util.resolve_git_url('https://git.example.com/repo.git?somedir#HEAD')

        self.assertEqual(url, 'https://git.example.com/repo.git?somedir#CAFEBABE')
        self.assertEqual(sleep.call_args_list, [mock.call(30)])
        self.assertEqual(run.call_args_list,
                         [mock.call(['git', 'ls-remote', 'https://git.example.com/repo.git', 'HEAD'])] * 2)


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

    def test_get_save_pattern(self):
        conf = {
            'foo': {
                '^Client$': 1,
                '^NotClient$': 2,
            }
        }
        patterns = set()
        result = util.get_variant_data(conf, 'foo', mock.Mock(uid='Client'), keys=patterns)
        self.assertEqual(result, [1])
        self.assertEqual(patterns, set(['^Client$']))


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

    @mock.patch('pungi.compose.ComposeInfo')
    def test_get_volid_too_long(self, ci):
        conf = {
            'release_short': 'rel_short2',
            'release_version': '6.0',
            'release_is_layered': False,
            'image_volid_formats': [
                'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',   # 34 chars
                'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',    # 33 chars
            ],
            'image_volid_layered_product_formats': [],
            'volume_id_substitutions': {},
        }
        variant = mock.Mock(uid='Server', type='variant')
        c = compose.Compose(conf, self.tmp_dir)

        with self.assertRaises(ValueError) as ctx:
            util.get_volid(c, 'x86_64', variant, escape_spaces=False, disc_type=False)

        self.assertIn('bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', str(ctx.exception))
        self.assertIn('aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', str(ctx.exception))


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

    def test_find_latest_with_two_digit_respin(self):
        touch(self.tmp_dir + '/Fedora-Rawhide-20160228.n.9/STATUS', 'FINISHED')
        touch(self.tmp_dir + '/Fedora-Rawhide-20160228.n.10/STATUS', 'FINISHED')
        old = util.find_old_compose(self.tmp_dir, 'Fedora', 'Rawhide')
        self.assertEqual(old, self.tmp_dir + '/Fedora-Rawhide-20160228.n.10')

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

    def _fakeProc(self, ret, err='', out=''):
        proc = mock.Mock(returncode=ret)
        proc.communicate.return_value = (out, err)
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

    @mock.patch('time.sleep')
    @mock.patch('subprocess.Popen')
    def test_fusermount_fail_then_retry_and_fail_with_debug(self, mockPopen, mock_sleep):
        logger = mock.Mock()
        mockPopen.side_effect = [self._fakeProc(1, 'Device or resource busy'),
                                 self._fakeProc(1, 'Device or resource busy'),
                                 self._fakeProc(1, 'Device or resource busy'),
                                 self._fakeProc(0, out='list of files'),
                                 self._fakeProc(0, out='It is very busy'),
                                 self._fakeProc(1, out='lsof output')]
        with self.assertRaises(RuntimeError) as ctx:
            util.fusermount('/path', max_retries=3, logger=logger)
        cmd = ['fusermount', '-u', '/path']
        expected = [mock.call(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE),
                    mock.call(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE),
                    mock.call(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE),
                    mock.call(['ls', '-lA', '/path'],
                              stderr=subprocess.STDOUT, stdout=subprocess.PIPE),
                    mock.call(['fuser', '-vm', '/path'],
                              stderr=subprocess.STDOUT, stdout=subprocess.PIPE),
                    mock.call(['lsof', '+D', '/path'],
                              stderr=subprocess.STDOUT, stdout=subprocess.PIPE)]
        self.assertEqual(mockPopen.call_args_list, expected)
        self.assertEqual(mock_sleep.call_args_list,
                         [mock.call(0), mock.call(1), mock.call(2)])
        self.assertEqual(str(ctx.exception),
                         "Failed to run ['fusermount', '-u', '/path']: Device or resource busy.")
        self.assertEqual(logger.mock_calls,
                         [mock.call.debug('`%s` exited with %s and following output:\n%s',
                                          'ls -lA /path', 0, 'list of files'),
                          mock.call.debug('`%s` exited with %s and following output:\n%s',
                                          'fuser -vm /path', 0, 'It is very busy'),
                          mock.call.debug('`%s` exited with %s and following output:\n%s',
                                          'lsof +D /path', 1, 'lsof output')])


class TranslatePathTestCase(unittest.TestCase):
    def test_does_nothing_without_config(self):
        compose = mock.Mock(conf={'translate_paths': []})
        ret = util.translate_path(compose, '/mnt/koji/compose/rawhide/XYZ')
        self.assertEqual(ret, '/mnt/koji/compose/rawhide/XYZ')

    def test_translates_prefix(self):
        compose = mock.Mock(conf={
            'translate_paths': [('/mnt/koji', 'http://example.com')]
        })
        ret = util.translate_path(compose, '/mnt/koji/compose/rawhide/XYZ')
        self.assertEqual(ret, 'http://example.com/compose/rawhide/XYZ')

    def test_does_not_translate_not_matching(self):
        compose = mock.Mock(conf={
            'translate_paths': [('/mnt/koji', 'http://example.com')]
        })
        ret = util.translate_path(compose, '/mnt/fedora_koji/compose/rawhide/XYZ')
        self.assertEqual(ret, '/mnt/fedora_koji/compose/rawhide/XYZ')


class GetRepoFuncsTestCase(unittest.TestCase):
    @mock.patch('pungi.compose.ComposeInfo')
    def setUp(self, ci):
        self.tmp_dir = tempfile.mkdtemp()
        conf = {
            'translate_paths': [(self.tmp_dir, 'http://example.com')]
        }
        ci.return_value.compose.respin = 0
        ci.return_value.compose.id = 'RHEL-8.0-20180101.n.0'
        ci.return_value.compose.date = '20160101'
        ci.return_value.compose.type = 'nightly'
        ci.return_value.compose.type_suffix = '.n'
        ci.return_value.compose.label = 'RC-1.0'
        ci.return_value.compose.label_major_version = '1'

        compose_dir = os.path.join(self.tmp_dir, ci.return_value.compose.id)
        self.compose = compose.Compose(conf, compose_dir)
        server_variant = mock.Mock(uid='Server', type='variant')
        client_variant = mock.Mock(uid='Client', type='variant')
        self.compose.all_variants = {
            'Server': server_variant,
            'Client': client_variant,
        }

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_get_repo_url_from_normal_url(self):
        url = util.get_repo_url(self.compose, 'http://example.com/repo')
        self.assertEqual(url, 'http://example.com/repo')

    def test_get_repo_url_from_variant_uid(self):
        url = util.get_repo_url(self.compose, 'Server')
        self.assertEqual(url, 'http://example.com/RHEL-8.0-20180101.n.0/compose/Server/$basearch/os')

    def test_get_repo_url_from_repo_dict(self):
        repo = {'baseurl': 'http://example.com/repo'}
        url = util.get_repo_url(self.compose, repo)
        self.assertEqual(url, 'http://example.com/repo')

        repo = {'baseurl': 'Server'}
        url = util.get_repo_url(self.compose, repo)
        self.assertEqual(url, 'http://example.com/RHEL-8.0-20180101.n.0/compose/Server/$basearch/os')

    def test_get_repo_urls(self):
        repos = [
            'http://example.com/repo',
            'Server',
            {'baseurl': 'Client'},
            {'baseurl': 'ftp://example.com/linux/repo'},
        ]

        expect = [
            'http://example.com/repo',
            'http://example.com/RHEL-8.0-20180101.n.0/compose/Server/$basearch/os',
            'http://example.com/RHEL-8.0-20180101.n.0/compose/Client/$basearch/os',
            'ftp://example.com/linux/repo',
        ]

        self.assertEqual(util.get_repo_urls(self.compose, repos), expect)

    def test_get_repo_dict_from_normal_url(self):
        repo_dict = util.get_repo_dict(self.compose, 'http://example.com/repo')
        expect = {'name': 'http:__example.com_repo', 'baseurl': 'http://example.com/repo'}
        self.assertEqual(repo_dict, expect)

    def test_get_repo_dict_from_variant_uid(self):
        repo_dict = util.get_repo_dict(self.compose, 'Server')
        expect = {
            'name': "%s-%s" % (self.compose.compose_id, 'Server'),
            'baseurl': 'http://example.com/RHEL-8.0-20180101.n.0/compose/Server/$basearch/os',
        }
        self.assertEqual(repo_dict, expect)

    def test_get_repo_dict_from_repo_dict(self):
        repo = {'baseurl': 'Server'}
        expect = {
            'name': '%s-%s' % (self.compose.compose_id, 'Server'),
            'baseurl': 'http://example.com/RHEL-8.0-20180101.n.0/compose/Server/$basearch/os'
        }
        repo_dict = util.get_repo_dict(self.compose, repo)
        self.assertEqual(repo_dict, expect)

    def test_get_repo_dicts(self):
        repos = [
            'http://example.com/repo',
            'Server',
            {'baseurl': 'Client'},
            {'baseurl': 'ftp://example.com/linux/repo'},
            {'name': 'testrepo', 'baseurl': 'ftp://example.com/linux/repo'},
        ]
        expect = [
            {'name': 'http:__example.com_repo', 'baseurl': 'http://example.com/repo'},
            {'name': '%s-%s' % (self.compose.compose_id, 'Server'), 'baseurl': 'http://example.com/RHEL-8.0-20180101.n.0/compose/Server/$basearch/os'},
            {'name': '%s-%s' % (self.compose.compose_id, 'Client'), 'baseurl': 'http://example.com/RHEL-8.0-20180101.n.0/compose/Client/$basearch/os'},
            {'name': 'ftp:__example.com_linux_repo', 'baseurl': 'ftp://example.com/linux/repo'},
            {'name': 'testrepo', 'baseurl': 'ftp://example.com/linux/repo'},
        ]
        repos = util.get_repo_dicts(self.compose, repos)
        self.assertEqual(repos, expect)


class TestVersionGenerator(unittest.TestCase):
    def test_unknown_generator(self):
        compose = mock.Mock()
        with self.assertRaises(RuntimeError) as ctx:
            util.version_generator(compose, '!GIMME_VERSION')

        self.assertEqual(str(ctx.exception),
                         "Unknown version generator '!GIMME_VERSION'")

    def test_passthrough_value(self):
        compose = mock.Mock()
        self.assertEqual(util.version_generator(compose, '1.2.3'), '1.2.3')

    def test_passthrough_none(self):
        compose = mock.Mock()
        self.assertEqual(util.version_generator(compose, None), None)


if __name__ == "__main__":
    unittest.main()
