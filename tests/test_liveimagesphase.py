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
        self.conf = config
        self.paths = mock.Mock(
            compose=mock.Mock(
                repository=mock.Mock(
                    side_effect=lambda arch, variant, create_dir=False: os.path.join('/repo', arch, variant.uid)
                ),
                iso_dir=mock.Mock(
                    side_effect=lambda arch, variant, symlink_to: os.path.join(
                        '/iso_dir', arch, variant.uid
                    )
                ),
                iso_path=mock.Mock(
                    side_effect=lambda arch, variant, filename, symlink_to: os.path.join(
                        '/iso_dir', arch, variant.uid, filename
                    )
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
        self.log_error = mock.Mock()
        self.get_image_name = mock.Mock(return_value='image-name')

    def get_arches(self):
        return ['x86_64', 'amd64']

    def get_variants(self, arch=None, types=None):
        return [v for v in self.variants.values() if not arch or arch in v.arches]

    def can_fail(self, variant, arch, deliverable):
        failable = get_arch_variant_data(self.conf, 'failable_deliverables', arch, variant)
        return deliverable in failable


class TestLiveImagesPhase(unittest.TestCase):

    @mock.patch('pungi.phases.live_images.ThreadPool')
    @mock.patch('pungi.phases.live_images.get_ks_in')
    @mock.patch('pungi.phases.live_images.tweak_ks')
    def test_image_build(self, tweak_ks, get_ks_in, ThreadPool):
        compose = _DummyCompose({
            'live_images': [
                ('^Client$', {
                    'amd64': {
                        'additional_repos': ['http://example.com/repo/'],
                        'repos_from': ['Everything'],
                    }
                })
            ],
        })

        get_ks_in.side_effect = (lambda compose, arch, variant:
                                 None if variant.uid != 'Client' or arch != 'amd64' else '/path/to/ks_in')
        tweak_ks.return_value = '/path/to/ks_file'

        phase = LiveImagesPhase(compose)

        phase.run()

        # assert at least one thread was started
        self.assertTrue(phase.pool.add.called)
        self.maxDiff = None
        self.assertItemsEqual(phase.pool.queue_put.mock_calls,
                              [mock.call((compose,
                                          {'ks_file': '/path/to/ks_file',
                                           'build_arch': 'amd64',
                                           'wrapped_rpms_path': '/iso_dir/amd64/Client',
                                           'scratch': False,
                                           'repos': ['/repo/amd64/Client',
                                                     'http://example.com/repo/',
                                                     '/repo/amd64/Everything'],
                                           'label': '',
                                           'name': None,
                                           'iso_path': '/iso_dir/amd64/Client/image-name',
                                           'version': None,
                                           'specfile': None},
                                          compose.variants['Client'],
                                          'amd64'))])


class TestCreateLiveImageThread(unittest.TestCase):

    @mock.patch('shutil.copy2')
    @mock.patch('pungi.phases.live_images.run')
    @mock.patch('pungi.phases.live_images.KojiWrapper')
    def test_process(self, KojiWrapper, run, copy2):
        compose = _DummyCompose({'koji_profile': 'koji'})
        pool = mock.Mock()
        cmd = {
            'ks_file': '/path/to/ks_file',
            'build_arch': 'amd64',
            'wrapped_rpms_path': '/iso_dir/amd64/Client',
            'scratch': False,
            'repos': ['/repo/amd64/Client',
                      'http://example.com/repo/',
                      '/repo/amd64/Everything'],
            'label': '',
            'name': None,
            'iso_path': '/iso_dir/amd64/Client/image-name',
            'version': None,
            'specfile': None
        }

        koji_wrapper = KojiWrapper.return_value
        koji_wrapper.get_create_image_cmd.return_value = 'koji spin-livecd ...'
        koji_wrapper.run_create_image_cmd.return_value = {
            'retcode': 0,
            'output': 'some output',
            'task_id': 123
        }
        koji_wrapper.get_image_path.return_value = ['/path/to/image']

        t = CreateLiveImageThread(pool)
        with mock.patch('time.sleep'):
            t.process((compose, cmd, compose.variants['Client'], 'amd64'), 1)

        self.assertEqual(koji_wrapper.run_create_image_cmd.mock_calls,
                         [mock.call('koji spin-livecd ...', log_file='/a/b/log/log_file')])
        self.assertEqual(koji_wrapper.get_image_path.mock_calls, [mock.call(123)])
        self.assertEqual(copy2.mock_calls,
                         [mock.call('/path/to/image', '/iso_dir/amd64/Client/image-name')])

        write_manifest_cmd = ' && '.join([
            'cd /iso_dir/amd64/Client',
            'isoinfo -R -f -i image-name | grep -v \'/TRANS.TBL$\' | sort >> image-name.manifest'
        ])
        self.assertEqual(run.mock_calls, [mock.call(write_manifest_cmd)])

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
            'wrapped_rpms_path': '/iso_dir/amd64/Client',
            'scratch': False,
            'repos': ['/repo/amd64/Client',
                      'http://example.com/repo/',
                      '/repo/amd64/Everything'],
            'label': '',
            'name': None,
            'iso_path': '/iso_dir/amd64/Client/image-name',
            'version': None,
            'specfile': None
        }

        koji_wrapper = KojiWrapper.return_value
        koji_wrapper.get_create_image_cmd.return_value = 'koji spin-livecd ...'
        koji_wrapper.run_create_image_cmd.return_value = {
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
            'wrapped_rpms_path': '/iso_dir/amd64/Client',
            'scratch': False,
            'repos': ['/repo/amd64/Client',
                      'http://example.com/repo/',
                      '/repo/amd64/Everything'],
            'label': '',
            'name': None,
            'iso_path': '/iso_dir/amd64/Client/image-name',
            'version': None,
            'specfile': None
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
