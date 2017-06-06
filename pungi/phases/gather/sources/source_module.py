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
        import yaml

        groups = set()
        packages = set()

        compatible_arches = pungi.arch.get_compatible_arches(arch)

        if variant is not None and variant.modules:
            variant.arch_mmds.setdefault(arch, {})

            # Contains per-module RPMs added to variant.
            added_rpms = {}

            rpms = sum([
                variant.pkgset.rpms_by_arch.get(a, [])
                for a in compatible_arches
            ], [])
            for rpm_obj in rpms:
                # Skip the RPM if it is excluded on this arch or exclusive
                # for different arch.
                if pungi.arch.is_excluded(rpm_obj, compatible_arches):
                    continue

                for mmd in variant.mmds:
                    mmd_id = "%s-%s" % (mmd.name, mmd.stream)
                    # Generate architecture specific modulemd metadata
                    # with list of artifacts only for this architecture.
                    if mmd_id not in variant.arch_mmds[arch]:
                        arch_mmd = yaml.safe_load(mmd.dumps())
                        variant.arch_mmds[arch][mmd_id] = arch_mmd
                    else:
                        arch_mmd = variant.arch_mmds[arch][mmd_id]

                    srpm = kobo.rpmlib.parse_nvr(rpm_obj.sourcerpm)["name"]
                    if (srpm in mmd.components.rpms.keys() and
                            rpm_obj.name not in mmd.filter.rpms):
                        packages.add((rpm_obj.name, None))
                        added_rpms.setdefault(mmd_id, [])
                        added_rpms[mmd_id].append(str(rpm_obj.nevra))

            # GatherSource returns all the packages in variant and does not
            # care which package is in which module, but for modular metadata
            # in the resulting compose repository, we have to know which RPM
            # is part of which module.
            # We therefore iterate over all the added packages grouped by
            # particular module and use them to filter out the packages which
            # have not been added to variant from the `arch_mmd`. This package
            # list is later used in createrepo phase to generated modules.yaml.
            for mmd_id, rpm_nevras in added_rpms.items():
                arch_mmd = variant.arch_mmds[arch][mmd_id]
                arch_mmd["data"]["artifacts"]["rpms"] = [
                    rpm_nevra for rpm_nevra in rpm_nevras
                    if rpm_nevra in arch_mmd["data"]["artifacts"]["rpms"]]

        return packages, groups
