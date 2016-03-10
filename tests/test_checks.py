#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import mock
import unittest
import os
import sys
import StringIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pungi import checks


class CheckDependenciesTestCase(unittest.TestCase):
    def test_all_deps_missing(self):
        def custom_exists(path):
            return False

        with mock.patch('sys.stdout', new_callable=StringIO.StringIO) as out:
            with mock.patch('os.path.exists') as exists:
                exists.side_effect = custom_exists
                result = checks.check({})

        self.assertEqual(12, len(out.getvalue().strip().split('\n')))
        self.assertFalse(result)

    def test_all_deps_ok(self):
        def custom_exists(path):
            return True

        with mock.patch('sys.stdout', new_callable=StringIO.StringIO) as out:
            with mock.patch('os.path.exists') as exists:
                exists.side_effect = custom_exists
                result = checks.check({})

        self.assertEqual('', out.getvalue())
        self.assertTrue(result)

    def test_does_not_require_jigdo_if_not_configured(self):
        conf = {
            'create_jigdo': False
        }

        def custom_exists(path):
            if path == '/usr/bin/jigdo-lite':
                return False
            return True

        with mock.patch('os.path.exists') as exists:
            exists.side_effect = custom_exists
            result = checks.check(conf)

        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
