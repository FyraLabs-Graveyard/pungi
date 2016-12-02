#!/usr/bin/env python
# -*- coding: utf-8 -*-


import unittest
import mock

import os
import json
import sys
import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bin'))

from tests import helpers
from pungi import ostree


class OstreeTreeScriptTest(helpers.PungiTestCase):

    def _make_dummy_config_dir(self, path):
        helpers.touch(os.path.join(path, 'fedora-atomic-docker-host.json'),
                      json.dumps({'ref': 'fedora-atomic/25/x86_64',
                                  'repos': ['fedora-rawhide', 'fedora-24', 'fedora-23']}))
        helpers.touch(os.path.join(path, 'fedora-rawhide.repo'),
                      '[fedora-rawhide]\nmirrorlist=mirror-mirror-on-the-wall')
        helpers.touch(os.path.join(path, 'fedora-24.repo'),
                      '[fedora-24]\nmetalink=who-is-the-fairest-of-them-all')
        helpers.touch(os.path.join(path, 'fedora-23.repo'),
                      '[fedora-23]\nbaseurl=why-not-zoidberg?')

    @mock.patch('kobo.shortcuts.run')
    def test_full_run(self, run):
        repo = os.path.join(self.topdir, 'atomic')

        ostree.main([
            'tree',
            '--repo=%s' % repo,
            '--log-dir=%s' % os.path.join(self.topdir, 'logs', 'Atomic'),
            '--treefile=%s/fedora-atomic-docker-host.json' % self.topdir,
        ])

        self.maxDiff = None
        self.assertItemsEqual(
            run.call_args_list,
            [mock.call(['ostree', 'init', '--repo=%s' % repo, '--mode=archive-z2'],
                       logfile=self.topdir + '/logs/Atomic/init-ostree-repo.log', show_cmd=True, stdout=True),
             mock.call(['rpm-ostree', 'compose', 'tree', '--repo=%s' % repo,
                        '--write-commitid-to=%s' % (self.topdir + '/logs/Atomic/commitid.log'),
                        self.topdir + '/fedora-atomic-docker-host.json'],
                       logfile=self.topdir + '/logs/Atomic/create-ostree-repo.log', show_cmd=True, stdout=True)])

    @mock.patch('kobo.shortcuts.run')
    def test_run_on_existing_empty_dir(self, run):
        repo = os.path.join(self.topdir, 'atomic')

        os.mkdir(repo)

        ostree.main([
            'tree',
            '--repo=%s' % repo,
            '--log-dir=%s' % os.path.join(self.topdir, 'logs', 'Atomic'),
            '--treefile=%s/fedora-atomic-docker-host.json' % self.topdir,
        ])

        self.maxDiff = None
        self.assertItemsEqual(
            run.call_args_list,
            [mock.call(['ostree', 'init', '--repo=%s' % repo, '--mode=archive-z2'],
                       logfile=self.topdir + '/logs/Atomic/init-ostree-repo.log', show_cmd=True, stdout=True),
             mock.call(['rpm-ostree', 'compose', 'tree', '--repo=%s' % repo,
                        '--write-commitid-to=%s' % (self.topdir + '/logs/Atomic/commitid.log'),
                        self.topdir + '/fedora-atomic-docker-host.json'],
                       logfile=self.topdir + '/logs/Atomic/create-ostree-repo.log', show_cmd=True, stdout=True)])

    @mock.patch('kobo.shortcuts.run')
    def test_run_on_initialized_repo(self, run):
        repo = os.path.join(self.topdir, 'atomic')

        helpers.touch(os.path.join(repo, 'initialized'))

        ostree.main([
            'tree',
            '--repo=%s' % repo,
            '--log-dir=%s' % os.path.join(self.topdir, 'logs', 'Atomic'),
            '--treefile=%s/fedora-atomic-docker-host.json' % self.topdir,
        ])

        self.maxDiff = None
        self.assertItemsEqual(
            run.call_args_list,
            [mock.call(['rpm-ostree', 'compose', 'tree', '--repo=%s' % repo,
                        '--write-commitid-to=%s' % (self.topdir + '/logs/Atomic/commitid.log'),
                        self.topdir + '/fedora-atomic-docker-host.json'],
                       logfile=self.topdir + '/logs/Atomic/create-ostree-repo.log', show_cmd=True, stdout=True)])

    @mock.patch('kobo.shortcuts.run')
    def test_update_summary(self, run):
        repo = os.path.join(self.topdir, 'atomic')

        ostree.main([
            'tree',
            '--repo=%s' % repo,
            '--log-dir=%s' % os.path.join(self.topdir, 'logs', 'Atomic'),
            '--treefile=%s/fedora-atomic-docker-host.json' % self.topdir,
            '--update-summary',
        ])

        self.maxDiff = None
        self.assertItemsEqual(
            run.call_args_list,
            [mock.call(['ostree', 'init', '--repo=%s' % repo, '--mode=archive-z2'],
                       logfile=self.topdir + '/logs/Atomic/init-ostree-repo.log', show_cmd=True, stdout=True),
             mock.call(['rpm-ostree', 'compose', 'tree', '--repo=%s' % repo,
                       '--write-commitid-to=%s' % (self.topdir + '/logs/Atomic/commitid.log'),
                        self.topdir + '/fedora-atomic-docker-host.json'],
                       logfile=self.topdir + '/logs/Atomic/create-ostree-repo.log', show_cmd=True, stdout=True),
             mock.call(['ostree', 'summary', '-u', '--repo=%s' % repo],
                       logfile=self.topdir + '/logs/Atomic/ostree-summary.log', show_cmd=True, stdout=True)]),

    @mock.patch('kobo.shortcuts.run')
    def test_versioning_metadata(self, run):
        repo = os.path.join(self.topdir, 'atomic')

        ostree.main([
            'tree',
            '--repo=%s' % repo,
            '--log-dir=%s' % os.path.join(self.topdir, 'logs', 'Atomic'),
            '--treefile=%s/fedora-atomic-docker-host.json' % self.topdir,
            '--version=24',
        ])

        self.maxDiff = None
        self.assertItemsEqual(
            run.call_args_list,
            [mock.call(['ostree', 'init', '--repo=%s' % repo, '--mode=archive-z2'],
                       logfile=self.topdir + '/logs/Atomic/init-ostree-repo.log', show_cmd=True, stdout=True),
             mock.call(['rpm-ostree', 'compose', 'tree', '--repo=%s' % repo,
                       '--write-commitid-to=%s' % (self.topdir + '/logs/Atomic/commitid.log'),
                        '--add-metadata-string=version=24',
                        self.topdir + '/fedora-atomic-docker-host.json'],
                       logfile=self.topdir + '/logs/Atomic/create-ostree-repo.log', show_cmd=True, stdout=True)])

    @mock.patch('pungi.ostree.utils.datetime')
    @mock.patch('kobo.shortcuts.run')
    def test_extra_config_with_extra_repos(self, run, time):
        time.datetime.now.return_value = datetime.datetime(2016, 1, 1, 1, 1)
        timestamp = time.datetime.now().strftime("%Y%m%d%H%M%S")

        configdir = os.path.join(self.topdir, 'config')
        self._make_dummy_config_dir(configdir)
        treefile = os.path.join(configdir, 'fedora-atomic-docker-host.json')

        repo = os.path.join(self.topdir, 'atomic')

        extra_config_file = os.path.join(self.topdir, 'extra_config.json')
        extra_config = {
            "source_repo_from": "http://www.example.com/Server.repo",
            "extra_source_repos": [
                {
                    "name": "optional",
                    "baseurl": "http://example.com/repo/x86_64/optional",
                    "exclude": "systemd-container",
                    "gpgcheck": False
                },
                {
                    "name": "extra",
                    "baseurl": "http://example.com/repo/x86_64/extra",
                }
            ]
        }
        helpers.touch(extra_config_file, json.dumps(extra_config))

        ostree.main([
            'tree',
            '--repo=%s' % repo,
            '--log-dir=%s' % os.path.join(self.topdir, 'logs', 'Atomic'),
            '--treefile=%s' % treefile,
            '--extra-config=%s' % extra_config_file,
        ])

        source_repo_from_name = "source_repo_from-%s" % timestamp
        source_repo_from_repo = os.path.join(configdir, "%s.repo" % source_repo_from_name)
        self.assertTrue(os.path.isfile(source_repo_from_repo))
        with open(source_repo_from_repo, 'r') as f:
            content = f.read()
            self.assertIn("[%s]" % source_repo_from_name, content)
            self.assertIn("name=%s" % source_repo_from_name, content)
            self.assertIn("baseurl=http://www.example.com/Server.repo", content)
            self.assertIn("gpgcheck=0", content)

        optional_repo_name = "optional-%s" % timestamp
        optional_repo = os.path.join(configdir, "%s.repo" % optional_repo_name)
        self.assertTrue(os.path.isfile(optional_repo))
        with open(optional_repo, 'r') as f:
            content = f.read()
            self.assertIn("[%s]" % optional_repo_name, content)
            self.assertIn("name=%s" % optional_repo_name, content)
            self.assertIn("baseurl=http://example.com/repo/x86_64/optional", content)
            self.assertIn("gpgcheck=0", content)

        extra_repo_name = "extra-%s" % timestamp
        extra_repo = os.path.join(configdir, "%s.repo" % extra_repo_name)
        self.assertTrue(os.path.isfile(extra_repo))
        with open(extra_repo, 'r') as f:
            content = f.read()
            self.assertIn("[%s]" % extra_repo_name, content)
            self.assertIn("name=%s" % extra_repo_name, content)
            self.assertIn("baseurl=http://example.com/repo/x86_64/extra", content)
            self.assertIn("gpgcheck=0", content)

        treeconf = json.load(open(treefile, 'r'))
        repos = treeconf['repos']
        self.assertEqual(len(repos), 3)
        for name in [source_repo_from_name, optional_repo_name, extra_repo_name]:
            self.assertIn(name, repos)

    @mock.patch('pungi.ostree.utils.datetime')
    @mock.patch('kobo.shortcuts.run')
    def test_extra_config_with_keep_original_sources(self, run, time):
        time.datetime.now.return_value = datetime.datetime(2016, 1, 1, 1, 1)
        timestamp = time.datetime.now().strftime("%Y%m%d%H%M%S")

        configdir = os.path.join(self.topdir, 'config')
        self._make_dummy_config_dir(configdir)
        treefile = os.path.join(configdir, 'fedora-atomic-docker-host.json')

        repo = os.path.join(self.topdir, 'atomic')

        extra_config_file = os.path.join(self.topdir, 'extra_config.json')
        extra_config = {
            "source_repo_from": "http://www.example.com/Server.repo",
            "extra_source_repos": [
                {
                    "name": "optional",
                    "baseurl": "http://example.com/repo/x86_64/optional",
                    "exclude": "systemd-container",
                    "gpgcheck": False
                },
                {
                    "name": "extra",
                    "baseurl": "http://example.com/repo/x86_64/extra",
                }
            ],
            "keep_original_sources": True
        }
        helpers.touch(extra_config_file, json.dumps(extra_config))

        ostree.main([
            'tree',
            '--repo=%s' % repo,
            '--log-dir=%s' % os.path.join(self.topdir, 'logs', 'Atomic'),
            '--treefile=%s' % treefile,
            '--extra-config=%s' % extra_config_file,
        ])

        source_repo_from_name = "source_repo_from-%s" % timestamp
        optional_repo_name = "optional-%s" % timestamp
        extra_repo_name = "extra-%s" % timestamp

        treeconf = json.load(open(treefile, 'r'))
        repos = treeconf['repos']
        self.assertEqual(len(repos), 6)
        for name in ['fedora-rawhide', 'fedora-24', 'fedora-23',
                     source_repo_from_name, optional_repo_name, extra_repo_name]:
            self.assertIn(name, repos)

if __name__ == '__main__':
    unittest.main()
