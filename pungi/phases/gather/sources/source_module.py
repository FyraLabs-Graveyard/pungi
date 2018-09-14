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
from pungi import Modulemd


class GatherSourceModule(pungi.phases.gather.source.GatherSourceBase):
    enabled = True

    def __call__(self, arch, variant):
        uid = variant.uid if variant else 'no-variant'
        logfile = self.compose.paths.log.log_file(arch, 'source-module-%s' % uid)
        with open(logfile, 'w') as log:
            return self.worker(log, arch, variant)

    def worker(self, log, arch, variant):
        groups = set()
        packages = set()

        # Check if this variant contains some modules
        if variant is None or variant.modules is None:
            return packages, groups

        # Check if we even support modules in Pungi.
        if not Modulemd:
            log.write(
                "pygobject module or libmodulemd library is not installed, "
                "support for modules is disabled\n")
            return packages, groups

        compatible_arches = pungi.arch.get_compatible_arches(arch, multilib=True)
        multilib_arches = set(compatible_arches) - set(
            pungi.arch.get_compatible_arches(arch))
        exclusivearchlist = pungi.arch.get_valid_arches(
            arch, multilib=False, add_noarch=False
        )

        # Generate architecture specific modulemd metadata, so we can
        # store per-architecture artifacts there later.
        variant.arch_mmds.setdefault(arch, {})
        for mmd in variant.mmds:
            mmd_id = "%s:%s:%s:%s" % (
                mmd.peek_name(),
                mmd.peek_stream(),
                mmd.peek_version(),
                mmd.peek_context(),
            )
            if mmd_id not in variant.arch_mmds[arch]:
                arch_mmd = mmd.copy()
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
            if pungi.arch.is_excluded(rpm_obj, exclusivearchlist):
                log.write('Skipping %s due to incompatible arch\n' % rpm_obj)
                continue

            for mmd in variant.mmds:
                mmd_id = "%s:%s:%s:%s" % (
                    mmd.peek_name(),
                    mmd.peek_stream(),
                    mmd.peek_version(),
                    mmd.peek_context(),
                )
                arch_mmd = variant.arch_mmds[arch][mmd_id]
                srpm = kobo.rpmlib.parse_nvr(rpm_obj.sourcerpm)["name"]

                filtered = False
                buildopts = mmd.get_buildopts()
                if buildopts:
                    whitelist = buildopts.get_rpm_whitelist()
                    if whitelist:
                        # We have whitelist, no filtering against components.
                        filtered = True
                        if srpm not in whitelist:
                            # Package is not on the list, skip it.
                            continue

                if not filtered:
                    # Skip this mmd if this RPM does not belong to it.
                    if (srpm not in mmd.get_rpm_components().keys() or
                            rpm_obj.nevra not in mmd.get_rpm_artifacts().get()):
                        continue

                # Filter out the RPM from artifacts if its filtered in MMD.
                if rpm_obj.name in mmd.get_rpm_filter().get():
                    # No need to check if the rpm_obj is in rpm artifacts,
                    # the .remove() method does that anyway.
                    arch_mmd.get_rpm_artifacts().remove(str(rpm_obj.nevra))
                    continue

                # Skip the rpm_obj if it's built for multilib arch, but
                # multilib is not enabled for this srpm in MMD.
                try:
                    mmd_component = mmd.get_rpm_components()[srpm]
                    multilib = mmd_component.get_multilib()
                    multilib = multilib.get() if multilib else set()
                    if arch not in multilib and rpm_obj.arch in multilib_arches:
                        continue
                except KeyError:
                    # No such component, disable any multilib
                    if rpm_obj.arch not in ("noarch", arch):
                        continue

                # Add RPM to packages.
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
            artifacts = arch_mmd.get_rpm_artifacts()

            # Modules without artifacts are also valid.
            if not artifacts or artifacts.size() == 0:
                continue

            added_artifacts = Modulemd.SimpleSet()
            for rpm_nevra in rpm_nevras:
                if artifacts.contains(rpm_nevra):
                    added_artifacts.add(rpm_nevra)
            arch_mmd.set_rpm_artifacts(added_artifacts)

        return packages, groups
