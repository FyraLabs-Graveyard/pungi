# -*- coding: utf-8 -*-


# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <https://gnu.org/licenses/>.

from collections import defaultdict
import os
from kobo.shortcuts import run
import kobo.rpmlib

import pungi.phases.gather.method
from pungi import Modulemd, multilib_dnf
from pungi.arch import get_valid_arches, tree_arch_to_yum_arch
from pungi.phases.gather import _mk_pkg_map
from pungi.util import (
    get_arch_variant_data,
    iter_module_defaults,
    pkg_is_debug,
    temp_dir,
)
from pungi.wrappers import fus
from pungi.wrappers.createrepo import CreaterepoWrapper

from .method_nodeps import expand_groups

import createrepo_c as cr


class FakePackage(object):
    """This imitates a DNF package object and can be passed to python-multilib
    library.
    """

    def __init__(self, pkg):
        self.pkg = pkg

    def __getattr__(self, attr):
        return getattr(self.pkg, attr)

    @property
    def files(self):
        return [
            os.path.join(dirname, basename) for (_, dirname, basename) in self.pkg.files
        ]

    @property
    def provides(self):
        # This is supposed to match what yum package object returns. It's a
        # nested tuple (name, flag, (epoch, version, release)). This code only
        # fills in the name, because that's all that python-multilib is using..
        return [(p[0].split()[0], None, (None, None, None)) for p in self.pkg.provides]


class GatherMethodHybrid(pungi.phases.gather.method.GatherMethodBase):
    enabled = True

    def __init__(self, *args, **kwargs):
        super(GatherMethodHybrid, self).__init__(*args, **kwargs)
        self.package_maps = {}
        self.packages = {}

    def _get_pkg_map(self, arch):
        """Create a mapping from NEVRA to actual package object. This will be
        done once for each architecture, since the package set is the same for
        all variants.

        The keys are in NEVRA format and only include the epoch if it's not
        zero. This makes it easier to query by results for the depsolver.
        """
        if arch not in self.package_maps:
            pkg_map = {}
            for pkg_arch in self.package_sets[arch].rpms_by_arch:
                for pkg in self.package_sets[arch].rpms_by_arch[pkg_arch]:
                    pkg_map[_fmt_nevra(pkg, pkg_arch)] = pkg
            self.package_maps[arch] = pkg_map

        return self.package_maps[arch]

    def _prepare_packages(self):
        repo_path = self.compose.paths.work.arch_repo(arch=self.arch)
        md = cr.Metadata()
        md.locate_and_load_xml(repo_path)
        for key in md.keys():
            pkg = md.get(key)
            if pkg.arch in self.valid_arches:
                self.packages[_fmt_nevra(pkg, arch=pkg.arch)] = FakePackage(pkg)

    def _get_package(self, nevra):
        if not self.packages:
            self._prepare_packages()
        return self.packages[nevra]

    def __call__(
        self,
        arch,
        variant,
        package_sets,
        packages=[],
        groups=[],
        multilib_whitelist=[],
        multilib_blacklist=[],
        **kwargs
    ):
        self.arch = arch
        self.valid_arches = get_valid_arches(arch, multilib=True)
        self.package_sets = package_sets

        self.multilib_methods = get_arch_variant_data(
            self.compose.conf, "multilib", arch, variant
        )
        self.multilib = multilib_dnf.Multilib(
            self.multilib_methods, multilib_blacklist, multilib_whitelist
        )

        platform, modular_rpms = create_module_repo(self.compose, variant, arch)

        packages.update(
            expand_groups(self.compose, arch, variant, groups, set_pkg_arch=False)
        )

        nvrs, modules = self.run_solver(variant, arch, packages, platform, modular_rpms)
        return expand_packages(
            self._get_pkg_map(arch),
            variant.arch_mmds.get(arch, {}),
            pungi.phases.gather.get_lookaside_repos(self.compose, arch, variant),
            nvrs,
            modules,
        )
        # maybe check invalid sigkeys

    def run_solver(self, variant, arch, packages, platform, modular_rpms):
        repos = [self.compose.paths.work.arch_repo(arch=arch)]

        modules = []
        if variant.arch_mmds.get(arch):
            repos.append(self.compose.paths.work.module_repo(arch, variant))
            for mmd in variant.arch_mmds[arch].values():
                modules.append("%s:%s" % (mmd.peek_name(), mmd.peek_stream()))

        input_packages = [
            _fmt_pkg(pkg_name, pkg_arch) for pkg_name, pkg_arch in packages
        ]

        step = 0

        while True:
            step += 1
            cmd = fus.get_cmd(
                tree_arch_to_yum_arch(arch),
                repos,
                pungi.phases.gather.get_lookaside_repos(self.compose, arch, variant),
                input_packages,
                modules,
                platform=platform,
            )
            logfile = self.compose.paths.log.log_file(
                arch, "hybrid-depsolver-%s-iter-%d" % (variant, step)
            )
            run(cmd, logfile=logfile, show_cmd=True)
            output, output_modules = fus.parse_output(logfile)
            new_multilib = self.add_multilib(variant, arch, output, modular_rpms)
            if not new_multilib:
                # No new multilib packages were added, we're done.
                break

            input_packages.extend(
                _fmt_pkg(pkg_name, pkg_arch) for pkg_name, pkg_arch in new_multilib
            )

        return output, output_modules

    def add_multilib(self, variant, arch, nvrs, modular_rpms):
        added = set()
        if not self.multilib_methods:
            return []

        for nvr, pkg_arch in nvrs:
            if pkg_arch != arch:
                # Not a native package, not checking to add multilib
                continue

            nevr = kobo.rpmlib.parse_nvr(nvr)
            nevr_copy = nevr.copy()
            nevr_copy["arch"] = pkg_arch

            if kobo.rpmlib.make_nvra(nevr_copy, force_epoch=True) in modular_rpms:
                # Skip modular package
                continue

            if self.multilib.is_multilib(self._get_package("%s.%s" % (nvr, pkg_arch))):
                for add_arch in self.valid_arches:
                    if add_arch == arch:
                        continue
                    if _nevra(arch=add_arch, **nevr) in self._get_pkg_map(arch):
                        added.add((nevr["name"], add_arch))

        # Remove packages that are already present
        for nvr, pkg_arch in nvrs:
            existing = (nvr.rsplit("-", 2)[0], pkg_arch)
            if existing in added:
                added.remove(existing)

        return sorted(added)


def create_module_repo(compose, variant, arch):
    """Create repository with module metadata. There are no packages otherwise."""
    createrepo_c = compose.conf["createrepo_c"]
    createrepo_checksum = compose.conf["createrepo_checksum"]
    msg = "Creating repo with modular metadata for %s.%s" % (variant, arch)

    if not variant.arch_mmds.get(arch):
        compose.log_debug("[SKIP ] %s: no modules found" % msg)
        return None, []

    compose.log_debug("[BEGIN] %s" % msg)

    platforms = set()
    modular_rpms = set()

    repo_path = compose.paths.work.module_repo(arch, variant)

    # Add modular metadata to it
    modules = []

    for mmd in variant.arch_mmds[arch].values():
        # Set the arch field, but no other changes are needed.
        repo_mmd = mmd.copy()
        repo_mmd.set_arch(tree_arch_to_yum_arch(arch))

        for dep in repo_mmd.peek_dependencies():
            streams = dep.peek_requires().get("platform")
            if streams:
                platforms.update(streams.dup())

        # Collect all modular NEVRAs
        artifacts = repo_mmd.get_rpm_artifacts()
        if artifacts:
            modular_rpms.update(artifacts.dup())

        modules.append(repo_mmd)

    if len(platforms) > 1:
        raise RuntimeError("There are conflicting requests for platform.")

    module_names = set([x.get_name() for x in modules])
    defaults_dir = compose.paths.work.module_defaults_dir()
    for mmddef in iter_module_defaults(defaults_dir):
        if mmddef.peek_module_name() in module_names:
            modules.append(mmddef)

    # Initialize empty repo
    repo = CreaterepoWrapper(createrepo_c=createrepo_c)
    cmd = repo.get_createrepo_cmd(
        repo_path, database=False, outputdir=repo_path, checksum=createrepo_checksum
    )
    logfile = "module_repo-%s" % variant
    run(cmd, logfile=compose.paths.log.log_file(arch, logfile), show_cmd=True)

    with temp_dir() as tmp_dir:
        modules_path = os.path.join(tmp_dir, "modules.yaml")
        Modulemd.dump(modules, modules_path)

        cmd = repo.get_modifyrepo_cmd(
            os.path.join(repo_path, "repodata"),
            modules_path,
            mdtype="modules",
            compress_type="gz",
        )
        log_file = compose.paths.log.log_file(
            arch, "gather-modifyrepo-modules-%s" % variant
        )
        run(cmd, logfile=log_file, show_cmd=True)

    compose.log_debug("[DONE ] %s" % msg)
    return list(platforms)[0] if platforms else None, modular_rpms


def _fmt_pkg(pkg_name, arch):
    if arch:
        pkg_name += ".%s" % arch
    return pkg_name


def _nevra(**kwargs):
    if kwargs.get("epoch") not in (None, "", 0, "0"):
        return "%(name)s-%(epoch)s:%(version)s-%(release)s.%(arch)s" % kwargs
    return "%(name)s-%(version)s-%(release)s.%(arch)s" % kwargs


def _fmt_nevra(pkg, arch):
    return _nevra(
        name=pkg.name,
        epoch=pkg.epoch,
        version=pkg.version,
        release=pkg.release,
        arch=arch,
    )


def _get_srpm_nevra(pkg):
    nevra = kobo.rpmlib.parse_nvra(pkg.sourcerpm)
    nevra["epoch"] = nevra["epoch"] or pkg.epoch
    return _nevra(**nevra)


def _make_result(paths):
    return [{"path": path, "flags": []} for path in sorted(paths)]


def expand_packages(nevra_to_pkg, variant_modules, lookasides, nvrs, modules):
    """For each package add source RPM and possibly also debuginfo."""
    # This will server as the final result. We collect sets of paths to the
    # packages.
    rpms = set()
    srpms = set()
    debuginfo = set()

    # Collect list of all packages in lookaside. These will not be added to the
    # result. Fus handles this in part: if a package is explicitly mentioned as
    # input (which can happen with comps group expansion), it will be in the
    # output even if it's in lookaside.
    lookaside_packages = set()
    for repo in lookasides:
        md = cr.Metadata()
        md.locate_and_load_xml(repo)
        for key in md.keys():
            pkg = md.get(key)
            url = os.path.join(pkg.location_base, pkg.location_href)
            # Strip file:// prefix
            lookaside_packages.add(url[7:])

    # Get all packages in modules and include them in rpms or debuginfo.
    variant_mmd = {}
    for mmd in variant_modules.values():
        nsvc = "%s:%s:%s:%s" % (
            mmd.peek_name(),
            mmd.peek_stream(),
            mmd.peek_version(),
            mmd.peek_context(),
        )
        variant_mmd[nsvc] = mmd

    for module in modules:
        mmd = variant_mmd.get(module)
        if not mmd:
            continue
        artifacts = mmd.get_rpm_artifacts()
        if not artifacts:
            continue
        for rpm in artifacts.dup():
            pkg = nevra_to_pkg[_nevra(**kobo.rpmlib.parse_nvra(rpm))]
            if pkg_is_debug(pkg):
                debuginfo.add(pkg.file_path)
            else:
                rpms.add(pkg.file_path)
            # Add source package. We don't need modular packages, those are
            # listed in modulemd.
            try:
                srpm_nevra = _get_srpm_nevra(pkg)
                srpm = nevra_to_pkg[srpm_nevra]
                if srpm.file_path not in lookaside_packages:
                    srpms.add(srpm.file_path)
            except KeyError:
                # Didn't find source RPM.. this should be logged
                pass

    # This is used to figure out which debuginfo packages to include. We keep
    # track of package architectures from each SRPM.
    srpm_arches = defaultdict(set)

    for nvr, arch in nvrs:
        pkg = nevra_to_pkg["%s.%s" % (nvr, arch)]
        if pkg.file_path in lookaside_packages:
            # Package is in lookaside, don't add it and ignore sources and
            # debuginfo too.
            continue
        rpms.add(pkg.file_path)

        try:
            srpm_nevra = _get_srpm_nevra(pkg)
            srpm = nevra_to_pkg[srpm_nevra]
            srpm_arches[srpm_nevra].add(arch)
            if srpm.file_path not in lookaside_packages:
                srpms.add(srpm.file_path)
        except KeyError:
            # Didn't find source RPM.. this should be logged
            pass

    # Get all debuginfo packages from all included sources. We iterate over all
    # available packages and if we see a debug package from included SRPM built
    # for architecture that has at least one binary package, we include it too.
    for pkg in nevra_to_pkg.values():
        if pkg_is_debug(pkg) and pkg.arch in srpm_arches[_get_srpm_nevra(pkg)]:
            if pkg.file_path not in lookaside_packages:
                debuginfo.add(pkg.file_path)

    return _mk_pkg_map(_make_result(rpms), _make_result(srpms), _make_result(debuginfo))
