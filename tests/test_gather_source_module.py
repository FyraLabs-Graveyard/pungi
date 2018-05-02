# -*- coding: utf-8 -*-

try:
    import unittest2 as unittest
except ImportError:
    import unittest

import mock
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi.phases.gather.sources.source_module import GatherSourceModule
from tests import helpers
from pungi import Modulemd


@unittest.skipUnless(Modulemd is not None, 'Skipped test, no module support.')
class TestGatherSourceModule(helpers.PungiTestCase):
    def setUp(self):
        super(TestGatherSourceModule, self).setUp()

        self.compose = helpers.DummyCompose(self.topdir, {})
        self.compose.DEBUG = False
        self.mmd = self.compose.variants["Server"].add_fake_module(
            "testmodule:master:1:2017", rpm_nvrs=["pkg-0:1.0.0-1.x86_64", "pkg-0:1.0.0-1.i686"])

        mock_rpm = mock.Mock(version='1.0.0', release='1',
                             epoch=0, excludearch=None, exclusivearch=None,
                             sourcerpm='pkg-1.0.0-1', nevra='pkg-0:1.0.0-1.x86_64',
                             arch="x86_64")
        mock_rpm.name = 'pkg'
        self.compose.variants['Server'].pkgset.rpms_by_arch['x86_64'] = [mock_rpm]
        mock_rpm = mock.Mock(version='1.0.0', release='1',
                             epoch=0, excludearch=None, exclusivearch=None,
                             sourcerpm='pkg-1.0.0-1', nevra='pkg-0:1.0.0-1.i686',
                             arch="i686")
        mock_rpm.name = 'pkg'
        self.compose.variants['Server'].pkgset.rpms_by_arch['i686'] = [mock_rpm]

    def test_gather_module(self):
        source = GatherSourceModule(self.compose)
        packages, groups = source("x86_64", self.compose.variants["Server"])
        self.assertEqual(len(packages), 1)
        self.assertEqual(list(packages)[0][0].nevra, "pkg-0:1.0.0-1.x86_64")
        self.assertEqual(len(groups), 0)

        variant = self.compose.variants["Server"]
        arch_mmd = variant.arch_mmds["x86_64"]["testmodule-master"]
        self.assertEqual(set(arch_mmd.get_rpm_artifacts().get()),
                         set(["pkg-0:1.0.0-1.x86_64"]))

    def test_gather_multilib(self):
        multilib = Modulemd.SimpleSet()
        multilib.add("x86_64")
        self.mmd.get_rpm_components()["pkg"].set_multilib(multilib)

        source = GatherSourceModule(self.compose)
        packages, groups = source("x86_64", self.compose.variants["Server"])
        self.assertEqual(len(packages), 2)
        self.assertEqual(set(package[0].nevra for package in packages),
                         set(["pkg-0:1.0.0-1.x86_64", "pkg-0:1.0.0-1.i686"]))
        self.assertEqual(len(groups), 0)

        variant = self.compose.variants["Server"]
        arch_mmd = variant.arch_mmds["x86_64"]["testmodule-master"]
        self.assertEqual(set(arch_mmd.get_rpm_artifacts().get()),
                         set(["pkg-0:1.0.0-1.x86_64", "pkg-0:1.0.0-1.i686"]))

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
