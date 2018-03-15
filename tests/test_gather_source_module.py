# -*- coding: utf-8 -*-

import mock
import os
import sys
import unittest

try:
    import gi # noqa
    gi.require_version('Modulemd', '1.0') # noqa
    from gi.repository import Modulemd # noqa
    import pdc_client       # noqa
    HAS_MODULE_SUPPORT = True
except ImportError:
    HAS_MODULE_SUPPORT = False

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi.phases.gather.sources.source_module import GatherSourceModule
from tests import helpers


@unittest.skipUnless(HAS_MODULE_SUPPORT, 'Skipped test, no module support.')
class TestGatherSourceModule(helpers.PungiTestCase):
    def setUp(self):
        super(TestGatherSourceModule, self).setUp()

        self.compose = helpers.DummyCompose(self.topdir, {})
        self.compose.DEBUG = False
        self.mmd = self.compose.variants["Server"].add_fake_module(
            "testmodule:master:1:2017", rpm_nvrs=["pkg-1.0.0-1"])

        mock_rpm = mock.Mock(version='1.0.0', release='1',
                             epoch=0, excludearch=None, exclusivearch=None,
                             sourcerpm='pkg-1.0.0-1', nevra='pkg-1.0.0-1')
        mock_rpm.name = 'pkg'
        self.compose.variants['Server'].pkgset.rpms_by_arch['x86_64'] = [mock_rpm]

    def test_gather_module(self):
        source = GatherSourceModule(self.compose)
        packages, groups = source("x86_64", self.compose.variants["Server"])
        self.assertEqual(len(packages), 1)
        self.assertEqual(list(packages)[0][0].nevra, "pkg-1.0.0-1")
        self.assertEqual(len(groups), 0)

        variant = self.compose.variants["Server"]
        arch_mmd = variant.arch_mmds["x86_64"]["testmodule-master"]
        self.assertEqual(set(arch_mmd.get_rpm_artifacts().get()),
                         set(["pkg-1.0.0-1"]))

    def test_gather_filtered_module(self):
        filter_set = Modulemd.SimpleSet()
        filter_set.add("pkg")
        self.mmd.set_rpm_filter(filter_set)

        source = GatherSourceModule(self.compose)
        packages, groups = source("x86_64", self.compose.variants["Server"])
        self.assertEqual(len(packages), 0)
        self.assertEqual(len(groups), 0)

        variant = self.compose.variants["Server"]
        arch_mmd = variant.arch_mmds["x86_64"]["testmodule-master"]
        self.assertEqual(len(arch_mmd.get_rpm_artifacts().get()), 0)
