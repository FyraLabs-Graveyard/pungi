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


import os
import shutil
import json

from kobo.rpmlib import parse_nvra
from productmd.rpms import Rpms

from pungi.wrappers.scm import get_file_from_scm
from .link import link_files

from pungi.util import get_arch_variant_data, get_arch_data, get_variant_data
from pungi.phases.base import PhaseBase
from pungi.arch import split_name_arch, get_compatible_arches


def get_gather_source(name):
    import pungi.phases.gather.sources
    from .source import GatherSourceContainer
    GatherSourceContainer.register_module(pungi.phases.gather.sources)
    container = GatherSourceContainer()
    return container["GatherSource%s" % name]


def get_gather_method(name):
    import pungi.phases.gather.methods
    from .method import GatherMethodContainer
    GatherMethodContainer.register_module(pungi.phases.gather.methods)
    container = GatherMethodContainer()
    return container["GatherMethod%s" % name]


class GatherPhase(PhaseBase):
    """GATHER"""
    name = "gather"

    def __init__(self, compose, pkgset_phase):
        PhaseBase.__init__(self, compose)
        # pkgset_phase provides package_sets and path_prefix
        self.pkgset_phase = pkgset_phase
        # Prepare empty manifest
        self.manifest_file = self.compose.paths.compose.metadata("rpms.json")
        self.manifest = Rpms()
        self.manifest.compose.id = self.compose.compose_id
        self.manifest.compose.type = self.compose.compose_type
        self.manifest.compose.date = self.compose.compose_date
        self.manifest.compose.respin = self.compose.compose_respin

    def validate(self):
        errors = []
        try:
            super(GatherPhase, self).validate()
        except ValueError as exc:
            errors = exc.message.split('\n')

        # This must be imported here to avoid circular deps problems.
        from pungi.phases.pkgset.sources import source_koji
        if not source_koji.WITH_MODULES:
            # Modules are not supported, check if we need them
            for variant in self.compose.variants.values():
                if variant.modules:
                    errors.append('Modular compose requires pdc_client and libmodulemd packages.')

        if errors:
            raise ValueError('\n'.join(errors))

    def _write_manifest(self):
        self.compose.log_info("Writing RPM manifest: %s" % self.manifest_file)
        self.manifest.dump(self.manifest_file)

    def run(self):
        pkg_map = gather_wrapper(self.compose, self.pkgset_phase.package_sets,
                                 self.pkgset_phase.path_prefix)

        for arch in self.compose.get_arches():
            for variant in self.compose.get_variants(arch=arch):
                if variant.is_empty:
                    continue
                link_files(self.compose, arch, variant,
                           pkg_map[arch][variant.uid],
                           self.pkgset_phase.package_sets,
                           manifest=self.manifest)

    def stop(self):
        self._write_manifest()
        super(GatherPhase, self).stop()


def _mk_pkg_map(rpm=None, srpm=None, debuginfo=None, iterable_class=list):
    return {
        "rpm": rpm or iterable_class(),
        "srpm": srpm or iterable_class(),
        "debuginfo": debuginfo or iterable_class(),
    }


def get_parent_pkgs(arch, variant, result_dict):
    """Find packages for parent variant (if any).

    :param result_dict: already known packages; a mapping from arch to variant uid
                        to package type to a list of dicts with path to package
    """
    result = _mk_pkg_map(iterable_class=set)
    if variant.parent is None:
        return result
    for pkg_type, pkgs in result_dict.get(arch, {}).get(variant.parent.uid, {}).items():
        for pkg in pkgs:
            nvra = parse_nvra(pkg["path"])
            result[pkg_type].add((nvra["name"], nvra["arch"]))
    return result


def gather_packages(compose, arch, variant, package_sets, fulltree_excludes=None):
    # multilib white/black-list is per-arch, common for all variants
    multilib_whitelist = get_multilib_whitelist(compose, arch)
    multilib_blacklist = get_multilib_blacklist(compose, arch)
    methods = compose.conf["gather_method"]
    global_method_name = methods
    if isinstance(methods, dict):
        try:
            methods = get_variant_data(compose.conf, 'gather_method', variant)[-1]
            global_method_name = None
        except IndexError:
            raise RuntimeError("Variant %s has no configured gather_method" % variant.uid)

    msg = "Gathering packages (arch: %s, variant: %s)" % (arch, variant)

    if variant.is_empty:
        compose.log_info("[SKIP ] %s" % msg)
        return _mk_pkg_map()

    compose.log_info("[BEGIN] %s" % msg)

    result = {
        "rpm": [],
        "srpm": [],
        "debuginfo": [],
    }

    prepopulate = get_prepopulate_packages(compose, arch, variant)
    fulltree_excludes = fulltree_excludes or set()

    for source_name in ('module', 'comps', 'json'):

        packages, groups, filter_packages = get_variant_packages(compose, arch, variant,
                                                                 source_name, package_sets)
        if not packages and not groups:
            # No inputs, nothing to do really.
            continue

        try:
            method_name = global_method_name or methods[source_name]
        except KeyError:
            raise RuntimeError("Variant %s has no configured gather_method for source %s"
                               % (variant.uid, source_name))

        GatherMethod = get_gather_method(method_name)
        method = GatherMethod(compose)
        method.source_name = source_name
        compose.log_debug("Gathering source %s, method %s" % (source_name, method_name))
        pkg_map = method(arch, variant, packages, groups, filter_packages,
                         multilib_whitelist, multilib_blacklist, package_sets,
                         fulltree_excludes=fulltree_excludes,
                         prepopulate=prepopulate if source_name == 'comps' else set())

        for t in ('rpm', 'srpm', 'debuginfo'):
            result[t].extend(pkg_map.get(t, []))

    compose.log_info("[DONE ] %s" % msg)
    return result


def write_packages(compose, arch, variant, pkg_map, path_prefix):
    """Write a list of packages to a file (one per package type).

    If any path begins with ``path_prefix``, this prefix will be stripped.
    """
    msg = "Writing package list (arch: %s, variant: %s)" % (arch, variant)
    compose.log_info("[BEGIN] %s" % msg)

    for pkg_type, pkgs in pkg_map.items():
        file_name = compose.paths.work.package_list(arch=arch, variant=variant, pkg_type=pkg_type)
        with open(file_name, "w") as pkg_list:
            for pkg in pkgs:
                # TODO: flags?
                pkg_path = pkg["path"]
                if pkg_path.startswith(path_prefix):
                    pkg_path = pkg_path[len(path_prefix):]
                pkg_list.write("%s\n" % pkg_path)

    compose.log_info("[DONE ] %s" % msg)


def trim_packages(compose, arch, variant, pkg_map, parent_pkgs=None, remove_pkgs=None):
    """Remove parent variant's packages from pkg_map <-- it gets modified in this function

    There are three cases where changes may happen:

     * If a package is mentioned explicitly in ``remove_pkgs``, it will be
       removed from the addon. Sources and debuginfo are not removed from
       layered-products though.
     * If a packages is present in parent, it will be removed from addon
       unconditionally.
     * A package in addon that is not present in parent and has
       ``fulltree-exclude`` flag will be moved to parent (unless it's
       explicitly included into the addon).

    :param parent_pkgs: mapping from pkg_type to a list of tuples (name, arch)
                        of packages present in parent variant
    :param remove_pkgs: mapping from pkg_type to a list of package names to be
                        removed from the variant
    """
    # TODO: remove debuginfo and srpm leftovers

    if not variant.parent:
        return

    msg = "Trimming package list (arch: %s, variant: %s)" % (arch, variant)
    compose.log_info("[BEGIN] %s" % msg)

    remove_pkgs = remove_pkgs or {}
    parent_pkgs = parent_pkgs or {}

    addon_pkgs = _mk_pkg_map(iterable_class=set)
    move_to_parent_pkgs = _mk_pkg_map()
    removed_pkgs = _mk_pkg_map()
    for pkg_type, pkgs in pkg_map.items():

        new_pkgs = []
        for pkg in pkgs:
            pkg_path = pkg["path"]
            if not pkg_path:
                continue
            nvra = parse_nvra(pkg_path)
            key = ((nvra["name"], nvra["arch"]))

            if nvra["name"] in remove_pkgs.get(pkg_type, set()):
                # TODO: make an option to turn this off
                if variant.type == "layered-product" and pkg_type in ("srpm", "debuginfo"):
                    new_pkgs.append(pkg)
                    # User may not have addons available, therefore we need to
                    # keep addon SRPMs in layered products in order not to violate GPL.
                    # The same applies on debuginfo availability.
                    continue
                compose.log_warning("Removed addon package (arch: %s, variant: %s): %s: %s" % (
                    arch, variant, pkg_type, pkg_path))
                removed_pkgs[pkg_type].append(pkg)
            elif key not in parent_pkgs.get(pkg_type, set()):
                if "fulltree-exclude" in pkg["flags"] and "input" not in pkg["flags"]:
                    # If a package wasn't explicitly included ('input') in an
                    # addon, move it to parent variant (cannot move it to
                    # optional, because addons can't depend on optional). This
                    # is a workaround for not having $addon-optional.
                    move_to_parent_pkgs[pkg_type].append(pkg)
                else:
                    new_pkgs.append(pkg)
                    addon_pkgs[pkg_type].add(nvra["name"])
            else:
                removed_pkgs[pkg_type].append(pkg)

        pkg_map[pkg_type] = new_pkgs
        compose.log_info("Removed packages (arch: %s, variant: %s): %s: %s" % (
            arch, variant, pkg_type, len(removed_pkgs[pkg_type])))
        compose.log_info("Moved to parent (arch: %s, variant: %s): %s: %s" % (
            arch, variant, pkg_type, len(move_to_parent_pkgs[pkg_type])))

    compose.log_info("[DONE ] %s" % msg)
    return addon_pkgs, move_to_parent_pkgs, removed_pkgs


def _gather_variants(result, compose, variant_type, package_sets, exclude_fulltree=False):
    """Run gathering on all arches of all variants of given type.

    If ``exclude_fulltree`` is set, all source packages from parent variants
    will be added to fulltree excludes for the processed variants.
    """
    for arch in compose.get_arches():
        for variant in compose.get_variants(arch=arch, types=[variant_type]):
            fulltree_excludes = set()
            if exclude_fulltree:
                for pkg_name, pkg_arch in get_parent_pkgs(arch, variant, result)["srpm"]:
                    fulltree_excludes.add(pkg_name)
            pkg_map = gather_packages(compose, arch, variant, package_sets, fulltree_excludes=fulltree_excludes)
            result.setdefault(arch, {})[variant.uid] = pkg_map


def _trim_variants(result, compose, variant_type, remove_pkgs=None, move_to_parent=True):
    """Trim all varians of given type.

    Returns a map of all packages included in these variants.
    """
    all_included_packages = {}
    for arch in compose.get_arches():
        for variant in compose.get_variants(arch=arch, types=[variant_type]):
            pkg_map = result[arch][variant.uid]
            parent_pkgs = get_parent_pkgs(arch, variant, result)
            included_packages, move_to_parent_pkgs, removed_pkgs = trim_packages(
                compose, arch, variant, pkg_map, parent_pkgs, remove_pkgs=remove_pkgs)

            # update all_addon_pkgs
            for pkg_type, pkgs in included_packages.items():
                all_included_packages.setdefault(pkg_type, set()).update(pkgs)

            if move_to_parent:
                # move packages to parent
                parent_pkg_map = result[arch][variant.parent.uid]
                for pkg_type, pkgs in move_to_parent_pkgs.items():
                    for pkg in pkgs:
                        compose.log_debug("Moving package to parent (arch: %s, variant: %s, pkg_type: %s): %s"
                                          % (arch, variant.uid, pkg_type, os.path.basename(pkg["path"])))
                        if pkg not in parent_pkg_map[pkg_type]:
                            parent_pkg_map[pkg_type].append(pkg)
    return all_included_packages


def gather_wrapper(compose, package_sets, path_prefix):
    result = {}

    _gather_variants(result, compose, 'variant', package_sets)
    _gather_variants(result, compose, 'addon', package_sets, exclude_fulltree=True)
    _gather_variants(result, compose, 'layered-product', package_sets, exclude_fulltree=True)
    _gather_variants(result, compose, 'optional', package_sets)

    all_addon_pkgs = _trim_variants(result, compose, 'addon')
    # TODO do we really want to move packages to parent here?
    all_lp_pkgs = _trim_variants(result, compose, 'layered-product', remove_pkgs=all_addon_pkgs)

    # merge all_addon_pkgs with all_lp_pkgs
    for pkg_type in set(all_addon_pkgs.keys()) | set(all_lp_pkgs.keys()):
        all_addon_pkgs.setdefault(pkg_type, set()).update(all_lp_pkgs.get(pkg_type, set()))

    _trim_variants(result, compose, 'optional', remove_pkgs=all_addon_pkgs, move_to_parent=False)

    # write packages (package lists) for all variants
    for arch in compose.get_arches():
        for variant in compose.get_variants(arch=arch):
            pkg_map = result[arch][variant.uid]
            write_packages(compose, arch, variant, pkg_map, path_prefix=path_prefix)

    return result


def write_prepopulate_file(compose):
    """Download prepopulate file according to configuration.

    It is stored in a location where ``get_prepopulate_packages`` function
    expects.
    """
    if 'gather_prepopulate' not in compose.conf:
        return

    prepopulate_file = os.path.join(compose.paths.work.topdir(arch="global"), "prepopulate.json")
    msg = "Writing prepopulate file: %s" % prepopulate_file

    if compose.DEBUG and os.path.isfile(prepopulate_file):
        compose.log_warning("[SKIP ] %s" % msg)
    else:
        scm_dict = compose.conf["gather_prepopulate"]
        if isinstance(scm_dict, dict):
            file_name = os.path.basename(scm_dict["file"])
            if scm_dict["scm"] == "file":
                scm_dict["file"] = os.path.join(compose.config_dir, os.path.basename(scm_dict["file"]))
        else:
            file_name = os.path.basename(scm_dict)
            scm_dict = os.path.join(compose.config_dir, os.path.basename(scm_dict))

        compose.log_debug(msg)
        tmp_dir = compose.mkdtemp(prefix="prepopulate_file_")
        get_file_from_scm(scm_dict, tmp_dir, logger=compose._logger)
        shutil.copy2(os.path.join(tmp_dir, file_name), prepopulate_file)
        shutil.rmtree(tmp_dir)


def get_prepopulate_packages(compose, arch, variant, include_arch=True):
    """Read prepopulate file and return list of packages for given tree.

    If ``variant`` is ``None``, all variants in the file are considered. The
    result of this function is a set of strings of format
    ``package_name.arch``. If ``include_arch`` is False, the ".arch" suffix
    is not included in packages in returned list.
    """
    result = set()

    prepopulate_file = os.path.join(compose.paths.work.topdir(arch="global"), "prepopulate.json")
    if not os.path.isfile(prepopulate_file):
        return result

    with open(prepopulate_file, "r") as f:
        prepopulate_data = json.load(f)

    variants = [variant.uid] if variant else prepopulate_data.keys()

    for var in variants:
        for build, packages in prepopulate_data.get(var, {}).get(arch, {}).items():
            for i in packages:
                pkg_name, pkg_arch = split_name_arch(i)
                if pkg_arch not in get_compatible_arches(arch, multilib=True):
                    raise ValueError(
                        "Incompatible package arch '%s' for tree arch '%s' in prepopulate package '%s'"
                        % (pkg_arch, arch, pkg_name))
                if include_arch:
                    result.add(i)
                else:
                    result.add(pkg_name)
    return result


def get_additional_packages(compose, arch, variant):
    result = set()
    for i in get_arch_variant_data(compose.conf, "additional_packages", arch, variant):
        pkg_name, pkg_arch = split_name_arch(i)
        if pkg_arch is not None and pkg_arch not in get_compatible_arches(arch, multilib=True):
            raise ValueError(
                "Incompatible package arch '%s' for tree arch '%s' in additional package '%s'"
                % (pkg_arch, arch, pkg_name))
        result.add((pkg_name, pkg_arch))
    return result


def get_filter_packages(compose, arch, variant):
    result = set()
    for i in get_arch_variant_data(compose.conf, "filter_packages", arch, variant):
        result.add(split_name_arch(i))
    return result


def get_multilib_whitelist(compose, arch):
    return set(get_arch_data(compose.conf, "multilib_whitelist", arch))


def get_multilib_blacklist(compose, arch):
    return set(get_arch_data(compose.conf, "multilib_blacklist", arch))


def get_lookaside_repos(compose, arch, variant):
    return get_arch_variant_data(compose.conf, "gather_lookaside_repos", arch, variant)


def get_variant_packages(compose, arch, variant, source_name, package_sets=None):
    """Find inputs for depsolving of variant.arch combination.

    Returns a triple: a list of input packages, a list of input comps groups
    and a list of packages to be filtered out of the variant.

    For addons and layered products the inputs of parent variant are added as
    well. For optional it's parent and all its addons and layered products.

    The filtered packages are never inherited from parent.

    When system-release packages should be filtered, the ``package_sets``
    argument is required.
    """
    packages, groups, filter_packages = set(), set(), set()
    GatherSource = get_gather_source(source_name)
    source = GatherSource(compose)
    p, g = source(arch, variant)

    if source_name != "comps" and not p and not g:
        # For modules and json source, if the source did not return anything,
        # we should skip all further work. Additional packages and possibly
        # system-release will be added to comps source.
        return packages, groups, filter_packages

    packages |= p
    groups |= g

    if variant is None:
        # no variant -> no parent -> we have everything we need
        # doesn't make sense to do any package filtering
        return packages, groups, filter_packages

    if source_name == 'comps':
        packages |= get_additional_packages(compose, arch, variant)
    filter_packages |= get_filter_packages(compose, arch, variant)

    if compose.conf['filter_system_release_packages']:
        system_release_packages, system_release_filter_packages = get_system_release_packages(
            compose, arch, variant, package_sets)
        packages |= system_release_packages
        filter_packages |= system_release_filter_packages

    if variant.type == "optional":
        for var in variant.parent.get_variants(
                arch=arch, types=["self", "variant", "addon", "layered-product"]):
            var_packages, var_groups, _ = get_variant_packages(
                compose, arch, var, source_name, package_sets=package_sets)
            packages |= var_packages
            groups |= var_groups

    if variant.type in ["addon", "layered-product"]:
        var_packages, var_groups, _ = get_variant_packages(
            compose, arch, variant.parent, source_name, package_sets=package_sets)
        packages |= var_packages
        groups |= var_groups

    return packages, groups, filter_packages


def get_system_release_packages(compose, arch, variant, package_sets):
    packages = set()
    filter_packages = set()

    if not package_sets or not package_sets.get(arch, None):
        return packages, filter_packages

    package_set = package_sets[arch]

    system_release_packages = set()
    for i in package_set:
        pkg = package_set[i]

        if pkg.is_system_release:
            system_release_packages.add(pkg)

    if not system_release_packages:
        return packages, filter_packages
    elif len(system_release_packages) == 1:
        # always include system-release package if available
        pkg = list(system_release_packages)[0]
        packages.add((pkg.name, None))
    else:
        if variant.type == "variant":
            # search for best match
            best_match = None
            for pkg in system_release_packages:
                if pkg.name.endswith("release-%s" % variant.uid.lower()) or pkg.name.startswith("%s-release" % variant.uid.lower()):
                    best_match = pkg
                    break
        else:
            # addons: return release packages from parent variant
            return get_system_release_packages(compose, arch, variant.parent, package_sets)

        if not best_match:
            # no package matches variant name -> pick the first one
            best_match = sorted(system_release_packages)[0]

        packages.add((best_match.name, None))
        for pkg in system_release_packages:
            if pkg.name == best_match.name:
                continue
            filter_packages.add((pkg.name, None))

    return packages, filter_packages


def get_packages_to_gather(compose, arch=None, variant=None, include_arch=True,
                           include_prepopulated=False):
    """
    Returns the list of names of packages and list of names of groups which
    would be included in a compose as GATHER phase result.

    :param str arch: Arch to return packages for. If not set, returns packages
        for all arches.
    :param Variant variant: Variant to return packages for, If not set, returns
        packages for all variants of a compose.
    :param include_arch: When True, the arch of package will be included in
        returned list as ["pkg_name.arch", ...]. Otherwise only
        ["pkg_name", ...] is returned.
    :param include_prepopulated: When True, the prepopulated packages will
        be included in a list of packages.
    """
    packages = set([])
    groups = set([])
    for source_name in ('module', 'comps', 'json'):
        GatherSource = get_gather_source(source_name)
        src = GatherSource(compose)

        arches = [arch] if arch else compose.get_arches()

        for arch in arches:
            pkgs, grps = src(arch, variant)
            groups = groups.union(set(grps))

            additional_packages = get_additional_packages(compose, arch, None)
            for pkg_name, pkg_arch in pkgs | additional_packages:
                if not include_arch or pkg_arch is None:
                    packages.add(pkg_name)
                else:
                    packages.add("%s.%s" % (pkg_name, pkg_arch))

            if include_prepopulated:
                prepopulated = get_prepopulate_packages(
                    compose, arch, variant, include_arch)
                packages = packages.union(prepopulated)

    return list(packages), list(groups)
