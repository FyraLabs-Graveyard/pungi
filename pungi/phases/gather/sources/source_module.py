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
        uid = variant.uid if variant else 'no-variant'
        logfile = self.compose.paths.log.log_file(arch, 'source-module-%s' % uid)
        with open(logfile, 'w') as log:
            return self.worker(log, arch, variant)

    def worker(self, log, arch, variant):
        import yaml

        groups = set()
        packages = set()

        # TODO: Enable multilib here and handle "multilib" field in the
        # components part of modulemd. We currently cannot do it, because
        # it is not clear what is semantic of that modulemd section.
        compatible_arches = pungi.arch.get_compatible_arches(arch, multilib=False)

        if variant is not None and variant.modules:
            variant.arch_mmds.setdefault(arch, {})

            # Generate architecture specific modulemd metadata, so we can
            # store per-architecture artifacts there later.
            for mmd in variant.mmds:
                mmd_id = "%s-%s" % (mmd.name, mmd.stream)
                if mmd_id not in variant.arch_mmds[arch]:
                    arch_mmd = yaml.safe_load(mmd.dumps())
                    variant.arch_mmds[arch][mmd_id] = arch_mmd

            # Contains per-module RPMs added to variant.
            added_rpms = {}

            rpms = sum([
                variant.pkgset.rpms_by_arch.get(a, [])
                for a in compatible_arches
            ], [])
            for rpm_obj in rpms:
                log.write('Examining %s for inclusion\n' % rpm_obj)
                # Skip the RPM if it is excluded on this arch or exclusive
                # for different arch.
                if pungi.arch.is_excluded(rpm_obj, compatible_arches):
                    log.write('Skipping %s due to incompatible arch\n' % rpm_obj)
                    continue

                for mmd in variant.mmds:
                    mmd_id = "%s-%s" % (mmd.name, mmd.stream)
                    arch_mmd = variant.arch_mmds[arch][mmd_id]

                    srpm = kobo.rpmlib.parse_nvr(rpm_obj.sourcerpm)["name"]
                    if (srpm in mmd.components.rpms.keys() and
                            rpm_obj.name not in mmd.filter.rpms and
                            rpm_obj.nevra in mmd.artifacts.rpms):
                        packages.add((rpm_obj, None))
                        added_rpms.setdefault(mmd_id, [])
                        added_rpms[mmd_id].append(str(rpm_obj.nevra))
                        log.write('Adding %s because it is in %s\n'
                                  % (rpm_obj, mmd_id))

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
                # Modules without artifacts are also valid.
                if ("artifacts" not in arch_mmd["data"] or
                        "rpms" not in arch_mmd["data"]["artifacts"]):
                    continue
                arch_mmd["data"]["artifacts"]["rpms"] = [
                    rpm_nevra for rpm_nevra in rpm_nevras
                    if rpm_nevra in arch_mmd["data"]["artifacts"]["rpms"]]

        return packages, groups
