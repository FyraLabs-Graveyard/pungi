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
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

import json
import threading

from kobo import shortcuts


class PungiNotifier(object):
    """Wrapper around an external script for sending messages.

    If no script is configured, the messages are just silently ignored. If the
    script fails, a warning will be logged, but the compose process will not be
    interrupted.
    """
    def __init__(self, cmd):
        self.cmd = cmd
        self.lock = threading.Lock()

    def _update_args(self, data):
        """Add compose related information to the data."""
        data.setdefault('compose_id', self.compose.compose_id)

    def send(self, msg, **kwargs):
        """Send a message.

        The actual meaning of ``msg`` depends on what the notification script
        will be doing. The keyword arguments will be JSON-encoded and passed on
        to standard input of the notification process.

        Unless you specify it manually, a ``compose_id`` key with appropriate
        value will be automatically added.
        """
        if not self.cmd:
            return

        self._update_args(kwargs)

        with self.lock:
            ret, _ = shortcuts.run((self.cmd, msg),
                                   stdin_data=json.dumps(kwargs),
                                   can_fail=True,
                                   workdir=self.compose.paths.compose.topdir(),
                                   return_stdout=False)
            if ret != 0:
                self.compose.log_warning('Failed to invoke notification script.')
