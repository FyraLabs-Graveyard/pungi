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


"""
Get a package list based on modulemd metadata loaded in pkgset phase.
"""


import pungi.arch
import pungi.phases.gather.source
import kobo.rpmlib


class GatherSourceModule(pungi.phases.gather.source.GatherSourceBase):
    enabled = True

    def __call__(self, arch, variant):
        groups = set()
        packages = set()

        compatible_arches = pungi.arch.get_compatible_arches(arch)

        if variant is not None and variant.modules:
            rpms = sum([
                variant.pkgset.rpms_by_arch.get(a, [])
                for a in compatible_arches
            ], [])
            for rpm_obj in rpms:
                for mmd in variant.mmds:
                    srpm = kobo.rpmlib.parse_nvr(rpm_obj.sourcerpm)["name"]
                    if (srpm in mmd.components.rpms.keys() and
                            rpm_obj.name not in mmd.filter.rpms):
                        packages.add((rpm_obj.name, None))

        return packages, groups
