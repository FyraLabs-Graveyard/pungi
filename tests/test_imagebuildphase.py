#!/usr/bin/env python2
# -*- coding: utf-8 -*-


import unittest
import mock

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi.phases.image_build import ImageBuildPhase, CreateImageBuildThread
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
            'Server': mock.Mock(uid='Server', arches=['x86_64', 'amd64'], is_empty=False),
            'Client': mock.Mock(uid='Client', arches=['amd64'], is_empty=False),
            'Everything': mock.Mock(uid='Everything', arches=['x86_64', 'amd64'], is_empty=False),
        }
        self.im = mock.Mock()
        self.log_error = mock.Mock()

    def get_arches(self):
        return ['x86_64', 'amd64']

    def get_variants(self, arch=None, types=None):
        return [v for v in self.variants.values() if not arch or arch in v.arches]

    def can_fail(self, variant, arch, deliverable):
        failable = get_arch_variant_data(self.conf, 'failable_deliverables', arch, variant)
        return deliverable in failable


class TestImageBuildPhase(unittest.TestCase):

    @mock.patch('pungi.phases.image_build.ThreadPool')
    def test_image_build(self, ThreadPool):
        compose = _DummyCompose({
            'image_build': {
                '^Client|Server$': [
                    {
                        'image-build': {
                            'format': [('docker', 'tar.xz')],
                            'name': 'Fedora-Docker-Base',
                            'target': 'f24',
                            'version': 'Rawhide',
                            'ksurl': 'git://git.fedorahosted.org/git/spin-kickstarts.git',
                            'kickstart': "fedora-docker-base.ks",
                            'distro': 'Fedora-20',
                            'disk_size': 3
                        }
                    }
                ]
            },
            'koji_profile': 'koji',
        })

        phase = ImageBuildPhase(compose)

        phase.run()
        self.maxDiff = None

        # assert at least one thread was started
        self.assertTrue(phase.pool.add.called)
        client_args = {
            "format": [('docker', 'tar.xz')],
            "image_conf": {
                'image-build': {
                    'install_tree': '/ostree/$arch/Client',
                    'kickstart': 'fedora-docker-base.ks',
                    'format': 'docker',
                    'repo': '/ostree/$arch/Client',
                    'variant': compose.variants['Client'],
                    'target': 'f24',
                    'disk_size': 3,
                    'name': 'Fedora-Docker-Base',
                    'arches': 'amd64',
                    'version': 'Rawhide',
                    'ksurl': 'git://git.fedorahosted.org/git/spin-kickstarts.git',
                    'distro': 'Fedora-20',
                }
            },
            "conf_file": 'Client-Fedora-Docker-Base-docker',
            "image_dir": '/image_dir/Client/%(arch)s',
            "relative_image_dir": 'image_dir/Client/%(arch)s',
            "link_type": 'hardlink-or-copy',
            "scratch": False,
        }
        server_args = {
            "format": [('docker', 'tar.xz')],
            "image_conf": {
                'image-build': {
                    'install_tree': '/ostree/$arch/Server',
                    'kickstart': 'fedora-docker-base.ks',
                    'format': 'docker',
                    'repo': '/ostree/$arch/Server',
                    'variant': compose.variants['Server'],
                    'target': 'f24',
                    'disk_size': 3,
                    'name': 'Fedora-Docker-Base',
                    'arches': 'amd64,x86_64',
                    'version': 'Rawhide',
                    'ksurl': 'git://git.fedorahosted.org/git/spin-kickstarts.git',
                    'distro': 'Fedora-20',
                }
            },
            "conf_file": 'Server-Fedora-Docker-Base-docker',
            "image_dir": '/image_dir/Server/%(arch)s',
            "relative_image_dir": 'image_dir/Server/%(arch)s',
            "link_type": 'hardlink-or-copy',
            "scratch": False,
        }
        self.assertItemsEqual(phase.pool.queue_put.mock_calls,
                              [mock.call((compose, client_args)),
                               mock.call((compose, server_args))])

    @mock.patch('pungi.phases.image_build.ThreadPool')
    def test_image_build_filter_all_variants(self, ThreadPool):
        compose = _DummyCompose({
            'image_build': {
                '^Client|Server$': [
                    {
                        'image-build': {
                            'format': [('docker', 'tar.xz')],
                            'name': 'Fedora-Docker-Base',
                            'target': 'f24',
                            'version': 'Rawhide',
                            'ksurl': 'git://git.fedorahosted.org/git/spin-kickstarts.git',
                            'kickstart': "fedora-docker-base.ks",
                            'distro': 'Fedora-20',
                            'disk_size': 3,
                            'arches': ['non-existing'],
                        }
                    }
                ]
            },
            'koji_profile': 'koji',
        })

        phase = ImageBuildPhase(compose)

        phase.run()

        # assert at least one thread was started
        self.assertFalse(phase.pool.add.called)
        self.assertFalse(phase.pool.queue_put.called)

    @mock.patch('pungi.phases.image_build.ThreadPool')
    def test_image_build_set_install_tree(self, ThreadPool):
        compose = _DummyCompose({
            'image_build': {
                '^Server$': [
                    {
                        'image-build': {
                            'format': [('docker', 'tar.xz')],
                            'name': 'Fedora-Docker-Base',
                            'target': 'f24',
                            'version': 'Rawhide',
                            'ksurl': 'git://git.fedorahosted.org/git/spin-kickstarts.git',
                            'kickstart': "fedora-docker-base.ks",
                            'distro': 'Fedora-20',
                            'disk_size': 3,
                            'arches': ['x86_64'],
                            'install_tree_from': 'Everything',
                        }
                    }
                ]
            },
            'koji_profile': 'koji',
        })

        phase = ImageBuildPhase(compose)

        phase.run()

        # assert at least one thread was started
        self.assertTrue(phase.pool.add.called)

        self.assertTrue(phase.pool.queue_put.called_once)
        args, kwargs = phase.pool.queue_put.call_args
        self.assertEqual(args[0][0], compose)
        self.maxDiff = None
        self.assertDictEqual(args[0][1], {
            "format": [('docker', 'tar.xz')],
            "image_conf": {
                'image-build': {
                    'install_tree': '/ostree/$arch/Everything',
                    'kickstart': 'fedora-docker-base.ks',
                    'format': 'docker',
                    'repo': '/ostree/$arch/Server',
                    'variant': compose.variants['Server'],
                    'target': 'f24',
                    'disk_size': 3,
                    'name': 'Fedora-Docker-Base',
                    'arches': 'x86_64',
                    'version': 'Rawhide',
                    'ksurl': 'git://git.fedorahosted.org/git/spin-kickstarts.git',
                    'distro': 'Fedora-20',
                }
            },
            "conf_file": 'Server-Fedora-Docker-Base-docker',
            "image_dir": '/image_dir/Server/%(arch)s',
            "relative_image_dir": 'image_dir/Server/%(arch)s',
            "link_type": 'hardlink-or-copy',
            "scratch": False,
        })

    @mock.patch('pungi.phases.image_build.ThreadPool')
    def test_image_build_set_extra_repos(self, ThreadPool):
        compose = _DummyCompose({
            'image_build': {
                '^Server$': [
                    {
                        'image-build': {
                            'format': [('docker', 'tar.xz')],
                            'name': 'Fedora-Docker-Base',
                            'target': 'f24',
                            'version': 'Rawhide',
                            'ksurl': 'git://git.fedorahosted.org/git/spin-kickstarts.git',
                            'kickstart': "fedora-docker-base.ks",
                            'distro': 'Fedora-20',
                            'disk_size': 3,
                            'arches': ['x86_64'],
                            'repo_from': 'Everything',
                        }
                    }
                ]
            },
            'koji_profile': 'koji',
        })

        phase = ImageBuildPhase(compose)

        phase.run()

        # assert at least one thread was started
        self.assertTrue(phase.pool.add.called)

        self.assertTrue(phase.pool.queue_put.called_once)
        args, kwargs = phase.pool.queue_put.call_args
        self.assertEqual(args[0][0], compose)
        self.maxDiff = None
        self.assertDictEqual(args[0][1], {
            "format": [('docker', 'tar.xz')],
            "image_conf": {
                'image-build': {
                    'install_tree': '/ostree/$arch/Server',
                    'kickstart': 'fedora-docker-base.ks',
                    'format': 'docker',
                    'repo': '/ostree/$arch/Everything,/ostree/$arch/Server',
                    'variant': compose.variants['Server'],
                    'target': 'f24',
                    'disk_size': 3,
                    'name': 'Fedora-Docker-Base',
                    'arches': 'x86_64',
                    'version': 'Rawhide',
                    'ksurl': 'git://git.fedorahosted.org/git/spin-kickstarts.git',
                    'distro': 'Fedora-20',
                }
            },
            "conf_file": 'Server-Fedora-Docker-Base-docker',
            "image_dir": '/image_dir/Server/%(arch)s',
            "relative_image_dir": 'image_dir/Server/%(arch)s',
            "link_type": 'hardlink-or-copy',
            "scratch": False,
        })

    @mock.patch('pungi.phases.image_build.ThreadPool')
    def test_image_build_create_release(self, ThreadPool):
        compose = _DummyCompose({
            'image_build': {
                '^Server$': [
                    {
                        'image-build': {
                            'format': [('docker', 'tar.xz')],
                            'name': 'Fedora-Docker-Base',
                            'target': 'f24',
                            'version': 'Rawhide',
                            'ksurl': 'git://git.fedorahosted.org/git/spin-kickstarts.git',
                            'kickstart': "fedora-docker-base.ks",
                            'distro': 'Fedora-20',
                            'disk_size': 3,
                            'arches': ['x86_64'],
                            'release': None,
                        }
                    }
                ]
            },
            'koji_profile': 'koji',
        })

        phase = ImageBuildPhase(compose)

        phase.run()

        # assert at least one thread was started
        self.assertTrue(phase.pool.add.called)

        self.assertTrue(phase.pool.queue_put.called_once)
        args, kwargs = phase.pool.queue_put.call_args
        self.assertEqual(args[0][1].get('image_conf', {}).get('image-build', {}).get('release'),
                         '20151203.0')

    @mock.patch('pungi.phases.image_build.ThreadPool')
    def test_image_build_scratch_build(self, ThreadPool):
        compose = _DummyCompose({
            'image_build': {
                '^Server$': [
                    {
                        'image-build': {
                            'format': [('docker', 'tar.xz')],
                            'name': 'Fedora-Docker-Base',
                            'target': 'f24',
                            'version': 'Rawhide',
                            'ksurl': 'git://git.fedorahosted.org/git/spin-kickstarts.git',
                            'kickstart': "fedora-docker-base.ks",
                            'distro': 'Fedora-20',
                            'disk_size': 3,
                            'arches': ['x86_64'],
                            'scratch': True,
                        }
                    }
                ]
            },
            'koji_profile': 'koji',
        })

        phase = ImageBuildPhase(compose)

        phase.run()

        # assert at least one thread was started
        self.assertTrue(phase.pool.add.called)

        self.assertTrue(phase.pool.queue_put.called_once)
        args, kwargs = phase.pool.queue_put.call_args
        self.assertTrue(args[0][1].get('scratch'))


class TestCreateImageBuildThread(unittest.TestCase):

    @mock.patch('pungi.phases.image_build.KojiWrapper')
    @mock.patch('pungi.phases.image_build.Linker')
    @mock.patch('pungi.phases.image_build.makedirs')
    def test_process(self, makedirs, Linker, KojiWrapper):
        compose = _DummyCompose({
            'koji_profile': 'koji'
        })
        pool = mock.Mock()
        cmd = {
            "format": [('docker', 'tar.xz'), ('qcow2', 'qcow2')],
            "image_conf": {
                'image-build': {
                    'install_tree': '/ostree/$arch/Client',
                    'kickstart': 'fedora-docker-base.ks',
                    'format': 'docker',
                    'repo': '/ostree/$arch/Client',
                    'variant': compose.variants['Client'],
                    'target': 'f24',
                    'disk_size': 3,
                    'name': 'Fedora-Docker-Base',
                    'arches': 'amd64,x86_64',
                    'version': 'Rawhide',
                    'ksurl': 'git://git.fedorahosted.org/git/spin-kickstarts.git',
                    'distro': 'Fedora-20',
                }
            },
            "conf_file": 'amd64,x86_64-Client-Fedora-Docker-Base-docker',
            "image_dir": '/image_dir/Client/%(arch)s',
            "relative_image_dir": 'image_dir/Client/%(arch)s',
            "link_type": 'hardlink-or-copy',
            "scratch": False,
        }
        koji_wrapper = KojiWrapper.return_value
        koji_wrapper.run_blocking_cmd.return_value = {
            "retcode": 0,
            "output": None,
            "task_id": 1234,
        }
        koji_wrapper.get_image_paths.return_value = {
            'amd64': [
                '/koji/task/1235/tdl-amd64.xml',
                '/koji/task/1235/Fedora-Docker-Base-20160103.amd64.qcow2',
                '/koji/task/1235/Fedora-Docker-Base-20160103.amd64.tar.xz'
            ],
            'x86_64': [
                '/koji/task/1235/tdl-x86_64.xml',
                '/koji/task/1235/Fedora-Docker-Base-20160103.x86_64.qcow2',
                '/koji/task/1235/Fedora-Docker-Base-20160103.x86_64.tar.xz'
            ]
        }

        linker = Linker.return_value

        t = CreateImageBuildThread(pool)
        with mock.patch('os.stat') as stat:
            with mock.patch('os.path.getsize') as getsize:
                with mock.patch('time.sleep'):
                    getsize.return_value = 1024
                    stat.return_value.st_mtime = 13579
                    t.process((compose, cmd), 1)

        self.assertItemsEqual(
            linker.mock_calls,
            [mock.call('/koji/task/1235/Fedora-Docker-Base-20160103.amd64.qcow2',
                       '/image_dir/Client/amd64/Fedora-Docker-Base-20160103.amd64.qcow2',
                       link_type='hardlink-or-copy'),
             mock.call('/koji/task/1235/Fedora-Docker-Base-20160103.amd64.tar.xz',
                       '/image_dir/Client/amd64/Fedora-Docker-Base-20160103.amd64.tar.xz',
                       link_type='hardlink-or-copy'),
             mock.call('/koji/task/1235/Fedora-Docker-Base-20160103.x86_64.qcow2',
                       '/image_dir/Client/x86_64/Fedora-Docker-Base-20160103.x86_64.qcow2',
                       link_type='hardlink-or-copy'),
             mock.call('/koji/task/1235/Fedora-Docker-Base-20160103.x86_64.tar.xz',
                       '/image_dir/Client/x86_64/Fedora-Docker-Base-20160103.x86_64.tar.xz',
                       link_type='hardlink-or-copy')])

        image_relative_paths = {
            'image_dir/Client/amd64/Fedora-Docker-Base-20160103.amd64.qcow2': {
                'format': 'qcow2',
                'type': 'qcow2',
                'arch': 'amd64',
            },
            'image_dir/Client/amd64/Fedora-Docker-Base-20160103.amd64.tar.xz': {
                'format': 'tar.xz',
                'type': 'docker',
                'arch': 'amd64',
            },
            'image_dir/Client/x86_64/Fedora-Docker-Base-20160103.x86_64.qcow2': {
                'format': 'qcow2',
                'type': 'qcow2',
                'arch': 'x86_64',
            },
            'image_dir/Client/x86_64/Fedora-Docker-Base-20160103.x86_64.tar.xz': {
                'format': 'tar.xz',
                'type': 'docker',
                'arch': 'x86_64',
            },
        }

        # Assert there are 4 images added to manifest and the arguments are sane
        self.assertEqual(len(compose.im.add.call_args_list), 4)
        for call in compose.im.add.call_args_list:
            _, kwargs = call
            image = kwargs['image']
            self.assertEqual(kwargs['variant'], 'Client')
            self.assertIn(kwargs['arch'], ('amd64', 'x86_64'))
            self.assertEqual(kwargs['arch'], image.arch)
            self.assertIn(image.path, image_relative_paths)
            data = image_relative_paths.pop(image.path)
            self.assertEqual(data['format'], image.format)
            self.assertEqual(data['type'], image.type)

        self.assertItemsEqual(makedirs.mock_calls,
                              [mock.call('/image_dir/Client/amd64'),
                               mock.call('/image_dir/Client/amd64'),
                               mock.call('/image_dir/Client/x86_64'),
                               mock.call('/image_dir/Client/x86_64')])

    @mock.patch('pungi.phases.image_build.KojiWrapper')
    @mock.patch('pungi.phases.image_build.Linker')
    def test_process_handle_fail(self, Linker, KojiWrapper):
        compose = _DummyCompose({
            'koji_profile': 'koji',
            'failable_deliverables': [
                ('^.*$', {
                    '*': ['image-build']
                })
            ]
        })
        pool = mock.Mock()
        cmd = {
            "format": [('docker', 'tar.xz'), ('qcow2', 'qcow2')],
            "image_conf": {
                'image-build': {
                    'install_tree': '/ostree/$arch/Client',
                    'kickstart': 'fedora-docker-base.ks',
                    'format': 'docker',
                    'repo': '/ostree/$arch/Client',
                    'variant': compose.variants['Client'],
                    'target': 'f24',
                    'disk_size': 3,
                    'name': 'Fedora-Docker-Base',
                    'arches': 'amd64,x86_64',
                    'version': 'Rawhide',
                    'ksurl': 'git://git.fedorahosted.org/git/spin-kickstarts.git',
                    'distro': 'Fedora-20',
                }
            },
            "conf_file": 'amd64,x86_64-Client-Fedora-Docker-Base-docker',
            "image_dir": '/image_dir/Client/%(arch)s',
            "relative_image_dir": 'image_dir/Client/%(arch)s',
            "link_type": 'hardlink-or-copy',
            'scratch': False,
        }
        koji_wrapper = KojiWrapper.return_value
        koji_wrapper.run_blocking_cmd.return_value = {
            "retcode": 1,
            "output": None,
            "task_id": 1234,
        }

        t = CreateImageBuildThread(pool)
        with mock.patch('os.stat') as stat:
            with mock.patch('os.path.getsize') as getsize:
                with mock.patch('time.sleep'):
                    getsize.return_value = 1024
                    stat.return_value.st_mtime = 13579
                    t.process((compose, cmd), 1)

    @mock.patch('pungi.phases.image_build.KojiWrapper')
    @mock.patch('pungi.phases.image_build.Linker')
    def test_process_handle_exception(self, Linker, KojiWrapper):
        compose = _DummyCompose({
            'koji_profile': 'koji',
            'failable_deliverables': [
                ('^.*$', {
                    '*': ['image-build']
                })
            ]
        })
        pool = mock.Mock()
        cmd = {
            "format": [('docker', 'tar.xz'), ('qcow2', 'qcow2')],
            "image_conf": {
                'image-build': {
                    'install_tree': '/ostree/$arch/Client',
                    'kickstart': 'fedora-docker-base.ks',
                    'format': 'docker',
                    'repo': '/ostree/$arch/Client',
                    'variant': compose.variants['Client'],
                    'target': 'f24',
                    'disk_size': 3,
                    'name': 'Fedora-Docker-Base',
                    'arches': 'amd64,x86_64',
                    'version': 'Rawhide',
                    'ksurl': 'git://git.fedorahosted.org/git/spin-kickstarts.git',
                    'distro': 'Fedora-20',
                }
            },
            "conf_file": 'amd64,x86_64-Client-Fedora-Docker-Base-docker',
            "image_dir": '/image_dir/Client/%(arch)s',
            "relative_image_dir": 'image_dir/Client/%(arch)s',
            "link_type": 'hardlink-or-copy',
            'scratch': False,
        }

        def boom(*args, **kwargs):
            raise RuntimeError('BOOM')

        koji_wrapper = KojiWrapper.return_value
        koji_wrapper.run_blocking_cmd.side_effect = boom

        t = CreateImageBuildThread(pool)
        with mock.patch('os.stat') as stat:
            with mock.patch('os.path.getsize') as getsize:
                with mock.patch('time.sleep'):
                    getsize.return_value = 1024
                    stat.return_value.st_mtime = 13579
                    t.process((compose, cmd), 1)


if __name__ == "__main__":
    unittest.main()
