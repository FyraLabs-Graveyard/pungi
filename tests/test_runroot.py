# -*- coding: utf-8 -*-

import mock
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi.runroot import Runroot
from tests import helpers


class TestRunrootOpenSSH(helpers.PungiTestCase):
    def setUp(self):
        super(TestRunrootOpenSSH, self).setUp()
        self.compose = helpers.DummyCompose(self.topdir, {
            "runroot": True,
            "runroot_method": "openssh",
            "runroot_ssh_user": "root",
            "runroot_ssh_hostnames": {
                "x86_64": "localhost"
            }
        })

        self.runroot = Runroot(self.compose)

    def test_get_runroot_method(self):
        method = self.runroot.get_runroot_method()
        self.assertEqual(method, "openssh")

    @mock.patch("pungi.runroot.run")
    def test_run(self, run):
        self.runroot.run("df -h", log_file="/foo/runroot.log", arch="x86_64")
        run.assert_has_calls([
            mock.call(
                ['ssh', '-oBatchMode=yes', '-n', '-l', 'root', 'localhost',
                 'df -h'], logfile='/foo/runroot.log', show_cmd=True),
            mock.call(
                ['ssh', '-oBatchMode=yes', '-n', '-l', 'root', 'localhost',
                 "rpm -qa --qf='%{name}-%{version}-%{release}.%{arch}\n'"],
                show_cmd=True)
        ])

    @mock.patch("pungi.runroot.run")
    def test_get_buildroot_rpms(self, run):
        # Run the runroot task at first.
        run.return_value = (0, "foo-1-1.fc29.noarch\nbar-1-1.fc29.noarch\n")
        self.runroot.run("df -h", log_file="/foo/runroot.log", arch="x86_64")

        rpms = self.runroot.get_buildroot_rpms()
        self.assertEqual(
            set(rpms), set(["foo-1-1.fc29.noarch", "bar-1-1.fc29.noarch"]))
