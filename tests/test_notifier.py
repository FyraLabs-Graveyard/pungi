#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime
import json
import mock
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi.notifier import PungiNotifier


mock_datetime = mock.Mock()
mock_datetime.utcnow.return_value = datetime(2017, 6, 28, 9, 34)
mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)


@mock.patch('pungi.util.makedirs')
@mock.patch('pungi.notifier.datetime', new=mock_datetime)
class TestNotifier(unittest.TestCase):

    def setUp(self):
        super(TestNotifier, self).setUp()
        self.logfile = '/logs/notifications/notification-2017-06-28_09-34-00.log'
        self.compose = mock.Mock(
            compose_id='COMPOSE_ID',
            log_warning=mock.Mock(),
            paths=mock.Mock(
                compose=mock.Mock(
                    topdir=mock.Mock(return_value='/a/b')
                ),
                log=mock.Mock(
                    topdir=mock.Mock(return_value='/logs')
                )
            )
        )
        self.data = {'foo': 'bar', 'baz': 'quux'}

    def _call(self, script, cmd, **kwargs):
        data = self.data.copy()
        data['compose_id'] = 'COMPOSE_ID'
        data['location'] = '/a/b'
        data.update(kwargs)
        return mock.call((script, cmd),
                         stdin_data=json.dumps(data),
                         can_fail=True, return_stdout=False,
                         workdir=self.compose.paths.compose.topdir.return_value,
                         show_cmd=True, logfile=self.logfile)

    @mock.patch('pungi.util.translate_path')
    @mock.patch('kobo.shortcuts.run')
    def test_invokes_script(self, run, translate_path, makedirs):
        run.return_value = (0, None)
        translate_path.side_effect = lambda compose, x: x

        n = PungiNotifier(['run-notify'])
        n.compose = self.compose
        n.send('cmd', **self.data)

        makedirs.assert_called_once_with('/logs/notifications')
        self.assertItemsEqual(run.call_args_list, [self._call('run-notify', 'cmd')])

    @mock.patch('pungi.util.translate_path')
    @mock.patch('kobo.shortcuts.run')
    def test_invokes_multiple_scripts(self, run, translate_path, makedirs):
        run.return_value = (0, None)
        translate_path.side_effect = lambda compose, x: x

        n = PungiNotifier(['run-notify', 'ping-user'])
        n.compose = self.compose
        n.send('cmd', **self.data)

        self.assertItemsEqual(
            run.call_args_list,
            [self._call('run-notify', 'cmd'),
             self._call('ping-user', 'cmd')])

    @mock.patch('kobo.shortcuts.run')
    def test_translates_path(self, run, makedirs):
        self.compose.paths.compose.topdir.return_value = '/root/a/b'
        self.compose.conf = {
            "translate_paths": [("/root/", "http://example.com/compose/")],
        }

        run.return_value = (0, None)

        n = PungiNotifier(['run-notify'])
        n.compose = self.compose
        n.send('cmd', **self.data)

        self.assertItemsEqual(
            run.call_args_list,
            [self._call('run-notify', 'cmd', location='http://example.com/compose/a/b')])

    @mock.patch('kobo.shortcuts.run')
    def test_does_not_run_without_config(self, run, makedirs):
        n = PungiNotifier(None)
        n.send('cmd', foo='bar', baz='quux')
        self.assertFalse(run.called)

    @mock.patch('pungi.util.translate_path')
    @mock.patch('kobo.shortcuts.run')
    def test_logs_warning_on_failure(self, run, translate_path, makedirs):
        translate_path.side_effect = lambda compose, x: x
        run.return_value = (1, None)

        n = PungiNotifier(['run-notify'])
        n.compose = self.compose
        n.send('cmd', **self.data)

        self.assertItemsEqual(run.call_args_list, [self._call('run-notify', 'cmd')])
        self.assertTrue(self.compose.log_warning.called)


if __name__ == "__main__":
    unittest.main()
