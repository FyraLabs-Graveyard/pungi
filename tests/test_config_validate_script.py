#!/usr/bin/env python
# -*- coding: utf-8 -*-


import unittest
import mock
import os
import subprocess
import sys


HERE = os.path.abspath(os.path.dirname(__file__))
BINDIR = os.path.join(HERE, '../bin')
PUNGI_CONFIG_VALIDATE = os.path.join(BINDIR, 'pungi-config-validate')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tests import helpers


class ConfigValidateScriptTest(helpers.PungiTestCase):

    @mock.patch('kobo.shortcuts.run')
    def test_validate_dummy_config(self, run):
        DUMMY_CONFIG = os.path.join(HERE, 'data/dummy-pungi.conf')
        p = subprocess.Popen([PUNGI_CONFIG_VALIDATE, DUMMY_CONFIG],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        (stdout, stderr) = p.communicate()
        self.assertEqual(0, p.returncode)
        self.assertEqual('', stdout)
        self.assertEqual('', stderr)

if __name__ == '__main__':
    unittest.main()
