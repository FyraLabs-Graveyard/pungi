#!/usr/bin/env python
# -*- coding: utf-8 -*-


import unittest
import mock

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tests import helpers
from pungi.phases import ostree


class OSTreePhaseTest(helpers.PungiTestCase):

    @mock.patch('pungi.phases.ostree.ThreadPool')
    def test_run(self, ThreadPool):
        cfg = mock.Mock()
        compose = helpers.DummyCompose(self.topdir, {
            'ostree': [
                ('^Everything$', {'x86_64': cfg})
            ]
        })

        pool = ThreadPool.return_value

        phase = ostree.OSTreePhase(compose)
        phase.run()

        self.assertEqual(len(pool.add.call_args_list), 1)
        self.assertEqual(pool.queue_put.call_args_list,
                         [mock.call((compose, compose.variants['Everything'], 'x86_64', cfg))])

    @mock.patch('pungi.phases.ostree.ThreadPool')
    def test_skip_without_config(self, ThreadPool):
        compose = helpers.DummyCompose(self.topdir, {})
        compose.just_phases = None
        compose.skip_phases = []
        phase = ostree.OSTreePhase(compose)
        self.assertTrue(phase.skip())


class OSTreeThreadTest(helpers.PungiTestCase):

    def setUp(self):
        super(OSTreeThreadTest, self).setUp()
        self.repo = os.path.join(self.topdir, 'place/for/atomic')

    def _dummy_config_repo(self, scm_dict, target, logger=None):
        helpers.touch(os.path.join(target, 'fedora-atomic-docker-host.json'))
        helpers.touch(os.path.join(target, 'fedora-rawhide.repo'),
                      'mirrorlist=mirror-mirror-on-the-wall')
        helpers.touch(os.path.join(target, 'fedora-24.repo'),
                      'metalink=who-is-the-fairest-of-them-all')
        helpers.touch(os.path.join(target, 'fedora-23.repo'),
                      'baseurl=why-not-zoidberg?')

    @mock.patch('pungi.wrappers.scm.get_dir_from_scm')
    @mock.patch('pungi.wrappers.kojiwrapper.KojiWrapper')
    def test_run(self, KojiWrapper, get_dir_from_scm):
        get_dir_from_scm.side_effect = self._dummy_config_repo

        compose = helpers.DummyCompose(self.topdir, {
            'koji_profile': 'koji',
            'runroot_tag': 'rrt',
            'translate_paths': [
                (self.topdir + '/compose', 'http://example.com')
            ]
        })
        pool = mock.Mock()
        cfg = {
            'source_repo_from': 'Everything',
            'config_url': 'https://git.fedorahosted.org/git/fedora-atomic.git',
            'config_branch': 'f24',
            'treefile': 'fedora-atomic-docker-host.json',
            'ostree_repo': self.repo
        }
        koji = KojiWrapper.return_value
        koji.run_runroot_cmd.return_value = {
            'task_id': 1234,
            'retcode': 0,
            'output': 'Foo bar\n',
        }

        t = ostree.OSTreeThread(pool)

        t.process((compose, compose.variants['Everything'], 'x86_64', cfg), 1)

        self.assertEqual(get_dir_from_scm.call_args_list,
                         [mock.call({'scm': 'git', 'repo': 'https://git.fedorahosted.org/git/fedora-atomic.git',
                                     'branch': 'f24', 'dir': '.'},
                                    self.topdir + '/work/ostree-1/config_repo', logger=pool._logger)])
        self.assertEqual(koji.get_runroot_cmd.call_args_list,
                         [mock.call('rrt', 'x86_64',
                                    ['pungi-make-ostree',
                                     '--log-dir=%s/logs/x86_64/Everything/ostree-1' % self.topdir,
                                     '--treefile=%s/fedora-atomic-docker-host.json' % (
                                         self.topdir + '/work/ostree-1/config_repo'),
                                     self.repo],
                                    channel=None, mounts=[self.topdir, self.repo],
                                    packages=['pungi', 'ostree', 'rpm-ostree'],
                                    task_id=True, use_shell=True)])
        self.assertEqual(koji.run_runroot_cmd.call_args_list,
                         [mock.call(koji.get_runroot_cmd.return_value,
                                    log_file=self.topdir + '/logs/x86_64/Everything/ostree-1/runroot.log')])

        with open(self.topdir + '/work/ostree-1/config_repo/fedora-rawhide.repo') as f:
            self.assertIn('baseurl=http://example.com/Everything/x86_64/os',
                          f.read())
        with open(self.topdir + '/work/ostree-1/config_repo/fedora-24.repo') as f:
            self.assertIn('baseurl=http://example.com/Everything/x86_64/os',
                          f.read())
        with open(self.topdir + '/work/ostree-1/config_repo/fedora-23.repo') as f:
            self.assertIn('baseurl=http://example.com/Everything/x86_64/os',
                          f.read())
        self.assertTrue(os.path.isdir(self.repo))

    @mock.patch('pungi.wrappers.scm.get_dir_from_scm')
    @mock.patch('pungi.wrappers.kojiwrapper.KojiWrapper')
    def test_run_fail(self, KojiWrapper, get_dir_from_scm):
        get_dir_from_scm.side_effect = self._dummy_config_repo

        compose = helpers.DummyCompose(self.topdir, {
            'koji_profile': 'koji',
            'runroot_tag': 'rrt',
        })
        pool = mock.Mock()
        cfg = {
            'source_repo_from': 'Everything',
            'config_url': 'https://git.fedorahosted.org/git/fedora-atomic.git',
            'config_branch': 'f24',
            'treefile': 'fedora-atomic-docker-host.json',
            'ostree_repo': self.repo,
            'failable': ['*']
        }
        koji = KojiWrapper.return_value
        koji.run_runroot_cmd.return_value = {
            'task_id': 1234,
            'retcode': 1,
            'output': 'Foo bar\n',
        }

        t = ostree.OSTreeThread(pool)

        t.process((compose, compose.variants['Everything'], 'x86_64', cfg), 1)

        compose.log_info.assert_has_calls([
            mock.call('[FAIL] Ostree (variant Everything, arch x86_64) failed, but going on anyway.'),
            mock.call('Runroot task failed: 1234. See %s for more details.'
                      % (self.topdir + '/logs/x86_64/Everything/ostree-1/runroot.log'))
        ])

    @mock.patch('pungi.wrappers.scm.get_dir_from_scm')
    @mock.patch('pungi.wrappers.kojiwrapper.KojiWrapper')
    def test_run_handle_exception(self, KojiWrapper, get_dir_from_scm):
        get_dir_from_scm.side_effect = self._dummy_config_repo

        compose = helpers.DummyCompose(self.topdir, {
            'koji_profile': 'koji',
            'runroot_tag': 'rrt',
        })
        pool = mock.Mock()
        cfg = {
            'source_repo_from': 'Everything',
            'config_url': 'https://git.fedorahosted.org/git/fedora-atomic.git',
            'config_branch': 'f24',
            'treefile': 'fedora-atomic-docker-host.json',
            'ostree_repo': self.repo,
            'failable': ['*']
        }
        koji = KojiWrapper.return_value
        koji.run_runroot_cmd.side_effect = helpers.boom

        t = ostree.OSTreeThread(pool)

        t.process((compose, compose.variants['Everything'], 'x86_64', cfg), 1)

        compose.log_info.assert_has_calls([
            mock.call('[FAIL] Ostree (variant Everything, arch x86_64) failed, but going on anyway.'),
            mock.call('BOOM')
        ])


if __name__ == '__main__':
    unittest.main()
