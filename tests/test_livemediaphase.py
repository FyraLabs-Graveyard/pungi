#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import unittest
import mock

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi.phases.livemedia_phase import LiveMediaPhase, LiveMediaThread
from pungi.util import get_arch_variant_data


class _DummyCompose(object):
    def __init__(self, config):
        self.compose_date = '20151203'
        self.compose_type_suffix = '.t'
        self.compose_respin = 0
        self.ci_base = mock.Mock(
            release_id='Test-1.0',
            release=mock.Mock(
                short='test',
                version='1.0',
            ),
        )
        self.conf = config
        self.paths = mock.Mock(
            compose=mock.Mock(
                topdir=mock.Mock(return_value='/a/b'),
                os_tree=mock.Mock(
                    side_effect=lambda arch, variant, create_dir=False: os.path.join('/ostree', arch, variant.uid)
                ),
                repository=mock.Mock(
                    side_effect=lambda arch, variant, create_dir=False: os.path.join('/repo', arch, variant.uid)
                ),
                image_dir=mock.Mock(
                    side_effect=lambda variant, relative=False: os.path.join(
                        '' if relative else '/', 'image_dir', variant.uid, '%(arch)s'
                    )
                )
            ),
            work=mock.Mock(
                image_build_conf=mock.Mock(
                    side_effect=lambda variant, image_name, image_type:
                        '-'.join([variant.uid, image_name, image_type])
                )
            ),
            log=mock.Mock(
                log_file=mock.Mock(return_value='/a/b/log/log_file')
            )
        )
        self._logger = mock.Mock()
        self.variants = {
            'Server': mock.Mock(uid='Server', arches=['x86_64', 'amd64']),
            'Client': mock.Mock(uid='Client', arches=['amd64']),
            'Everything': mock.Mock(uid='Everything', arches=['x86_64', 'amd64']),
        }
        self.im = mock.Mock()
        self.log_error = mock.Mock()

    def get_variants(self, arch=None, types=None):
        return [v for v in self.variants.values() if not arch or arch in v.arches]

    def can_fail(self, variant, arch, deliverable):
        failable = get_arch_variant_data(self.conf, 'failable_deliverables', arch, variant)
        return deliverable in failable


class TestLiveMediaPhase(unittest.TestCase):
    @mock.patch('pungi.phases.livemedia_phase.ThreadPool')
    def test_live_media_minimal(self, ThreadPool):
        compose = _DummyCompose({
            'live_media': {
                '^Server$': [
                    {
                        'target': 'f24',
                        'kickstart': 'file.ks',
                        'ksurl': 'git://example.com/repo.git',
                        'name': 'Fedora Server Live',
                        'version': 'Rawhide',
                    }
                ]
            },
            'koji_profile': 'koji',
        })

        phase = LiveMediaPhase(compose)

        phase.run()
        self.assertTrue(phase.pool.add.called)
        self.assertEqual(phase.pool.queue_put.call_args_list,
                         [mock.call((compose,
                                     compose.variants['Server'],
                                     {
                                         'arches': ['amd64', 'x86_64'],
                                         'kickstart': 'file.ks',
                                         'ksurl': 'git://example.com/repo.git',
                                         'ksversion': None,
                                         'name': 'Fedora Server Live',
                                         'release': None,
                                         'repo': ['/repo/$arch/Server'],
                                         'scratch': False,
                                         'skip_tag': None,
                                         'target': 'f24',
                                         'title': None,
                                         'install_tree': '/ostree/$arch/Server',
                                         'version': 'Rawhide',
                                     }))])

    @mock.patch('pungi.phases.livemedia_phase.resolve_git_url')
    @mock.patch('pungi.phases.livemedia_phase.ThreadPool')
    def test_live_media_full(self, ThreadPool, resolve_git_url):
        compose = _DummyCompose({
            'live_media': {
                '^Server$': [
                    {
                        'target': 'f24',
                        'kickstart': 'file.ks',
                        'ksurl': 'git://example.com/repo.git#HEAD',
                        'name': 'Fedora Server Live',
                        'scratch': True,
                        'skip_tag': True,
                        'title': 'Custom Title',
                        'repo_from': ['Everything'],
                        'repo': ['http://example.com/extra_repo'],
                        'arches': ['x86_64'],
                        'ksversion': '24',
                        'release': None,
                        'version': 'Rawhide',
                    }
                ]
            }
        })

        resolve_git_url.return_value = 'resolved'

        phase = LiveMediaPhase(compose)

        phase.run()
        self.assertTrue(phase.pool.add.called)
        self.assertEqual(phase.pool.queue_put.call_args_list,
                         [mock.call((compose,
                                     compose.variants['Server'],
                                     {
                                         'arches': ['x86_64'],
                                         'kickstart': 'file.ks',
                                         'ksurl': 'resolved',
                                         'ksversion': '24',
                                         'name': 'Fedora Server Live',
                                         'release': '20151203.0',
                                         'repo': ['http://example.com/extra_repo',
                                                  '/repo/$arch/Everything',
                                                  '/repo/$arch/Server'],
                                         'scratch': True,
                                         'skip_tag': True,
                                         'target': 'f24',
                                         'title': 'Custom Title',
                                         'install_tree': '/ostree/$arch/Server',
                                         'version': 'Rawhide',
                                     }))])


class TestCreateImageBuildThread(unittest.TestCase):

    @mock.patch('pungi.phases.livemedia_phase.KojiWrapper')
    @mock.patch('pungi.phases.livemedia_phase.Linker')
    @mock.patch('pungi.phases.livemedia_phase.makedirs')
    def test_process(self, makedirs, Linker, KojiWrapper):
        compose = _DummyCompose({
            'koji_profile': 'koji'
        })
        config = {
            'arches': ['amd64', 'x86_64'],
            'kickstart': 'file.ks',
            'ksurl': 'git://example.com/repo.git',
            'ksversion': None,
            'name': 'Fedora Server Live',
            'release': None,
            'repo': ['/repo/$arch/Server'],
            'scratch': False,
            'skip_tag': None,
            'target': 'f24',
            'title': None,
            'version': 'Rawhide',
        }
        pool = mock.Mock()

        get_live_media_cmd = KojiWrapper.return_value.get_live_media_cmd
        get_live_media_cmd.return_value = 'koji-spin-livemedia'

        run_blocking_cmd = KojiWrapper.return_value.run_blocking_cmd
        run_blocking_cmd.return_value = {
            'task_id': 1234,
            'retcode': 0,
            'output': None,
        }

        get_image_paths = KojiWrapper.return_value.get_image_paths
        get_image_paths.return_value = {
            'x86_64': [
                '/koji/task/1235/tdl-amd64.xml',
                '/koji/task/1235/Live-20160103.x86_64.iso',
                '/koji/task/1235/Live-20160103.x86_64.tar.xz'
            ],
            'amd64': [
                '/koji/task/1235/tdl-amd64.xml',
                '/koji/task/1235/Live-20160103.amd64.iso',
                '/koji/task/1235/Live-20160103.amd64.tar.xz'
            ]
        }

        t = LiveMediaThread(pool)
        with mock.patch('os.stat') as stat:
            with mock.patch('os.path.getsize') as getsize:
                with mock.patch('time.sleep'):
                    getsize.return_value = 1024
                    stat.return_value.st_mtime = 13579
                    t.process((compose, compose.variants['Server'], config), 1)

        self.assertEqual(run_blocking_cmd.mock_calls,
                         [mock.call('koji-spin-livemedia', log_file='/a/b/log/log_file')])
        self.assertEqual(get_live_media_cmd.mock_calls,
                         [mock.call(config)])
        self.assertEqual(get_image_paths.mock_calls,
                         [mock.call(1234)])
        self.assertItemsEqual(makedirs.mock_calls,
                              [mock.call('/image_dir/Server/x86_64'),
                               mock.call('/image_dir/Server/amd64')])
        link = Linker.return_value.link
        self.assertItemsEqual(link.mock_calls,
                              [mock.call('/koji/task/1235/Live-20160103.amd64.iso',
                                         '/image_dir/Server/amd64/Live-20160103.amd64.iso',
                                         link_type='hardlink-or-copy'),
                               mock.call('/koji/task/1235/Live-20160103.x86_64.iso',
                                         '/image_dir/Server/x86_64/Live-20160103.x86_64.iso',
                                         link_type='hardlink-or-copy')])

        image_relative_paths = [
            'image_dir/Server/amd64/Live-20160103.amd64.iso',
            'image_dir/Server/x86_64/Live-20160103.x86_64.iso'
        ]

        self.assertEqual(len(compose.im.add.call_args_list), 2)
        for call in compose.im.add.call_args_list:
            _, kwargs = call
            image = kwargs['image']
            self.assertEqual(kwargs['variant'], 'Server')
            self.assertIn(kwargs['arch'], ('amd64', 'x86_64'))
            self.assertEqual(kwargs['arch'], image.arch)
            self.assertIn(image.path, image_relative_paths)
            self.assertEqual('iso', image.format)
            self.assertEqual('live', image.type)

    @mock.patch('pungi.phases.livemedia_phase.KojiWrapper')
    def test_handle_koji_fail(self, KojiWrapper):
        compose = _DummyCompose({
            'koji_profile': 'koji',
            'failable_deliverables': [
                ('^.+$', {'*': ['live-media']})
            ]
        })
        config = {
            'arches': ['amd64', 'x86_64'],
            'kickstart': 'file.ks',
            'ksurl': 'git://example.com/repo.git',
            'ksversion': None,
            'name': 'Fedora Server Live',
            'release': None,
            'repo': ['/repo/$arch/Server'],
            'scratch': False,
            'skip_tag': None,
            'target': 'f24',
            'title': None,
            'version': 'Rawhide',
        }
        pool = mock.Mock()

        run_blocking_cmd = KojiWrapper.return_value.run_blocking_cmd
        run_blocking_cmd.return_value = {
            'task_id': 1234,
            'retcode': 1,
            'output': None,
        }

        t = LiveMediaThread(pool)
        with mock.patch('os.stat') as stat:
            with mock.patch('os.path.getsize') as getsize:
                with mock.patch('time.sleep'):
                    getsize.return_value = 1024
                    stat.return_value.st_mtime = 13579
                    t.process((compose, compose.variants['Server'], config), 1)

    @mock.patch('pungi.phases.livemedia_phase.KojiWrapper')
    def test_handle_exception(self, KojiWrapper):
        compose = _DummyCompose({
            'koji_profile': 'koji',
            'failable_deliverables': [
                ('^.+$', {'*': ['live-media']})
            ]
        })
        config = {
            'arches': ['amd64', 'x86_64'],
            'kickstart': 'file.ks',
            'ksurl': 'git://example.com/repo.git',
            'ksversion': None,
            'name': 'Fedora Server Live',
            'release': None,
            'repo': ['/repo/$arch/Server'],
            'scratch': False,
            'skip_tag': None,
            'target': 'f24',
            'title': None,
            'version': 'Rawhide',
        }
        pool = mock.Mock()

        def boom(*args, **kwargs):
            raise Exception('BOOM')

        run_blocking_cmd = KojiWrapper.return_value.run_blocking_cmd
        run_blocking_cmd.side_effect = boom

        t = LiveMediaThread(pool)
        with mock.patch('os.stat') as stat:
            with mock.patch('os.path.getsize') as getsize:
                with mock.patch('time.sleep'):
                    getsize.return_value = 1024
                    stat.return_value.st_mtime = 13579
                    t.process((compose, compose.variants['Server'], config), 1)


if __name__ == "__main__":
    unittest.main()
