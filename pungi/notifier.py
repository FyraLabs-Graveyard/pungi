# -*- coding: utf-8 -*-

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <https://gnu.org/licenses/>.

from datetime import datetime
import json
import os
import threading

import pungi.util

from kobo import shortcuts


class PungiNotifier(object):
    """Wrapper around an external script for sending messages.

    If no script is configured, the messages are just silently ignored. If the
    script fails, a warning will be logged, but the compose process will not be
    interrupted.
    """
    def __init__(self, cmds):
        self.cmds = cmds
        self.lock = threading.Lock()
        self.compose = None

    def _update_args(self, data):
        """Add compose related information to the data."""
        if not self.compose:
            return
        data.setdefault('compose_id', self.compose.compose_id)

        # Publish where in the world this compose will end up living
        location = pungi.util.translate_path(
            self.compose, self.compose.paths.compose.topdir())
        data.setdefault('location', location)

    def send(self, msg, workdir=None, **kwargs):
        """Send a message.

        The actual meaning of ``msg`` depends on what the notification script
        will be doing. The keyword arguments will be JSON-encoded and passed on
        to standard input of the notification process.

        Unless you specify it manually, a ``compose_id`` key with appropriate
        value will be automatically added.
        """
        if not self.cmds:
            return

        self._update_args(kwargs)

        if self.compose:
            workdir = self.compose.paths.compose.topdir()

        with self.lock:
            for cmd in self.cmds:
                self._run_script(cmd, msg, workdir, kwargs)

    def _run_script(self, cmd, msg, workdir, kwargs):
        """Run a single notification script with proper logging."""
        logfile = None
        if self.compose:
            self.compose.log_debug("Notification: %r %r, %r" % (
                cmd, msg, kwargs))
            logfile = os.path.join(
                self.compose.paths.log.topdir(),
                'notifications',
                'notification-%s.log' % datetime.utcnow().strftime('%Y-%m-%d_%H-%M-%S')
            )
            pungi.util.makedirs(os.path.dirname(logfile))

        ret, _ = shortcuts.run((cmd, msg),
                               stdin_data=json.dumps(kwargs),
                               can_fail=True,
                               workdir=workdir,
                               return_stdout=False,
                               show_cmd=True,
                               logfile=logfile)
        if ret != 0:
            if self.compose:
                self.compose.log_warning('Failed to invoke notification script.')
