#!/usr/bin/env python2
# -*- coding: utf-8 -*-


try:
    import unittest2 as unittest
except ImportError:
    import unittest
import mock

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi.phases.buildinstall import BuildinstallPhase, BuildinstallThread, link_boot_iso
from tests.helpers import DummyCompose, PungiTestCase, touch, boom


class BuildInstallCompose(DummyCompose):
    def __init__(self, *args, **kwargs):
        super(BuildInstallCompose, self).__init__(*args, **kwargs)
        self.variants = {
            'Server': mock.Mock(uid='Server', arches=['x86_64', 'amd64'],
                                type='variant', buildinstallpackages=['bash', 'vim'],
                                is_empty=False),
            'Client': mock.Mock(uid='Client', arches=['amd64'],
                                type='variant', buildinstallpackages=[],
                                is_empty=False),
        }


class TestBuildinstallPhase(PungiTestCase):

    def test_config_skip_unless_bootable(self):
        compose = BuildInstallCompose(self.topdir, {})
        compose.just_phases = None
        compose.skip_phases = []

        phase = BuildinstallPhase(compose)

        self.assertTrue(phase.skip())

    def test_does_not_skip_on_bootable(self):
        compose = BuildInstallCompose(self.topdir, {'bootable': True})
        compose.just_phases = None
        compose.skip_phases = []

        phase = BuildinstallPhase(compose)

        self.assertFalse(phase.skip())

    @mock.patch('pungi.phases.buildinstall.ThreadPool')
    @mock.patch('pungi.phases.buildinstall.LoraxWrapper')
    @mock.patch('pungi.phases.buildinstall.get_volid')
    def test_starts_threads_for_each_cmd_with_lorax(self, get_volid, loraxCls, poolCls):
        compose = BuildInstallCompose(self.topdir, {
            'bootable': True,
            'release_name': 'Test',
            'release_short': 't',
            'release_version': '1',
            'release_is_layered': False,
            'buildinstall_method': 'lorax',
            'disc_types': {'dvd': 'DVD'},
        })

        get_volid.return_value = 'vol_id'
        loraxCls.return_value.get_lorax_cmd.return_value = ['lorax', '...']

        phase = BuildinstallPhase(compose)

        phase.run()

        # Three items added for processing in total.
        # Server.x86_64, Client.amd64, Server.x86_64
        pool = poolCls.return_value
        self.assertEqual(3, len(pool.queue_put.mock_calls))
        self.assertItemsEqual(
            [call[0][0][3] for call in pool.queue_put.call_args_list],
            ['rm -rf %s/work/amd64/buildinstall/Client && lorax ...' % self.topdir,
             'rm -rf %s/work/amd64/buildinstall/Server && lorax ...' % self.topdir,
             'rm -rf %s/work/x86_64/buildinstall/Server && lorax ...' % self.topdir])

        # Obtained correct lorax commands.
        self.assertItemsEqual(
            loraxCls.return_value.get_lorax_cmd.mock_calls,
            [mock.call('Test', '1', '1', self.topdir + '/work/x86_64/repo',
                       self.topdir + '/work/x86_64/buildinstall/Server',
                       buildarch='x86_64', is_final=True, nomacboot=True, noupgrade=True,
                       volid='vol_id', variant='Server', buildinstallpackages=['bash', 'vim'],
                       bugurl=None),
             mock.call('Test', '1', '1', self.topdir + '/work/amd64/repo',
                       self.topdir + '/work/amd64/buildinstall/Server',
                       buildarch='amd64', is_final=True, nomacboot=True, noupgrade=True,
                       volid='vol_id', variant='Server', buildinstallpackages=['bash', 'vim'],
                       bugurl=None),
             mock.call('Test', '1', '1', self.topdir + '/work/amd64/repo',
                       self.topdir + '/work/amd64/buildinstall/Client',
                       buildarch='amd64', is_final=True, nomacboot=True, noupgrade=True,
                       volid='vol_id', variant='Client', buildinstallpackages=[],
                       bugurl=None)])
        self.assertItemsEqual(
            get_volid.mock_calls,
            [mock.call(compose, 'x86_64', variant=compose.variants['Server'], disc_type='DVD'),
             mock.call(compose, 'amd64', variant=compose.variants['Client'], disc_type='DVD'),
             mock.call(compose, 'amd64', variant=compose.variants['Server'], disc_type='DVD')])

    @mock.patch('pungi.phases.buildinstall.ThreadPool')
    @mock.patch('pungi.phases.buildinstall.LoraxWrapper')
    @mock.patch('pungi.phases.buildinstall.get_volid')
    def test_lorax_skips_empty_variants(self, get_volid, loraxCls, poolCls):
        compose = BuildInstallCompose(self.topdir, {
            'bootable': True,
            'release_name': 'Test',
            'release_short': 't',
            'release_version': '1',
            'release_is_layered': False,
            'buildinstall_method': 'lorax'
        })

        get_volid.return_value = 'vol_id'
        compose.variants['Server'].is_empty = True
        loraxCls.return_value.get_lorax_cmd.return_value = ['lorax', '...']

        phase = BuildinstallPhase(compose)

        phase.run()

        pool = poolCls.return_value
        self.assertEqual(1, len(pool.queue_put.mock_calls))
        self.assertItemsEqual(
            [call[0][0][3] for call in pool.queue_put.call_args_list],
            ['rm -rf %s/work/amd64/buildinstall/Client && lorax ...' % self.topdir])

        # Obtained correct lorax command.
        lorax = loraxCls.return_value
        lorax.get_lorax_cmd.assert_has_calls(
            [mock.call('Test', '1', '1', self.topdir + '/work/amd64/repo',
                       self.topdir + '/work/amd64/buildinstall/Client',
                       buildarch='amd64', is_final=True, nomacboot=True, noupgrade=True,
                       volid='vol_id', variant='Client', buildinstallpackages=[],
                       bugurl=None)],
            any_order=True)
        self.assertItemsEqual(
            get_volid.mock_calls,
            [mock.call(compose, 'amd64', variant=compose.variants['Client'], disc_type='dvd')])

    @mock.patch('pungi.phases.buildinstall.ThreadPool')
    @mock.patch('pungi.phases.buildinstall.LoraxWrapper')
    @mock.patch('pungi.phases.buildinstall.get_volid')
    def test_starts_threads_for_each_cmd_with_buildinstall(self, get_volid, loraxCls, poolCls):
        compose = BuildInstallCompose(self.topdir, {
            'bootable': True,
            'release_name': 'Test',
            'release_short': 't',
            'release_version': '1',
            'release_is_layered': False,
            'buildinstall_method': 'buildinstall',
            'disc_types': {'dvd': 'DVD'},
        })

        get_volid.return_value = 'vol_id'

        phase = BuildinstallPhase(compose)

        phase.run()

        # Two items added for processing in total.
        pool = poolCls.return_value
        self.assertEqual(2, len(pool.queue_put.mock_calls))

        # Obtained correct lorax commands.
        self.assertItemsEqual(
            loraxCls.return_value.get_buildinstall_cmd.mock_calls,
            [mock.call('Test', '1', '1', self.topdir + '/work/x86_64/repo',
                       self.topdir + '/work/x86_64/buildinstall',
                       buildarch='x86_64', is_final=True, volid='vol_id'),
             mock.call('Test', '1', '1', self.topdir + '/work/amd64/repo',
                       self.topdir + '/work/amd64/buildinstall',
                       buildarch='amd64', is_final=True, volid='vol_id')])
        self.assertItemsEqual(
            get_volid.mock_calls,
            [mock.call(compose, 'x86_64', disc_type='DVD'),
             mock.call(compose, 'amd64', disc_type='DVD')])

    @mock.patch('pungi.phases.buildinstall.ThreadPool')
    @mock.patch('pungi.phases.buildinstall.LoraxWrapper')
    @mock.patch('pungi.phases.buildinstall.get_volid')
    def test_uses_lorax_options(self, get_volid, loraxCls, poolCls):
        compose = BuildInstallCompose(self.topdir, {
            'bootable': True,
            'release_name': 'Test',
            'release_short': 't',
            'release_version': '1',
            'release_is_layered': False,
            'buildinstall_method': 'lorax',
            'lorax_options': [
                ('^Server$', {
                    'x86_64': {'bugurl': 'http://example.com'},
                    'amd64': {'noupgrade': False}
                }),
                ('^Client$', {
                    '*': {'nomacboot': False}
                }),
            ]
        })

        get_volid.return_value = 'vol_id'
        loraxCls.return_value.get_lorax_cmd.return_value = ['lorax', '...']

        phase = BuildinstallPhase(compose)

        phase.run()

        # Three items added for processing in total.
        # Server.x86_64, Client.amd64, Server.x86_64
        pool = poolCls.return_value
        self.assertEqual(3, len(pool.queue_put.mock_calls))
        self.assertItemsEqual(
            [call[0][0][3] for call in pool.queue_put.call_args_list],
            ['rm -rf %s/work/amd64/buildinstall/Client && lorax ...' % self.topdir,
             'rm -rf %s/work/amd64/buildinstall/Server && lorax ...' % self.topdir,
             'rm -rf %s/work/x86_64/buildinstall/Server && lorax ...' % self.topdir])

        # Obtained correct lorax commands.
        self.assertItemsEqual(
            loraxCls.return_value.get_lorax_cmd.mock_calls,
            [mock.call('Test', '1', '1', self.topdir + '/work/x86_64/repo',
                       self.topdir + '/work/x86_64/buildinstall/Server',
                       buildarch='x86_64', is_final=True, nomacboot=True, noupgrade=True,
                       volid='vol_id', variant='Server', buildinstallpackages=['bash', 'vim'],
                       bugurl='http://example.com'),
             mock.call('Test', '1', '1', self.topdir + '/work/amd64/repo',
                       self.topdir + '/work/amd64/buildinstall/Server',
                       buildarch='amd64', is_final=True, nomacboot=True, noupgrade=False,
                       volid='vol_id', variant='Server', buildinstallpackages=['bash', 'vim'],
                       bugurl=None),
             mock.call('Test', '1', '1', self.topdir + '/work/amd64/repo',
                       self.topdir + '/work/amd64/buildinstall/Client',
                       buildarch='amd64', is_final=True, nomacboot=False, noupgrade=True,
                       volid='vol_id', variant='Client', buildinstallpackages=[],
                       bugurl=None)])
        self.assertItemsEqual(
            get_volid.mock_calls,
            [mock.call(compose, 'x86_64', variant=compose.variants['Server'], disc_type='dvd'),
             mock.call(compose, 'amd64', variant=compose.variants['Client'], disc_type='dvd'),
             mock.call(compose, 'amd64', variant=compose.variants['Server'], disc_type='dvd')])

    @mock.patch('pungi.phases.buildinstall.ThreadPool')
    @mock.patch('pungi.phases.buildinstall.LoraxWrapper')
    @mock.patch('pungi.phases.buildinstall.get_volid')
    def test_multiple_lorax_options(self, get_volid, loraxCls, poolCls):
        compose = BuildInstallCompose(self.topdir, {
            'bootable': True,
            'release_name': 'Test',
            'release_short': 't',
            'release_version': '1',
            'release_is_layered': False,
            'buildinstall_method': 'lorax',
            'lorax_options': [
                ('^.*$', {
                    'x86_64': {'nomacboot': False},
                    '*': {'noupgrade': False}
                }),
            ]
        })

        get_volid.return_value = 'vol_id'
        loraxCls.return_value.get_lorax_cmd.return_value = ['lorax', '...']

        phase = BuildinstallPhase(compose)

        phase.run()

        # Three items added for processing in total.
        # Server.x86_64, Client.amd64, Server.x86_64
        pool = poolCls.return_value
        self.assertEqual(3, len(pool.queue_put.mock_calls))
        self.assertItemsEqual(
            [call[0][0][3] for call in pool.queue_put.call_args_list],
            ['rm -rf %s/work/amd64/buildinstall/Client && lorax ...' % self.topdir,
             'rm -rf %s/work/amd64/buildinstall/Server && lorax ...' % self.topdir,
             'rm -rf %s/work/x86_64/buildinstall/Server && lorax ...' % self.topdir])

        # Obtained correct lorax commands.
        self.assertItemsEqual(
            loraxCls.return_value.get_lorax_cmd.mock_calls,
            [mock.call('Test', '1', '1', self.topdir + '/work/x86_64/repo',
                       self.topdir + '/work/x86_64/buildinstall/Server',
                       buildarch='x86_64', is_final=True, nomacboot=False, noupgrade=False,
                       volid='vol_id', variant='Server', buildinstallpackages=['bash', 'vim'],
                       bugurl=None),
             mock.call('Test', '1', '1', self.topdir + '/work/amd64/repo',
                       self.topdir + '/work/amd64/buildinstall/Server',
                       buildarch='amd64', is_final=True, nomacboot=True, noupgrade=False,
                       volid='vol_id', variant='Server', buildinstallpackages=['bash', 'vim'],
                       bugurl=None),
             mock.call('Test', '1', '1', self.topdir + '/work/amd64/repo',
                       self.topdir + '/work/amd64/buildinstall/Client',
                       buildarch='amd64', is_final=True, nomacboot=True, noupgrade=False,
                       volid='vol_id', variant='Client', buildinstallpackages=[],
                       bugurl=None)])
        self.assertItemsEqual(
            get_volid.mock_calls,
            [mock.call(compose, 'x86_64', variant=compose.variants['Server'], disc_type='dvd'),
             mock.call(compose, 'amd64', variant=compose.variants['Client'], disc_type='dvd'),
             mock.call(compose, 'amd64', variant=compose.variants['Server'], disc_type='dvd')])


class TestCopyFiles(PungiTestCase):

    @mock.patch('pungi.phases.buildinstall.link_boot_iso')
    @mock.patch('pungi.phases.buildinstall.tweak_buildinstall')
    @mock.patch('pungi.phases.buildinstall.get_volid')
    @mock.patch('os.listdir')
    @mock.patch('os.path.isdir')
    @mock.patch('pungi.phases.buildinstall.get_kickstart_file')
    def test_copy_files_buildinstall(self, get_kickstart_file, isdir, listdir,
                                     get_volid, tweak_buildinstall, link_boot_iso):
        compose = BuildInstallCompose(self.topdir, {
            'buildinstall_method': 'buildinstall'
        })

        get_volid.side_effect = (
            lambda compose, arch, variant, escape_spaces, disc_type: "%s.%s" % (variant.uid, arch)
        )
        get_kickstart_file.return_value = 'kickstart'

        phase = BuildinstallPhase(compose)
        phase.copy_files()

        self.assertItemsEqual(
            get_volid.mock_calls,
            [mock.call(compose, 'x86_64', compose.variants['Server'], escape_spaces=False, disc_type='dvd'),
             mock.call(compose, 'amd64', compose.variants['Client'], escape_spaces=False, disc_type='dvd'),
             mock.call(compose, 'amd64', compose.variants['Server'], escape_spaces=False, disc_type='dvd')])
        self.assertItemsEqual(
            tweak_buildinstall.mock_calls,
            [mock.call(self.topdir + '/work/x86_64/buildinstall',
                       self.topdir + '/compose/Server/x86_64/os',
                       'x86_64', 'Server', '', 'Server.x86_64', 'kickstart'),
             mock.call(self.topdir + '/work/amd64/buildinstall',
                       self.topdir + '/compose/Server/amd64/os',
                       'amd64', 'Server', '', 'Server.amd64', 'kickstart'),
             mock.call(self.topdir + '/work/amd64/buildinstall',
                       self.topdir + '/compose/Client/amd64/os',
                       'amd64', 'Client', '', 'Client.amd64', 'kickstart')])
        self.assertItemsEqual(
            link_boot_iso.mock_calls,
            [mock.call(compose, 'x86_64', compose.variants['Server'], False),
             mock.call(compose, 'amd64', compose.variants['Client'], False),
             mock.call(compose, 'amd64', compose.variants['Server'], False)])

    @mock.patch('pungi.phases.buildinstall.link_boot_iso')
    @mock.patch('pungi.phases.buildinstall.tweak_buildinstall')
    @mock.patch('pungi.phases.buildinstall.get_volid')
    @mock.patch('os.listdir')
    @mock.patch('os.path.isdir')
    @mock.patch('pungi.phases.buildinstall.get_kickstart_file')
    def test_copy_files_lorax(self, get_kickstart_file, isdir, listdir,
                              get_volid, tweak_buildinstall, link_boot_iso):
        compose = BuildInstallCompose(self.topdir, {
            'buildinstall_method': 'lorax'
        })

        get_volid.side_effect = (
            lambda compose, arch, variant, escape_spaces, disc_type: "%s.%s" % (variant.uid, arch)
        )
        get_kickstart_file.return_value = 'kickstart'

        phase = BuildinstallPhase(compose)
        phase.copy_files()

        self.assertItemsEqual(
            get_volid.mock_calls,
            [mock.call(compose, 'x86_64', compose.variants['Server'], escape_spaces=False, disc_type='dvd'),
             mock.call(compose, 'amd64', compose.variants['Client'], escape_spaces=False, disc_type='dvd'),
             mock.call(compose, 'amd64', compose.variants['Server'], escape_spaces=False, disc_type='dvd')])
        self.assertItemsEqual(
            tweak_buildinstall.mock_calls,
            [mock.call(self.topdir + '/work/x86_64/buildinstall/Server',
                       self.topdir + '/compose/Server/x86_64/os',
                       'x86_64', 'Server', '', 'Server.x86_64', 'kickstart'),
             mock.call(self.topdir + '/work/amd64/buildinstall/Server',
                       self.topdir + '/compose/Server/amd64/os',
                       'amd64', 'Server', '', 'Server.amd64', 'kickstart'),
             mock.call(self.topdir + '/work/amd64/buildinstall/Client',
                       self.topdir + '/compose/Client/amd64/os',
                       'amd64', 'Client', '', 'Client.amd64', 'kickstart')])
        self.assertItemsEqual(
            link_boot_iso.mock_calls,
            [mock.call(compose, 'x86_64', compose.variants['Server'], False),
             mock.call(compose, 'amd64', compose.variants['Client'], False),
             mock.call(compose, 'amd64', compose.variants['Server'], False)])

    @mock.patch('pungi.phases.buildinstall.link_boot_iso')
    @mock.patch('pungi.phases.buildinstall.tweak_buildinstall')
    @mock.patch('pungi.phases.buildinstall.get_volid')
    @mock.patch('os.listdir')
    @mock.patch('os.path.isdir')
    @mock.patch('pungi.phases.buildinstall.get_kickstart_file')
    def test_copy_fail(self, get_kickstart_file, isdir, listdir,
                       get_volid, tweak_buildinstall, link_boot_iso):
        compose = BuildInstallCompose(self.topdir, {
            'buildinstall_method': 'lorax',
            'failable_deliverables': [
                ('^.+$', {'*': ['buildinstall']})
            ],
        })

        get_volid.side_effect = (
            lambda compose, arch, variant, escape_spaces, disc_type: "%s.%s" % (variant.uid, arch)
        )
        get_kickstart_file.return_value = 'kickstart'
        tweak_buildinstall.side_effect = boom

        phase = BuildinstallPhase(compose)
        phase.copy_files()

        self.assertItemsEqual(
            get_volid.mock_calls,
            [mock.call(compose, 'x86_64', compose.variants['Server'], escape_spaces=False, disc_type='dvd'),
             mock.call(compose, 'amd64', compose.variants['Client'], escape_spaces=False, disc_type='dvd'),
             mock.call(compose, 'amd64', compose.variants['Server'], escape_spaces=False, disc_type='dvd')])
        self.assertItemsEqual(
            tweak_buildinstall.mock_calls,
            [mock.call(self.topdir + '/work/x86_64/buildinstall/Server',
                       self.topdir + '/compose/Server/x86_64/os',
                       'x86_64', 'Server', '', 'Server.x86_64', 'kickstart'),
             mock.call(self.topdir + '/work/amd64/buildinstall/Server',
                       self.topdir + '/compose/Server/amd64/os',
                       'amd64', 'Server', '', 'Server.amd64', 'kickstart'),
             mock.call(self.topdir + '/work/amd64/buildinstall/Client',
                       self.topdir + '/compose/Client/amd64/os',
                       'amd64', 'Client', '', 'Client.amd64', 'kickstart')])
        self.assertItemsEqual(link_boot_iso.mock_calls, [])


class BuildinstallThreadTestCase(PungiTestCase):

    @mock.patch('pungi.phases.buildinstall.KojiWrapper')
    @mock.patch('pungi.phases.buildinstall.get_buildroot_rpms')
    @mock.patch('pungi.phases.buildinstall.run')
    def test_buildinstall_thread_with_lorax_in_runroot(self, run, get_buildroot_rpms, KojiWrapperMock):
        compose = BuildInstallCompose(self.topdir, {
            'buildinstall_method': 'lorax',
            'runroot': True,
            'runroot_tag': 'rrt',
            'koji_profile': 'koji',
        })

        get_buildroot_rpms.return_value = ['bash', 'zsh']
        pool = mock.Mock()
        cmd = mock.Mock()

        get_runroot_cmd = KojiWrapperMock.return_value.get_runroot_cmd

        run_runroot_cmd = KojiWrapperMock.return_value.run_runroot_cmd
        run_runroot_cmd.return_value = {
            'output': 'Foo bar baz',
            'retcode': 0,
            'task_id': 1234,
        }

        t = BuildinstallThread(pool)

        with mock.patch('time.sleep'):
            t.process((compose, 'x86_64', compose.variants['Server'], cmd), 0)

        self.assertItemsEqual(
            get_runroot_cmd.mock_calls,
            [mock.call('rrt', 'x86_64', cmd, channel=None,
                       use_shell=True, task_id=True,
                       packages=['strace', 'lorax'], mounts=[self.topdir])])
        self.assertItemsEqual(
            run_runroot_cmd.mock_calls,
            [mock.call(get_runroot_cmd.return_value,
                       log_file=self.topdir + '/logs/x86_64/buildinstall-Server.x86_64.log')])
        with open(self.topdir + '/logs/x86_64/buildinstall-Server-RPMs.x86_64.log') as f:
            rpms = f.read().strip().split('\n')
        self.assertItemsEqual(rpms, ['bash', 'zsh'])

    @mock.patch('pungi.phases.buildinstall.KojiWrapper')
    @mock.patch('pungi.phases.buildinstall.get_buildroot_rpms')
    @mock.patch('pungi.phases.buildinstall.run')
    def test_buildinstall_thread_with_buildinstall_in_runroot(self, run, get_buildroot_rpms, KojiWrapperMock):
        compose = BuildInstallCompose(self.topdir, {
            'buildinstall_method': 'buildinstall',
            'runroot': True,
            'runroot_tag': 'rrt',
            'koji_profile': 'koji',
        })

        get_buildroot_rpms.return_value = ['bash', 'zsh']
        pool = mock.Mock()
        cmd = mock.Mock()

        get_runroot_cmd = KojiWrapperMock.return_value.get_runroot_cmd

        run_runroot_cmd = KojiWrapperMock.return_value.run_runroot_cmd
        run_runroot_cmd.return_value = {
            'output': 'Foo bar baz',
            'retcode': 0,
            'task_id': 1234,
        }

        t = BuildinstallThread(pool)

        with mock.patch('time.sleep'):
            t.process((compose, 'x86_64', None, cmd), 0)

        self.assertItemsEqual(
            get_runroot_cmd.mock_calls,
            [mock.call('rrt', 'x86_64', cmd, channel=None,
                       use_shell=True, task_id=True,
                       packages=['strace', 'anaconda'], mounts=[self.topdir])])
        self.assertItemsEqual(
            run_runroot_cmd.mock_calls,
            [mock.call(get_runroot_cmd.return_value,
                       log_file=self.topdir + '/logs/x86_64/buildinstall.x86_64.log')])
        with open(self.topdir + '/logs/x86_64/buildinstall-RPMs.x86_64.log') as f:
            rpms = f.read().strip().split('\n')
        self.assertItemsEqual(rpms, ['bash', 'zsh'])

    @mock.patch('pungi.phases.buildinstall.KojiWrapper')
    @mock.patch('pungi.phases.buildinstall.get_buildroot_rpms')
    @mock.patch('pungi.phases.buildinstall.run')
    def test_buildinstall_fail_exit_code(self, run, get_buildroot_rpms, KojiWrapperMock):
        compose = BuildInstallCompose(self.topdir, {
            'buildinstall_method': 'buildinstall',
            'runroot': True,
            'runroot_tag': 'rrt',
            'koji_profile': 'koji',
            'failable_deliverables': [
                ('^.+$', {'*': ['buildinstall']})
            ],
        })

        get_buildroot_rpms.return_value = ['bash', 'zsh']
        pool = mock.Mock()
        cmd = mock.Mock()

        run_runroot_cmd = KojiWrapperMock.return_value.run_runroot_cmd
        run_runroot_cmd.return_value = {
            'output': 'Foo bar baz',
            'retcode': 1,
            'task_id': 1234,
        }

        t = BuildinstallThread(pool)

        with mock.patch('time.sleep'):
            t.process((compose, 'x86_64', None, cmd), 0)

        compose.log_info.assert_has_calls([
            mock.call('[FAIL] Buildinstall (variant None, arch x86_64) failed, but going on anyway.'),
            mock.call('Runroot task failed: 1234. See %s/logs/x86_64/buildinstall.x86_64.log for more details.'
                      % self.topdir)
        ])

    @mock.patch('pungi.phases.buildinstall.KojiWrapper')
    @mock.patch('pungi.phases.buildinstall.get_buildroot_rpms')
    @mock.patch('pungi.phases.buildinstall.run')
    def test_lorax_fail_exit_code(self, run, get_buildroot_rpms, KojiWrapperMock):
        compose = BuildInstallCompose(self.topdir, {
            'buildinstall_method': 'lorax',
            'runroot': True,
            'runroot_tag': 'rrt',
            'koji_profile': 'koji',
            'failable_deliverables': [
                ('^.+$', {'*': ['buildinstall']})
            ],
        })

        get_buildroot_rpms.return_value = ['bash', 'zsh']
        pool = mock.Mock()
        cmd = mock.Mock()

        run_runroot_cmd = KojiWrapperMock.return_value.run_runroot_cmd
        run_runroot_cmd.return_value = {
            'output': 'Foo bar baz',
            'retcode': 1,
            'task_id': 1234,
        }

        t = BuildinstallThread(pool)

        with mock.patch('time.sleep'):
            t.process((compose, 'x86_64', compose.variants['Server'], cmd), 0)

        compose.log_info.assert_has_calls([
            mock.call('[FAIL] Buildinstall (variant Server, arch x86_64) failed, but going on anyway.'),
            mock.call('Runroot task failed: 1234. See %s/logs/x86_64/buildinstall-Server.x86_64.log for more details.' % self.topdir)
        ])

    @mock.patch('pungi.phases.buildinstall.KojiWrapper')
    @mock.patch('pungi.phases.buildinstall.get_buildroot_rpms')
    @mock.patch('pungi.phases.buildinstall.run')
    def test_skips_on_existing_output_dir(self, run, get_buildroot_rpms, KojiWrapperMock):
        compose = BuildInstallCompose(self.topdir, {
            'buildinstall_method': 'lorax',
            'runroot': True,
            'runroot_tag': 'rrt',
            'koji_profile': 'koji',
            'failable_deliverables': [
                ('^.+$', {'*': ['buildinstall']})
            ],
        })

        get_buildroot_rpms.return_value = ['bash', 'zsh']
        pool = mock.Mock()
        cmd = mock.Mock()

        dummy_file = os.path.join(self.topdir, 'work/x86_64/buildinstall/Server/dummy')
        touch(os.path.join(dummy_file))

        t = BuildinstallThread(pool)

        with mock.patch('time.sleep'):
            t.process((compose, 'x86_64', compose.variants['Server'], cmd), 0)

        self.assertEqual(0, len(run.mock_calls))

        self.assertTrue(os.path.exists(dummy_file))


class TestSymlinkIso(PungiTestCase):

    def setUp(self):
        super(TestSymlinkIso, self).setUp()
        self.compose = BuildInstallCompose(self.topdir, {})
        os_tree = self.compose.paths.compose.os_tree('x86_64', self.compose.variants['Server'])
        self.boot_iso_path = os.path.join(os_tree, "images", "boot.iso")
        touch(self.boot_iso_path)

    @mock.patch('pungi.phases.buildinstall.Image')
    @mock.patch('pungi.phases.buildinstall.get_mtime')
    @mock.patch('pungi.phases.buildinstall.get_file_size')
    @mock.patch('pungi.phases.buildinstall.iso')
    @mock.patch('pungi.phases.buildinstall.run')
    def test_hardlink(self, run, iso, get_file_size, get_mtime, ImageCls):
        self.compose.conf = {'buildinstall_symlink': False, 'disc_types': {}}
        get_file_size.return_value = 1024
        get_mtime.return_value = 13579

        link_boot_iso(self.compose, 'x86_64', self.compose.variants['Server'], False)

        tgt = self.topdir + '/compose/Server/x86_64/iso/image-name'
        self.assertTrue(os.path.isfile(tgt))
        self.assertEqual(os.stat(tgt).st_ino,
                         os.stat(self.topdir + '/compose/Server/x86_64/os/images/boot.iso').st_ino)

        self.assertItemsEqual(
            self.compose.get_image_name.mock_calls,
            [mock.call('x86_64', self.compose.variants['Server'],
                       disc_type='boot', disc_num=None, suffix='.iso')])
        self.assertItemsEqual(iso.get_implanted_md5.mock_calls,
                              [mock.call(tgt)])
        self.assertItemsEqual(iso.get_manifest_cmd.mock_calls,
                              [mock.call('image-name')])
        self.assertItemsEqual(iso.get_volume_id.mock_calls,
                              [mock.call(tgt)])
        self.assertItemsEqual(run.mock_calls,
                              [mock.call(iso.get_manifest_cmd.return_value,
                                         workdir=self.topdir + '/compose/Server/x86_64/iso')])

        image = ImageCls.return_value
        self.assertEqual(image.path, 'Server/x86_64/iso/image-name')
        self.assertEqual(image.mtime, 13579)
        self.assertEqual(image.size, 1024)
        self.assertEqual(image.arch, 'x86_64')
        self.assertEqual(image.type, "boot")
        self.assertEqual(image.format, "iso")
        self.assertEqual(image.disc_number, 1)
        self.assertEqual(image.disc_count, 1)
        self.assertEqual(image.bootable, True)
        self.assertEqual(image.implant_md5, iso.get_implanted_md5.return_value)
        self.assertEqual(image.can_fail, False)
        self.assertEqual(self.compose.im.add.mock_calls,
                         [mock.call('Server', 'x86_64', image)])

    @mock.patch('pungi.phases.buildinstall.Image')
    @mock.patch('pungi.phases.buildinstall.get_mtime')
    @mock.patch('pungi.phases.buildinstall.get_file_size')
    @mock.patch('pungi.phases.buildinstall.iso')
    @mock.patch('pungi.phases.buildinstall.run')
    def test_hardlink_with_custom_type(self, run, iso, get_file_size, get_mtime, ImageCls):
        self.compose.conf = {
            'buildinstall_symlink': False,
            'disc_types': {'boot': 'netinst'},
        }
        get_file_size.return_value = 1024
        get_mtime.return_value = 13579

        link_boot_iso(self.compose, 'x86_64', self.compose.variants['Server'], True)

        tgt = self.topdir + '/compose/Server/x86_64/iso/image-name'
        self.assertTrue(os.path.isfile(tgt))
        self.assertEqual(os.stat(tgt).st_ino,
                         os.stat(self.topdir + '/compose/Server/x86_64/os/images/boot.iso').st_ino)

        self.assertItemsEqual(
            self.compose.get_image_name.mock_calls,
            [mock.call('x86_64', self.compose.variants['Server'],
                       disc_type='netinst', disc_num=None, suffix='.iso')])
        self.assertItemsEqual(iso.get_implanted_md5.mock_calls,
                              [mock.call(tgt)])
        self.assertItemsEqual(iso.get_manifest_cmd.mock_calls,
                              [mock.call('image-name')])
        self.assertItemsEqual(iso.get_volume_id.mock_calls,
                              [mock.call(tgt)])
        self.assertItemsEqual(run.mock_calls,
                              [mock.call(iso.get_manifest_cmd.return_value,
                                         workdir=self.topdir + '/compose/Server/x86_64/iso')])

        image = ImageCls.return_value
        self.assertEqual(image.path, 'Server/x86_64/iso/image-name')
        self.assertEqual(image.mtime, 13579)
        self.assertEqual(image.size, 1024)
        self.assertEqual(image.arch, 'x86_64')
        self.assertEqual(image.type, "boot")
        self.assertEqual(image.format, "iso")
        self.assertEqual(image.disc_number, 1)
        self.assertEqual(image.disc_count, 1)
        self.assertEqual(image.bootable, True)
        self.assertEqual(image.implant_md5, iso.get_implanted_md5.return_value)
        self.assertEqual(image.can_fail, True)
        self.assertEqual(self.compose.im.add.mock_calls,
                         [mock.call('Server', 'x86_64', image)])


if __name__ == "__main__":
    unittest.main()
