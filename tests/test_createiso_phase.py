#!/usr/bin/env python
# -*- coding: utf-8 -*-


import unittest
import mock

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tests import helpers
from pungi.phases import createiso


class CreateisoPhaseTest(helpers.PungiTestCase):

    @mock.patch('pungi.phases.createiso.ThreadPool')
    def test_skip_all(self, ThreadPool):
        compose = helpers.DummyCompose(self.topdir, {
            'createiso_skip': [
                ('^.*$', {'*': True, 'src': True})
            ]
        })

        pool = ThreadPool.return_value

        phase = createiso.CreateisoPhase(compose)
        phase.run()

        self.assertEqual(len(pool.add.call_args_list), 0)
        self.assertEqual(pool.queue_put.call_args_list, [])

    @mock.patch('pungi.phases.createiso.ThreadPool')
    def test_nothing_happens_without_rpms(self, ThreadPool):
        compose = helpers.DummyCompose(self.topdir, {
            'release_short': 'test',
            'release_version': '1.0',
            'release_is_layered': False,
            'createiso_skip': [
            ]
        })

        pool = ThreadPool.return_value

        phase = createiso.CreateisoPhase(compose)
        phase.run()

        self.assertEqual(len(pool.add.call_args_list), 0)
        self.assertEqual(pool.queue_put.call_args_list, [])
        self.assertItemsEqual(
            compose.log_warning.call_args_list,
            [mock.call('No RPMs found for Everything.x86_64, skipping ISO'),
             mock.call('No RPMs found for Everything.amd64, skipping ISO'),
             mock.call('No RPMs found for Everything.src, skipping ISO'),
             mock.call('No RPMs found for Client.amd64, skipping ISO'),
             mock.call('No RPMs found for Client.src, skipping ISO'),
             mock.call('No RPMs found for Server.x86_64, skipping ISO'),
             mock.call('No RPMs found for Server.amd64, skipping ISO'),
             mock.call('No RPMs found for Server.src, skipping ISO')]
        )

    @mock.patch('pungi.phases.createiso.prepare_iso')
    @mock.patch('pungi.phases.createiso.split_iso')
    @mock.patch('pungi.phases.createiso.ThreadPool')
    def test_start_one_worker(self, ThreadPool, split_iso, prepare_iso):
        compose = helpers.DummyCompose(self.topdir, {
            'release_short': 'test',
            'release_version': '1.0',
            'release_is_layered': False,
            'createiso_skip': [
            ]
        })
        helpers.touch(os.path.join(
            compose.paths.compose.os_tree('x86_64', compose.variants['Server']),
            'dummy.rpm'))
        disc_data = mock.Mock()
        split_iso.return_value = [disc_data]
        prepare_iso.return_value = 'dummy-graft-points'

        pool = ThreadPool.return_value

        phase = createiso.CreateisoPhase(compose)
        phase.run()

        self.assertEqual(prepare_iso.call_args_list,
                         [mock.call(compose, 'x86_64', compose.variants['Server'],
                                    disc_count=1, disc_num=1, split_iso_data=disc_data)])
        self.assertEqual(split_iso.call_args_list,
                         [mock.call(compose, 'x86_64', compose.variants['Server'])])
        self.assertEqual(len(pool.add.call_args_list), 1)
        self.maxDiff = None
        self.assertItemsEqual(
            pool.queue_put.call_args_list,
            [mock.call((
                compose,
                {
                    'iso_path': '{}/compose/Server/x86_64/iso/image-name'.format(self.topdir),
                    'bootable': False,
                    'cmd': ['pungi-createiso',
                            '--output-dir={}/compose/Server/x86_64/iso'.format(self.topdir),
                            '--iso-name=image-name', '--volid=test-1.0 Server.x86_64',
                            '--graft-points=dummy-graft-points',
                            '--arch=x86_64', '--supported',
                            '--jigdo-dir={}/compose/Server/x86_64/jigdo'.format(self.topdir),
                            '--os-tree={}/compose/Server/x86_64/os'.format(self.topdir)],
                    'label': '',
                    'disc_num': 1,
                    'disc_count': 1,
                },
                compose.variants['Server'],
                'x86_64'
            ))]
        )

    @mock.patch('pungi.phases.createiso.prepare_iso')
    @mock.patch('pungi.phases.createiso.split_iso')
    @mock.patch('pungi.phases.createiso.ThreadPool')
    def test_bootable(self, ThreadPool, split_iso, prepare_iso):
        compose = helpers.DummyCompose(self.topdir, {
            'release_short': 'test',
            'release_version': '1.0',
            'release_is_layered': False,
            'buildinstall_method': 'lorax',
            'bootable': True,
            'createiso_skip': [
            ]
        })
        helpers.touch(os.path.join(
            compose.paths.compose.os_tree('x86_64', compose.variants['Server']),
            'dummy.rpm'))
        helpers.touch(os.path.join(
            compose.paths.compose.os_tree('src', compose.variants['Server']),
            'dummy.rpm'))
        disc_data = mock.Mock()
        split_iso.return_value = [disc_data]
        prepare_iso.return_value = 'dummy-graft-points'

        pool = ThreadPool.return_value

        phase = createiso.CreateisoPhase(compose)
        phase.run()

        self.assertItemsEqual(
            prepare_iso.call_args_list,
            [mock.call(compose, 'x86_64', compose.variants['Server'],
                       disc_count=1, disc_num=1, split_iso_data=disc_data),
             mock.call(compose, 'src', compose.variants['Server'],
                       disc_count=1, disc_num=1, split_iso_data=disc_data)])
        self.assertItemsEqual(
            split_iso.call_args_list,
            [mock.call(compose, 'x86_64', compose.variants['Server']),
             mock.call(compose, 'src', compose.variants['Server'])])
        self.assertEqual(len(pool.add.call_args_list), 2)
        self.maxDiff = None
        self.assertItemsEqual(
            pool.queue_put.call_args_list,
            [mock.call((compose,
                        {'iso_path': '{}/compose/Server/x86_64/iso/image-name'.format(self.topdir),
                         'bootable': True,
                         'cmd': ['pungi-createiso',
                                 '--output-dir={}/compose/Server/x86_64/iso'.format(self.topdir),
                                 '--iso-name=image-name', '--volid=test-1.0 Server.x86_64',
                                 '--graft-points=dummy-graft-points',
                                 '--arch=x86_64',
                                 '--buildinstall-method=lorax',
                                 '--supported',
                                 '--jigdo-dir={}/compose/Server/x86_64/jigdo'.format(self.topdir),
                                 '--os-tree={}/compose/Server/x86_64/os'.format(self.topdir)],
                         'label': '',
                         'disc_num': 1,
                         'disc_count': 1},
                        compose.variants['Server'],
                        'x86_64')),
             mock.call((compose,
                        {'iso_path': '{}/compose/Server/source/iso/image-name'.format(self.topdir),
                         'bootable': False,
                         'cmd': ['pungi-createiso',
                                 '--output-dir={}/compose/Server/source/iso'.format(self.topdir),
                                 '--iso-name=image-name', '--volid=test-1.0 Server.src',
                                 '--graft-points=dummy-graft-points',
                                 '--arch=src', '--supported',
                                 '--jigdo-dir={}/compose/Server/source/jigdo'.format(self.topdir),
                                 '--os-tree={}/compose/Server/source/tree'.format(self.topdir)],
                         'label': '',
                         'disc_num': 1,
                         'disc_count': 1},
                        compose.variants['Server'],
                        'src'))]
        )


class CreateisoThreadTest(helpers.PungiTestCase):

    @mock.patch('pungi.phases.createiso.IsoWrapper')
    @mock.patch('pungi.phases.createiso.get_mtime')
    @mock.patch('pungi.phases.createiso.get_file_size')
    @mock.patch('pungi.phases.createiso.KojiWrapper')
    def test_process_in_runroot(self, KojiWrapper, get_file_size, get_mtime, IsoWrapper):
        compose = helpers.DummyCompose(self.topdir, {
            'release_short': 'test',
            'release_version': '1.0',
            'release_is_layered': False,
            'runroot': True,
            'runroot_tag': 'f25-build',
            'koji_profile': 'koji',
        })
        cmd = {
            'iso_path': '{}/compose/Server/x86_64/iso/image-name'.format(self.topdir),
            'bootable': False,
            'cmd': mock.Mock(),
            'label': '',
            'disc_num': 1,
            'disc_count': 1,
        }
        get_file_size.return_value = 1024
        get_mtime.return_value = 13579
        getTag = KojiWrapper.return_value.koji_proxy.getTag
        getTag.return_value = {'arches': 'x86_64'}
        get_runroot_cmd = KojiWrapper.return_value.get_runroot_cmd
        run_runroot = KojiWrapper.return_value.run_runroot_cmd
        run_runroot.return_value = {
            'retcode': 0,
            'output': 'whatever',
            'task_id': 1234,
        }

        t = createiso.CreateIsoThread(mock.Mock())
        with mock.patch('time.sleep'):
            t.process((compose, cmd, compose.variants['Server'], 'x86_64'), 1)

        self.assertEqual(getTag.call_args_list, [mock.call('f25-build')])
        self.assertEqual(get_runroot_cmd.call_args_list,
                         [mock.call('f25-build', 'x86_64', cmd['cmd'], channel=None,
                                    mounts=['{}'.format(self.topdir)],
                                    packages=['coreutils', 'genisoimage', 'isomd5sum',
                                              'jigdo', 'pungi'],
                                    task_id=True, use_shell=True)])
        self.assertEqual(
            run_runroot.call_args_list,
            [mock.call(get_runroot_cmd.return_value,
                       log_file='{}/logs/x86_64/createiso-image-name.x86_64.log'.format(self.topdir))])
        self.assertEqual(IsoWrapper.return_value.get_implanted_md5.call_args_list,
                         [mock.call(cmd['iso_path'])])
        self.assertEqual(IsoWrapper.return_value.get_volume_id.call_args_list,
                         [mock.call(cmd['iso_path'])])

        self.assertEqual(len(compose.im.add.call_args_list), 1)
        args, _ = compose.im.add.call_args_list[0]
        self.assertEqual(args[0], 'Server')
        self.assertEqual(args[1], 'x86_64')
        image = args[2]
        self.assertEqual(image.arch, 'x86_64')
        self.assertEqual(image.path, 'Server/x86_64/iso/image-name')
        self.assertEqual(image.format, 'iso')
        self.assertEqual(image.type, 'dvd')
        self.assertEqual(image.subvariant, 'Server')

    @mock.patch('pungi.phases.createiso.IsoWrapper')
    @mock.patch('pungi.phases.createiso.get_mtime')
    @mock.patch('pungi.phases.createiso.get_file_size')
    @mock.patch('pungi.phases.createiso.KojiWrapper')
    def test_process_bootable(self, KojiWrapper, get_file_size, get_mtime, IsoWrapper):
        compose = helpers.DummyCompose(self.topdir, {
            'release_short': 'test',
            'release_version': '1.0',
            'release_is_layered': False,
            'runroot': True,
            'bootable': True,
            'buildinstall_method': 'lorax',
            'runroot_tag': 'f25-build',
            'koji_profile': 'koji',
        })
        cmd = {
            'iso_path': '{}/compose/Server/x86_64/iso/image-name'.format(self.topdir),
            'bootable': True,
            'cmd': mock.Mock(),
            'label': '',
            'disc_num': 1,
            'disc_count': 1,
        }
        get_file_size.return_value = 1024
        get_mtime.return_value = 13579
        getTag = KojiWrapper.return_value.koji_proxy.getTag
        getTag.return_value = {'arches': 'x86_64'}
        get_runroot_cmd = KojiWrapper.return_value.get_runroot_cmd
        run_runroot = KojiWrapper.return_value.run_runroot_cmd
        run_runroot.return_value = {
            'retcode': 0,
            'output': 'whatever',
            'task_id': 1234,
        }

        t = createiso.CreateIsoThread(mock.Mock())
        with mock.patch('time.sleep'):
            t.process((compose, cmd, compose.variants['Server'], 'x86_64'), 1)

        self.assertEqual(getTag.call_args_list, [mock.call('f25-build')])
        self.assertEqual(get_runroot_cmd.call_args_list,
                         [mock.call('f25-build', 'x86_64', cmd['cmd'], channel=None,
                                    mounts=['{}'.format(self.topdir)],
                                    packages=['coreutils', 'genisoimage', 'isomd5sum',
                                              'jigdo', 'pungi', 'lorax'],
                                    task_id=True, use_shell=True)])
        self.assertEqual(
            run_runroot.call_args_list,
            [mock.call(get_runroot_cmd.return_value,
                       log_file='{}/logs/x86_64/createiso-image-name.x86_64.log'.format(self.topdir))])
        self.assertEqual(IsoWrapper.return_value.get_implanted_md5.call_args_list,
                         [mock.call(cmd['iso_path'])])
        self.assertEqual(IsoWrapper.return_value.get_volume_id.call_args_list,
                         [mock.call(cmd['iso_path'])])

        self.assertEqual(len(compose.im.add.call_args_list), 1)
        args, _ = compose.im.add.call_args_list[0]
        self.assertEqual(args[0], 'Server')
        self.assertEqual(args[1], 'x86_64')
        image = args[2]
        self.assertEqual(image.arch, 'x86_64')
        self.assertEqual(image.path, 'Server/x86_64/iso/image-name')
        self.assertEqual(image.format, 'iso')
        self.assertEqual(image.type, 'dvd')
        self.assertEqual(image.subvariant, 'Server')

    @mock.patch('pungi.phases.createiso.IsoWrapper')
    @mock.patch('pungi.phases.createiso.get_mtime')
    @mock.patch('pungi.phases.createiso.get_file_size')
    @mock.patch('pungi.phases.createiso.KojiWrapper')
    def test_process_in_runroot_crash(self, KojiWrapper, get_file_size, get_mtime, IsoWrapper):
        compose = helpers.DummyCompose(self.topdir, {
            'release_short': 'test',
            'release_version': '1.0',
            'release_is_layered': False,
            'runroot': True,
            'runroot_tag': 'f25-build',
            'koji_profile': 'koji',
            'failable_deliverables': [
                ('^.*$', {'*': 'iso'})
            ]
        })
        cmd = {
            'iso_path': '{}/compose/Server/x86_64/iso/image-name'.format(self.topdir),
            'bootable': False,
            'cmd': mock.Mock(),
            'label': '',
            'disc_num': 1,
            'disc_count': 1,
        }
        getTag = KojiWrapper.return_value.koji_proxy.getTag
        getTag.return_value = {'arches': 'x86_64'}
        run_runroot = KojiWrapper.return_value.run_runroot_cmd
        run_runroot.side_effect = helpers.boom

        t = createiso.CreateIsoThread(mock.Mock())
        with mock.patch('time.sleep'):
            t.process((compose, cmd, compose.variants['Server'], 'x86_64'), 1)

        compose.log_info.assert_has_calls([
            mock.call('[FAIL] Creating ISO (variant Server, arch x86_64) failed, but going on anyway.'),
            mock.call('BOOM')
        ])

    @mock.patch('pungi.phases.createiso.IsoWrapper')
    @mock.patch('pungi.phases.createiso.get_mtime')
    @mock.patch('pungi.phases.createiso.get_file_size')
    @mock.patch('pungi.phases.createiso.KojiWrapper')
    def test_process_in_runroot_fail(self, KojiWrapper, get_file_size, get_mtime, IsoWrapper):
        compose = helpers.DummyCompose(self.topdir, {
            'release_short': 'test',
            'release_version': '1.0',
            'release_is_layered': False,
            'runroot': True,
            'runroot_tag': 'f25-build',
            'koji_profile': 'koji',
            'failable_deliverables': [
                ('^.*$', {'*': 'iso'})
            ]
        })
        cmd = {
            'iso_path': '{}/compose/Server/x86_64/iso/image-name'.format(self.topdir),
            'bootable': False,
            'cmd': mock.Mock(),
            'label': '',
            'disc_num': 1,
            'disc_count': 1,
        }
        getTag = KojiWrapper.return_value.koji_proxy.getTag
        getTag.return_value = {'arches': 'x86_64'}
        run_runroot = KojiWrapper.return_value.run_runroot_cmd
        run_runroot.return_value = {
            'retcode': 1,
            'output': 'Nope',
            'task_id': '1234',
        }

        t = createiso.CreateIsoThread(mock.Mock())
        with mock.patch('time.sleep'):
            t.process((compose, cmd, compose.variants['Server'], 'x86_64'), 1)

        compose.log_info.assert_has_calls([
            mock.call('[FAIL] Creating ISO (variant Server, arch x86_64) failed, but going on anyway.'),
            mock.call('Runroot task failed: 1234. See {} for more details.'.format(
                self.topdir + '/logs/x86_64/createiso-image-name.x86_64.log'))
        ])

    @mock.patch('pungi.phases.createiso.IsoWrapper')
    @mock.patch('pungi.phases.createiso.get_mtime')
    @mock.patch('pungi.phases.createiso.get_file_size')
    @mock.patch('pungi.phases.createiso.run')
    @mock.patch('pungi.phases.createiso.KojiWrapper')
    def test_process_locally(self, KojiWrapper, run, get_file_size, get_mtime, IsoWrapper):
        compose = helpers.DummyCompose(self.topdir, {
            'release_short': 'test',
            'release_version': '1.0',
            'release_is_layered': False,
            'runroot': False,
        })
        cmd = {
            'iso_path': '{}/compose/Server/x86_64/iso/image-name'.format(self.topdir),
            'bootable': False,
            'cmd': mock.Mock(),
            'label': '',
            'disc_num': 1,
            'disc_count': 1,
        }
        get_file_size.return_value = 1024
        get_mtime.return_value = 13579

        t = createiso.CreateIsoThread(mock.Mock())
        with mock.patch('time.sleep'):
            t.process((compose, cmd, compose.variants['Server'], 'x86_64'), 1)

        self.assertEqual(KojiWrapper.return_value.mock_calls, [])
        self.assertEqual(
            run.call_args_list,
            [mock.call(cmd['cmd'], show_cmd=True,
                       logfile='{}/logs/x86_64/createiso-image-name.x86_64.log'.format(self.topdir))])
        self.assertEqual(IsoWrapper.return_value.get_implanted_md5.call_args_list,
                         [mock.call(cmd['iso_path'])])
        self.assertEqual(IsoWrapper.return_value.get_volume_id.call_args_list,
                         [mock.call(cmd['iso_path'])])

        self.assertEqual(len(compose.im.add.call_args_list), 1)
        args, _ = compose.im.add.call_args_list[0]
        self.assertEqual(args[0], 'Server')
        self.assertEqual(args[1], 'x86_64')
        image = args[2]
        self.assertEqual(image.arch, 'x86_64')
        self.assertEqual(image.path, 'Server/x86_64/iso/image-name')
        self.assertEqual(image.format, 'iso')
        self.assertEqual(image.type, 'dvd')
        self.assertEqual(image.subvariant, 'Server')

    @mock.patch('pungi.phases.createiso.run')
    @mock.patch('pungi.phases.createiso.KojiWrapper')
    def test_process_locally_crash(self, KojiWrapper, run):
        compose = helpers.DummyCompose(self.topdir, {
            'release_short': 'test',
            'release_version': '1.0',
            'release_is_layered': False,
            'runroot': False,
            'failable_deliverables': [
                ('^.*$', {'*': 'iso'})
            ]
        })
        cmd = {
            'iso_path': '{}/compose/Server/x86_64/iso/image-name'.format(self.topdir),
            'bootable': False,
            'cmd': mock.Mock(),
            'label': '',
            'disc_num': 1,
            'disc_count': 1,
        }
        run.side_effect = helpers.boom

        t = createiso.CreateIsoThread(mock.Mock())
        with mock.patch('time.sleep'):
            t.process((compose, cmd, compose.variants['Server'], 'x86_64'), 1)

        compose.log_info.assert_has_calls([
            mock.call('[FAIL] Creating ISO (variant Server, arch x86_64) failed, but going on anyway.'),
            mock.call('BOOM')
        ])


if __name__ == '__main__':
    unittest.main()
