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

    def _dummy_config_repo(self, scm_dict, target, logger=None):
        helpers.touch(os.path.join(target, 'fedora-atomic-docker-host.json'))
        helpers.touch(os.path.join(target, 'fedora-rawhide.repo'))

    @mock.patch('kobo.shortcuts.run')
    @mock.patch('pungi.wrappers.scm.get_dir_from_scm')
    def test_full_run(self, get_dir_from_scm, run):
        get_dir_from_scm.side_effect = self._dummy_config_repo

        repo = os.path.join(self.topdir, 'atomic')

        ostree.main([
            '--log-dir={}'.format(os.path.join(self.topdir, 'logs', 'Atomic')),
            '--work-dir={}'.format(self.topdir),
            '--treefile={}'.format('fedora-atomic-docker-host.json'),
            '--config-url=https://git.fedorahosted.org/git/fedora-atomic.git',
            '--config-branch=f24',
            '--source-repo=https://kojipkgs.fedoraproject.org/repo',
            repo,
        ])

        self.maxDiff = None
        self.assertEqual(get_dir_from_scm.call_args_list,
                         [mock.call({'scm': 'git', 'repo': 'https://git.fedorahosted.org/git/fedora-atomic.git',
                                     'branch': 'f24', 'dir': '.'},
                                    self.topdir + '/config_repo')])
        self.assertItemsEqual(
            run.call_args_list,
            [mock.call(['ostree', 'init', '--repo={}'.format(repo), '--mode=archive-z2'],
                       logfile=self.topdir + '/logs/Atomic/init-ostree-repo.log', show_cmd=True),
             mock.call(['rpm-ostree', 'compose', 'tree', '--repo={}'.format(repo),
                        self.topdir + '/config_repo/fedora-atomic-docker-host.json'],
                       logfile=self.topdir + '/logs/Atomic/create-ostree-repo.log', show_cmd=True)])


if __name__ == '__main__':
    unittest.main()
