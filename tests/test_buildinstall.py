#!/usr/bin/env python2
# -*- coding: utf-8 -*-


import unittest
import mock

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi.phases.buildinstall import BuildinstallPhase, BuildinstallThread
from pungi.util import get_arch_variant_data


class _DummyCompose(object):
    def __init__(self, config):
        self.conf = config
        self.topdir = '/topdir'
        self.paths = mock.Mock(
            compose=mock.Mock(
                topdir=mock.Mock(return_value='/a/b'),
                os_tree=mock.Mock(side_effect=lambda arch, variant: os.path.join('/ostree', arch, variant.uid))
            ),
            work=mock.Mock(
                arch_repo=mock.Mock(return_value='file:///a/b/'),
                buildinstall_dir=mock.Mock(side_effect=lambda x: '/buildinstall_dir/' + x),
            ),
            log=mock.Mock(
                log_file=mock.Mock(side_effect=lambda arch, filename: '/log/%s.%s.log' % (filename, arch)),
            )
        )
        self._logger = mock.Mock()
        self.log_debug = mock.Mock()
        self.supported = True
        self.variants = {
            'x86_64': [mock.Mock(uid='Server', buildinstallpackages=['bash', 'vim'])],
            'amd64': [mock.Mock(uid='Client', buildinstallpackages=[]),
                      mock.Mock(uid='Server', buildinstallpackages=['bash', 'vim'])],
        }

    def get_arches(self):
        return ['x86_64', 'amd64']

    def get_variants(self, arch, types):
        return self.variants.get(arch, [])

    def can_fail(self, variant, arch, deliverable):
        failable = get_arch_variant_data(self.conf, 'failable_deliverables', arch, variant)
        return deliverable in failable


class TestBuildinstallPhase(unittest.TestCase):

    def test_config_skip_unless_bootable(self):
        compose = _DummyCompose({})
        compose.just_phases = None
        compose.skip_phases = []

        phase = BuildinstallPhase(compose)

        self.assertTrue(phase.skip())

    def test_does_not_skip_on_bootable(self):
        compose = _DummyCompose({'bootable': True})
        compose.just_phases = None
        compose.skip_phases = []

        phase = BuildinstallPhase(compose)

        self.assertFalse(phase.skip())

    @mock.patch('pungi.phases.buildinstall.ThreadPool')
    @mock.patch('pungi.phases.buildinstall.LoraxWrapper')
    @mock.patch('pungi.phases.buildinstall.get_volid')
    def test_starts_threads_for_each_cmd_with_lorax(self, get_volid, loraxCls, poolCls):
        compose = _DummyCompose({
            'bootable': True,
            'release_name': 'Test',
            'release_short': 't',
            'release_version': '1',
            'release_is_layered': False,
            'buildinstall_method': 'lorax'
        })

        get_volid.return_value = 'vol_id'

        phase = BuildinstallPhase(compose)

        phase.run()

        # Three items added for processing in total.
        # Server.x86_64, Client.amd64, Server.x86_64
        pool = poolCls.return_value
        self.assertEqual(3, len(pool.queue_put.mock_calls))

        # Obtained correct lorax commands.
        lorax = loraxCls.return_value
        lorax.get_lorax_cmd.assert_has_calls(
            [mock.call('Test', '1', '1', 'file:///a/b/', '/buildinstall_dir/x86_64/Server',
                       buildarch='x86_64', is_final=True, nomacboot=True, noupgrade=True,
                       volid='vol_id', variant='Server', buildinstallpackages=['bash', 'vim'],
                       bugurl=None),
             mock.call('Test', '1', '1', 'file:///a/b/', '/buildinstall_dir/amd64/Server',
                       buildarch='amd64', is_final=True, nomacboot=True, noupgrade=True,
                       volid='vol_id', variant='Server', buildinstallpackages=['bash', 'vim'],
                       bugurl=None),
             mock.call('Test', '1', '1', 'file:///a/b/', '/buildinstall_dir/amd64/Client',
                       buildarch='amd64', is_final=True, nomacboot=True, noupgrade=True,
                       volid='vol_id', variant='Client', buildinstallpackages=[],
                       bugurl=None)],
            any_order=True)

    @mock.patch('pungi.phases.buildinstall.ThreadPool')
    @mock.patch('pungi.phases.buildinstall.LoraxWrapper')
    @mock.patch('pungi.phases.buildinstall.get_volid')
    def test_starts_threads_for_each_cmd_with_buildinstall(self, get_volid, loraxCls, poolCls):
        compose = _DummyCompose({
            'bootable': True,
            'release_name': 'Test',
            'release_short': 't',
            'release_version': '1',
            'release_is_layered': False,
            'buildinstall_method': 'buildinstall'
        })

        get_volid.return_value = 'vol_id'

        phase = BuildinstallPhase(compose)

        phase.run()

        # Two items added for processing in total.
        pool = poolCls.return_value
        self.assertEqual(2, len(pool.queue_put.mock_calls))

        # Obtained correct lorax commands.
        lorax = loraxCls.return_value
        lorax.get_buildinstall_cmd.assert_has_calls(
            [mock.call('Test', '1', '1', 'file:///a/b/', '/buildinstall_dir/x86_64',
                       buildarch='x86_64', is_final=True, volid='vol_id'),
             mock.call('Test', '1', '1', 'file:///a/b/', '/buildinstall_dir/amd64',
                       buildarch='amd64', is_final=True, volid='vol_id')],
            any_order=True)

    def test_global_upgrade_with_lorax(self):
        compose = _DummyCompose({
            'bootable': True,
            'buildinstall_method': 'lorax',
            'buildinstall_upgrade_image': True,
        })

        phase = BuildinstallPhase(compose)

        with self.assertRaises(ValueError) as ctx:
            phase.validate()

        self.assertIn('Deprecated config option: buildinstall_upgrade_image',
                      ctx.exception.message)

    def test_lorax_options_with_buildinstall(self):
        compose = _DummyCompose({
            'bootable': True,
            'buildinstall_method': 'buildinstall',
            'lorax_options': [],
        })

        phase = BuildinstallPhase(compose)

        with self.assertRaises(ValueError) as ctx:
            phase.validate()

        self.assertIn('buildinstall', ctx.exception.message)
        self.assertIn('lorax_options', ctx.exception.message)

    @mock.patch('pungi.phases.buildinstall.ThreadPool')
    @mock.patch('pungi.phases.buildinstall.LoraxWrapper')
    @mock.patch('pungi.phases.buildinstall.get_volid')
    def test_uses_lorax_options(self, get_volid, loraxCls, poolCls):
        compose = _DummyCompose({
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

        phase = BuildinstallPhase(compose)

        phase.run()

        # Three items added for processing in total.
        # Server.x86_64, Client.amd64, Server.x86_64
        pool = poolCls.return_value
        self.assertEqual(3, len(pool.queue_put.mock_calls))

        # Obtained correct lorax commands.
        lorax = loraxCls.return_value
        lorax.get_lorax_cmd.assert_has_calls(
            [mock.call('Test', '1', '1', 'file:///a/b/', '/buildinstall_dir/x86_64/Server',
                       buildarch='x86_64', is_final=True, nomacboot=True, noupgrade=True,
                       volid='vol_id', variant='Server', buildinstallpackages=['bash', 'vim'],
                       bugurl='http://example.com'),
             mock.call('Test', '1', '1', 'file:///a/b/', '/buildinstall_dir/amd64/Server',
                       buildarch='amd64', is_final=True, nomacboot=True, noupgrade=False,
                       volid='vol_id', variant='Server', buildinstallpackages=['bash', 'vim'],
                       bugurl=None),
             mock.call('Test', '1', '1', 'file:///a/b/', '/buildinstall_dir/amd64/Client',
                       buildarch='amd64', is_final=True, nomacboot=False, noupgrade=True,
                       volid='vol_id', variant='Client', buildinstallpackages=[],
                       bugurl=None)],
            any_order=True)

    @mock.patch('pungi.phases.buildinstall.ThreadPool')
    @mock.patch('pungi.phases.buildinstall.LoraxWrapper')
    @mock.patch('pungi.phases.buildinstall.get_volid')
    def test_multiple_lorax_options(self, get_volid, loraxCls, poolCls):
        compose = _DummyCompose({
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

        phase = BuildinstallPhase(compose)

        phase.run()

        # Three items added for processing in total.
        # Server.x86_64, Client.amd64, Server.x86_64
        pool = poolCls.return_value
        self.assertEqual(3, len(pool.queue_put.mock_calls))

        # Obtained correct lorax commands.
        lorax = loraxCls.return_value
        lorax.get_lorax_cmd.assert_has_calls(
            [mock.call('Test', '1', '1', 'file:///a/b/', '/buildinstall_dir/x86_64/Server',
                       buildarch='x86_64', is_final=True, nomacboot=False, noupgrade=False,
                       volid='vol_id', variant='Server', buildinstallpackages=['bash', 'vim'],
                       bugurl=None),
             mock.call('Test', '1', '1', 'file:///a/b/', '/buildinstall_dir/amd64/Server',
                       buildarch='amd64', is_final=True, nomacboot=True, noupgrade=False,
                       volid='vol_id', variant='Server', buildinstallpackages=['bash', 'vim'],
                       bugurl=None),
             mock.call('Test', '1', '1', 'file:///a/b/', '/buildinstall_dir/amd64/Client',
                       buildarch='amd64', is_final=True, nomacboot=True, noupgrade=False,
                       volid='vol_id', variant='Client', buildinstallpackages=[],
                       bugurl=None)],
            any_order=True)


class TestCopyFiles(unittest.TestCase):

    @mock.patch('pungi.phases.buildinstall.symlink_boot_iso')
    @mock.patch('pungi.phases.buildinstall.tweak_buildinstall')
    @mock.patch('pungi.phases.buildinstall.get_volid')
    @mock.patch('os.listdir')
    @mock.patch('os.path.isdir')
    @mock.patch('pungi.phases.buildinstall.get_kickstart_file')
    def test_copy_files_buildinstall(self, get_kickstart_file, isdir, listdir,
                                     get_volid, tweak_buildinstall, symlink_boot_iso):
        compose = _DummyCompose({
            'buildinstall_method': 'buildinstall'
        })

        get_volid.side_effect = (
            lambda compose, arch, variant, escape_spaces, disc_type: "%s.%s" % (variant.uid, arch)
        )
        get_kickstart_file.return_value = 'kickstart'

        phase = BuildinstallPhase(compose)
        phase.copy_files()

        get_volid.assert_has_calls(
            [mock.call(compose, 'x86_64', compose.variants['x86_64'][0], escape_spaces=False, disc_type='boot'),
             mock.call(compose, 'amd64', compose.variants['amd64'][0], escape_spaces=False, disc_type='boot'),
             mock.call(compose, 'amd64', compose.variants['amd64'][1], escape_spaces=False, disc_type='boot')],
            any_order=True
        )
        tweak_buildinstall.assert_has_calls(
            [mock.call('/buildinstall_dir/x86_64', '/ostree/x86_64/Server', 'x86_64', 'Server', '',
                       'Server.x86_64', 'kickstart'),
             mock.call('/buildinstall_dir/amd64', '/ostree/amd64/Server', 'amd64', 'Server', '',
                       'Server.amd64', 'kickstart'),
             mock.call('/buildinstall_dir/amd64', '/ostree/amd64/Client', 'amd64', 'Client', '',
                       'Client.amd64', 'kickstart')],
            any_order=True
        )
        symlink_boot_iso.assert_has_calls(
            [mock.call(compose, 'x86_64', compose.variants['x86_64'][0]),
             mock.call(compose, 'amd64', compose.variants['amd64'][0]),
             mock.call(compose, 'amd64', compose.variants['amd64'][1])],
            any_order=True
        )

    @mock.patch('pungi.phases.buildinstall.symlink_boot_iso')
    @mock.patch('pungi.phases.buildinstall.tweak_buildinstall')
    @mock.patch('pungi.phases.buildinstall.get_volid')
    @mock.patch('os.listdir')
    @mock.patch('os.path.isdir')
    @mock.patch('pungi.phases.buildinstall.get_kickstart_file')
    def test_copy_files_lorax(self, get_kickstart_file, isdir, listdir,
                              get_volid, tweak_buildinstall, symlink_boot_iso):
        compose = _DummyCompose({
            'buildinstall_method': 'lorax'
        })

        get_volid.side_effect = (
            lambda compose, arch, variant, escape_spaces, disc_type: "%s.%s" % (variant.uid, arch)
        )
        get_kickstart_file.return_value = 'kickstart'

        phase = BuildinstallPhase(compose)
        phase.copy_files()

        get_volid.assert_has_calls(
            [mock.call(compose, 'x86_64', compose.variants['x86_64'][0], escape_spaces=False, disc_type='boot'),
             mock.call(compose, 'amd64', compose.variants['amd64'][0], escape_spaces=False, disc_type='boot'),
             mock.call(compose, 'amd64', compose.variants['amd64'][1], escape_spaces=False, disc_type='boot')],
            any_order=True
        )
        tweak_buildinstall.assert_has_calls(
            [mock.call('/buildinstall_dir/x86_64/Server', '/ostree/x86_64/Server', 'x86_64', 'Server', '',
                       'Server.x86_64', 'kickstart'),
             mock.call('/buildinstall_dir/amd64/Server', '/ostree/amd64/Server', 'amd64', 'Server', '',
                       'Server.amd64', 'kickstart'),
             mock.call('/buildinstall_dir/amd64/Client', '/ostree/amd64/Client', 'amd64', 'Client', '',
                       'Client.amd64', 'kickstart')],
            any_order=True
        )
        symlink_boot_iso.assert_has_calls(
            [mock.call(compose, 'x86_64', compose.variants['x86_64'][0]),
             mock.call(compose, 'amd64', compose.variants['amd64'][0]),
             mock.call(compose, 'amd64', compose.variants['amd64'][1])],
            any_order=True
        )


class BuildinstallThreadTestCase(unittest.TestCase):

    @mock.patch('pungi.phases.buildinstall.KojiWrapper')
    @mock.patch('pungi.phases.buildinstall.get_buildroot_rpms')
    @mock.patch('pungi.phases.buildinstall.open')
    @mock.patch('pungi.phases.buildinstall.run')
    def test_buildinstall_thread_with_lorax_in_runroot(self, run, mock_open,
                                                       get_buildroot_rpms, KojiWrapperMock):
        compose = _DummyCompose({
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
            t.process((compose, 'x86_64', compose.variants['x86_64'][0], cmd), 0)

        get_runroot_cmd.assert_has_calls([
            mock.call('rrt', 'x86_64', cmd, channel=None,
                      use_shell=True, task_id=True,
                      packages=['strace', 'lorax'], mounts=['/topdir'])
        ])
        run_runroot_cmd(get_runroot_cmd.return_value, log_file='/log/buildinstall-Server.x86_64.log')
        mock_open.return_value.write.assert_has_calls([
            mock.call('bash\nzsh')
        ])

    @mock.patch('pungi.phases.buildinstall.KojiWrapper')
    @mock.patch('pungi.phases.buildinstall.get_buildroot_rpms')
    @mock.patch('pungi.phases.buildinstall.open')
    @mock.patch('pungi.phases.buildinstall.run')
    def test_buildinstall_thread_with_buildinstall_in_runroot(self, run, mock_open,
                                                              get_buildroot_rpms, KojiWrapperMock):
        compose = _DummyCompose({
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

        get_runroot_cmd.assert_has_calls([
            mock.call('rrt', 'x86_64', cmd, channel=None,
                      use_shell=True, task_id=True,
                      packages=['strace', 'anaconda'], mounts=['/topdir'])
        ])
        run_runroot_cmd(get_runroot_cmd.return_value, log_file='/log/buildinstall.x86_64.log')
        mock_open.return_value.write.assert_has_calls([
            mock.call('bash\nzsh')
        ])

    @mock.patch('pungi.phases.buildinstall.KojiWrapper')
    @mock.patch('pungi.phases.buildinstall.get_buildroot_rpms')
    @mock.patch('pungi.phases.buildinstall.open')
    @mock.patch('pungi.phases.buildinstall.run')
    def test_buildinstall_fail_exit_code(self, run, mock_open,
                                         get_buildroot_rpms, KojiWrapperMock):
        compose = _DummyCompose({
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

        pool.log_info.assert_has_calls([
            mock.call('[BEGIN] Running buildinstall for arch x86_64'),
            mock.call('[FAIL] Buildinstall for variant None arch x86_64 failed, but going on anyway.\nRunroot task failed: 1234. See /log/buildinstall.x86_64.log for more details.')
        ])

    @mock.patch('pungi.phases.buildinstall.KojiWrapper')
    @mock.patch('pungi.phases.buildinstall.get_buildroot_rpms')
    @mock.patch('pungi.phases.buildinstall.open')
    @mock.patch('pungi.phases.buildinstall.run')
    def test_lorax_fail_exit_code(self, run, mock_open,
                                  get_buildroot_rpms, KojiWrapperMock):
        compose = _DummyCompose({
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
            t.process((compose, 'x86_64', compose.variants['x86_64'][0], cmd), 0)

        pool.log_info.assert_has_calls([
            mock.call('[BEGIN] Running buildinstall for arch x86_64'),
            mock.call('[FAIL] Buildinstall for variant Server arch x86_64 failed, but going on anyway.\nRunroot task failed: 1234. See /log/buildinstall-Server.x86_64.log for more details.')
        ])


if __name__ == "__main__":
    unittest.main()
