#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import mock
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi.notifier import PungiNotifier


class TestNotifier(unittest.TestCase):
    @mock.patch('pungi.paths.translate_path')
    @mock.patch('kobo.shortcuts.run')
    def test_invokes_script(self, run, translate_path):
        compose = mock.Mock(
            compose_id='COMPOSE_ID',
            paths=mock.Mock(
                compose=mock.Mock(
                    topdir=mock.Mock(return_value='/a/b')
                )
            )
        )

        run.return_value = (0, None)
        translate_path.side_effect = lambda compose, x: x

        n = PungiNotifier('run-notify')
        n.compose = compose
        data = {'foo': 'bar', 'baz': 'quux'}
        n.send('cmd', **data)

        data['compose_id'] = 'COMPOSE_ID'
        data['location'] = '/a/b'
        run.assert_called_once_with(('run-notify', 'cmd'),
                                    stdin_data=json.dumps(data),
                                    can_fail=True, return_stdout=False, workdir='/a/b')

    @mock.patch('kobo.shortcuts.run')
    def test_does_not_run_without_config(self, run):
        n = PungiNotifier(None)
        n.send('cmd', foo='bar', baz='quux')
        self.assertFalse(run.called)

    @mock.patch('pungi.paths.translate_path')
    @mock.patch('kobo.shortcuts.run')
    def test_logs_warning_on_failure(self, run, translate_path):
        compose = mock.Mock(
            compose_id='COMPOSE_ID',
            log_warning=mock.Mock(),
            paths=mock.Mock(
                compose=mock.Mock(
                    topdir=mock.Mock(return_value='/a/b')
                )
            )
        )

        translate_path.side_effect = lambda compose, x: x
        run.return_value = (1, None)

        n = PungiNotifier('run-notify')
        n.compose = compose
        n.send('cmd')

        run.assert_called_once_with(('run-notify', 'cmd'),
                                    stdin_data=json.dumps({'compose_id': 'COMPOSE_ID', 'location': '/a/b'}),
                                    can_fail=True, return_stdout=False, workdir='/a/b')
        self.assertTrue(compose.log_warning.called)


if __name__ == "__main__":
    unittest.main()
