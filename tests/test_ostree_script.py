#!/usr/bin/env python
# -*- coding: utf-8 -*-


import unittest
import mock

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bin'))

from tests import helpers
from pungi import ostree


class OstreeScriptTest(helpers.PungiTestCase):

    @mock.patch('kobo.shortcuts.run')
    def test_full_run(self, run):
        repo = os.path.join(self.topdir, 'atomic')

        ostree.main([
            '--log-dir=%s' % os.path.join(self.topdir, 'logs', 'Atomic'),
            '--treefile=%s/fedora-atomic-docker-host.json' % self.topdir,
            repo,
        ])

        self.maxDiff = None
        self.assertItemsEqual(
            run.call_args_list,
            [mock.call(['ostree', 'init', '--repo=%s' % repo, '--mode=archive-z2'],
                       logfile=self.topdir + '/logs/Atomic/init-ostree-repo.log', show_cmd=True, stdout=True),
             mock.call(['rpm-ostree', 'compose', 'tree', '--repo=%s' % repo,
                        self.topdir + '/fedora-atomic-docker-host.json'],
                       logfile=self.topdir + '/logs/Atomic/create-ostree-repo.log', show_cmd=True, stdout=True)])

    @mock.patch('kobo.shortcuts.run')
    def test_run_on_existing_empty_dir(self, run):
        repo = os.path.join(self.topdir, 'atomic')

        os.mkdir(repo)

        ostree.main([
            '--log-dir=%s' % os.path.join(self.topdir, 'logs', 'Atomic'),
            '--treefile=%s/fedora-atomic-docker-host.json' % self.topdir,
            repo,
        ])

        self.maxDiff = None
        self.assertItemsEqual(
            run.call_args_list,
            [mock.call(['ostree', 'init', '--repo=%s' % repo, '--mode=archive-z2'],
                       logfile=self.topdir + '/logs/Atomic/init-ostree-repo.log', show_cmd=True, stdout=True),
             mock.call(['rpm-ostree', 'compose', 'tree', '--repo=%s' % repo,
                        self.topdir + '/fedora-atomic-docker-host.json'],
                       logfile=self.topdir + '/logs/Atomic/create-ostree-repo.log', show_cmd=True, stdout=True)])

    @mock.patch('kobo.shortcuts.run')
    def test_run_on_initialized_repo(self, run):
        repo = os.path.join(self.topdir, 'atomic')

        helpers.touch(os.path.join(repo, 'initialized'))

        ostree.main([
            '--log-dir=%s' % os.path.join(self.topdir, 'logs', 'Atomic'),
            '--treefile=%s/fedora-atomic-docker-host.json' % self.topdir,
            repo,
        ])

        self.maxDiff = None
        self.assertItemsEqual(
            run.call_args_list,
            [mock.call(['rpm-ostree', 'compose', 'tree', '--repo=%s' % repo,
                        self.topdir + '/fedora-atomic-docker-host.json'],
                       logfile=self.topdir + '/logs/Atomic/create-ostree-repo.log', show_cmd=True, stdout=True)])


if __name__ == '__main__':
    unittest.main()
