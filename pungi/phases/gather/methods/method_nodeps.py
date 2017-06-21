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


import pungi.arch
from pungi.util import pkg_is_rpm, pkg_is_srpm, pkg_is_debug
from pungi.wrappers.comps import CompsWrapper

import pungi.phases.gather.method
from kobo.pkgset import SimpleRpmWrapper, RpmWrapper


class GatherMethodNodeps(pungi.phases.gather.method.GatherMethodBase):
    enabled = True

    def __call__(self, arch, variant, pkgs, groups, filter_packages,
                 multilib_whitelist, multilib_blacklist, package_sets,
                 path_prefix=None, fulltree_excludes=None, prepopulate=None):
        global_pkgset = package_sets["global"]
        result = {
            "rpm": [],
            "srpm": [],
            "debuginfo": [],
        }

        group_packages = expand_groups(self.compose, arch, groups)
        packages = pkgs | group_packages

        seen_rpms = {}
        seen_srpms = {}

        valid_arches = pungi.arch.get_valid_arches(arch, multilib=True)
        compatible_arches = {}
        for i in valid_arches:
            compatible_arches[i] = pungi.arch.get_compatible_arches(i)

        for i in global_pkgset:
            pkg = global_pkgset[i]
            if not pkg_is_rpm(pkg):
                continue
            for gathered_pkg, pkg_arch in packages:
                if pkg.arch not in valid_arches:
                    continue
                if (type(gathered_pkg) in [str, unicode]
                        and pkg.name != gathered_pkg):
                    continue
                elif (type(gathered_pkg) in [SimpleRpmWrapper, RpmWrapper]
                      and pkg.nevra != gathered_pkg.nevra):
                    continue
                if pkg_arch is not None and pkg.arch != pkg_arch:
                    continue
                result["rpm"].append({
                    "path": pkg.file_path,
                    "flags": ["input"],
                })
                seen_rpms.setdefault(pkg.name, set()).add(pkg.arch)
                seen_srpms.setdefault(pkg.sourcerpm, set()).add(pkg.arch)

        for i in global_pkgset:
            pkg = global_pkgset[i]
            if not pkg_is_srpm(pkg):
                continue
            if pkg.file_name in seen_srpms:
                result["srpm"].append({
                    "path": pkg.file_path,
                    "flags": ["input"],
                })

        for i in global_pkgset:
            pkg = global_pkgset[i]
            if pkg.arch not in valid_arches:
                continue
            if not pkg_is_debug(pkg):
                continue
            if pkg.sourcerpm not in seen_srpms:
                continue
            if not set(compatible_arches[pkg.arch]) & set(seen_srpms[pkg.sourcerpm]):
                # this handles stuff like i386 debuginfo in a i686 package
                continue
            result["debuginfo"].append({
                "path": pkg.file_path,
                "flags": ["input"],
            })

        return result


def expand_groups(compose, arch, groups):
    """Read comps file filtered for given architecture and return all packages
    in given groups.

    :returns: A set of tuples (pkg_name, arch)
    """
    comps_file = compose.paths.work.comps(arch, create_dir=False)
    comps = CompsWrapper(comps_file)
    packages = set()

    for group in groups:
        packages.update([(pkg, arch) for pkg in comps.get_packages(group)])

    return packages
