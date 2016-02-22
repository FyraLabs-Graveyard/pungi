#!/usr/bin/env python2
# -*- coding: utf-8 -*-


import unittest
import mock

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi.phases.live_images import LiveImagesPhase, CreateLiveImageThread
from pungi.util import get_arch_variant_data


class _DummyCompose(object):
    def __init__(self, config):
        self.compose_id = 'Test-20151203.0.t'
        self.compose_date = '20151203'
        self.compose_respin = '0'
        self.conf = config
        self.paths = mock.Mock(
            compose=mock.Mock(
                topdir=mock.Mock(return_value='/top'),
                repository=mock.Mock(
                    side_effect=lambda arch, variant, create_dir=False: os.path.join('/repo', arch, variant.uid)
                ),
                iso_dir=mock.Mock(
                    side_effect=lambda arch, variant, symlink_to: os.path.join(
                        '/top/iso_dir', arch, variant.uid
                    )
                ),
                image_dir=mock.Mock(
                    side_effect=lambda variant, symlink_to: os.path.join(
                        '/top/image_dir/%(arch)s', variant.uid
                    )
                ),
            ),
            log=mock.Mock(
                log_file=mock.Mock(return_value='/a/b/log/log_file')
            )
        )
        self._logger = mock.Mock()
        self.variants = {
            'Server': mock.Mock(uid='Server', arches=['x86_64', 'amd64'], is_empty=False),
            'Client': mock.Mock(uid='Client', arches=['amd64'], is_empty=False),
            'Everything': mock.Mock(uid='Everything', arches=['x86_64', 'amd64'], is_empty=False),
        }
        self.log_error = mock.Mock()
        self.get_image_name = mock.Mock(return_value='image-name')
        self.im = mock.Mock()

    def get_arches(self):
        return ['x86_64', 'amd64']

    def get_variants(self, arch=None, types=None):
        return [v for v in self.variants.values() if not arch or arch in v.arches]

    def can_fail(self, variant, arch, deliverable):
        failable = get_arch_variant_data(self.conf, 'failable_deliverables', arch, variant)
        return deliverable in failable


class TestLiveImagesPhase(unittest.TestCase):

    @mock.patch('pungi.phases.live_images.ThreadPool')
    def test_live_image_build(self, ThreadPool):
        compose = _DummyCompose({
            'live_images': [
                ('^Client$', {
                    'amd64': {
                        'kickstart': 'test.ks',
                        'additional_repos': ['http://example.com/repo/'],
                        'repo_from': ['Everything'],
                        'release': None,
                    }
                })
            ],
        })

        phase = LiveImagesPhase(compose)

        phase.run()

        # assert at least one thread was started
        self.assertTrue(phase.pool.add.called)
        self.maxDiff = None
        self.assertItemsEqual(phase.pool.queue_put.mock_calls,
                              [mock.call((compose,
                                          {'ks_file': 'test.ks',
                                           'build_arch': 'amd64',
                                           'dest_dir': '/top/iso_dir/amd64/Client',
                                           'scratch': False,
                                           'repos': ['/repo/amd64/Client',
                                                     'http://example.com/repo/',
                                                     '/repo/amd64/Everything'],
                                           'label': '',
                                           'name': None,
                                           'filename': 'image-name',
                                           'version': None,
                                           'specfile': None,
                                           'sign': False,
                                           'type': 'live',
                                           'release': '20151203.0',
                                           'ksurl': None},
                                          compose.variants['Client'],
                                          'amd64'))])

    @mock.patch('pungi.phases.live_images.ThreadPool')
    def test_live_image_build_without_rename(self, ThreadPool):
        compose = _DummyCompose({
            'live_images_no_rename': True,
            'live_images': [
                ('^Client$', {
                    'amd64': {
                        'kickstart': 'test.ks',
                        'additional_repos': ['http://example.com/repo/'],
                        'repo_from': ['Everything'],
                        'release': None,
                    }
                })
            ],
        })

        phase = LiveImagesPhase(compose)

        phase.run()

        # assert at least one thread was started
        self.assertTrue(phase.pool.add.called)
        self.maxDiff = None
        self.assertItemsEqual(phase.pool.queue_put.mock_calls,
                              [mock.call((compose,
                                          {'ks_file': 'test.ks',
                                           'build_arch': 'amd64',
                                           'dest_dir': '/top/iso_dir/amd64/Client',
                                           'scratch': False,
                                           'repos': ['/repo/amd64/Client',
                                                     'http://example.com/repo/',
                                                     '/repo/amd64/Everything'],
                                           'label': '',
                                           'name': None,
                                           'filename': None,
                                           'version': None,
                                           'specfile': None,
                                           'sign': False,
                                           'type': 'live',
                                           'release': '20151203.0',
                                           'ksurl': None},
                                          compose.variants['Client'],
                                          'amd64'))])

    @mock.patch('pungi.phases.live_images.ThreadPool')
    def test_live_image_build_two_images(self, ThreadPool):
        compose = _DummyCompose({
            'live_images': [
                ('^Client$', {
                    'amd64': [{
                        'kickstart': 'test.ks',
                        'additional_repos': ['http://example.com/repo/'],
                        'repo_from': ['Everything'],
                    }, {
                        'kickstart': 'another.ks',
                        'additional_repos': ['http://example.com/repo/'],
                        'repo_from': ['Everything'],
                    }]
                })
            ],
        })

        phase = LiveImagesPhase(compose)

        phase.run()

        # assert at least one thread was started
        self.assertTrue(phase.pool.add.called)
        self.maxDiff = None
        self.assertItemsEqual(phase.pool.queue_put.mock_calls,
                              [mock.call((compose,
                                          {'ks_file': 'test.ks',
                                           'build_arch': 'amd64',
                                           'dest_dir': '/top/iso_dir/amd64/Client',
                                           'scratch': False,
                                           'repos': ['/repo/amd64/Client',
                                                     'http://example.com/repo/',
                                                     '/repo/amd64/Everything'],
                                           'label': '',
                                           'name': None,
                                           'filename': 'image-name',
                                           'version': None,
                                           'specfile': None,
                                           'sign': False,
                                           'type': 'live',
                                           'release': None,
                                           'ksurl': None},
                                          compose.variants['Client'],
                                          'amd64')),
                               mock.call((compose,
                                          {'ks_file': 'another.ks',
                                           'build_arch': 'amd64',
                                           'dest_dir': '/top/iso_dir/amd64/Client',
                                           'scratch': False,
                                           'repos': ['/repo/amd64/Client',
                                                     'http://example.com/repo/',
                                                     '/repo/amd64/Everything'],
                                           'label': '',
                                           'name': None,
                                           'filename': 'image-name',
                                           'version': None,
                                           'specfile': None,
                                           'sign': False,
                                           'type': 'live',
                                           'release': None,
                                           'ksurl': None},
                                          compose.variants['Client'],
                                          'amd64'))])

    @mock.patch('pungi.phases.live_images.ThreadPool')
    @mock.patch('pungi.phases.live_images.resolve_git_url')
    def test_spin_appliance(self, resolve_git_url, ThreadPool):
        compose = _DummyCompose({
            'live_images': [
                ('^Client$', {
                    'amd64': {
                        'kickstart': 'test.ks',
                        'ksurl': 'https://git.example.com/kickstarts.git?#HEAD',
                        'additional_repos': ['http://example.com/repo/'],
                        'repo_from': ['Everything'],
                        'type': 'appliance',
                    }
                })
            ],
        })

        resolve_git_url.return_value = 'https://git.example.com/kickstarts.git?#CAFEBABE'

        phase = LiveImagesPhase(compose)

        phase.run()

        # assert at least one thread was started
        self.assertTrue(phase.pool.add.called)
        self.maxDiff = None
        self.assertItemsEqual(phase.pool.queue_put.mock_calls,
                              [mock.call((compose,
                                          {'ks_file': 'test.ks',
                                           'build_arch': 'amd64',
                                           'dest_dir': '/top/image_dir/amd64/Client',
                                           'scratch': False,
                                           'repos': ['/repo/amd64/Client',
                                                     'http://example.com/repo/',
                                                     '/repo/amd64/Everything'],
                                           'label': '',
                                           'name': None,
                                           'filename': 'image-name',
                                           'version': None,
                                           'specfile': None,
                                           'sign': False,
                                           'type': 'appliance',
                                           'release': None,
                                           'ksurl': 'https://git.example.com/kickstarts.git?#CAFEBABE'},
                                          compose.variants['Client'],
                                          'amd64'))])
        self.assertEqual(resolve_git_url.mock_calls,
                         [mock.call('https://git.example.com/kickstarts.git?#HEAD')])


class TestCreateLiveImageThread(unittest.TestCase):

    @mock.patch('pungi.phases.live_images.Image')
    @mock.patch('shutil.copy2')
    @mock.patch('pungi.phases.live_images.run')
    @mock.patch('pungi.phases.live_images.KojiWrapper')
    def test_process(self, KojiWrapper, run, copy2, Image):
        compose = _DummyCompose({'koji_profile': 'koji'})
        pool = mock.Mock()
        cmd = {
            'ks_file': '/path/to/ks_file',
            'build_arch': 'amd64',
            'dest_dir': '/top/iso_dir/amd64/Client',
            'scratch': False,
            'repos': ['/repo/amd64/Client',
                      'http://example.com/repo/',
                      '/repo/amd64/Everything'],
            'label': '',
            'name': None,
            'filename': 'image-name',
            'version': None,
            'specfile': None,
            'type': 'live',
            'ksurl': 'https://git.example.com/kickstarts.git?#CAFEBABE',
            'release': None,
        }

        koji_wrapper = KojiWrapper.return_value
        koji_wrapper.get_create_image_cmd.return_value = 'koji spin-livecd ...'
        koji_wrapper.run_blocking_cmd.return_value = {
            'retcode': 0,
            'output': 'some output',
            'task_id': 123
        }
        koji_wrapper.get_image_path.return_value = ['/path/to/image.iso']

        t = CreateLiveImageThread(pool)
        with mock.patch('os.stat') as stat:
            with mock.patch('os.path.getsize') as getsize:
                with mock.patch('time.sleep'):
                    getsize.return_value = 1024
                    stat.return_value.st_mtime = 13579
                    t.process((compose, cmd, compose.variants['Client'], 'amd64'), 1)

        self.assertEqual(koji_wrapper.run_blocking_cmd.mock_calls,
                         [mock.call('koji spin-livecd ...', log_file='/a/b/log/log_file')])
        self.assertEqual(koji_wrapper.get_image_path.mock_calls, [mock.call(123)])
        self.assertEqual(copy2.mock_calls,
                         [mock.call('/path/to/image.iso', '/top/iso_dir/amd64/Client/image-name')])

        write_manifest_cmd = ' && '.join([
            'cd /top/iso_dir/amd64/Client',
            'isoinfo -R -f -i image-name | grep -v \'/TRANS.TBL$\' | sort >> image-name.manifest'
        ])
        self.assertEqual(run.mock_calls, [mock.call(write_manifest_cmd)])
        self.assertEqual(koji_wrapper.get_create_image_cmd.mock_calls,
                         [mock.call('Test', '20151203.0.t', 'rhel-7.0-candidate',
                                    'amd64', '/path/to/ks_file',
                                    ['/repo/amd64/Client',
                                     'http://example.com/repo/',
                                     '/repo/amd64/Everything'],
                                    image_type='live',
                                    archive=False,
                                    specfile=None,
                                    wait=True,
                                    release=None,
                                    ksurl='https://git.example.com/kickstarts.git?#CAFEBABE')])
        self.assertEqual(Image.return_value.type, 'live')
        self.assertEqual(Image.return_value.format, 'iso')
        self.assertEqual(Image.return_value.path, 'iso_dir/amd64/Client/image-name')
        self.assertEqual(Image.return_value.size, 1024)
        self.assertEqual(Image.return_value.mtime, 13579)
        self.assertEqual(Image.return_value.arch, 'amd64')
        self.assertEqual(Image.return_value.disc_number, 1)
        self.assertEqual(Image.return_value.disc_count, 1)
        self.assertTrue(Image.return_value.bootable)
        self.assertEqual(compose.im.add.mock_calls,
                         [mock.call(variant='Client', arch='amd64', image=Image.return_value)])

    @mock.patch('pungi.phases.live_images.Image')
    @mock.patch('shutil.copy2')
    @mock.patch('pungi.phases.live_images.run')
    @mock.patch('pungi.phases.live_images.KojiWrapper')
    def test_process_no_rename(self, KojiWrapper, run, copy2, Image):
        compose = _DummyCompose({'koji_profile': 'koji'})
        pool = mock.Mock()
        cmd = {
            'ks_file': '/path/to/ks_file',
            'build_arch': 'amd64',
            'dest_dir': '/top/iso_dir/amd64/Client',
            'scratch': False,
            'repos': ['/repo/amd64/Client',
                      'http://example.com/repo/',
                      '/repo/amd64/Everything'],
            'label': '',
            'name': None,
            'filename': None,
            'version': None,
            'specfile': None,
            'type': 'live',
            'ksurl': 'https://git.example.com/kickstarts.git?#CAFEBABE',
            'release': None,
        }

        koji_wrapper = KojiWrapper.return_value
        koji_wrapper.get_create_image_cmd.return_value = 'koji spin-livecd ...'
        koji_wrapper.run_blocking_cmd.return_value = {
            'retcode': 0,
            'output': 'some output',
            'task_id': 123
        }
        koji_wrapper.get_image_path.return_value = ['/path/to/image.iso']

        t = CreateLiveImageThread(pool)
        with mock.patch('os.stat') as stat:
            with mock.patch('os.path.getsize') as getsize:
                getsize.return_value = 1024
                getsize.return_value = 1024
                getsize.return_value = 1024
                getsize.return_value = 1024
                with mock.patch('time.sleep'):
                    getsize.return_value = 1024
                    stat.return_value.st_mtime = 13579
                    t.process((compose, cmd, compose.variants['Client'], 'amd64'), 1)

        self.assertEqual(koji_wrapper.run_blocking_cmd.mock_calls,
                         [mock.call('koji spin-livecd ...', log_file='/a/b/log/log_file')])
        self.assertEqual(koji_wrapper.get_image_path.mock_calls, [mock.call(123)])
        self.assertEqual(copy2.mock_calls,
                         [mock.call('/path/to/image.iso', '/top/iso_dir/amd64/Client/image.iso')])

        write_manifest_cmd = ' && '.join([
            'cd /top/iso_dir/amd64/Client',
            'isoinfo -R -f -i image.iso | grep -v \'/TRANS.TBL$\' | sort >> image.iso.manifest'
        ])
        self.assertEqual(run.mock_calls, [mock.call(write_manifest_cmd)])
        self.assertEqual(koji_wrapper.get_create_image_cmd.mock_calls,
                         [mock.call('Test', '20151203.0.t', 'rhel-7.0-candidate',
                                    'amd64', '/path/to/ks_file',
                                    ['/repo/amd64/Client',
                                     'http://example.com/repo/',
                                     '/repo/amd64/Everything'],
                                    image_type='live',
                                    archive=False,
                                    specfile=None,
                                    wait=True,
                                    release=None,
                                    ksurl='https://git.example.com/kickstarts.git?#CAFEBABE')])

        self.assertEqual(Image.return_value.type, 'live')
        self.assertEqual(Image.return_value.format, 'iso')
        self.assertEqual(Image.return_value.path, 'iso_dir/amd64/Client/image.iso')
        self.assertEqual(Image.return_value.size, 1024)
        self.assertEqual(Image.return_value.mtime, 13579)
        self.assertEqual(Image.return_value.arch, 'amd64')
        self.assertEqual(Image.return_value.disc_number, 1)
        self.assertEqual(Image.return_value.disc_count, 1)
        self.assertTrue(Image.return_value.bootable)
        self.assertEqual(compose.im.add.mock_calls,
                         [mock.call(variant='Client', arch='amd64', image=Image.return_value)])

    @mock.patch('pungi.phases.live_images.Image')
    @mock.patch('shutil.copy2')
    @mock.patch('pungi.phases.live_images.run')
    @mock.patch('pungi.phases.live_images.KojiWrapper')
    def test_process_applicance(self, KojiWrapper, run, copy2, Image):
        compose = _DummyCompose({'koji_profile': 'koji'})
        pool = mock.Mock()
        cmd = {
            'ks_file': '/path/to/ks_file',
            'build_arch': 'amd64',
            'dest_dir': '/top/iso_dir/amd64/Client',
            'scratch': False,
            'repos': ['/repo/amd64/Client',
                      'http://example.com/repo/',
                      '/repo/amd64/Everything'],
            'label': '',
            'name': None,
            'filename': 'image-name',
            'version': None,
            'specfile': None,
            'type': 'appliance',
            'ksurl': None,
            'release': None,
        }

        koji_wrapper = KojiWrapper.return_value
        koji_wrapper.get_create_image_cmd.return_value = 'koji spin-livecd ...'
        koji_wrapper.run_blocking_cmd.return_value = {
            'retcode': 0,
            'output': 'some output',
            'task_id': 123
        }
        koji_wrapper.get_image_path.return_value = ['/path/to/image.raw.xz']

        t = CreateLiveImageThread(pool)
        with mock.patch('os.stat') as stat:
            with mock.patch('os.path.getsize') as getsize:
                with mock.patch('time.sleep'):
                    getsize.return_value = 1024
                    stat.return_value.st_mtime = 13579
                    t.process((compose, cmd, compose.variants['Client'], 'amd64'), 1)

        self.assertEqual(koji_wrapper.run_blocking_cmd.mock_calls,
                         [mock.call('koji spin-livecd ...', log_file='/a/b/log/log_file')])
        self.assertEqual(koji_wrapper.get_image_path.mock_calls, [mock.call(123)])
        self.assertEqual(copy2.mock_calls,
                         [mock.call('/path/to/image.raw.xz', '/top/iso_dir/amd64/Client/image-name')])

        write_manifest_cmd = ' && '.join([
            'cd /top/iso_dir/amd64/Client',
            'isoinfo -R -f -i image-name | grep -v \'/TRANS.TBL$\' | sort >> image-name.manifest'
        ])
        self.assertEqual(run.mock_calls, [mock.call(write_manifest_cmd)])
        self.assertEqual(koji_wrapper.get_create_image_cmd.mock_calls,
                         [mock.call('Test', '20151203.0.t', 'rhel-7.0-candidate',
                                    'amd64', '/path/to/ks_file',
                                    ['/repo/amd64/Client',
                                     'http://example.com/repo/',
                                     '/repo/amd64/Everything'],
                                    image_type='appliance',
                                    archive=False,
                                    specfile=None,
                                    wait=True,
                                    release=None,
                                    ksurl=None)])

        self.assertEqual(Image.return_value.type, 'appliance')
        self.assertEqual(Image.return_value.format, 'raw.xz')
        self.assertEqual(Image.return_value.path, 'iso_dir/amd64/Client/image-name')
        self.assertEqual(Image.return_value.size, 1024)
        self.assertEqual(Image.return_value.mtime, 13579)
        self.assertEqual(Image.return_value.arch, 'amd64')
        self.assertEqual(Image.return_value.disc_number, 1)
        self.assertEqual(Image.return_value.disc_count, 1)
        self.assertTrue(Image.return_value.bootable)
        self.assertEqual(compose.im.add.mock_calls,
                         [mock.call(variant='Client', arch='amd64', image=Image.return_value)])

    @mock.patch('shutil.copy2')
    @mock.patch('pungi.phases.live_images.run')
    @mock.patch('pungi.phases.live_images.KojiWrapper')
    def test_process_handles_fail(self, KojiWrapper, run, copy2):
        compose = _DummyCompose({
            'koji_profile': 'koji',
            'failable_deliverables': [('^.+$', {'*': ['live']})],
        })
        pool = mock.Mock()
        cmd = {
            'ks_file': '/path/to/ks_file',
            'build_arch': 'amd64',
            'dest_dir': '/top/iso_dir/amd64/Client',
            'scratch': False,
            'repos': ['/repo/amd64/Client',
                      'http://example.com/repo/',
                      '/repo/amd64/Everything'],
            'label': '',
            'name': None,
            'filename': 'image-name',
            'version': None,
            'specfile': None,
            'ksurl': None,
        }

        koji_wrapper = KojiWrapper.return_value
        koji_wrapper.get_create_image_cmd.return_value = 'koji spin-livecd ...'
        koji_wrapper.run_blocking_cmd.return_value = {
            'retcode': 1,
            'output': 'some output',
            'task_id': 123
        }

        t = CreateLiveImageThread(pool)
        with mock.patch('time.sleep'):
            t.process((compose, cmd, compose.variants['Client'], 'amd64'), 1)

    @mock.patch('shutil.copy2')
    @mock.patch('pungi.phases.live_images.run')
    @mock.patch('pungi.phases.live_images.KojiWrapper')
    def test_process_handles_exception(self, KojiWrapper, run, copy2):
        compose = _DummyCompose({
            'koji_profile': 'koji',
            'failable_deliverables': [('^.+$', {'*': ['live']})],
        })
        pool = mock.Mock()
        cmd = {
            'ks_file': '/path/to/ks_file',
            'build_arch': 'amd64',
            'dest_dir': '/top/iso_dir/amd64/Client',
            'scratch': False,
            'repos': ['/repo/amd64/Client',
                      'http://example.com/repo/',
                      '/repo/amd64/Everything'],
            'label': '',
            'name': None,
            'filename': 'image-name',
            'version': None,
            'specfile': None,
            'ksurl': None,
        }

        def boom(*args, **kwargs):
            raise RuntimeError('BOOM')

        koji_wrapper = KojiWrapper.return_value
        koji_wrapper.get_create_image_cmd.side_effect = boom

        t = CreateLiveImageThread(pool)
        with mock.patch('time.sleep'):
            t.process((compose, cmd, compose.variants['Client'], 'amd64'), 1)


if __name__ == "__main__":
    unittest.main()
