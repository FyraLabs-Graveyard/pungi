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
        variant.dev_mmds.setdefault(arch, {})
        include_devel = self.compose.conf.get("include_devel_modules", {}).get(variant.uid, [])
        for mmd in variant.mmds:
            nsvc = "%s:%s:%s:%s" % (
                mmd.peek_name(),
                mmd.peek_stream(),
                mmd.peek_version(),
                mmd.peek_context(),
            )
            if nsvc not in variant.arch_mmds[arch]:
                arch_mmd = mmd.copy()
                variant.arch_mmds[arch][nsvc] = arch_mmd

            if self.compose.conf.get("include_devel_modules"):
                # Devel modules are enabled, we need to create it.
                devel_nsvc = "%s-devel:%s:%s:%s" % (
                    mmd.peek_name(),
                    mmd.peek_stream(),
                    mmd.peek_version(),
                    mmd.peek_context(),
                )
                if (
                    devel_nsvc not in variant.arch_mmds[arch]
                    and devel_nsvc not in variant.dev_mmds[arch]
                ):
                    arch_mmd = mmd.copy()
                    arch_mmd.set_name(arch_mmd.peek_name() + "-devel")
                    # Depend on the actual module
                    for dep in arch_mmd.get_dependencies():
                        dep.add_requires_single(mmd.peek_name(), mmd.peek_stream())
                    # Delete API and profiles
                    arch_mmd.set_rpm_api(Modulemd.SimpleSet())
                    arch_mmd.clear_profiles()

                    ns = "%s:%s" % (arch_mmd.peek_name(), arch_mmd.peek_stream())

                    # Store the new modulemd
                    variant.module_uid_to_koji_tag[devel_nsvc] = variant.module_uid_to_koji_tag.get(nsvc)
                    if ns in include_devel:
                        variant.arch_mmds[arch][devel_nsvc] = arch_mmd
                    else:
                        variant.dev_mmds[arch][devel_nsvc] = arch_mmd

        # Contains per-module RPMs added to variant.
        added_rpms = {}

        for mmd in variant.mmds:
            nsvc = "%s:%s:%s:%s" % (
                mmd.peek_name(),
                mmd.peek_stream(),
                mmd.peek_version(),
                mmd.peek_context(),
            )
            arch_mmd = variant.arch_mmds[arch][nsvc]

            rpms = sum([
                variant.nsvc_to_pkgset[nsvc].rpms_by_arch.get(a, [])
                for a in compatible_arches
            ], [])
            for rpm_obj in rpms:
                log.write('Examining %s for inclusion\n' % rpm_obj)
                # Skip the RPM if it is excluded on this arch or exclusive
                # for different arch.
                if pungi.arch.is_excluded(rpm_obj, exclusivearchlist):
                    log.write('Skipping %s due to incompatible arch\n' % rpm_obj)
                    continue

                if should_include(rpm_obj, arch, arch_mmd, multilib_arches):
                    # Add RPM to packages.
                    packages.add((rpm_obj, None))
                    added_rpms.setdefault(nsvc, [])
                    added_rpms[nsvc].append(str(rpm_obj.nevra))
                    log.write('Adding %s because it is in %s\n'
                              % (rpm_obj, nsvc))
                elif self.compose.conf.get("include_devel_modules"):
                    nsvc_devel = "%s-devel:%s:%s:%s" % (
                        mmd.peek_name(),
                        mmd.peek_stream(),
                        mmd.peek_version(),
                        mmd.peek_context(),
                    )
                    added_rpms.setdefault(nsvc_devel, [])
                    added_rpms[nsvc_devel].append(str(rpm_obj.nevra))
                    log.write("Adding %s to %s module\n" % (rpm_obj, nsvc_devel))

        # GatherSource returns all the packages in variant and does not
        # care which package is in which module, but for modular metadata
        # in the resulting compose repository, we have to know which RPM
        # is part of which module.
        # We therefore iterate over all the added packages grouped by
        # particular module and use them to filter out the packages which
        # have not been added to variant from the `arch_mmd`. This package
        # list is later used in createrepo phase to generated modules.yaml.
        for nsvc, rpm_nevras in added_rpms.items():
            # If we added some RPMs from a module, that module must exist in
            # exactly one of the dicts. We need to find the metadata object for
            # it.
            arch_mmd = variant.arch_mmds[arch].get(nsvc) or variant.dev_mmds[arch].get(
                nsvc
            )

            added_artifacts = Modulemd.SimpleSet()
            for rpm_nevra in rpm_nevras:
                added_artifacts.add(rpm_nevra)
            arch_mmd.set_rpm_artifacts(added_artifacts)

        return packages, groups


def should_include(rpm_obj, arch, arch_mmd, multilib_arches):
    srpm = kobo.rpmlib.parse_nvr(rpm_obj.sourcerpm)["name"]

    buildopts = arch_mmd.get_buildopts()
    if buildopts:
        whitelist = buildopts.get_rpm_whitelist()
        if whitelist:
            # We have whitelist, no filtering against components.
            if srpm not in whitelist:
                # Package is not on the list, skip it.
                return False

    # Filter out the RPM from artifacts if its filtered in MMD.
    if rpm_obj.name in arch_mmd.get_rpm_filter().get():
        return False

    # Skip the rpm_obj if it's built for multilib arch, but multilib is not
    # enabled for this srpm in MMD.
    try:
        mmd_component = arch_mmd.get_rpm_components()[srpm]
        multilib = mmd_component.get_multilib()
        multilib = multilib.get() if multilib else set()
        if arch not in multilib and rpm_obj.arch in multilib_arches:
            return False
    except KeyError:
        # No such component, disable any multilib
        if rpm_obj.arch not in ("noarch", arch):
            return False

    return True
