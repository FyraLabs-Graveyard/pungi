#!/usr/bin/python
# -*- coding: utf-8 -*-

import json
import mock
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi.notifier import PungiNotifier


class TestNotifier(unittest.TestCase):
    def test_incorrect_config(self):
        compose = mock.Mock(
            conf={'notification_script': [1, 2]}
        )

        n = PungiNotifier(compose)
        with self.assertRaises(ValueError) as err:
            n.validate()
            self.assertIn('notification_script', err.message)

    @mock.patch('kobo.shortcuts.run')
    def test_invokes_script(self, run):
        compose = mock.Mock(
            compose_id='COMPOSE_ID',
            conf={'notification_script': 'run-notify'},
            paths=mock.Mock(
                compose=mock.Mock(
                    topdir=mock.Mock(return_value='/a/b')
                )
            )
        )

        run.return_value = (0, None)

        n = PungiNotifier(compose)
        data = {'foo': 'bar', 'baz': 'quux'}
        n.send('cmd', **data)

        data['compose_id'] = 'COMPOSE_ID'
        run.assert_called_once_with(('run-notify', 'cmd'),
                                    stdin_data=json.dumps(data),
                                    can_fail=True, return_stdout=False, workdir='/a/b')

    @mock.patch('kobo.shortcuts.run')
    def test_does_not_run_without_config(self, run):
        compose = mock.Mock(conf={})

        n = PungiNotifier(compose)
        n.send('cmd', foo='bar', baz='quux')
        self.assertFalse(run.called)

    @mock.patch('kobo.shortcuts.run')
    def test_logs_warning_on_failure(self, run):
        compose = mock.Mock(
            compose_id='COMPOSE_ID',
            log_warning=mock.Mock(),
            conf={'notification_script': 'run-notify'},
            paths=mock.Mock(
                compose=mock.Mock(
                    topdir=mock.Mock(return_value='/a/b')
                )
            )
        )

        run.return_value = (1, None)

        n = PungiNotifier(compose)
        n.send('cmd')

        run.assert_called_once_with(('run-notify', 'cmd'),
                                    stdin_data=json.dumps({'compose_id': 'COMPOSE_ID'}),
                                    can_fail=True, return_stdout=False, workdir='/a/b')
        self.assertTrue(compose.log_warning.called)


if __name__ == "__main__":
    unittest.main()
