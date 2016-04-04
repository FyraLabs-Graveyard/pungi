#!/usr/bin/env python
# -*- coding: utf-8 -*-


import unittest
import mock

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bin'))

from tests import helpers
from pungi import atomic


class OstreeScriptTest(helpers.PungiTestCase):

    @mock.patch('kobo.shortcuts.run')
    def test_full_run(self, run):
        atomic.main([
            '--log-dir={}'.format(os.path.join(self.topdir, 'logs', 'Atomic')),
            '--treefile={}'.format(os.path.join(self.topdir, 'work', 'fedora-atomic-docker-host.json')),
            os.path.join(self.topdir, 'atomic'),
        ])
        self.maxDiff = None
        self.assertItemsEqual(
            run.call_args_list,
            [mock.call(['ostree', 'init', '--repo={}/atomic'.format(self.topdir), '--mode=archive-z2'],
                       logfile=self.topdir + '/logs/Atomic/init-atomic-repo.log'),
             mock.call(['rpm-ostree', 'compose', 'tree', '--repo={}/atomic'.format(self.topdir),
                        self.topdir + '/work/fedora-atomic-docker-host.json'],
                       logfile=self.topdir + '/logs/Atomic/create-atomic-repo.log')])


if __name__ == '__main__':
    unittest.main()
