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

from kobo.shortcuts import run

from pungi.phases.base import PhaseBase
from pungi.phases.gather import write_prepopulate_file
from pungi.wrappers.createrepo import CreaterepoWrapper
from pungi.wrappers.comps import CompsWrapper
from pungi.wrappers.scm import get_file_from_scm, get_dir_from_scm
from pungi.util import temp_dir


class InitPhase(PhaseBase):
    """INIT is a mandatory phase"""
    name = "init"

    def skip(self):
        # INIT must never be skipped,
        # because it generates data for LIVEIMAGES
        return False

    def run(self):
        if self.compose.has_comps:
            # write global comps and arch comps, create comps repos
            write_global_comps(self.compose)
            for arch in self.compose.get_arches():
                write_arch_comps(self.compose, arch)
                create_comps_repo(self.compose, arch)

            # write variant comps
            for variant in self.compose.get_variants():
                for arch in variant.arches:
                    write_variant_comps(self.compose, arch, variant)

        # download variants.xml / product.xml?

        # download module defaults
        if self.compose.has_module_defaults:
            write_module_defaults(self.compose)

        # write prepopulate file
        write_prepopulate_file(self.compose)


def write_global_comps(compose):
    comps_file_global = compose.paths.work.comps(arch="global")
    msg = "Writing global comps file: %s" % comps_file_global

    if compose.DEBUG and os.path.isfile(comps_file_global):
        compose.log_warning("[SKIP ] %s" % msg)
    else:
        scm_dict = compose.conf["comps_file"]
        if isinstance(scm_dict, dict):
            comps_name = os.path.basename(scm_dict["file"])
            if scm_dict["scm"] == "file":
                scm_dict["file"] = os.path.join(compose.config_dir, scm_dict["file"])
        else:
            comps_name = os.path.basename(scm_dict)
            scm_dict = os.path.join(compose.config_dir, scm_dict)

        compose.log_debug(msg)
        tmp_dir = compose.mkdtemp(prefix="comps_")
        get_file_from_scm(scm_dict, tmp_dir, logger=compose._logger)
        shutil.copy2(os.path.join(tmp_dir, comps_name), comps_file_global)
        shutil.rmtree(tmp_dir)


def write_arch_comps(compose, arch):
    comps_file_arch = compose.paths.work.comps(arch=arch)
    msg = "Writing comps file for arch '%s': %s" % (arch, comps_file_arch)

    if compose.DEBUG and os.path.isfile(comps_file_arch):
        compose.log_warning("[SKIP ] %s" % msg)
        return

    compose.log_debug(msg)
    run(["comps_filter", "--arch=%s" % arch, "--no-cleanup",
         "--output=%s" % comps_file_arch,
         compose.paths.work.comps(arch="global")])


UNMATCHED_GROUP_MSG = 'Variant %s.%s requires comps group %s which does not match anything in input comps file'


def write_variant_comps(compose, arch, variant):
    comps_file = compose.paths.work.comps(arch=arch, variant=variant)
    msg = "Writing comps file (arch: %s, variant: %s): %s" % (arch, variant, comps_file)

    if compose.DEBUG and os.path.isfile(comps_file):
        # read display_order and groups for environments (needed for live images)
        comps = CompsWrapper(comps_file)
        # groups = variant.groups
        comps.filter_groups(variant.groups)
        if compose.conf["comps_filter_environments"]:
            comps.filter_environments(variant.environments)

        compose.log_warning("[SKIP ] %s" % msg)
        return

    compose.log_debug(msg)
    run(["comps_filter", "--arch=%s" % arch, "--keep-empty-group=conflicts",
         "--keep-empty-group=conflicts-%s" % variant.uid.lower(),
         "--output=%s" % comps_file, compose.paths.work.comps(arch="global")])

    comps = CompsWrapper(comps_file)
    if variant.groups or variant.modules is not None or variant.type != 'variant':
        # Filter groups if the variant has some, or it's a modular variant, or
        # is not a base variant.
        unmatched = comps.filter_groups(variant.groups)
        for grp in unmatched:
            compose.log_warning(UNMATCHED_GROUP_MSG % (variant.uid, arch, grp))
    if compose.conf["comps_filter_environments"]:
        comps.filter_environments(variant.environments)
    comps.write_comps()


def create_comps_repo(compose, arch):
    createrepo_c = compose.conf["createrepo_c"]
    createrepo_checksum = compose.conf["createrepo_checksum"]
    repo = CreaterepoWrapper(createrepo_c=createrepo_c)
    comps_repo = compose.paths.work.comps_repo(arch=arch)
    comps_path = compose.paths.work.comps(arch=arch)
    msg = "Creating comps repo for arch '%s'" % arch
    if compose.DEBUG and os.path.isdir(os.path.join(comps_repo, "repodata")):
        compose.log_warning("[SKIP ] %s" % msg)
    else:
        compose.log_info("[BEGIN] %s" % msg)
        cmd = repo.get_createrepo_cmd(comps_repo, update=True, database=True, skip_stat=True,
                                      outputdir=comps_repo, groupfile=comps_path,
                                      checksum=createrepo_checksum)
        run(cmd, logfile=compose.paths.log.log_file(arch, "comps_repo"), show_cmd=True)
        compose.log_info("[DONE ] %s" % msg)


def write_module_defaults(compose):
    scm_dict = compose.conf["module_defaults_dir"]

    with temp_dir(prefix="moduledefaults_") as tmp_dir:
        get_dir_from_scm(scm_dict, tmp_dir, logger=compose._logger)
        compose.log_debug("Writing module defaults")
        shutil.rmtree(os.path.join(compose.config_dir, "module_defaults"), ignore_errors=True)
        shutil.copytree(tmp_dir, os.path.join(compose.config_dir, "module_defaults"))
