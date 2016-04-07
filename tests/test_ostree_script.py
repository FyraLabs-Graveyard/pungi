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
            '--log-dir={}'.format(os.path.join(self.topdir, 'logs', 'Atomic')),
            '--treefile={}/fedora-atomic-docker-host.json'.format(self.topdir),
            repo,
        ])

        self.maxDiff = None
        self.assertItemsEqual(
            run.call_args_list,
            [mock.call(['ostree', 'init', '--repo={}'.format(repo), '--mode=archive-z2'],
                       logfile=self.topdir + '/logs/Atomic/init-ostree-repo.log', show_cmd=True),
             mock.call(['rpm-ostree', 'compose', 'tree', '--repo={}'.format(repo),
                        self.topdir + '/fedora-atomic-docker-host.json'],
                       logfile=self.topdir + '/logs/Atomic/create-ostree-repo.log', show_cmd=True)])


if __name__ == '__main__':
    unittest.main()
