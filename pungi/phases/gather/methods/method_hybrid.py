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
from fnmatch import fnmatch
import gzip

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
from pungi.wrappers.comps import CompsWrapper
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
        # Mapping from package name to set of langpack packages (stored as
        # names).
        self.langpacks = {}
        # Set of packages for which we already added langpacks.
        self.added_langpacks = set()
        # Set of NEVRAs of modular packages
        self.modular_packages = set()

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

    def expand_list(self, patterns):
        """Given a list of globs, create a list of package names matching any
        of the pattern.
        """
        expanded = set()
        for pkg_arch in self.package_sets[self.arch].rpms_by_arch:
            for pkg in self.package_sets[self.arch].rpms_by_arch[pkg_arch]:
                for pattern in patterns:
                    if fnmatch(pkg.name, pattern):
                        expanded.add(pkg)
                        break
        return expanded

    def prepare_modular_packages(self):
        for var in self.compose.all_variants.values():
            for mmd in var.arch_mmds.get(self.arch, {}).values():
                self.modular_packages.update(mmd.get_rpm_artifacts().dup())

    def prepare_langpacks(self, arch, variant):
        if not self.compose.has_comps:
            return
        comps_file = self.compose.paths.work.comps(arch, variant, create_dir=False)
        comps = CompsWrapper(comps_file)

        for name, install in comps.get_langpacks().items():
            # Replace %s with * for fnmatch.
            install_match = install % "*"
            self.langpacks[name] = set()
            for pkg_arch in self.package_sets[arch].rpms_by_arch:
                for pkg in self.package_sets[arch].rpms_by_arch[pkg_arch]:
                    if not fnmatch(pkg.name, install_match):
                        # Does not match the pattern, ignore...
                        continue
                    if pkg.name.endswith("-devel") or pkg.name.endswith("-static"):
                        continue
                    if pkg_is_debug(pkg):
                        continue
                    self.langpacks[name].add(pkg.name)

    def __call__(
        self,
        arch,
        variant,
        package_sets,
        packages=[],
        groups=[],
        multilib_whitelist=[],
        multilib_blacklist=[],
        filter_packages=[],
        **kwargs
    ):
        self.arch = arch
        self.valid_arches = get_valid_arches(arch, multilib=True)
        self.package_sets = package_sets

        self.prepare_langpacks(arch, variant)
        self.prepare_modular_packages()

        self.multilib_methods = get_arch_variant_data(
            self.compose.conf, "multilib", arch, variant
        )
        self.multilib = multilib_dnf.Multilib(
            self.multilib_methods,
            set(p.name for p in self.expand_list(multilib_blacklist)),
            set(p.name for p in self.expand_list(multilib_whitelist)),
        )

        platform = create_module_repo(self.compose, variant, arch)

        packages.update(
            expand_groups(self.compose, arch, variant, groups, set_pkg_arch=False)
        )

        # Filters are received as tuples (name, arch), we should convert it to
        # strings.
        filter_packages = [_fmt_pkg(*p) for p in filter_packages]

        nvrs, out_modules = self.run_solver(
            variant, arch, packages, platform, filter_packages
        )
        filter_modules(variant, arch, out_modules)
        return expand_packages(
            self._get_pkg_map(arch),
            variant.arch_mmds.get(arch, {}),
            pungi.phases.gather.get_lookaside_repos(self.compose, arch, variant),
            nvrs,
        )
        # maybe check invalid sigkeys

    def run_solver(self, variant, arch, packages, platform, filter_packages):
        repos = [self.compose.paths.work.arch_repo(arch=arch)]

        modules = []
        if variant.arch_mmds.get(arch):
            repos.append(self.compose.paths.work.module_repo(arch, variant))
            for mmd in variant.arch_mmds[arch].values():
                modules.append("%s:%s" % (mmd.peek_name(), mmd.peek_stream()))

        input_packages = []
        for pkg_name, pkg_arch in packages:
            input_packages.extend(self._expand_wildcard(pkg_name, pkg_arch))

        step = 0

        old_multilib = set()

        while True:
            step += 1
            conf_file = self.compose.paths.work.fus_conf(arch, variant, step)
            fus.write_config(conf_file, sorted(modules), sorted(input_packages))
            cmd = fus.get_cmd(
                conf_file,
                tree_arch_to_yum_arch(arch),
                repos,
                pungi.phases.gather.get_lookaside_repos(self.compose, arch, variant),
                platform=platform,
                filter_packages=filter_packages,
            )
            logfile = self.compose.paths.log.log_file(
                arch, "hybrid-depsolver-%s-iter-%d" % (variant, step)
            )
            # Adding this environement variable will tell GLib not to prefix
            # any log messages with the PID of the fus process (which is quite
            # useless for us anyway).
            env = os.environ.copy()
            env["G_MESSAGES_PREFIXED"] = ""
            run(cmd, logfile=logfile, show_cmd=True, env=env)
            output, out_modules = fus.parse_output(logfile)
            new_multilib = self.add_multilib(variant, arch, output, old_multilib)
            old_multilib = new_multilib
            if new_multilib:
                input_packages.extend(
                    _fmt_pkg(pkg_name, pkg_arch)
                    for pkg_name, pkg_arch in sorted(new_multilib)
                )
                continue

            new_langpacks = self.add_langpacks(output)
            if new_langpacks:
                input_packages.extend(new_langpacks)
                continue

            # Nothing new was added, we can stop now.
            break

        return output, out_modules

    def add_multilib(self, variant, arch, nvrs, old_multilib):
        added = set()
        if not self.multilib_methods:
            return []

        for nvr, pkg_arch, flags in nvrs:
            if "modular" in flags:
                continue

            if pkg_arch != arch:
                # Not a native package, not checking to add multilib
                continue

            nevr = kobo.rpmlib.parse_nvr(nvr)

            for add_arch in self.valid_arches:
                if add_arch == arch:
                    continue
                try:
                    multilib_candidate = self._get_package("%s.%s" % (nvr, add_arch))
                except KeyError:
                    continue
                if self.multilib.is_multilib(multilib_candidate):
                    added.add((nevr["name"], add_arch))

        return added - old_multilib

    def add_langpacks(self, nvrs):
        if not self.langpacks:
            return set()
        added = set()
        for nvr, pkg_arch, flags in nvrs:
            if "modular" in flags:
                continue
            name = nvr.rsplit("-", 2)[0]
            if name in self.added_langpacks:
                # This package is already processed.
                continue
            added.update(self.langpacks.get(name, []))
            self.added_langpacks.add(name)

        return sorted(added)

    def _expand_wildcard(self, pkg_name, pkg_arch):
        if "*" not in pkg_name:
            return [_fmt_pkg(pkg_name, pkg_arch)]

        packages = []

        for pkg in self.expand_list([pkg_name]):
            if pkg_is_debug(pkg):
                # No debuginfo
                continue

            if pkg_arch:
                if pkg_arch != pkg.arch:
                    # Arch is specified and does not match, skip the package.
                    continue
            else:
                if pkg.arch not in ("noarch", self.arch):
                    # No arch specified and package does not match
                    continue

            strict_nevra = "%s-%s:%s-%s.%s" % (
                pkg.name, pkg.epoch or "0", pkg.version, pkg.release, pkg.arch
            )
            if strict_nevra in self.modular_packages:
                # Wildcards should not match modular packages.
                continue

            packages.append(_fmt_nevra(pkg, pkg.arch))

        return packages


def get_lookaside_modules(lookasides):
    """Get list of NSVC of all modules in all lookaside repos."""
    modules = set()
    for repo in lookasides:
        repo = fus._prep_path(repo)
        repomd = cr.Repomd(os.path.join(repo, "repodata/repomd.xml"))
        for rec in repomd.records:
            if rec.type != "modules":
                continue
            with gzip.GzipFile(os.path.join(repo, rec.location_href), "r") as f:
                # This can't use _from_stream, since gobject-introspection
                # refuses to pass a file object.
                mmds = Modulemd.objects_from_string(f.read())
            for mmd in mmds:
                if isinstance(mmd, Modulemd.Module):
                    modules.add(
                        "%s:%s:%s:%s"
                        % (
                            mmd.peek_name(),
                            mmd.peek_stream(),
                            mmd.peek_version(),
                            mmd.peek_context(),
                        )
                    )
    return modules


def create_module_repo(compose, variant, arch):
    """Create repository with module metadata. There are no packages otherwise."""
    createrepo_c = compose.conf["createrepo_c"]
    createrepo_checksum = compose.conf["createrepo_checksum"]
    msg = "Creating repo with modular metadata for %s.%s" % (variant, arch)

    repo_path = compose.paths.work.module_repo(arch, variant)

    compose.log_debug("[BEGIN] %s" % msg)

    platforms = set()

    lookaside_modules = get_lookaside_modules(
        pungi.phases.gather.get_lookaside_repos(compose, arch, variant)
    )

    # Add modular metadata to it
    modules = []

    # We need to include metadata for all variants. The packages are in the
    # set, so we need their metadata.
    for var in compose.all_variants.values():
        for mmd in var.arch_mmds.get(arch, {}).values():
            # Set the arch field, but no other changes are needed.
            repo_mmd = mmd.copy()
            repo_mmd.set_arch(tree_arch_to_yum_arch(arch))

            for dep in repo_mmd.peek_dependencies():
                streams = dep.peek_requires().get("platform")
                if streams:
                    platforms.update(streams.dup())

            nsvc = "%s:%s:%s:%s" % (
                repo_mmd.peek_name(),
                repo_mmd.peek_stream(),
                repo_mmd.peek_version(),
                repo_mmd.peek_context(),
            )
            if nsvc not in lookaside_modules:
                modules.append(repo_mmd)

    if len(platforms) > 1:
        raise RuntimeError("There are conflicting requests for platform.")

    module_names = set([x.get_name() for x in modules])
    defaults_dir = compose.paths.work.module_defaults_dir()
    for mmddef in iter_module_defaults(defaults_dir):
        if mmddef.peek_module_name() in module_names:
            modules.append(mmddef)

    if modules:
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
    return list(platforms)[0] if platforms else None


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


def expand_packages(nevra_to_pkg, variant_modules, lookasides, nvrs):
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
            url = os.path.join(pkg.location_base or repo, pkg.location_href)
            # Strip file:// prefix
            lookaside_packages.add(url[7:])

    # This is used to figure out which debuginfo packages to include. We keep
    # track of package architectures from each SRPM.
    srpm_arches = defaultdict(set)

    for nvr, arch, flags in nvrs:
        pkg = nevra_to_pkg["%s.%s" % (nvr, arch)]
        if pkg.file_path in lookaside_packages:
            # Package is in lookaside, don't add it and ignore sources and
            # debuginfo too.
            continue
        if pkg_is_debug(pkg):
            debuginfo.add(pkg.file_path)
        else:
            rpms.add(pkg.file_path)

        try:
            srpm_nevra = _get_srpm_nevra(pkg)
            srpm = nevra_to_pkg[srpm_nevra]
            if "modular" not in flags:
                # Only mark the arch for sources of non-modular packages. The
                # debuginfo is explicitly listed in the output, and we don't
                # want anything more.
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


def filter_modules(variant, arch, nsvcs_to_keep):
    """Remove any arch-specific module metadata from the module if it's not
    listed in the list to keep. This will ultimately cause the module to not be
    included in the final repodata and module metadata.
    """
    for nsvc in list(variant.arch_mmds.get(arch, {}).keys()):
        if nsvc not in nsvcs_to_keep:
            del variant.arch_mmds[arch][nsvc]
