#!/usr/bin/python
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
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.




import hawkey
import logging
import pungi.dnf_wrapper
import pungi.multilib_dnf
from pungi.profiler import Profiler
from kobo.rpmlib import parse_nvra

class GatherOptions(object):
    def __init__(self, **kwargs):
        super(GatherOptions, self).__init__()

        # include all unused sub-packages of already included RPMs
        self.fulltree = False

        # include langpacks
        self.langpacks = []  # format: [{"package": "langpack-pattern-%s"}]

        # resolve dependencies
        self.resolve_deps = True

        # pull build dependencies
        self.selfhosting = False

        # none, all, build
        # TODO: validate values
        self.greedy_method = "none"

        # multilib options
        self.multilib_methods = []
        self.multilib_blacklist = []
        self.multilib_whitelist = []

        # prepopulate
        self.prepopulate = []

        # lookaside repos; packages will be flagged accordingly
        self.lookaside_repos = []

        for key, value in kwargs.items():
            if not hasattr(self, key):
                raise ValueError("Invalid gather option: %s" % key)
            setattr(self, key, value)


def filter_debug_packages(q, arch=None):
    result = q.filter(arch__neq=["src", "nosrc"])
    if arch:
        arches = pungi.dnf_wrapper.ArchWrapper(arch).all_arches
        result = result.filter(arch=arches)
    result = result.filter(name__glob=["*-debuginfo", "*-debuginfo-*"])
    return result


def filter_native_debug_packages(q, arch):
    result = q.filter(arch__neq=["src", "nosrc"])
    arches = pungi.dnf_wrapper.ArchWrapper(arch).native_arches
    result = result.filter(arch=arches)
    result = result.filter(name__glob=["*-debuginfo", "*-debuginfo-*"])
    return result


def filter_multilib_debug_packages(q, arch):
    result = q.filter(arch__neq=["src", "nosrc"])
    arches = pungi.dnf_wrapper.ArchWrapper(arch).multilib_arches
    result = result.filter(arch=arches)
    result = result.filter(name__glob=["*-debuginfo", "*-debuginfo-*"])
    return result


def filter_source_packages(q):
    result = q.filter(arch=["src", "nosrc"])
    return result


def filter_binary_packages(q, arch=None):
    result = q.filter(arch__neq=["src", "nosrc"])
    if arch:
        arches = pungi.dnf_wrapper.ArchWrapper(arch).all_arches
        result = result.filter(arch=arches)
    result = result.filter(latest_per_arch=True)
    result = result.filter(name__glob__not=["*-debuginfo", "*-debuginfo-*"])
    return result


def filter_native_binary_packages(q, arch):
    result = q.filter(arch__neq=["src", "nosrc"])
    arches = pungi.dnf_wrapper.ArchWrapper(arch).native_arches
    result = result.filter(arch=arches)
    result = result.filter(latest_per_arch=True)
    result = result.filter(name__glob__not=["*-debuginfo", "*-debuginfo-*"])
    return result


def filter_multilib_binary_packages(q, arch):
    result = q.filter(arch__neq=["src", "nosrc"])
    arches = pungi.dnf_wrapper.ArchWrapper(arch).multilib_arches
    result = result.filter(arch=arches)
    result = result.filter(latest_per_arch=True)
    result = result.filter(name__glob__not=["*-debuginfo", "*-debuginfo-*"])
    return result


def filter_binary_noarch_packages(q):
    result = q.filter(arch="noarch")
    result = result.filter(latest_per_arch=True)
    result = result.filter(name__glob__not=["*-debuginfo", "*-debuginfo-*"])
    return result


class QueryCache(object):
    def __init__(self, queue, *args, **kwargs):
        self.cache = {}
        self.nargs = len(args)

        if kwargs:
            queue = queue.filter(**kwargs)

        for pkg in queue:
            key = tuple(getattr(pkg, arg) for arg in args)
            pkgs = self.cache.setdefault(key, [])
            if pkg not in pkgs:
                # use list preserve package order
                pkgs.append(pkg)

    def get(self, *args):
        if len(args) != self.nargs:
            raise ValueError("Expected %s arguments, got %s" % (self.nargs, len(args)))
        key = tuple(args)
        return self.cache.get(key, None)


class GatherBase(object):
    def __init__(self, dnf_obj):
        self.dnf = dnf_obj
        self.q_binary_packages = filter_binary_packages(self._query, arch=self.dnf.basearch).apply()
        self.q_native_binary_packages = filter_native_binary_packages(self._query, arch=self.dnf.basearch).apply()
        self.q_multilib_binary_packages = filter_multilib_binary_packages(self._query, arch=self.dnf.basearch).apply()
        self.q_noarch_binary_packages = filter_binary_packages(self._query).apply()
        self.q_debug_packages = filter_debug_packages(self._query, arch=self.dnf.basearch).apply()
        self.q_native_debug_packages = filter_native_debug_packages(self._query, arch=self.dnf.basearch).apply()
        self.q_multilib_debug_packages = filter_multilib_debug_packages(self._query, arch=self.dnf.basearch).apply()
        self.q_source_packages = filter_source_packages(self._query).apply()

    @property
    def _query(self):
        return self.dnf._sack.query()

    def is_noarch_package(self, pkg):
        return pkg.arch == "noarch"

    def is_native_package(self, pkg):
        if pkg.arch in ["src", "nosrc"]:
            return False
        if pkg.arch == "noarch":
            return True
        if pkg.arch in self.dnf.arch_wrapper.native_arches:
            return True
        return False

    def is_multilib_package(self, pkg):
        if pkg.arch in ["src", "nosrc"]:
            return False
        if pkg.arch == "noarch":
            return False
        if pkg.arch in self.dnf.arch_wrapper.multilib_arches:
            return True
        return False


class Gather(GatherBase):
    def __init__(self, dnf_obj, gather_options, logger=None):
        super(Gather, self).__init__(dnf_obj)
        self.logger = logger
        if not self.logger:
            # Default logger
            self.logger = logging.getLogger("gather_dnf")
            self.logger.setLevel(logging.DEBUG)

        self.opts = gather_options
        self.logger.debug("Gather received gather_options=%s" % gather_options.__dict__)
        self._multilib = pungi.multilib_dnf.Multilib(self.dnf._sack, gather_options.multilib_methods, blacklist=self.opts.multilib_blacklist, whitelist=self.opts.multilib_whitelist)

        # already processed packages
        self.finished_add_binary_package_deps = {}      # {pkg: [deps]}
        self.finished_add_debug_package_deps = {}       # {pkg: [deps]}
        self.finished_add_source_package_deps = {}      # {pkg: [deps]}

        self.finished_get_package_deps_reqs = {}

        self.finished_add_conditional_packages = {}     # {pkg: [pkgs]}
        self.finished_add_source_packages = {}          # {pkg: src-pkg|None}
        self.sourcerpm_cache = {}                       # {src_nvra: src-pkg|None}
        self.finished_add_debug_packages = {}           # {pkg: [debug-pkgs]}
        self.finished_add_fulltree_packages = {}        # {pkg: [pkgs]}
        self.finished_add_langpack_packages = {}        # {pkg: [pkgs]}
        self.finished_add_multilib_packages = {}        # {pkg: pkg|None}

        # result
        self.result_binary_packages = set()
        self.result_debug_packages = set()
        self.result_source_packages = set()
        self.result_package_flags = {}

    def _set_flag(self, pkg, *flags):
        self.result_package_flags.setdefault(pkg, set()).update(flags)

    def _has_flag(self, pkg, flag):
        return flag in self.result_package_flags.get(pkg, set())

    def _get_best_package(self, package_list, pkg=None, req=None):
        if not package_list:
            return []

        if self.opts.greedy_method == "all":
            return list(package_list)

        all_pkgs = list(package_list)
        native_pkgs = self.q_native_binary_packages.filter(pkg=all_pkgs).apply()
        multilib_pkgs = [pkg for pkg in all_pkgs if pkg.arch != "noarch"]

        result = set()

        # try seen native packages first
        seen_pkgs = set(native_pkgs) & self.result_binary_packages
        if seen_pkgs:
            result = seen_pkgs

        # then try seen multilib packages
        if not result:
            seen_pkgs = set(multilib_pkgs) & self.result_binary_packages
            if seen_pkgs:
                result = seen_pkgs

        if not result:
            result = set(native_pkgs)

        if not result:
            result = set(multilib_pkgs)

        if not result:
            return []

        # return package with shortest name, alphabetically ordered
        result = list(result)
        result.sort(lambda x, y: cmp(x.name, y.name))
        result.sort(lambda x, y: cmp(len(x.name), len(y.name)))

        # best arch
        arches = self.dnf.arch_wrapper.all_arches
        result.sort(lambda x, y: cmp(arches.index(x.arch), arches.index(y.arch)))
        match = result[0]

        if self.opts.greedy_method == "build" and req:
            if self.is_native_package(match):
                return [i for i in native_pkgs if i.sourcerpm == match.sourcerpm]
#                return list(native_pkgs.filter(sourcerpm=match.sourcerpm, provides=req))
            else:
                return [i for i in multilib_pkgs if i.sourcerpm == match.sourcerpm]
#                return list(multilib_pkgs.filter(sourcerpm=match.sourcerpm, provides=req))
        return [match]

    def _add_packages(self, packages, pulled_by=None):
        added = set()
        for i in packages:
            assert i is not None
            if i not in self.result_binary_packages:
                added.add(i)
                pb = ""
                if pulled_by:
                    pb = " (pulled by %s, repo: %s)" % (pulled_by, pulled_by.repo.id)
                self.logger.debug("Added package %s%s" % (i, pb))
                self.result_binary_packages.add(i)
                # lookaside
                if i.repoid in self.opts.lookaside_repos:
                    self._set_flag(i, "lookaside")

        for pkg in added:
            if pkg is None:
                continue
            for prov in pkg.provides:
                self.finished_get_package_deps_reqs.setdefault(str(prov), set()).add(pkg)

        self.result_binary_packages.update(added)

    def _get_package_deps(self, pkg):
        """
        Return all direct (1st level) deps for a package.
        """
        assert pkg is not None
        result = set()

        q = self.q_binary_packages.filter(provides=pkg.requires).apply()
        for req in pkg.requires:
            deps = self.finished_get_package_deps_reqs.setdefault(str(req), set())
            if deps:
                result.update(deps)
                continue

            # TODO: need query also debuginfo
            deps = q.filter(provides=req)
            if deps:
                deps = self._get_best_package(deps, req=req)
                self.finished_get_package_deps_reqs[str(req)].update(deps)
                result.update(deps)

        return result

    @Profiler("Gather.add_initial_packages()")
    def add_initial_packages(self, pattern_list):
        added = set()

        excludes = []
        includes = []
        for pattern in pattern_list:
            if pattern.startswith("-"):
                excludes.append(pattern[1:])
            else:
                includes.append(pattern)

        exclude = set()
        for pattern in excludes:
            with Profiler("Gather.add_initial_packages():exclude"):
                # TODO: debug, source
                if pattern.endswith(".+"):
                    pkgs = self.q_multilib_binary_packages.filter_autoglob(name=pattern[:-2])
                else:
                    pkgs = self.q_binary_packages.filter_autoglob(name=pattern)

                exclude.update(pkgs)
                self.logger.debug("EXCLUDED: %s" % list(pkgs))
                self.dnf._sack.add_excludes(pkgs)

        # HACK
        self.q_binary_packages = self.q_binary_packages.filter(pkg=[i for i in self.q_binary_packages if i not in exclude]).apply()
        self.q_native_binary_packages = self.q_native_binary_packages.filter(pkg=[i for i in self.q_native_binary_packages if i not in exclude]).apply()
        self.q_multilib_binary_packages = self.q_multilib_binary_packages.filter(pkg=[i for i in self.q_multilib_binary_packages if i not in exclude]).apply()
        self.q_noarch_binary_packages = self.q_noarch_binary_packages.filter(pkg=[i for i in self.q_noarch_binary_packages if i not in exclude]).apply()

        self.init_query_cache()

        for pattern in includes:
            with Profiler("Gather.add_initial_packages():include"):
                if pattern == "system-release" and self.opts.greedy_method == "all":
                    pkgs = self.q_binary_packages.filter(provides=hawkey.Reldep(self.dnf.sack, "system-release")).apply()
                else:
                    if pattern.endswith(".+"):
                        pkgs = self.q_multilib_binary_packages.filter_autoglob(name=pattern[:-2]).apply()
                    else:
                        pkgs = self.q_binary_packages.filter_autoglob(name=pattern).apply()

                pkgs = self._get_best_package(pkgs)
                if pkgs:
                    added.update(pkgs)
                else:
                    self.logger.error("Doesn't match: %s" % pattern)

        for pkg in added:
            self._set_flag(pkg, "input")

        native_binary_packages = set(self.q_native_binary_packages)

        if self.opts.greedy_method == "build":
            for pkg in added.copy():
                with Profiler("Gather.add_initial_packages():greedy-build"):
                    if pkg in native_binary_packages:
                        greedy_build_packages = self.q_native_pkgs_by_sourcerpm_cache.get(pkg.sourcerpm) or []
                    else:
                        greedy_build_packages = self.q_multilib_pkgs_by_sourcerpm_cache.get(pkg.sourcerpm) or []
                    greedy_build_packages += self.q_noarch_pkgs_by_sourcerpm_cache.get(pkg.sourcerpm) or []

                    for greedy_pkg in greedy_build_packages[:]:
                        # filter out packages that don't provide package name
                        provides = set([str(i).split(" ")[0] for i in greedy_pkg.provides])
                        if pkg.name not in provides:
                            greedy_build_packages.remove(greedy_pkg)

                    for i in greedy_build_packages:
                        self._set_flag(i, "input", "greedy:build")
                        added.add(i)

        return added

    @Profiler("Gather.init_query_cache()")
    def init_query_cache(self):
        # HACK: workaround for insufficient hawkey query performance
        # Must be executed *after* add_initial_packages() to exclude packages properly.

        # source
        self.source_pkgs_cache = QueryCache(self.q_source_packages, "name", "version", "release")

        # debug
        self.native_debug_packages_cache = QueryCache(self.q_native_debug_packages, "sourcerpm")
        self.multilib_debug_packages_cache = QueryCache(self.q_multilib_debug_packages, "sourcerpm")

        # packages by sourcerpm
        self.q_native_pkgs_by_sourcerpm_cache = QueryCache(self.q_native_binary_packages, "sourcerpm", arch__neq="noarch")
        self.q_multilib_pkgs_by_sourcerpm_cache = QueryCache(self.q_multilib_binary_packages, "sourcerpm", arch__neq="noarch")
        self.q_noarch_pkgs_by_sourcerpm_cache = QueryCache(self.q_native_binary_packages, "sourcerpm", arch="noarch")

        # multilib
        self.q_multilib_binary_packages_cache = QueryCache(self.q_multilib_binary_packages, "name", "version", "release", arch__neq="noarch")

        # prepopulate
        self.prepopulate_cache = QueryCache(self.q_binary_packages, "name", "arch")

    @Profiler("Gather.add_prepopulate_packages()")
    def add_prepopulate_packages(self):
        added = set()

        for name_arch in self.opts.prepopulate:
            name, arch = name_arch.rsplit(".", 1)
            pkgs = self.prepopulate_cache.get(name, arch)
            pkgs = self._get_best_package(pkgs)
            if pkgs:
                added.update(pkgs)
            else:
                self.logger.warn("Prepopulate: Doesn't match: %s" % name_arch)

        for pkg in added:
            self._set_flag(pkg, "prepopulate")

        return added

    @Profiler("Gather.add_binary_package_deps()")
    def add_binary_package_deps(self):
        added = set()

        if not self.opts.resolve_deps:
            return added

        for pkg in self.result_binary_packages.copy():
            assert pkg is not None

            try:
                deps = self.finished_add_binary_package_deps[pkg]
            except KeyError:
                deps = self._get_package_deps(pkg)
                for i in deps:
                    if i not in self.result_binary_packages:
                        self._add_packages([i], pulled_by=pkg)
                        added.add(i)
                self.finished_add_binary_package_deps[pkg] = deps

        return added

    @Profiler("Gather.add_conditional_packages()")
    def add_conditional_packages(self):
        """
        For each binary package add their conditional dependencies as specified in comps.
        Return newly added packages.
        """
        added = set()

        if not self.opts.resolve_deps:
            return added

        for pkg in self.result_binary_packages.copy():
            assert pkg is not None

            try:
                deps = self.finished_add_conditional_packages[pkg]
            except KeyError:
                deps = set()
                for cond in self.conditional_packages:
                    if cond["name"] != pkg.name:
                        continue
                    pkgs = self.q_binary_packages.filter(name=cond["install"]).apply()
                    pkgs = self._get_best_package(pkgs)  # TODO: multilib?
                    deps.update(pkgs)
                self.finished_add_conditional_packages[pkg] = deps

            for i in deps:
                if i not in self.result_binary_packages:
                    self._add_packages([i], pulled_by=pkg)
                    self._set_flag(pkg, "conditional")
                    added.add(i)

        return added

    @Profiler("Gather.add_source_package_deps()")
    def add_source_package_deps(self):
        added = set()

        if not self.opts.selfhosting:
            return added

        for pkg in self.result_source_packages:
            assert pkg is not None

            try:
                deps = self.finished_add_source_package_deps[pkg]
            except KeyError:
                deps = self._get_package_deps(pkg)
                self.finished_add_source_package_deps[pkg] = deps
                for i in deps:
                    if i not in self.result_binary_packages:
                        self._add_packages([i], pulled_by=pkg)
                        added.add(i)
                        self._set_flag(pkg, "self-hosting")

        return added

    @Profiler("Gather.add_source_packages()")
    def add_source_packages(self):
        """
        For each binary package add it's source package.
        Return newly added source packages.
        """
        added = set()

        for pkg in self.result_binary_packages:
            assert pkg is not None

            try:
                source_pkg = self.finished_add_source_packages[pkg]
            except KeyError:
                source_pkg = None
                if pkg.sourcerpm:
                    source_pkg = self.sourcerpm_cache.get(pkg.sourcerpm, None)
                    if source_pkg is None:
                        nvra = parse_nvra(pkg.sourcerpm)
                        source_pkgs = self.source_pkgs_cache.get(nvra["name"], nvra["version"], nvra["release"])
                        if source_pkgs:
                            source_pkg = list(source_pkgs)[0]
                            self.sourcerpm_cache[pkg.sourcerpm] = source_pkg
                self.finished_add_source_packages[pkg] = source_pkg

            if not source_pkg:
                continue

            lookaside = self._has_flag(pkg, "lookaside")
            if lookaside:
                self._set_flag(source_pkg, "lookaside")
            if source_pkg not in self.result_source_packages:
                added.add(source_pkg)
            self.result_source_packages.add(source_pkg)

        return added

    @Profiler("Gather.add_debug_packages()")
    def add_debug_packages(self):
        """
        For each binary package add debuginfo packages built from the same source.
        Return newly added debug packages.
        """
        added = set()

        for pkg in self.result_binary_packages:
            assert pkg is not None

            if self.is_noarch_package(pkg):
                self.finished_add_debug_packages[pkg] = []
                continue

            try:
                debug_pkgs = self.finished_add_debug_packages[pkg]
            except KeyError:
                debug_pkgs = []
                if pkg.sourcerpm:
                    if self.is_native_package(pkg):
                        debug_pkgs = self.native_debug_packages_cache.get(pkg.sourcerpm)
                    else:
                        debug_pkgs = self.multilib_debug_packages_cache.get(pkg.sourcerpm)

            if not debug_pkgs:
                continue

            lookaside = self._has_flag(pkg, "lookaside")
            for i in debug_pkgs:
                if lookaside:
                    self._set_flag(i, "lookaside")
                if i not in self.result_debug_packages:
                    added.add(i)

            self.finished_add_debug_packages[pkg] = debug_pkgs
            self.result_debug_packages.update(debug_pkgs)

        return added

    @Profiler("Gather.add_fulltree_packages()")
    def add_fulltree_packages(self):
        """
        For each binary package add all binary packages built from the same source.
        Return newly added binary packages.
        """
        added = set()

        if not self.opts.fulltree:
            return added

        for pkg in sorted(self.result_binary_packages):
            assert pkg is not None

            try:
                fulltree_pkgs = self.finished_add_fulltree_packages[pkg]
            except KeyError:
                native_fulltree_pkgs = self.q_native_pkgs_by_sourcerpm_cache.get(pkg.sourcerpm) or []
                multilib_fulltree_pkgs = self.q_multilib_pkgs_by_sourcerpm_cache.get(pkg.sourcerpm) or []
                noarch_fulltree_pkgs = self.q_noarch_pkgs_by_sourcerpm_cache.get(pkg.sourcerpm) or []

                if not native_fulltree_pkgs:
                    # no existing native pkgs -> pull multilib
                    pull_native = False
                elif set(native_fulltree_pkgs) & self.result_binary_packages:
                    # native pkgs in result -> pull native
                    pull_native = True
                elif set(multilib_fulltree_pkgs) & self.result_binary_packages:
                    # multilib pkgs in result -> pull multilib
                    pull_native = False
                else:
                    # fallback / default
                    pull_native = True

                if pull_native:
                    fulltree_pkgs = native_fulltree_pkgs
                else:
                    fulltree_pkgs = multilib_fulltree_pkgs

                # always pull all noarch subpackages
                fulltree_pkgs += noarch_fulltree_pkgs

            for i in fulltree_pkgs:
                if i not in self.result_binary_packages:
                    self._add_packages([i])
                    self._set_flag(i, "fulltree")
                    added.add(i)

                # don't run fulltree on added packages
                self.finished_add_fulltree_packages[i] = []

            self.finished_add_fulltree_packages[pkg] = fulltree_pkgs

        return added

    @Profiler("Gather.add_langpack_packages()")
    def add_langpack_packages(self, langpack_patterns):
        """
        For each binary package add all matching langpack packages.
        Return newly added binary packages.

        langpack_patterns: [{"name": <str>, "install": <str>}]
        """
        added = set()

        if not self.opts.langpacks:
            return added

        exceptions = ["man-pages-overrides"]

        for pkg in sorted(self.result_binary_packages):
            assert pkg is not None

            try:
                langpack_pkgs = self.finished_add_langpack_packages[pkg]
            except KeyError:
                patterns = [i["install"] for i in langpack_patterns if i["name"] == pkg.name]
                patterns = [i.replace("%s", "*") for i in patterns]

                if not patterns:
                    self.finished_add_langpack_packages[pkg] = []
                    continue

                langpack_pkgs = self.q_binary_packages.filter(name__glob=patterns).apply()
                langpack_pkgs = langpack_pkgs.filter(name__glob__not=["*-devel", "*-static"])
                langpack_pkgs = langpack_pkgs.filter(name__neq=exceptions)

            pkgs_by_name = {}
            for i in langpack_pkgs:
                pkgs_by_name.setdefault(i.name, set()).add(i)

            langpack_pkgs = set()
            for name in sorted(pkgs_by_name):
                pkgs = pkgs_by_name[name]
                i = self._get_best_package(pkgs)
                if i:
                    # TODO: greedy
                    i = i[0]
                langpack_pkgs.add(i)
                self._set_flag(i, "langpack")
                if i not in self.result_binary_packages:
                    self._add_packages([i], pulled_by=pkg)
                    added.add(pkg)
            self.finished_add_langpack_packages[pkg] = langpack_pkgs

        return added

    @Profiler("Gather.add_multilib_packages()")
    def add_multilib_packages(self):
        added = set()

        if not self.opts.multilib_methods or self.opts.multilib_methods == ["none"]:
            return added

        for pkg in sorted(self.result_binary_packages):
            try:
                self.finished_add_multilib_packages[pkg]
            except KeyError:

                if pkg.arch in ("noarch", "src", "nosrc"):
                    self.finished_add_multilib_packages[pkg] = None
                    continue

                if pkg.arch in self.dnf.arch_wrapper.multilib_arches:
                    self.finished_add_multilib_packages[pkg] = None
                    continue

                pkgs = self.q_multilib_binary_packages_cache.get(pkg.name, pkg.version, pkg.release)
                pkgs = self._get_best_package(pkgs)
                multilib_pkgs = []
                for i in pkgs:
                    is_multilib = self._multilib.is_multilib(i)
                    if is_multilib:
                        multilib_pkgs.append(i)
                        added.add(i)
                        self._set_flag(i, "multilib")
                        self._add_packages([i])
                        self.finished_add_multilib_packages[pkg] = i
                        # TODO: ^^^ may get multiple results; i686, i586, etc.

        return added

    @Profiler("Gather.gather()")
    def gather(self, pattern_list, conditional_packages=None):
        self.conditional_packages = conditional_packages or []

        self.logger.debug("INITIAL PACKAGES")
        added = self.add_initial_packages(pattern_list)
        self._add_packages(added)

        self.logger.debug("PREPOPULATE")
        added = self.add_prepopulate_packages()
        self._add_packages(added)

        pass_num = 0
        added = False
        while 1:
            if pass_num > 0 and not added:
                break
            pass_num += 1
            self.logger.debug("PASS %s" % pass_num)

            self.logger.debug("DEPS")
            added = self.add_conditional_packages()
            self.logger.debug("ADDED: %s" % bool(added))
            if added:
                continue

            # resolve deps
            self.logger.debug("DEPS")
            added = self.add_binary_package_deps()
            self.logger.debug("ADDED: %s" % bool(added))
            if added:
                continue

            added = self.add_source_package_deps()
            self.logger.debug("ADDED: %s" % bool(added))
            if added:
                continue

            self.logger.debug("SOURCE PACKAGES")
            added = self.add_source_packages()
            self.logger.debug("ADDED: %s" % bool(added))
            if added:
                continue

            self.logger.debug("DEBUG PACKAGES")
            added = self.add_debug_packages()
            self.logger.debug("ADDED: %s" % bool(added))
            if added:
                continue
            # TODO: debug deps

            self.logger.debug("FULLTREE")
            added = self.add_fulltree_packages()
            self.logger.debug("ADDED: %s" % bool(added))
            if added:
                continue

            self.logger.debug("LANGPACKS")
            added = self.add_langpack_packages(self.opts.langpacks)
            self.logger.debug("ADDED: %s" % bool(added))
            if added:
                continue

            self.logger.debug("MULTILIB")
            added = self.add_multilib_packages()
            self.logger.debug("ADDED: %s" % bool(added))
            if added:
                continue

            # nothing added -> break depsolving cycle
            break
