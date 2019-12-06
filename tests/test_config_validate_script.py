# -*- coding: utf-8 -*-


import mock
import os
import subprocess
import sys
import six

from pungi.scripts.config_validate import cli_main
from tests import helpers


HERE = os.path.abspath(os.path.dirname(__file__))
DUMMY_CONFIG = os.path.join(HERE, 'data/dummy-pungi.conf')


class ConfigValidateScriptTest(helpers.PungiTestCase):

    @mock.patch('sys.argv', new=['pungi-config-validate', DUMMY_CONFIG])
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('sys.stdout', new_callable=six.StringIO)
    def test_validate_dummy_config(self, stdout, stderr):
        cli_main()
        self.assertEqual('', stdout.getvalue())
        self.assertEqual('', stderr.getvalue())
