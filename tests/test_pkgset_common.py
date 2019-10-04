# -*- coding: utf-8 -*-

import os
import sys

import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi.module_util import Modulemd
from pungi.phases.pkgset import common
from tests import helpers


class MockCreateRepo(object):
    def __init__(self, createrepo_c):
        self.createrepo_c = createrepo_c

    def get_createrepo_cmd(self, path_prefix, outputdir, pkglist, **kwargs):
        return (path_prefix, outputdir, pkglist)


@mock.patch("pungi.phases.init.run_in_threads", new=helpers.fake_run_in_threads)
@mock.patch("pungi.phases.pkgset.common.CreaterepoWrapper", new=MockCreateRepo)
@mock.patch("pungi.phases.pkgset.common.run")
class TestMaterializedPkgsetCreate(helpers.PungiTestCase):
    def setUp(self):
        super(TestMaterializedPkgsetCreate, self).setUp()
        self.compose = helpers.DummyCompose(self.topdir, {})
        self.prefix = "/prefix"
        self.pkgset = self._make_pkgset("foo")
        self.subsets = {}

    def _mk_call(self, arch, name):
        pkglist = "%s.%s.conf" % (arch, name)
        logfile = "arch_repo.%s.%s.log" % (name, arch)
        return mock.call(
            (
                self.prefix,
                os.path.join(self.topdir, "work", arch, "repo", name),
                os.path.join(self.topdir, "work", arch, "package_list", pkglist),
            ),
            logfile=os.path.join(self.topdir, "logs", arch, logfile),
            show_cmd=True,
        )

    def _make_pkgset(self, name):
        pkgset = mock.Mock()
        pkgset.name = name

        def mock_subset(primary, arch_list, exclusive_noarch):
            self.subsets[primary] = mock.Mock()
            return self.subsets[primary]

        pkgset.subset.side_effect = mock_subset
        return pkgset

    def _mk_paths(self, name, arches):
        paths = {"global": os.path.join(self.topdir, "work/global/repo", name)}
        for arch in arches:
            paths[arch] = os.path.join(self.topdir, "work", arch, "repo", name)
        return paths

    def test_run(self, mock_run):
        result = common.MaterializedPackageSet.create(
            self.compose, self.pkgset, self.prefix
        )

        self.assertItemsEqual(result.package_sets.keys(), ["global", "amd64", "x86_64"])
        self.assertEqual(result["global"], self.pkgset)
        self.assertEqual(result["x86_64"], self.subsets["x86_64"])
        self.assertEqual(result["amd64"], self.subsets["amd64"])

        self.pkgset.subset.assert_any_call(
            "x86_64", ["x86_64", "noarch", "src"], exclusive_noarch=True
        )
        self.pkgset.subset.assert_any_call(
            "amd64", ["amd64", "x86_64", "noarch", "src"], exclusive_noarch=True
        )

        for arch, pkgset in result.package_sets.items():
            pkgset.save_file_list.assed_any_call(
                os.path.join(
                    self.topdir, "work", arch, "package_list", arch + ".foo.conf"
                ),
                remove_path_prefix=self.prefix,
            )

        self.assertEqual(result.paths, self._mk_paths("foo", ["amd64", "x86_64"]))

        mock_run.assert_has_calls(
            [self._mk_call(arch, "foo") for arch in ["global", "amd64", "x86_64"]],
            any_order=True,
        )

    @helpers.unittest.skipUnless(Modulemd, "Skipping tests, no module support")
    @mock.patch("pungi.phases.pkgset.common.collect_module_defaults")
    @mock.patch("pungi.phases.pkgset.common.add_modular_metadata")
    def test_run_with_modulemd(self, amm, cmd, mock_run):
        mmd = {"x86_64": [mock.Mock()]}
        common.MaterializedPackageSet.create(
            self.compose, self.pkgset, self.prefix, mmd=mmd
        )
        cmd.assert_called_once_with(
            os.path.join(self.topdir, "work/global/module_defaults"),
            set(x.get_module_name.return_value for x in mmd["x86_64"]),
            overrides_dir=None,
        )
        amm.assert_called_once_with(
            mock.ANY,
            os.path.join(self.topdir, "work/x86_64/repo/foo"),
            cmd.return_value,
            os.path.join(self.topdir, "logs/x86_64/arch_repo_modulemd.foo.x86_64.log"),
        )
        cmd.return_value.add_module_stream.assert_called_once_with(mmd["x86_64"][0])
