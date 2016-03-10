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

    def dont_find(self, paths):
        return lambda path: path not in paths

    def test_all_deps_missing(self):
        def custom_exists(path):
            return False

        with mock.patch('sys.stdout', new_callable=StringIO.StringIO) as out:
            with mock.patch('os.path.exists') as exists:
                exists.side_effect = custom_exists
                result = checks.check({})

        self.assertGreater(len(out.getvalue().strip().split('\n')), 1)
        self.assertFalse(result)

    def test_all_deps_ok(self):
        with mock.patch('sys.stdout', new_callable=StringIO.StringIO) as out:
            with mock.patch('os.path.exists') as exists:
                exists.side_effect = self.dont_find([])
                result = checks.check({})

        self.assertEqual('', out.getvalue())
        self.assertTrue(result)

    def test_does_not_require_jigdo_if_not_configured(self):
        conf = {
            'create_jigdo': False
        }

        with mock.patch('os.path.exists') as exists:
            exists.side_effect = self.dont_find(['/usr/bin/jigdo-lite'])
            result = checks.check(conf)

        self.assertTrue(result)

    def test_isohybrid_not_required_without_productimg_phase(self):
        conf = {
            'bootable': True,
            'productimg': False,
            'runroot': True,
        }

        with mock.patch('os.path.exists') as exists:
            exists.side_effect = self.dont_find(['/usr/bin/isohybrid'])
            result = checks.check(conf)

        self.assertTrue(result)

    def test_isohybrid_not_required_on_not_bootable(self):
        conf = {
            'bootable': False,
            'runroot': True,
        }

        with mock.patch('os.path.exists') as exists:
            exists.side_effect = self.dont_find(['/usr/bin/isohybrid'])
            result = checks.check(conf)

        self.assertTrue(result)

    def test_isohybrid_not_required_on_arm(self):
        conf = {
            'bootable': True,
            'productimg': True,
            'runroot': True,
        }

        with mock.patch('sys.stdout', new_callable=StringIO.StringIO) as out:
            with mock.patch('platform.machine') as machine:
                machine.return_value = 'armhfp'
                with mock.patch('os.path.exists') as exists:
                    exists.side_effect = self.dont_find(['/usr/bin/isohybrid'])
                    result = checks.check(conf)

        self.assertRegexpMatches(out.getvalue(), r'^Not checking.*Expect failures.*$')
        self.assertTrue(result)

    def test_isohybrid_not_needed_in_runroot(self):
        conf = {
            'runroot': True,
        }

        with mock.patch('os.path.exists') as exists:
            exists.side_effect = self.dont_find(['/usr/bin/isohybrid'])
            result = checks.check(conf)

        self.assertTrue(result)

    def test_genisoimg_not_needed_in_runroot(self):
        conf = {
            'runroot': True,
        }

        with mock.patch('os.path.exists') as exists:
            exists.side_effect = self.dont_find(['/usr/bin/genisoimage'])
            result = checks.check(conf)

        self.assertTrue(result)

    def test_genisoimg_needed_for_productimg(self):
        conf = {
            'runroot': True,
            'productimg': True,
            'bootable': True,
        }

        with mock.patch('sys.stdout', new_callable=StringIO.StringIO) as out:
            with mock.patch('os.path.exists') as exists:
                exists.side_effect = self.dont_find(['/usr/bin/genisoimage'])
                result = checks.check(conf)

        self.assertIn('genisoimage', out.getvalue())
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
