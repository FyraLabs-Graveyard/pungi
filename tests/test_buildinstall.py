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
                topdir=mock.Mock(return_value='/a/b')
            ),
            work=mock.Mock(
                arch_repo=mock.Mock(return_value='file:///a/b/'),
                buildinstall_dir=mock.Mock(side_effect=lambda x: '/buildinstall_dir/' + x),
            )
        )
        self._logger = mock.Mock()
        self.log_debug = mock.Mock()
        self.supported = True

    def get_arches(self):
        return ['x86_64', 'amd64']


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

        # Two items added for processing in total.
        pool = poolCls.return_value
        self.assertEqual(2, len(pool.queue_put.mock_calls))

        # Obtained correct lorax commands.
        lorax = loraxCls.return_value
        lorax.get_lorax_cmd.assert_has_calls(
            [mock.call('Test', '1', '1', 'file:///a/b/', '/buildinstall_dir/x86_64',
                       buildarch='x86_64', is_final=True, nomacboot=True, noupgrade=True, volid='vol_id'),
             mock.call('Test', '1', '1', 'file:///a/b/', '/buildinstall_dir/amd64',
                       buildarch='amd64', is_final=True, nomacboot=True, noupgrade=True, volid='vol_id')],
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


if __name__ == "__main__":
    unittest.main()
