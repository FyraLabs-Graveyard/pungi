#!/usr/bin/env python2
# -*- coding: utf-8 -*-


import unittest
import mock

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi.phases.buildinstall import BuildinstallPhase


class _DummyCompose(object):
    def __init__(self, config):
        self.conf = config
        self.paths = mock.Mock(
            compose=mock.Mock(
                topdir=mock.Mock(return_value='/a/b'),
                os_tree=mock.Mock(side_effect=lambda arch, variant: os.path.join('/ostree', arch, variant.uid))
            ),
            work=mock.Mock(
                arch_repo=mock.Mock(return_value='file:///a/b/'),
                buildinstall_dir=mock.Mock(side_effect=lambda x: '/buildinstall_dir/' + x),
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


class TestImageChecksumPhase(unittest.TestCase):

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
                       volid='vol_id', variant='Server', buildinstallpackages=['bash', 'vim']),
             mock.call('Test', '1', '1', 'file:///a/b/', '/buildinstall_dir/amd64/Server',
                       buildarch='amd64', is_final=True, nomacboot=True, noupgrade=True,
                       volid='vol_id', variant='Server', buildinstallpackages=['bash', 'vim']),
             mock.call('Test', '1', '1', 'file:///a/b/', '/buildinstall_dir/amd64/Client',
                       buildarch='amd64', is_final=True, nomacboot=True, noupgrade=True,
                       volid='vol_id', variant='Client', buildinstallpackages=[])],
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

        get_volid.side_effect = lambda compose, arch, variant, escape_spaces: "%s.%s" % (variant.uid, arch)
        get_kickstart_file.return_value = 'kickstart'

        phase = BuildinstallPhase(compose)
        phase.copy_files()

        get_volid.assert_has_calls(
            [mock.call(compose, 'x86_64', compose.variants['x86_64'][0], escape_spaces=False),
             mock.call(compose, 'amd64', compose.variants['amd64'][0], escape_spaces=False),
             mock.call(compose, 'amd64', compose.variants['amd64'][1], escape_spaces=False)],
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

        get_volid.side_effect = lambda compose, arch, variant, escape_spaces: "%s.%s" % (variant.uid, arch)
        get_kickstart_file.return_value = 'kickstart'

        phase = BuildinstallPhase(compose)
        phase.copy_files()

        get_volid.assert_has_calls(
            [mock.call(compose, 'x86_64', compose.variants['x86_64'][0], escape_spaces=False),
             mock.call(compose, 'amd64', compose.variants['amd64'][0], escape_spaces=False),
             mock.call(compose, 'amd64', compose.variants['amd64'][1], escape_spaces=False)],
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

if __name__ == "__main__":
    unittest.main()
