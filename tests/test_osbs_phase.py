#!/usr/bin/env python
# -*- coding: utf-8 -*-

try:
    import unittest2 as unittest
except ImportError:
    import unittest
import mock
import json

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tests import helpers
from pungi.phases import osbs


class OSBSPhaseTest(helpers.PungiTestCase):

    @mock.patch('pungi.phases.osbs.ThreadPool')
    def test_run(self, ThreadPool):
        cfg = mock.Mock()
        compose = helpers.DummyCompose(self.topdir, {
            'osbs': {'^Everything$': cfg}
        })

        pool = ThreadPool.return_value

        phase = osbs.OSBSPhase(compose)
        phase.run()

        self.assertEqual(len(pool.add.call_args_list), 1)
        self.assertEqual(pool.queue_put.call_args_list,
                         [mock.call((compose, compose.variants['Everything'], cfg))])

    @mock.patch('pungi.phases.osbs.ThreadPool')
    def test_skip_without_config(self, ThreadPool):
        compose = helpers.DummyCompose(self.topdir, {})
        compose.just_phases = None
        compose.skip_phases = []
        phase = osbs.OSBSPhase(compose)
        self.assertTrue(phase.skip())

    @mock.patch('pungi.phases.osbs.ThreadPool')
    def test_dump_metadata(self, ThreadPool):
        compose = helpers.DummyCompose(self.topdir, {
            'osbs': {'^Everything$': {}}
        })
        compose.just_phases = None
        compose.skip_phases = []
        compose.notifier = mock.Mock()
        phase = osbs.OSBSPhase(compose)
        phase.start()
        phase.stop()
        phase.pool.metadata = METADATA
        phase.dump_metadata()

        with open(self.topdir + '/compose/metadata/osbs.json') as f:
            data = json.load(f)
            self.assertEqual(data, METADATA)

    @mock.patch('pungi.phases.osbs.ThreadPool')
    def test_dump_metadata_after_skip(self, ThreadPool):
        compose = helpers.DummyCompose(self.topdir, {})
        compose.just_phases = None
        compose.skip_phases = []
        phase = osbs.OSBSPhase(compose)
        phase.start()
        phase.stop()
        phase.dump_metadata()

        self.assertFalse(os.path.isfile(self.topdir + '/compose/metadata/osbs.json'))


TASK_RESULT = {
    'koji_builds': ['54321'],
    'repositories': [
        'registry.example.com:8888/rcm/buildroot:f24-docker-candidate-20160617141632',
    ]
}

BUILD_INFO = {
    'completion_time': '2016-06-17 18:25:30',
    'completion_ts': 1466187930.0,
    'creation_event_id': 13227702,
    'creation_time': '2016-06-17 18:25:57.611172',
    'creation_ts': 1466187957.61117,
    'epoch': None,
    'extra': {'container_koji_task_id': '12345', 'image': {}},
    'id': 54321,
    'name': 'my-name',
    'nvr': 'my-name-1.0-1',
    'owner_id': 3436,
    'owner_name': 'osbs',
    'package_id': 50072,
    'package_name': 'my-name',
    'release': '1',
    'source': 'git://example.com/repo?#BEEFCAFE',
    'start_time': '2016-06-17 18:16:37',
    'start_ts': 1466187397.0,
    'state': 1,
    'task_id': None,
    'version': '1.0',
    'volume_id': 0,
    'volume_name': 'DEFAULT'
}

ARCHIVES = [
    {'build_id': 54321,
     'buildroot_id': 2955357,
     'checksum': 'a2922842dc80873ac782da048c54f6cc',
     'checksum_type': 0,
     'extra': {
         'docker': {
             'id': '408c4cd37a87a807bec65dd13b049a32fe090d2fa1a8e891f65e3e3e683996d7',
             'parent_id': '6c3a84d798dc449313787502060b6d5b4694d7527d64a7c99ba199e3b2df834e',
             'repositories': ['registry.example.com:8888/rcm/buildroot:1.0-1']},
         'image': {'arch': 'x86_64'}},
     'filename': 'docker-image-408c4cd37a87a807bec65dd13b049a32fe090d2fa1a8e891f65e3e3e683996d7.x86_64.tar.gz',
     'id': 1436049,
     'metadata_only': False,
     'size': 174038795,
     'type_description': 'Tar file',
     'type_extensions': 'tar tar.gz tar.bz2 tar.xz',
     'type_id': 4,
     'type_name': 'tar'}
]

METADATA = {
    'Server': {'x86_64': [{
        'name': 'my-name',
        'version': '1.0',
        'release': '1',
        'creation_time': BUILD_INFO['creation_time'],
        'filename': ARCHIVES[0]['filename'],
        'size': ARCHIVES[0]['size'],
        'docker': {
            'id': '408c4cd37a87a807bec65dd13b049a32fe090d2fa1a8e891f65e3e3e683996d7',
            'parent_id': '6c3a84d798dc449313787502060b6d5b4694d7527d64a7c99ba199e3b2df834e',
            'repositories': ['registry.example.com:8888/rcm/buildroot:1.0-1']},
        'image': {'arch': 'x86_64'},
        'checksum': ARCHIVES[0]['checksum'],
    }]}
}


class OSBSThreadTest(helpers.PungiTestCase):

    def setUp(self):
        super(OSBSThreadTest, self).setUp()
        self.pool = mock.Mock(metadata={})
        self.t = osbs.OSBSThread(self.pool)
        self.compose = helpers.DummyCompose(self.topdir, {
            'koji_profile': 'koji',
            'translate_paths': [
                (self.topdir, 'http://root'),
            ]
        })

    def _setupMock(self, KojiWrapper, resolve_git_url):
        resolve_git_url.return_value = 'git://example.com/repo?#BEEFCAFE'
        self.wrapper = KojiWrapper.return_value
        self.wrapper.koji_proxy.buildContainer.return_value = 12345
        self.wrapper.koji_proxy.getTaskResult.return_value = TASK_RESULT
        self.wrapper.koji_proxy.getBuild.return_value = BUILD_INFO
        self.wrapper.koji_proxy.listArchives.return_value = ARCHIVES
        self.wrapper.koji_proxy.getLatestBuilds.return_value = [mock.Mock(), mock.Mock()]
        self.wrapper.koji_proxy.getNextRelease.return_value = 3
        self.wrapper.watch_task.return_value = 0

    def _assertCorrectMetadata(self):
        self.maxDiff = None
        self.assertEqual(self.pool.metadata, METADATA)

    def _assertCorrectCalls(self, opts, setupCalls=None):
        setupCalls = setupCalls or []
        options = {'yum_repourls': ['http://root/work/global/tmp-Server/compose-rpms-1.repo']}
        options.update(opts)
        self.assertEqual(
            self.wrapper.mock_calls,
            [mock.call.login()] + setupCalls + [
                mock.call.koji_proxy.buildContainer(
                    'git://example.com/repo?#BEEFCAFE',
                    'f24-docker-candidate',
                    options,
                    priority=None),
                mock.call.watch_task(
                    12345, self.topdir + '/logs/global/osbs/Server-1-watch-task.log'),
                mock.call.koji_proxy.getTaskResult(12345),
                mock.call.koji_proxy.getBuild(54321),
                mock.call.koji_proxy.listArchives(54321)])

    def _assertRepoFile(self):
        with open(self.topdir + '/work/global/tmp-Server/compose-rpms-1.repo') as f:
            lines = f.read().split('\n')
            self.assertIn('baseurl=http://root/compose/Server/$baseurl/os', lines)

    @mock.patch('pungi.util.resolve_git_url')
    @mock.patch('pungi.phases.osbs.kojiwrapper.KojiWrapper')
    def test_minimal_run(self, KojiWrapper, resolve_git_url):
        cfg = {
            'url': 'git://example.com/repo?#HEAD',
            'target': 'f24-docker-candidate',
        }
        self._setupMock(KojiWrapper, resolve_git_url)

        self.t.process((self.compose, self.compose.variants['Server'], cfg), 1)

        self._assertCorrectCalls({})
        self._assertCorrectMetadata()

    @mock.patch('pungi.util.resolve_git_url')
    @mock.patch('pungi.phases.osbs.kojiwrapper.KojiWrapper')
    def test_run_failable(self, KojiWrapper, resolve_git_url):
        cfg = {
            'url': 'git://example.com/repo?#HEAD',
            'target': 'f24-docker-candidate',
            'failable': ['*']
        }
        self._setupMock(KojiWrapper, resolve_git_url)

        self.t.process((self.compose, self.compose.variants['Server'], cfg), 1)

        self._assertCorrectCalls({})
        self._assertCorrectMetadata()

    @mock.patch('pungi.util.resolve_git_url')
    @mock.patch('pungi.phases.osbs.kojiwrapper.KojiWrapper')
    def test_run_with_more_args(self, KojiWrapper, resolve_git_url):
        cfg = {
            'url': 'git://example.com/repo?#HEAD',
            'target': 'f24-docker-candidate',
            'name': 'my-name',
            'version': '1.0',
        }
        self._setupMock(KojiWrapper, resolve_git_url)

        self.t.process((self.compose, self.compose.variants['Server'], cfg), 1)

        self._assertCorrectCalls({'name': 'my-name', 'version': '1.0'})
        self._assertCorrectMetadata()

    @mock.patch('pungi.util.resolve_git_url')
    @mock.patch('pungi.phases.osbs.kojiwrapper.KojiWrapper')
    def test_run_with_extra_repos(self, KojiWrapper, resolve_git_url):
        cfg = {
            'url': 'git://example.com/repo?#HEAD',
            'target': 'f24-docker-candidate',
            'name': 'my-name',
            'version': '1.0',
            'repo': 'http://pkgs.example.com/my.repo',
            'repo_from': 'Everything',
        }
        self._setupMock(KojiWrapper, resolve_git_url)

        self.t.process((self.compose, self.compose.variants['Server'], cfg), 1)

        options = {
            'name': 'my-name',
            'version': '1.0',
            'yum_repourls': [
                'http://root/work/global/tmp-Server/compose-rpms-1.repo',
                'http://root/work/global/tmp-Everything/compose-rpms-1.repo',
                'http://pkgs.example.com/my.repo',
            ]
        }
        self._assertCorrectCalls(options)
        self._assertCorrectMetadata()

    @mock.patch('pungi.util.resolve_git_url')
    @mock.patch('pungi.phases.osbs.kojiwrapper.KojiWrapper')
    def test_run_with_extra_repos_in_list(self, KojiWrapper, resolve_git_url):
        cfg = {
            'url': 'git://example.com/repo?#HEAD',
            'target': 'f24-docker-candidate',
            'name': 'my-name',
            'version': '1.0',
            'repo': ['http://pkgs.example.com/my.repo'],
            'repo_from': ['Everything', 'Client'],
        }
        self._setupMock(KojiWrapper, resolve_git_url)

        self.t.process((self.compose, self.compose.variants['Server'], cfg), 1)

        options = {
            'name': 'my-name',
            'version': '1.0',
            'yum_repourls': [
                'http://root/work/global/tmp-Server/compose-rpms-1.repo',
                'http://root/work/global/tmp-Everything/compose-rpms-1.repo',
                'http://root/work/global/tmp-Client/compose-rpms-1.repo',
                'http://pkgs.example.com/my.repo',
            ]
        }
        self._assertCorrectCalls(options)
        self._assertCorrectMetadata()

    @mock.patch('pungi.util.resolve_git_url')
    @mock.patch('pungi.phases.osbs.kojiwrapper.KojiWrapper')
    def test_run_with_extra_repos_missing_variant(self, KojiWrapper, resolve_git_url):
        cfg = {
            'url': 'git://example.com/repo?#HEAD',
            'target': 'f24-docker-candidate',
            'name': 'my-name',
            'version': '1.0',
            'repo_from': 'Gold',
        }
        self._setupMock(KojiWrapper, resolve_git_url)

        with self.assertRaises(RuntimeError) as ctx:
            self.t.process((self.compose, self.compose.variants['Server'], cfg), 1)

        self.assertIn('no variant Gold', str(ctx.exception))

    @mock.patch('pungi.util.resolve_git_url')
    @mock.patch('pungi.phases.osbs.kojiwrapper.KojiWrapper')
    def test_run_with_missing_url(self, KojiWrapper, resolve_git_url):
        cfg = {
            'target': 'f24-docker-candidate',
            'name': 'my-name',
        }
        self._setupMock(KojiWrapper, resolve_git_url)

        with self.assertRaises(RuntimeError) as ctx:
            self.t.process((self.compose, self.compose.variants['Server'], cfg), 1)

        self.assertIn("missing config key 'url' for Server", str(ctx.exception))

    @mock.patch('pungi.util.resolve_git_url')
    @mock.patch('pungi.phases.osbs.kojiwrapper.KojiWrapper')
    def test_run_with_missing_target(self, KojiWrapper, resolve_git_url):
        cfg = {
            'url': 'git://example.com/repo?#HEAD',
            'name': 'my-name',
        }
        self._setupMock(KojiWrapper, resolve_git_url)

        with self.assertRaises(RuntimeError) as ctx:
            self.t.process((self.compose, self.compose.variants['Server'], cfg), 1)

        self.assertIn("missing config key 'target' for Server", str(ctx.exception))

    @mock.patch('pungi.util.resolve_git_url')
    @mock.patch('pungi.phases.osbs.kojiwrapper.KojiWrapper')
    def test_failing_task(self, KojiWrapper, resolve_git_url):
        cfg = {
            'url': 'git://example.com/repo?#HEAD',
            'target': 'fedora-24-docker-candidate',
        }
        self._setupMock(KojiWrapper, resolve_git_url)
        self.wrapper.watch_task.return_value = 1

        with self.assertRaises(RuntimeError) as ctx:
            self.t.process((self.compose, self.compose.variants['Server'], cfg), 1)

        self.assertRegexpMatches(str(ctx.exception), r"task 12345 failed: see .+ for details")

    @mock.patch('pungi.util.resolve_git_url')
    @mock.patch('pungi.phases.osbs.kojiwrapper.KojiWrapper')
    def test_failing_task_with_failable(self, KojiWrapper, resolve_git_url):
        cfg = {
            'url': 'git://example.com/repo?#HEAD',
            'target': 'fedora-24-docker-candidate',
            'failable': ['*']
        }
        self._setupMock(KojiWrapper, resolve_git_url)
        self.wrapper.watch_task.return_value = 1

        self.t.process((self.compose, self.compose.variants['Server'], cfg), 1)

    @mock.patch('pungi.util.resolve_git_url')
    @mock.patch('pungi.phases.osbs.kojiwrapper.KojiWrapper')
    def test_scratch_has_no_metadata(self, KojiWrapper, resolve_git_url):
        cfg = {
            'url': 'git://example.com/repo?#HEAD',
            'target': 'fedora-24-docker-candidate',
            'scratch': True,
        }
        self._setupMock(KojiWrapper, resolve_git_url)

        self.t.process((self.compose, self.compose.variants['Server'], cfg), 1)

        self.assertEqual(self.pool.metadata, {})


if __name__ == '__main__':
    unittest.main()
