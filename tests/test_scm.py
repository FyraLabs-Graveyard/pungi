#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import mock
import unittest
import shutil
import tempfile

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi.wrappers import scm
from tests.helpers import touch


class FileSCMTestCase(unittest.TestCase):
    def setUp(self):
        """
        Prepares a source structure and destination directory.

        srcdir
         +- in_root
         +- subdir
             +- first
             +- second
        """
        self.srcdir = tempfile.mkdtemp()
        self.destdir = tempfile.mkdtemp()
        touch(os.path.join(self.srcdir, 'in_root'))
        touch(os.path.join(self.srcdir, 'subdir', 'first'))
        touch(os.path.join(self.srcdir, 'subdir', 'second'))

    def tearDown(self):
        shutil.rmtree(self.srcdir)
        shutil.rmtree(self.destdir)

    def test_get_file_by_name(self):
        file = os.path.join(self.srcdir, 'in_root')
        scm.get_file_from_scm(file, self.destdir)
        self.assertItemsEqual(os.listdir(self.destdir),
                              ['in_root'])
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'in_root')))

    def test_get_file_by_dict(self):
        scm.get_file_from_scm({'scm': 'file',
                               'repo': None,
                               'file': os.path.join(self.srcdir, 'subdir', 'first')},
                              self.destdir)
        self.assertItemsEqual(os.listdir(self.destdir),
                              ['first'])
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'first')))

    def test_get_dir_by_name(self):
        scm.get_dir_from_scm(os.path.join(self.srcdir, 'subdir'), self.destdir)
        self.assertItemsEqual(os.listdir(self.destdir),
                              ['first', 'second'])
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'first')))
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'second')))

    def test_get_dir_by_dict(self):
        scm.get_dir_from_scm({'scm': 'file',
                              'repo': None,
                              'dir': os.path.join(self.srcdir, 'subdir')},
                             self.destdir)
        self.assertItemsEqual(os.listdir(self.destdir),
                              ['first', 'second'])
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'first')))
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'second')))

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


class GitSCMTestCase(unittest.TestCase):
    def setUp(self):
        self.destdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.destdir)

    @mock.patch('pungi.wrappers.scm.run')
    def test_get_file(self, run):
        commands = []

        def process(cmd, workdir=None, **kwargs):
            fname = cmd.split('|')[0].strip().split(' ')[-1]
            touch(os.path.join(workdir, fname))
            commands.append(cmd)

        run.side_effect = process

        scm.get_file_from_scm({'scm': 'git',
                               'repo': 'git://example.com/git/repo.git',
                               'file': 'some_file.txt'},
                              self.destdir)
        self.assertItemsEqual(os.listdir(self.destdir),
                              ['some_file.txt'])
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'some_file.txt')))
        self.assertEqual(
            commands,
            ['/usr/bin/git archive --remote=git://example.com/git/repo.git master some_file.txt | tar xf -'])

    @mock.patch('pungi.wrappers.scm.run')
    def test_get_file_via_https(self, run):
        commands = []

        def process(cmd, workdir=None, **kwargs):
            checkout = cmd.split(' ')[-1]
            touch(os.path.join(checkout, 'some_file.txt'))
            touch(os.path.join(checkout, 'other_file.txt'))
            commands.append(cmd)

        run.side_effect = process

        scm.get_file_from_scm({'scm': 'git',
                               'repo': 'https://example.com/git/repo.git',
                               'file': 'some_file.txt'},
                              self.destdir)
        self.assertItemsEqual(os.listdir(self.destdir),
                              ['some_file.txt'])
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'some_file.txt')))
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

        scm.get_dir_from_scm({'scm': 'git',
                              'repo': 'git://example.com/git/repo.git',
                              'dir': 'subdir'},
                             self.destdir)
        self.assertItemsEqual(os.listdir(self.destdir),
                              ['first', 'second'])
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'first')))
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'second')))

        self.assertEqual(
            commands,
            ['/usr/bin/git archive --remote=git://example.com/git/repo.git master subdir | tar xf -'])

    @mock.patch('pungi.wrappers.scm.run')
    def test_get_dir_via_https(self, run):
        commands = []

        def process(cmd, workdir=None, **kwargs):
            checkout = cmd.split(' ')[-1]
            touch(os.path.join(checkout, 'subdir', 'first'))
            touch(os.path.join(checkout, 'subdir', 'second'))
            commands.append(cmd)

        run.side_effect = process

        scm.get_dir_from_scm({'scm': 'git',
                              'repo': 'https://example.com/git/repo.git',
                              'dir': 'subdir'},
                             self.destdir)
        self.assertItemsEqual(os.listdir(self.destdir),
                              ['first', 'second'])
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'first')))
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'second')))

        self.assertRegexpMatches(
            commands[0],
            r'/usr/bin/git clone --depth 1 --branch=master https://example.com/git/repo.git /tmp/.+')


class RpmSCMTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.destdir = tempfile.mkdtemp()
        self.exploded = set()
        self.rpms = [self.tmpdir + '/whatever.rpm', self.tmpdir + '/another.rpm']
        self.numbered = [self.tmpdir + x for x in ['/one1.rpm', '/one2.rpm', '/two1.rpm', '/two2.rpm']]
        for rpm in self.rpms + self.numbered:
            touch(rpm)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        shutil.rmtree(self.destdir)

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

        scm.get_file_from_scm({'scm': 'rpm',
                               'repo': self.rpms[0],
                               'file': 'some-file.txt'},
                              self.destdir)

        self.assertItemsEqual(os.listdir(self.destdir),
                              ['some-file.txt'])
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'some-file.txt')))
        self.assertItemsEqual(self.exploded, [self.rpms[0]])

    @mock.patch('pungi.wrappers.scm.explode_rpm_package')
    def test_get_more_files(self, explode):
        explode.side_effect = self._explode_rpm

        scm.get_file_from_scm({'scm': 'rpm',
                               'repo': self.rpms[0],
                               'file': ['some-file.txt', 'subdir/foo.txt']},
                              self.destdir)

        self.assertItemsEqual(os.listdir(self.destdir),
                              ['some-file.txt', 'foo.txt'])
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'some-file.txt')))
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'foo.txt')))
        self.assertItemsEqual(self.exploded, [self.rpms[0]])

    @mock.patch('pungi.wrappers.scm.explode_rpm_package')
    def test_get_whole_dir(self, explode):
        explode.side_effect = self._explode_rpm

        scm.get_dir_from_scm({'scm': 'rpm',
                              'repo': self.rpms[0],
                              'dir': 'subdir'},
                             self.destdir)

        self.assertItemsEqual(os.listdir(self.destdir),
                              ['subdir'])
        self.assertTrue(os.path.isdir(os.path.join(self.destdir, 'subdir')))
        self.assertItemsEqual(os.listdir(os.path.join(self.destdir, 'subdir')),
                              ['foo.txt', 'bar.txt'])
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'subdir', 'foo.txt')))
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'subdir', 'bar.txt')))
        self.assertItemsEqual(self.exploded, [self.rpms[0]])

    @mock.patch('pungi.wrappers.scm.explode_rpm_package')
    def test_get_dir_contents(self, explode):
        explode.side_effect = self._explode_rpm

        scm.get_dir_from_scm({'scm': 'rpm',
                              'repo': self.rpms[0],
                              'dir': 'subdir/'},
                             self.destdir)

        self.assertItemsEqual(os.listdir(self.destdir),
                              ['foo.txt', 'bar.txt'])
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'foo.txt')))
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'bar.txt')))
        self.assertItemsEqual(self.exploded, [self.rpms[0]])

    @mock.patch('pungi.wrappers.scm.explode_rpm_package')
    def test_get_files_from_two_rpms(self, explode):
        explode.side_effect = self._explode_multiple

        scm.get_file_from_scm({'scm': 'rpm',
                               'repo': self.rpms,
                               'file': ['some-file-1.txt', 'some-file-2.txt']},
                              self.destdir)

        self.assertItemsEqual(os.listdir(self.destdir),
                              ['some-file-1.txt', 'some-file-2.txt'])
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'some-file-1.txt')))
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'some-file-2.txt')))
        self.assertItemsEqual(self.exploded, self.rpms)

    @mock.patch('pungi.wrappers.scm.explode_rpm_package')
    def test_get_files_from_glob_rpms(self, explode):
        explode.side_effect = self._explode_multiple

        scm.get_file_from_scm({'scm': 'rpm',
                               'repo': [self.tmpdir + '/one*.rpm', self.tmpdir + '/two*.rpm'],
                               'file': 'some-file-*.txt'},
                              self.destdir)

        self.assertItemsEqual(os.listdir(self.destdir),
                              ['some-file-1.txt', 'some-file-2.txt', 'some-file-3.txt', 'some-file-4.txt'])
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'some-file-1.txt')))
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'some-file-2.txt')))
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'some-file-3.txt')))
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'some-file-4.txt')))
        self.assertItemsEqual(self.exploded, self.numbered)

    @mock.patch('pungi.wrappers.scm.explode_rpm_package')
    def test_get_dir_from_two_rpms(self, explode):
        explode.side_effect = self._explode_multiple

        scm.get_dir_from_scm({'scm': 'rpm',
                              'repo': self.rpms,
                              'dir': 'common'},
                             self.destdir)

        self.assertItemsEqual(os.listdir(self.destdir),
                              ['common'])
        self.assertTrue(os.path.isdir(os.path.join(self.destdir, 'common')))
        self.assertItemsEqual(os.listdir(os.path.join(self.destdir, 'common')),
                              ['foo-1.txt', 'foo-2.txt'])
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'common', 'foo-1.txt')))
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'common', 'foo-2.txt')))
        self.assertItemsEqual(self.exploded, self.rpms)

    @mock.patch('pungi.wrappers.scm.explode_rpm_package')
    def test_get_dir_from_glob_rpms(self, explode):
        explode.side_effect = self._explode_multiple

        scm.get_dir_from_scm({'scm': 'rpm',
                              'repo': [self.tmpdir + '/one*.rpm', self.tmpdir + '/two*.rpm'],
                              'dir': 'common/'},
                             self.destdir)

        self.assertItemsEqual(os.listdir(self.destdir),
                              ['foo-1.txt', 'foo-2.txt', 'foo-3.txt', 'foo-4.txt'])
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'foo-1.txt')))
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'foo-2.txt')))
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'foo-3.txt')))
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'foo-4.txt')))
        self.assertItemsEqual(self.exploded, self.numbered)


class CvsSCMTestCase(unittest.TestCase):
    def setUp(self):
        self.destdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.destdir)

    @mock.patch('pungi.wrappers.scm.run')
    def test_get_file(self, run):
        commands = []

        def process(cmd, workdir=None, **kwargs):
            fname = cmd[-1]
            touch(os.path.join(workdir, fname))
            commands.append(' '.join(cmd))

        run.side_effect = process

        scm.get_file_from_scm({'scm': 'cvs',
                               'repo': 'http://example.com/cvs',
                               'file': 'some_file.txt'},
                              self.destdir)
        self.assertItemsEqual(os.listdir(self.destdir),
                              ['some_file.txt'])
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'some_file.txt')))
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

        scm.get_dir_from_scm({'scm': 'cvs',
                              'repo': 'http://example.com/cvs',
                              'dir': 'subdir'},
                             self.destdir)
        self.assertItemsEqual(os.listdir(self.destdir),
                              ['first', 'second'])
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'first')))
        self.assertTrue(os.path.isfile(os.path.join(self.destdir, 'second')))

        self.assertEqual(
            commands,
            ['/usr/bin/cvs -q -d http://example.com/cvs export -r HEAD subdir'])


if __name__ == "__main__":
    unittest.main()
