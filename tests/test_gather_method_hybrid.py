# -*- coding: utf-8 -*-

from collections import namedtuple
import copy
import mock
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi.phases.gather.methods import method_hybrid as hybrid
from tests import helpers


MockPkg = namedtuple(
    "MockPkg", ["name", "version", "release", "epoch", "sourcerpm", "file_path", "arch"]
)


class NamedMock(mock.Mock):
    def __init__(self, name=None, **kwargs):
        super(NamedMock, self).__init__(**kwargs)
        self.name = name


class TestMethodHybrid(helpers.PungiTestCase):
    @mock.patch("pungi.phases.gather.methods.method_hybrid.CompsWrapper")
    @mock.patch("pungi.phases.gather.get_lookaside_repos")
    @mock.patch("pungi.phases.gather.methods.method_hybrid.expand_groups")
    @mock.patch("pungi.phases.gather.methods.method_hybrid.expand_packages")
    @mock.patch("pungi.phases.gather.methods.method_hybrid.create_module_repo")
    def test_call_method(self, cmr, ep, eg, glr, CW):
        compose = helpers.DummyCompose(self.topdir, {})
        m = hybrid.GatherMethodHybrid(compose)
        m.run_solver = mock.Mock(return_value=(mock.Mock(), mock.Mock()))
        pkg = MockPkg(
            name="pkg",
            version="1",
            release="2",
            arch="x86_64",
            epoch=3,
            sourcerpm=None,
            file_path=None,
        )
        CW.return_value.get_langpacks.return_value = {"glibc": "glibc-langpack-%s"}
        eg.return_value = ["foo", "bar"]
        package_sets = {"x86_64": mock.Mock(rpms_by_arch={"x86_64": [pkg]})}
        arch = "x86_64"
        variant = compose.variants["Server"]

        res = m(arch, variant, package_sets, set(["pkg"]), ["standard"])

        self.assertEqual(res, ep.return_value)
        self.assertEqual(cmr.call_args_list, [mock.call(compose, variant, arch)])
        self.assertEqual(
            m.run_solver.call_args_list,
            [mock.call(variant, arch, set(["pkg", "foo", "bar"]), cmr.return_value, [])],
        )
        self.assertEqual(
            ep.call_args_list,
            [
                mock.call(
                    {"pkg-3:1-2.x86_64": pkg},
                    {},
                    glr.return_value,
                    m.run_solver.return_value[0],
                )
            ],
        )
        self.assertEqual(
            eg.call_args_list,
            [mock.call(compose, arch, variant, ["standard"], set_pkg_arch=False)],
        )
        print(CW.mock_calls)
        self.assertEqual(
            CW.mock_calls,
            [
                mock.call(
                    os.path.join(
                        self.topdir, "work/x86_64/comps/comps-Server.x86_64.xml"
                    )
                ),
                mock.call().get_langpacks(),
            ],
        )

    @mock.patch("pungi.phases.gather.methods.method_hybrid.CompsWrapper")
    def test_prepare_langpacks(self, CW):
        compose = helpers.DummyCompose(self.topdir, {})
        CW.return_value.get_langpacks.return_value = {"foo": "foo-%s"}
        m = hybrid.GatherMethodHybrid(compose)
        m.package_sets = {
            "x86_64": mock.Mock(
                rpms_by_arch={
                    "x86_64": [
                        MockPkg(
                            name="foo",
                            version="1",
                            release="2",
                            arch="x86_64",
                            epoch=0,
                            sourcerpm=None,
                            file_path=None,
                        ),
                        MockPkg(
                            name="foo-en",
                            version="1",
                            release="2",
                            arch="x86_64",
                            epoch=0,
                            sourcerpm=None,
                            file_path=None,
                        ),
                        MockPkg(
                            name="foo-devel",
                            version="1",
                            release="2",
                            arch="x86_64",
                            epoch=0,
                            sourcerpm=None,
                            file_path=None,
                        ),
                    ]
                }
            )
        }
        m.prepare_langpacks("x86_64", compose.variants["Server"])

        self.assertEqual(m.langpacks, {"foo": set(["foo-en"])})

    def test_expand_list(self):
        compose = helpers.DummyCompose(self.topdir, {})
        m = hybrid.GatherMethodHybrid(compose)
        m.package_sets = {
            "x86_64": mock.Mock(
                rpms_by_arch={
                    "x86_64": [
                        MockPkg(
                            name="foo",
                            version="1",
                            release="2",
                            arch="x86_64",
                            epoch=0,
                            sourcerpm=None,
                            file_path=None,
                        ),
                        MockPkg(
                            name="foo-en",
                            version="1",
                            release="2",
                            arch="x86_64",
                            epoch=0,
                            sourcerpm=None,
                            file_path=None,
                        ),
                        MockPkg(
                            name="bar",
                            version="1",
                            release="2",
                            arch="x86_64",
                            epoch=0,
                            sourcerpm=None,
                            file_path=None,
                        ),
                    ]
                }
            )
        }
        expanded = m.expand_list("x86_64", ["foo*"])

        self.assertItemsEqual(expanded, ["foo", "foo-en"])


class MockModule(object):
    def __init__(
        self, name, platform=None, stream=None, version=None, context=None, rpms=None
    ):
        self.name = name
        self.platform = platform
        self.stream = stream
        self.version = version
        self.context = context
        self.rpms = rpms or ["pkg-1.0-1.x86_64"]

    def get_name(self):
        return self.name

    def peek_name(self):
        return self.name

    def peek_stream(self):
        return self.stream

    def peek_version(self):
        return self.version

    def peek_context(self):
        return self.context

    def peek_dependencies(self):
        return [
            mock.Mock(
                peek_requires=mock.Mock(
                    return_value={
                        "platform": mock.Mock(
                            dup=mock.Mock(return_value=[self.platform])
                        )
                    }
                )
            )
        ]

    def copy(self):
        return self

    def set_arch(self, arch):
        pass

    def get_rpm_artifacts(self):
        return mock.Mock(dup=mock.Mock(return_value=self.rpms))


class HelperMixin(object):
    def _repo(self, name):
        return os.path.join(self.compose.topdir, "work/x86_64/%s" % name)


@mock.patch("pungi.phases.gather.methods.method_hybrid.Modulemd")
@mock.patch("pungi.phases.gather.methods.method_hybrid.run")
class TestCreateModuleRepo(HelperMixin, helpers.PungiTestCase):
    def setUp(self):
        super(TestCreateModuleRepo, self).setUp()
        self.compose = helpers.DummyCompose(self.topdir, {})
        self.variant = self.compose.variants["Server"]

    def test_no_modules(self, run, Modulemd):
        plat, pkgs = hybrid.create_module_repo(self.compose, self.variant, "x86_64")

        self.assertIsNone(plat)
        self.assertItemsEqual(pkgs, [])
        self.assertEqual(run.call_args_list, [])
        self.assertEqual(Modulemd.mock_calls, [])

    def test_more_than_one_platform(self, run, Modulemd):
        self.variant.arch_mmds["x86_64"] = {
            "mod:1": MockModule("mod", platform="f29"),
            "mod:2": MockModule("mod", platform="f30"),
        }

        with self.assertRaises(RuntimeError) as ctx:
            hybrid.create_module_repo(self.compose, self.variant, "x86_64")

        self.assertIn("conflicting requests for platform", str(ctx.exception))
        self.assertEqual(run.call_args_list, [])
        self.assertEqual(Modulemd.mock_calls, [])

    @mock.patch("pungi.phases.gather.methods.method_hybrid.iter_module_defaults")
    def test_creating_repo_with_module_and_default(self, imd, run, Modulemd):
        mod = MockModule("mod", platform="f29")
        self.variant.arch_mmds["x86_64"] = {"mod:1": mod}
        default = mock.Mock(peek_module_name=mock.Mock(return_value="mod"))
        imd.return_value = [default]

        plat = hybrid.create_module_repo(self.compose, self.variant, "x86_64")

        self.assertEqual(plat, "f29")

        self.assertEqual(
            Modulemd.mock_calls, [mock.call.dump([mod, default], mock.ANY)]
        )
        create, modify = run.call_args_list
        self.assertEqual(
            create[0][0][:2], ["createrepo_c", self._repo("module_repo_Server")]
        )
        self.assertEqual(
            modify[0][0][:4],
            [
                "modifyrepo_c",
                Modulemd.mock_calls[0][1][1],
                self._repo("module_repo_Server/repodata"),
                "--mdtype=modules",
            ],
        )


class ModifiedMagicMock(mock.MagicMock):
    """Like MagicMock, but remembers original values or mutable arguments."""

    def _mock_call(_mock_self, *args, **kwargs):
        return super(ModifiedMagicMock, _mock_self)._mock_call(
            *copy.deepcopy(args), **copy.deepcopy(kwargs)
        )


@mock.patch("pungi.wrappers.fus.parse_output")
@mock.patch("pungi.wrappers.fus.get_cmd", new_callable=ModifiedMagicMock)
@mock.patch("pungi.phases.gather.methods.method_hybrid.run")
class TestRunSolver(HelperMixin, helpers.PungiTestCase):
    def setUp(self):
        super(TestRunSolver, self).setUp()
        self.compose = helpers.DummyCompose(self.topdir, {})
        self.phase = hybrid.GatherMethodHybrid(self.compose)
        self.phase.multilib_methods = []
        self.logfile1 = os.path.join(
            self.compose.topdir, "logs/x86_64/hybrid-depsolver-Server-iter-1.x86_64.log"
        )
        self.logfile2 = os.path.join(
            self.compose.topdir, "logs/x86_64/hybrid-depsolver-Server-iter-2.x86_64.log"
        )

    def test_with_modules(self, run, gc, po):
        self.compose.has_comps = False
        self.compose.variants["Server"].arch_mmds["x86_64"] = {
            "mod:master": mock.Mock(
                peek_name=mock.Mock(return_value="mod"),
                peek_stream=mock.Mock(return_value="master"),
                peek_version=mock.Mock(return_value="ver"),
                peek_context=mock.Mock(return_value="ctx"),
            )
        }
        self.compose.variants["Server"].mmds = [
            mock.Mock(
                peek_name=mock.Mock(return_value="mod"),
                peek_stream=mock.Mock(return_value="master"),
                peek_version=mock.Mock(return_value="ver"),
                peek_context=mock.Mock(return_value="ctx"),
            )
        ]
        po.return_value = (mock.Mock(), mock.Mock())

        res = self.phase.run_solver(
            self.compose.variants["Server"],
            "x86_64",
            [],
            platform="pl",
            filter_packages=["foo"],
        )

        self.assertEqual(res, po.return_value)
        self.assertEqual(po.call_args_list, [mock.call(self.logfile1)])
        self.assertEqual(
            run.call_args_list,
            [
                mock.call(
                    gc.return_value, logfile=self.logfile1, show_cmd=True, env=mock.ANY
                )
            ],
        )
        self.assertEqual(
            gc.call_args_list,
            [
                mock.call(
                    "x86_64",
                    [self._repo("repo"), self._repo("module_repo_Server")],
                    [],
                    [],
                    ["mod:master"],
                    platform="pl",
                    filter_packages=["foo"],
                )
            ],
        )

    def test_with_modules_with_devel(self, run, gc, po):
        self.compose.has_comps = False
        self.compose.variants["Server"].arch_mmds["x86_64"] = {
            "mod:master": mock.Mock(
                peek_name=mock.Mock(return_value="mod"),
                peek_stream=mock.Mock(return_value="master"),
                peek_version=mock.Mock(return_value="ver"),
                peek_context=mock.Mock(return_value="ctx"),
            ),
            "mod-devel:master": mock.Mock(
                peek_name=mock.Mock(return_value="mod-devel"),
                peek_stream=mock.Mock(return_value="master"),
                peek_version=mock.Mock(return_value="ver"),
                peek_context=mock.Mock(return_value="ctx"),
            ),
        }
        po.return_value = (mock.Mock(), mock.Mock())

        res = self.phase.run_solver(
            self.compose.variants["Server"],
            "x86_64",
            [],
            platform="pl",
            filter_packages=["foo"],
        )

        self.assertEqual(res, po.return_value)
        self.assertEqual(po.call_args_list, [mock.call(self.logfile1)])
        self.assertEqual(
            run.call_args_list,
            [
                mock.call(
                    gc.return_value, logfile=self.logfile1, show_cmd=True, env=mock.ANY
                )
            ],
        )
        self.assertEqual(
            gc.call_args_list,
            [
                mock.call(
                    "x86_64",
                    [self._repo("repo"), self._repo("module_repo_Server")],
                    [],
                    [],
                    ["mod:master", "mod-devel:master"],
                    platform="pl",
                    filter_packages=["foo"],
                )
            ],
        )

    def test_with_comps(self, run, gc, po):
        po.return_value = (mock.Mock(), mock.Mock())
        res = self.phase.run_solver(
            self.compose.variants["Server"],
            "x86_64",
            [("pkg", None)],
            platform=None,
            filter_packages=[],
        )

        self.assertEqual(res, po.return_value)
        self.assertEqual(po.call_args_list, [mock.call(self.logfile1)])
        self.assertEqual(
            run.call_args_list,
            [
                mock.call(
                    gc.return_value, logfile=self.logfile1, show_cmd=True, env=mock.ANY
                )
            ],
        )
        self.assertEqual(
            gc.call_args_list,
            [
                mock.call(
                    "x86_64",
                    [self._repo("repo")],
                    [],
                    ["pkg"],
                    [],
                    platform=None,
                    filter_packages=[],
                )
            ],
        )

    def test_with_langpacks(self, run, gc, po):
        self.phase.langpacks = {"pkg": set(["pkg-en"])}
        final = [("pkg-1.0-1", "x86_64", []), ("pkg-en-1.0-1", "noarch", [])]
        po.side_effect = [([("pkg-1.0-1", "x86_64", [])], set()), (final, [])]

        res = self.phase.run_solver(
            self.compose.variants["Server"],
            "x86_64",
            [("pkg", None)],
            platform=None,
            filter_packages=["foo"],
        )

        self.assertEqual(res, (final, []))
        self.assertEqual(
            po.call_args_list, [mock.call(self.logfile1), mock.call(self.logfile2)]
        )
        self.assertEqual(
            run.call_args_list,
            [
                mock.call(
                    gc.return_value, logfile=self.logfile1, show_cmd=True, env=mock.ANY
                ),
                mock.call(
                    gc.return_value, logfile=self.logfile2, show_cmd=True, env=mock.ANY
                ),
            ],
        )
        self.assertEqual(
            gc.call_args_list,
            [
                mock.call(
                    "x86_64",
                    [self._repo("repo")],
                    [],
                    ["pkg"],
                    [],
                    platform=None,
                    filter_packages=["foo"],
                ),
                mock.call(
                    "x86_64",
                    [self._repo("repo")],
                    [],
                    ["pkg", "pkg-en"],
                    [],
                    platform=None,
                    filter_packages=["foo"],
                ),
            ],
        )

    @mock.patch("pungi.phases.gather.methods.method_hybrid.cr")
    def test_multilib_devel(self, cr, run, gc, po):
        self.phase.arch = "x86_64"
        self.phase.multilib_methods = ["devel"]
        self.phase.multilib = mock.Mock()
        self.phase.multilib.is_multilib.side_effect = (
            lambda pkg: pkg.name == "pkg-devel"
        )
        self.phase.valid_arches = ["x86_64", "i686", "noarch"]
        cr.Metadata.return_value.keys.return_value = []
        self.phase.package_maps = {
            "x86_64": {
                "pkg-devel-1.0-1.x86_64": NamedMock(name="pkg-devel"),
                "pkg-devel-1.0-1.i686": NamedMock(name="pkg-devel"),
                "foo-1.0-1.x86_64": NamedMock(name="foo"),
            }
        }
        self.phase.packages = self.phase.package_maps["x86_64"]
        final = [
            ("pkg-devel-1.0-1", "x86_64", []),
            ("foo-1.0-1", "x86_64", []),
            ("pkg-devel-1.0-1", "i686", []),
        ]
        po.side_effect = [
            ([("pkg-devel-1.0-1", "x86_64", []), ("foo-1.0-1", "x86_64", [])], []),
            (final, []),
        ]

        res = self.phase.run_solver(
            self.compose.variants["Server"],
            "x86_64",
            [("pkg-devel", None), ("foo", None)],
            platform=None,
            filter_packages=[],
        )

        self.assertEqual(res, (final, []))
        self.assertEqual(
            po.call_args_list, [mock.call(self.logfile1), mock.call(self.logfile2)]
        )
        self.assertEqual(
            run.call_args_list,
            [
                mock.call(
                    gc.return_value, logfile=self.logfile1, show_cmd=True, env=mock.ANY
                ),
                mock.call(
                    gc.return_value, logfile=self.logfile2, show_cmd=True, env=mock.ANY
                ),
            ],
        )
        self.assertEqual(
            gc.call_args_list,
            [
                mock.call(
                    "x86_64",
                    [self._repo("repo")],
                    [],
                    ["pkg-devel", "foo"],
                    [],
                    platform=None,
                    filter_packages=[],
                ),
                mock.call(
                    "x86_64",
                    [self._repo("repo")],
                    [],
                    ["pkg-devel", "foo", "pkg-devel.i686"],
                    [],
                    platform=None,
                    filter_packages=[],
                ),
            ],
        )

    @mock.patch("pungi.phases.gather.methods.method_hybrid.cr")
    def test_multilib_runtime(self, cr, run, gc, po):
        packages = {
            "abc": NamedMock(
                name="foo",
                epoch=None,
                version="1.0",
                release="1",
                arch="x86_64",
                provides=[("/usr/lib/libfoo.1.so.1", None, None)],
            ),
            "def": NamedMock(
                name="foo",
                epoch=None,
                version="1.0",
                release="1",
                arch="i686",
                provides=[("/usr/lib/libfoo.1.so.1", None, None)],
            ),
            "ghi": NamedMock(
                name="pkg-devel",
                epoch=None,
                version="1.0",
                release="1",
                arch="x86_64",
                provides=[],
            ),
        }
        cr.Metadata.return_value.keys.return_value = packages.keys()
        cr.Metadata.return_value.get.side_effect = lambda key: packages[key]

        self.phase.multilib_methods = ["runtime"]
        self.phase.multilib = mock.Mock()
        self.phase.multilib.is_multilib.side_effect = lambda pkg: pkg.name == "foo"
        self.phase.valid_arches = ["x86_64", "i686", "noarch"]
        self.phase.arch = "x86_64"
        self.phase.package_maps = {
            "x86_64": {
                "pkg-devel-1.0-1.x86_64": mock.Mock(),
                "pkg-devel-1.0-1.i686": mock.Mock(),
                "foo-1.0-1.x86_64": mock.Mock(),
                "foo-1.0-1.i686": mock.Mock(),
            }
        }
        final = [
            ("pkg-devel-1.0-1", "x86_64", []),
            ("foo-1.0-1", "x86_64", []),
            ("foo-1.0-1", "i686", []),
        ]
        po.side_effect = [
            ([("pkg-devel-1.0-1", "x86_64", []), ("foo-1.0-1", "x86_64", [])], []),
            (final, []),
        ]

        res = self.phase.run_solver(
            self.compose.variants["Server"],
            "x86_64",
            [("pkg-devel", None), ("foo", None)],
            platform=None,
            filter_packages=[],
        )

        self.assertEqual(res, (final, []))
        self.assertEqual(
            po.call_args_list, [mock.call(self.logfile1), mock.call(self.logfile2)]
        )
        self.assertEqual(
            run.call_args_list,
            [
                mock.call(
                    gc.return_value, logfile=self.logfile1, show_cmd=True, env=mock.ANY
                ),
                mock.call(
                    gc.return_value, logfile=self.logfile2, show_cmd=True, env=mock.ANY
                ),
            ],
        )
        self.assertEqual(
            gc.call_args_list,
            [
                mock.call(
                    "x86_64",
                    [self._repo("repo")],
                    [],
                    ["pkg-devel", "foo"],
                    [],
                    platform=None,
                    filter_packages=[],
                ),
                mock.call(
                    "x86_64",
                    [self._repo("repo")],
                    [],
                    ["pkg-devel", "foo", "foo.i686"],
                    [],
                    platform=None,
                    filter_packages=[],
                ),
            ],
        )


class TestExpandPackages(helpers.PungiTestCase):
    def _mk_packages(self, src=None, debug_arch=None):
        pkg = MockPkg(
            name="pkg",
            version="1",
            release="2",
            arch="x86_64",
            epoch=3,
            sourcerpm="pkg-1-2.src",
            file_path="/tmp/pkg.rpm",
        )
        nevra_to_pkg = {"pkg-3:1-2.x86_64": pkg}
        if src or debug_arch:
            nevra_to_pkg["pkg-3:1-2.src"] = pkg._replace(
                arch="src", file_path="/tmp/spkg.rpm"
            )
        if debug_arch:
            nevra_to_pkg["pkg-debuginfo-3:1-2.%s" % debug_arch] = pkg._replace(
                name="pkg-debuginfo", arch=debug_arch, file_path="/tmp/d1.rpm"
            )
        return nevra_to_pkg

    def test_single_package(self):
        nevra_to_pkg = self._mk_packages()

        res = hybrid.expand_packages(
            nevra_to_pkg, {}, [], [("pkg-3:1-2", "x86_64", [])]
        )

        self.assertEqual(
            res,
            {
                "rpm": [{"path": "/tmp/pkg.rpm", "flags": []}],
                "srpm": [],
                "debuginfo": [],
            },
        )

    def test_include_src_and_debuginfo(self):
        nevra_to_pkg = self._mk_packages(debug_arch="x86_64")

        res = hybrid.expand_packages(
            nevra_to_pkg, {}, [], [("pkg-3:1-2", "x86_64", [])]
        )

        self.assertEqual(
            res,
            {
                "rpm": [{"path": "/tmp/pkg.rpm", "flags": []}],
                "srpm": [{"path": "/tmp/spkg.rpm", "flags": []}],
                "debuginfo": [{"path": "/tmp/d1.rpm", "flags": []}],
            },
        )

    def test_modular_include_src_but_not_debuginfo(self):
        nevra_to_pkg = self._mk_packages(debug_arch="x86_64")

        res = hybrid.expand_packages(
            nevra_to_pkg, {}, [], [("pkg-3:1-2", "x86_64", ["modular"])]
        )

        self.assertEqual(
            res,
            {
                "rpm": [{"path": "/tmp/pkg.rpm", "flags": []}],
                "srpm": [{"path": "/tmp/spkg.rpm", "flags": []}],
                "debuginfo": [],
            },
        )

    def test_modular_debug_in_correct_place(self):
        nevra_to_pkg = self._mk_packages(debug_arch="x86_64")

        res = hybrid.expand_packages(
            nevra_to_pkg, {}, [], [("pkg-debuginfo-3:1-2", "x86_64", ["modular"])]
        )

        self.assertEqual(
            res,
            {
                "rpm": [],
                "srpm": [{"path": "/tmp/spkg.rpm", "flags": []}],
                "debuginfo": [{"path": "/tmp/d1.rpm", "flags": []}],
            },
        )

    def test_skip_debuginfo_for_different_arch(self):
        nevra_to_pkg = self._mk_packages(debug_arch="i686")

        res = hybrid.expand_packages(
            nevra_to_pkg, {}, [], [("pkg-3:1-2", "x86_64", [])]
        )

        self.assertEqual(
            res,
            {
                "rpm": [{"path": "/tmp/pkg.rpm", "flags": []}],
                "srpm": [{"path": "/tmp/spkg.rpm", "flags": []}],
                "debuginfo": [],
            },
        )

    @mock.patch("pungi.phases.gather.methods.method_hybrid.cr")
    def test_skip_lookaside_source_and_debuginfo(self, cr):
        nevra_to_pkg = self._mk_packages(debug_arch="x86_64")
        lookasides = [mock.Mock()]
        repo = {
            "abc": NamedMock(
                name="pkg",
                arch="src",
                location_base="file:///tmp/",
                location_href="spkg.rpm",
            ),
            "def": NamedMock(
                name="pkg-debuginfo",
                arch="x86_64",
                location_base="file:///tmp/",
                location_href="d1.rpm",
            ),
        }
        cr.Metadata.return_value.keys.return_value = repo.keys()
        cr.Metadata.return_value.get.side_effect = lambda key: repo[key]

        res = hybrid.expand_packages(
            nevra_to_pkg, {}, lookasides, [("pkg-3:1-2", "x86_64", [])]
        )

        self.assertEqual(
            res,
            {
                "rpm": [{"path": "/tmp/pkg.rpm", "flags": []}],
                "srpm": [],
                "debuginfo": [],
            },
        )

    @mock.patch("pungi.phases.gather.methods.method_hybrid.cr")
    def test_skip_lookaside_packages(self, cr):
        nevra_to_pkg = self._mk_packages(debug_arch="x86_64")
        lookasides = [mock.Mock()]
        repo = {
            "abc": NamedMock(
                name="pkg",
                arch="x86_64",
                location_base="file:///tmp/",
                location_href="pkg.rpm",
            )
        }
        cr.Metadata.return_value.keys.return_value = repo.keys()
        cr.Metadata.return_value.get.side_effect = lambda key: repo[key]

        res = hybrid.expand_packages(
            nevra_to_pkg, {}, lookasides, [("pkg-3:1-2", "x86_64", [])]
        )

        self.assertEqual(res, {"rpm": [], "srpm": [], "debuginfo": []})


class TestFilterModules(helpers.PungiTestCase):
    def test_remove_one(self):
        self.compose = helpers.DummyCompose(self.topdir, {})
        self.variant = self.compose.variants["Server"]
        self.variant.arch_mmds["x86_64"] = {
            "mod:1": MockModule("mod", platform="f29"),
            "mod:2": MockModule("mod", platform="f30"),
        }

        hybrid.filter_modules(self.variant, "x86_64", ["mod:1"])

        self.assertItemsEqual(self.variant.arch_mmds["x86_64"].keys(), ["mod:1"])
