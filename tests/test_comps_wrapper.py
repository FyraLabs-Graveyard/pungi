# -*- coding: utf-8 -*-

try:
    import unittest2 as unittest
except ImportError:
    import unittest
import tempfile
import difflib

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi.wrappers.comps import CompsWrapper
from tests.helpers import FIXTURE_DIR

COMPS_FILE = os.path.join(FIXTURE_DIR, 'comps.xml')
COMPS_FORMATTED_FILE = os.path.join(FIXTURE_DIR, 'comps-formatted.xml')
COMPS_GROUP_FILE = os.path.join(FIXTURE_DIR, 'comps-group.xml')
COMPS_ENVIRONMENT_FILE = os.path.join(FIXTURE_DIR, 'comps-env.xml')
COMPS_FILE_WITH_TYPO = os.path.join(FIXTURE_DIR, 'comps-typo.xml')


class CompsWrapperTest(unittest.TestCase):
    def setUp(self):
        self.file = tempfile.NamedTemporaryFile(prefix='comps-wrapper-test-')

    def assertFilesEqual(self, fn1, fn2):
        with open(fn1, 'rb') as f1:
            lines1 = f1.read().decode('utf-8').splitlines()
        with open(fn2, 'rb') as f2:
            lines2 = f2.read().decode('utf-8').splitlines()
        diff = '\n'.join(difflib.unified_diff(lines1, lines2,
                                              fromfile='EXPECTED', tofile='ACTUAL'))
        self.assertEqual(diff, '', 'Files differ:\n' + diff)

    def test_get_groups(self):
        comps = CompsWrapper(COMPS_FILE)
        self.assertItemsEqual(
            comps.get_comps_groups(),
            ['core', 'standard', 'text-internet', 'firefox', 'resilient-storage', 'basic-desktop'])

    def test_get_packages(self):
        comps = CompsWrapper(COMPS_FILE)
        self.assertItemsEqual(
            comps.get_packages('text-internet'),
            {'dummy-elinks', 'dummy-tftp'})

    def test_get_packages_for_non_existing_group(self):
        comps = CompsWrapper(COMPS_FILE)
        with self.assertRaises(KeyError):
            comps.get_packages('foo')

    def test_write_comps(self):
        comps = CompsWrapper(COMPS_FILE)
        comps.write_comps(target_file=self.file.name)
        self.assertFilesEqual(COMPS_FORMATTED_FILE, self.file.name)

    def test_filter_groups(self):
        comps = CompsWrapper(COMPS_FILE)
        unmatched = comps.filter_groups([
            {"name": "core", "glob": False, "default": False, "uservisible": True},
            {"name": "*a*", "glob": True, "default": None, "uservisible": None},
        ])
        self.assertEqual(unmatched, set())
        comps.write_comps(target_file=self.file.name)
        self.assertFilesEqual(COMPS_GROUP_FILE, self.file.name)

    def test_filter_groups_unused_filter(self):
        comps = CompsWrapper(COMPS_FILE)
        unmatched = comps.filter_groups([
            {"name": "boom", "glob": False, "default": False, "uservisible": True},
        ])
        self.assertEqual(unmatched, set(["boom"]))

    def test_filter_environments(self):
        comps = CompsWrapper(COMPS_FILE)
        comps.filter_environments([
            {"name": "minimal", "display_order": 10}
        ])
        comps.write_comps(target_file=self.file.name)
        self.assertFilesEqual(COMPS_ENVIRONMENT_FILE, self.file.name)

    def test_read_display_order(self):
        comps = CompsWrapper(COMPS_FILE)
        groups = [
            {"name": "minimal", "display_order": None}
        ]
        comps.filter_environments(groups)
        self.assertEqual(groups, [{"name": "minimal", "display_order": 99, "groups": ["core"]}])

    def test_report_typo_in_package_type(self):
        comps = CompsWrapper(COMPS_FILE_WITH_TYPO)
        with self.assertRaises(RuntimeError) as ctx:
            comps.write_comps(target_file=self.file.name)
        self.assertIn(
            'Package dummy-bash in group core has unknown type',
            str(ctx.exception))
