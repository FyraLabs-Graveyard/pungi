# -*- coding: utf-8 -*-

try:
    import unittest2 as unittest
except ImportError:
    import unittest

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi.wrappers import repoclosure


class RepoclosureWrapperTestCase(unittest.TestCase):
    def test_minimal_command(self):
        rc = repoclosure.RepoclosureWrapper()

        self.assertEqual(rc.get_repoclosure_cmd(),
                         ['/usr/bin/repoclosure'])

    def test_multiple_arches(self):
        rc = repoclosure.RepoclosureWrapper()

        self.assertEqual(rc.get_repoclosure_cmd(arch=['x86_64', 'ppc64']),
                         ['/usr/bin/repoclosure', '--arch=x86_64', '--arch=ppc64'])

    def test_full_command(self):
        rc = repoclosure.RepoclosureWrapper()

        repos = {'my-repo': '/mnt/koji/repo'}
        lookaside = {'fedora': 'http://kojipkgs.fp.o/repo'}

        cmd = rc.get_repoclosure_cmd(arch='x86_64', builddeps=True,
                                     repos=repos, lookaside=lookaside)
        self.assertEqual(cmd[0], '/usr/bin/repoclosure')
        self.assertItemsEqual(
            cmd[1:],
            ['--arch=x86_64',
             '--builddeps',
             '--repofrompath=my-repo,file:///mnt/koji/repo',
             '--repofrompath=fedora,http://kojipkgs.fp.o/repo',
             '--repoid=my-repo',
             '--lookaside=fedora'])

    def test_expand_repo(self):
        rc = repoclosure.RepoclosureWrapper()
        repos = {
            'local': '/mnt/koji/repo',
            'remote': 'http://kojipkgs.fp.o/repo',
        }
        cmd = rc.get_repoclosure_cmd(repos=repos)
        self.assertEqual(cmd[0], '/usr/bin/repoclosure')
        self.assertItemsEqual(
            cmd[1:],
            ['--repofrompath=local,file:///mnt/koji/repo',
             '--repofrompath=remote,http://kojipkgs.fp.o/repo',
             '--repoid=local',
             '--repoid=remote'])

    def test_expand_lookaside(self):
        rc = repoclosure.RepoclosureWrapper()
        repos = {
            'local': '/mnt/koji/repo',
            'remote': 'http://kojipkgs.fp.o/repo',
        }
        cmd = rc.get_repoclosure_cmd(lookaside=repos)
        self.assertEqual(cmd[0], '/usr/bin/repoclosure')
        self.assertItemsEqual(
            cmd[1:],
            ['--repofrompath=local,file:///mnt/koji/repo',
             '--repofrompath=remote,http://kojipkgs.fp.o/repo',
             '--lookaside=local',
             '--lookaside=remote'])
