#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import mock
try:
    import unittest2 as unittest
except ImportError:
    import unittest
import shutil
import tempfile

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi.wrappers import scm
from tests.helpers import touch


class SCMBaseTest(unittest.TestCase):
    def setUp(self):
        self.destdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.destdir)

    def assertStructure(self, returned, expected):
        # Check we returned the correct files
        self.assertItemsEqual(returned, expected)

        # Each file must exist
        for f in expected:
            self.assertTrue(os.path.isfile(os.path.join(self.destdir, f)))

        # Only expected files should exist
        found = []
        for root, dirs, files in os.walk(self.destdir):
            for f in files:
                p = os.path.relpath(os.path.join(root, f), self.destdir)
                found.append(p)
        self.assertItemsEqual(expected, found)


class FileSCMTestCase(SCMBaseTest):
    def setUp(self):
        """
        Prepares a source structure and destination directory.

        srcdir
         +- in_root
         +- subdir
             +- first
             +- second
        """
        super(FileSCMTestCase, self).setUp()
        self.srcdir = tempfile.mkdtemp()
        touch(os.path.join(self.srcdir, 'in_root'))
        touch(os.path.join(self.srcdir, 'subdir', 'first'))
        touch(os.path.join(self.srcdir, 'subdir', 'second'))

    def tearDown(self):
        super(FileSCMTestCase, self).tearDown()
        shutil.rmtree(self.srcdir)

    def test_get_file_by_name(self):
        file = os.path.join(self.srcdir, 'in_root')
        retval = scm.get_file_from_scm(file, self.destdir)
        self.assertStructure(retval, ['in_root'])

    def test_get_file_by_dict(self):
        retval = scm.get_file_from_scm({
            'scm': 'file', 'repo': None, 'file': os.path.join(self.srcdir, 'subdir', 'first')},
            self.destdir)
        self.assertStructure(retval, ['first'])

    def test_get_dir_by_name(self):
        retval = scm.get_dir_from_scm(os.path.join(self.srcdir, 'subdir'), self.destdir)
        self.assertStructure(retval, ['first', 'second'])

    def test_get_dir_by_dict(self):
        retval = scm.get_dir_from_scm(
            {'scm': 'file', 'repo': None, 'dir': os.path.join(self.srcdir, 'subdir')},
            self.destdir)
        self.assertStructure(retval, ['first', 'second'])

    def test_get_missing_file(self):
        with self.assertRaises(RuntimeError) as ctx:
            scm.get_file_from_scm({'scm': 'file',
                                   'repo': None,
                                   'file': 'this-is-really-not-here.txt'},
                                  self.destdir)

        self.assertIn('No files matched', str(ctx.exception))

    def test_get_missing_dir(self):
        with self.assertRaises(RuntimeError) as ctx:
            scm.get_dir_from_scm({'scm': 'file',
                                  'repo': None,
                                  'dir': 'this-is-really-not-here'},
                                 self.destdir)

        self.assertIn('No directories matched', str(ctx.exception))


class GitSCMTestCase(SCMBaseTest):
    @mock.patch('pungi.wrappers.scm.run')
    def test_get_file(self, run):
        commands = []

        def process(cmd, workdir=None, **kwargs):
            if cmd.startswith('/usr/bin/git'):
                fname = cmd.split('|')[0].strip().split(' ')[-1]
                touch(os.path.join(workdir, fname))
            commands.append(cmd)

        run.side_effect = process

        retval = scm.get_file_from_scm({'scm': 'git',
                                        'repo': 'git://example.com/git/repo.git',
                                        'file': 'some_file.txt'},
                                       self.destdir)
        self.assertStructure(retval, ['some_file.txt'])
        self.assertEqual(
            commands,
            ['/usr/bin/git archive --remote=git://example.com/git/repo.git master some_file.txt | tar xf -'])

    @mock.patch('pungi.wrappers.scm.run')
    def test_get_file_generated_by_command_via_git(self, run):
        commands = []

        def process(cmd, workdir=None, **kwargs):
            if cmd.startswith('/usr/bin/git'):
                checkout = cmd.split(' ')[-1]
                touch(os.path.join(checkout, 'some_file.txt'))
            commands.append(cmd)
            return 0, ''

        run.side_effect = process

        retval = scm.get_file_from_scm({'scm': 'git',
                                        'repo': 'git://example.com/git/repo.git',
                                        'file': 'some_file.txt',
                                        'command': 'make'},
                                       self.destdir)
        self.assertStructure(retval, ['some_file.txt'])
        self.assertRegexpMatches(
            commands[0],
            r'/usr/bin/git clone --depth 1 --branch=master git://example.com/git/repo.git /tmp/.+')
        self.assertEqual(commands[1:], ['make'])

    @mock.patch('pungi.wrappers.scm.run')
    def test_get_file_and_fail_to_generate(self, run):
        commands = []

        def process(cmd, workdir=None, **kwargs):
            if cmd.startswith('/usr/bin/git'):
                checkout = cmd.split(' ')[-1]
                touch(os.path.join(checkout, 'some_file.txt'))
            commands.append(cmd)
            return len(commands), 'output'

        run.side_effect = process

        with self.assertRaises(RuntimeError) as ctx:
            scm.get_file_from_scm({'scm': 'git',
                                   'repo': 'git://example.com/git/repo.git',
                                   'file': 'some_file.txt',
                                   'command': 'make'},
                                  self.destdir)

        self.assertEqual(str(ctx.exception), "'make' failed with exit code 2")

    @mock.patch('pungi.wrappers.scm.run')
    def test_get_file_generated_by_command_via_https(self, run):
        commands = []

        def process(cmd, workdir=None, **kwargs):
            if cmd.startswith('/usr/bin/git'):
                checkout = cmd.split(' ')[-1]
                touch(os.path.join(checkout, 'some_file.txt'))
            commands.append(cmd)
            return 0, ''

        run.side_effect = process

        retval = scm.get_file_from_scm({'scm': 'git',
                                        'repo': 'https://example.com/git/repo.git',
                                        'file': 'some_file.txt',
                                        'command': 'make'},
                                       self.destdir)
        self.assertStructure(retval, ['some_file.txt'])
        self.assertRegexpMatches(
            commands[0],
            r'/usr/bin/git clone --depth 1 --branch=master https://example.com/git/repo.git /tmp/.+')
        self.assertEqual(commands[1:], ['make'])

    @mock.patch('pungi.wrappers.scm.run')
    def test_get_file_via_https(self, run):
        commands = []

        def process(cmd, workdir=None, **kwargs):
            checkout = cmd.split(' ')[-1]
            touch(os.path.join(checkout, 'some_file.txt'))
            touch(os.path.join(checkout, 'other_file.txt'))
            commands.append(cmd)

        run.side_effect = process

        retval = scm.get_file_from_scm({'scm': 'git',
                                        'repo': 'https://example.com/git/repo.git',
                                        'file': 'some_file.txt'},
                                       self.destdir)
        self.assertStructure(retval, ['some_file.txt'])
        self.assertEqual(1, len(commands))
        self.assertRegexpMatches(
            commands[0],
            r'/usr/bin/git clone --depth 1 --branch=master https://example.com/git/repo.git /tmp/.+')

    @mock.patch('pungi.wrappers.scm.run')
    def test_get_dir(self, run):
        commands = []

        def process(cmd, workdir=None, **kwargs):
            fname = cmd.split('|')[0].strip().split(' ')[-1]
            touch(os.path.join(workdir, fname, 'first'))
            touch(os.path.join(workdir, fname, 'second'))
            commands.append(cmd)

        run.side_effect = process

        retval = scm.get_dir_from_scm({'scm': 'git',
                                       'repo': 'git://example.com/git/repo.git',
                                       'dir': 'subdir'},
                                      self.destdir)
        self.assertStructure(retval, ['first', 'second'])

        self.assertEqual(
            commands,
            ['/usr/bin/git archive --remote=git://example.com/git/repo.git master subdir | tar xf -'])

    @mock.patch('pungi.wrappers.scm.run')
    def test_get_dir_via_git_and_generate(self, run):
        commands = []

        def process(cmd, workdir=None, **kwargs):
            if cmd.startswith('/usr/bin/git'):
                checkout = cmd.split(' ')[-1]
                touch(os.path.join(checkout, 'subdir', 'first'))
                touch(os.path.join(checkout, 'subdir', 'second'))
            commands.append(cmd)
            return 0, ''

        run.side_effect = process

        retval = scm.get_dir_from_scm({'scm': 'git',
                                       'repo': 'git://example.com/git/repo.git',
                                       'dir': 'subdir',
                                       'command': 'make'},
                                      self.destdir)
        self.assertStructure(retval, ['first', 'second'])

        self.assertRegexpMatches(
            commands[0],
            r'/usr/bin/git clone --depth 1 --branch=master git://example.com/git/repo.git /tmp/.+')
        self.assertEqual(commands[1:], ['make'])

    @mock.patch('pungi.wrappers.scm.run')
    def test_get_dir_via_https(self, run):
        commands = []

        def process(cmd, workdir=None, **kwargs):
            checkout = cmd.split(' ')[-1]
            touch(os.path.join(checkout, 'subdir', 'first'))
            touch(os.path.join(checkout, 'subdir', 'second'))
            commands.append(cmd)

        run.side_effect = process

        retval = scm.get_dir_from_scm({'scm': 'git',
                                       'repo': 'https://example.com/git/repo.git',
                                       'dir': 'subdir'},
                                      self.destdir)
        self.assertStructure(retval, ['first', 'second'])

        self.assertRegexpMatches(
            commands[0],
            r'/usr/bin/git clone --depth 1 --branch=master https://example.com/git/repo.git /tmp/.+')

    @mock.patch('pungi.wrappers.scm.run')
    def test_get_dir_via_https_and_generate(self, run):
        commands = []

        def process(cmd, workdir=None, **kwargs):
            if cmd.startswith('/usr/bin/git'):
                checkout = cmd.split(' ')[-1]
                touch(os.path.join(checkout, 'subdir', 'first'))
                touch(os.path.join(checkout, 'subdir', 'second'))
            commands.append(cmd)
            return 0, ''

        run.side_effect = process

        retval = scm.get_dir_from_scm({'scm': 'git',
                                       'repo': 'https://example.com/git/repo.git',
                                       'dir': 'subdir',
                                       'command': 'make'},
                                      self.destdir)
        self.assertStructure(retval, ['first', 'second'])

        self.assertRegexpMatches(
            commands[0],
            r'/usr/bin/git clone --depth 1 --branch=master https://example.com/git/repo.git /tmp/.+')
        self.assertEqual(commands[1:], ['make'])


class RpmSCMTestCase(SCMBaseTest):
    def setUp(self):
        super(RpmSCMTestCase, self).setUp()
        self.tmpdir = tempfile.mkdtemp()
        self.exploded = set()
        self.rpms = [self.tmpdir + '/whatever.rpm', self.tmpdir + '/another.rpm']
        self.numbered = [self.tmpdir + x for x in ['/one1.rpm', '/one2.rpm', '/two1.rpm', '/two2.rpm']]
        for rpm in self.rpms + self.numbered:
            touch(rpm)

    def tearDown(self):
        super(RpmSCMTestCase, self).tearDown()
        shutil.rmtree(self.tmpdir)

    def _explode_rpm(self, path, dest):
        self.exploded.add(path)
        touch(os.path.join(dest, 'some-file.txt'))
        touch(os.path.join(dest, 'subdir', 'foo.txt'))
        touch(os.path.join(dest, 'subdir', 'bar.txt'))

    def _explode_multiple(self, path, dest):
        self.exploded.add(path)
        cnt = len(self.exploded)
        touch(os.path.join(dest, 'some-file-%d.txt' % cnt))
        touch(os.path.join(dest, 'subdir-%d' % cnt, 'foo-%d.txt' % cnt))
        touch(os.path.join(dest, 'common', 'foo-%d.txt' % cnt))

    @mock.patch('pungi.wrappers.scm.explode_rpm_package')
    def test_get_file(self, explode):
        explode.side_effect = self._explode_rpm

        retval = scm.get_file_from_scm(
            {'scm': 'rpm', 'repo': self.rpms[0], 'file': 'some-file.txt'},
            self.destdir)

        self.assertStructure(retval, ['some-file.txt'])
        self.assertItemsEqual(self.exploded, [self.rpms[0]])

    @mock.patch('pungi.wrappers.scm.explode_rpm_package')
    def test_get_more_files(self, explode):
        explode.side_effect = self._explode_rpm

        retval = scm.get_file_from_scm(
            {'scm': 'rpm', 'repo': self.rpms[0],
             'file': ['some-file.txt', 'subdir/foo.txt']},
            self.destdir)

        self.assertStructure(retval, ['some-file.txt', 'foo.txt'])
        self.assertItemsEqual(self.exploded, [self.rpms[0]])

    @mock.patch('pungi.wrappers.scm.explode_rpm_package')
    def test_get_whole_dir(self, explode):
        explode.side_effect = self._explode_rpm

        retval = scm.get_dir_from_scm(
            {'scm': 'rpm', 'repo': self.rpms[0], 'dir': 'subdir'},
            self.destdir)

        self.assertStructure(retval, ['subdir/foo.txt', 'subdir/bar.txt'])
        self.assertItemsEqual(self.exploded, [self.rpms[0]])

    @mock.patch('pungi.wrappers.scm.explode_rpm_package')
    def test_get_dir_contents(self, explode):
        explode.side_effect = self._explode_rpm

        retval = scm.get_dir_from_scm(
            {'scm': 'rpm', 'repo': self.rpms[0], 'dir': 'subdir/'},
            self.destdir)

        self.assertStructure(retval, ['foo.txt', 'bar.txt'])
        self.assertItemsEqual(self.exploded, [self.rpms[0]])

    @mock.patch('pungi.wrappers.scm.explode_rpm_package')
    def test_get_files_from_two_rpms(self, explode):
        explode.side_effect = self._explode_multiple

        retval = scm.get_file_from_scm(
            {'scm': 'rpm', 'repo': self.rpms,
             'file': ['some-file-1.txt', 'some-file-2.txt']},
            self.destdir)

        self.assertStructure(retval, ['some-file-1.txt', 'some-file-2.txt'])
        self.assertItemsEqual(self.exploded, self.rpms)

    @mock.patch('pungi.wrappers.scm.explode_rpm_package')
    def test_get_files_from_glob_rpms(self, explode):
        explode.side_effect = self._explode_multiple

        retval = scm.get_file_from_scm(
            {'scm': 'rpm', 'file': 'some-file-*.txt',
             'repo': [self.tmpdir + '/one*.rpm', self.tmpdir + '/two*.rpm']},
            self.destdir)

        self.assertStructure(retval,
                             ['some-file-1.txt', 'some-file-2.txt', 'some-file-3.txt', 'some-file-4.txt'])
        self.assertItemsEqual(self.exploded, self.numbered)

    @mock.patch('pungi.wrappers.scm.explode_rpm_package')
    def test_get_dir_from_two_rpms(self, explode):
        explode.side_effect = self._explode_multiple

        retval = scm.get_dir_from_scm({'scm': 'rpm',
                                       'repo': self.rpms,
                                       'dir': 'common'},
                                      self.destdir)

        self.assertStructure(retval, ['common/foo-1.txt', 'common/foo-2.txt'])
        self.assertItemsEqual(self.exploded, self.rpms)

    @mock.patch('pungi.wrappers.scm.explode_rpm_package')
    def test_get_dir_from_glob_rpms(self, explode):
        explode.side_effect = self._explode_multiple

        retval = scm.get_dir_from_scm(
            {'scm': 'rpm', 'dir': 'common/',
             'repo': [self.tmpdir + '/one*.rpm', self.tmpdir + '/two*.rpm']},
            self.destdir)

        self.assertStructure(retval,
                             ['foo-1.txt', 'foo-2.txt', 'foo-3.txt', 'foo-4.txt'])
        self.assertItemsEqual(self.exploded, self.numbered)


class CvsSCMTestCase(SCMBaseTest):
    @mock.patch('pungi.wrappers.scm.run')
    def test_get_file(self, run):
        commands = []

        def process(cmd, workdir=None, **kwargs):
            fname = cmd[-1]
            touch(os.path.join(workdir, fname))
            commands.append(' '.join(cmd))

        run.side_effect = process

        retval = scm.get_file_from_scm({'scm': 'cvs',
                                        'repo': 'http://example.com/cvs',
                                        'file': 'some_file.txt'},
                                       self.destdir)
        self.assertStructure(retval, ['some_file.txt'])
        self.assertEqual(
            commands,
            ['/usr/bin/cvs -q -d http://example.com/cvs export -r HEAD some_file.txt'])

    @mock.patch('pungi.wrappers.scm.run')
    def test_get_dir(self, run):
        commands = []

        def process(cmd, workdir=None, **kwargs):
            fname = cmd[-1]
            touch(os.path.join(workdir, fname, 'first'))
            touch(os.path.join(workdir, fname, 'second'))
            commands.append(' '.join(cmd))

        run.side_effect = process

        retval = scm.get_dir_from_scm({'scm': 'cvs',
                                       'repo': 'http://example.com/cvs',
                                       'dir': 'subdir'},
                                      self.destdir)
        self.assertStructure(retval, ['first', 'second'])

        self.assertEqual(
            commands,
            ['/usr/bin/cvs -q -d http://example.com/cvs export -r HEAD subdir'])


if __name__ == "__main__":
    unittest.main()
