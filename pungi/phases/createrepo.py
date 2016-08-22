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
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.


__all__ = (
    "create_variant_repo",
)


import os
import glob
import shutil
import tempfile
import threading

from kobo.threads import ThreadPool, WorkerThread
from kobo.shortcuts import run, relative_path

from ..wrappers.scm import get_dir_from_scm
from ..wrappers.createrepo import CreaterepoWrapper
from .base import PhaseBase
from ..util import find_old_compose

import productmd.rpms


createrepo_lock = threading.Lock()
createrepo_dirs = set()


class CreaterepoPhase(PhaseBase):
    name = "createrepo"

    def __init__(self, compose):
        PhaseBase.__init__(self, compose)
        self.pool = ThreadPool(logger=self.compose._logger)

    def validate(self):
        errors = []
        try:
            super(CreaterepoPhase, self).validate()
        except ValueError as exc:
            errors = exc.message.split('\n')

        if not self.compose.old_composes and self.compose.conf['createrepo_deltas']:
            errors.append('Can not generate deltas without old compose')

        if errors:
            raise ValueError('\n'.join(errors))

    def run(self):
        get_productids_from_scm(self.compose)
        for i in range(3):
            self.pool.add(CreaterepoThread(self.pool))

        for variant in self.compose.get_variants():
            if variant.is_empty:
                continue
            self.pool.queue_put((self.compose, None, variant, "srpm"))
            for arch in variant.arches:
                self.pool.queue_put((self.compose, arch, variant, "rpm"))
                self.pool.queue_put((self.compose, arch, variant, "debuginfo"))

        self.pool.start()


def create_variant_repo(compose, arch, variant, pkg_type):
    types = {
        'rpm': ('binary',
                lambda: compose.paths.compose.repository(arch=arch, variant=variant)),
        'srpm': ('source',
                 lambda: compose.paths.compose.repository(arch='src', variant=variant)),
        'debuginfo': ('debug',
                      lambda: compose.paths.compose.debug_repository(arch=arch, variant=variant)),
    }

    if variant.is_empty or (arch is None and pkg_type != 'srpm'):
        compose.log_info("[SKIP ] Creating repo (arch: %s, variant: %s): %s" % (arch, variant))
        return

    createrepo_c = compose.conf["createrepo_c"]
    createrepo_checksum = compose.conf["createrepo_checksum"]
    createrepo_deltas = compose.conf["createrepo_deltas"]
    repo = CreaterepoWrapper(createrepo_c=createrepo_c)
    repo_dir_arch = compose.paths.work.arch_repo(arch='global' if pkg_type == 'srpm' else arch)

    try:
        repo_dir = types[pkg_type][1]()
    except KeyError:
        raise ValueError("Unknown package type: %s" % pkg_type)

    msg = "Creating repo (arch: %s, variant: %s): %s" % (arch, variant, repo_dir)

    # HACK: using global lock
    # This is important when addons put packages into parent variant directory.
    # There can't be multiple createrepo processes operating on the same
    # directory.
    with createrepo_lock:
        if repo_dir in createrepo_dirs:
            compose.log_warning("[SKIP ] Already in progress: %s" % msg)
            return
        createrepo_dirs.add(repo_dir)

    if compose.DEBUG and os.path.isdir(os.path.join(repo_dir, "repodata")):
        compose.log_warning("[SKIP ] %s" % msg)
        return

    compose.log_info("[BEGIN] %s" % msg)

    rpms = set()

    # read rpms from metadata rather than guessing it by scanning filesystem
    manifest_file = compose.paths.compose.metadata("rpms.json")
    manifest = productmd.rpms.Rpms()
    manifest.load(manifest_file)

    for rpms_arch, data in manifest.rpms.get(variant.uid, {}).iteritems():
        if arch is not None and arch != rpms_arch:
            continue
        for srpm_data in data.itervalues():
            for rpm_data in srpm_data.itervalues():
                if types[pkg_type][0] != rpm_data['category']:
                    continue
                path = os.path.join(compose.topdir, "compose", rpm_data["path"])
                rel_path = relative_path(path, repo_dir.rstrip("/") + "/")
                rpms.add(rel_path)

    file_list = compose.paths.work.repo_package_list(arch, variant, pkg_type)
    with open(file_list, 'w') as f:
        for rel_path in sorted(rpms):
            f.write("%s\n" % rel_path)

    old_packages_dir = None
    if createrepo_deltas:
        old_compose_path = find_old_compose(
            compose.old_composes,
            compose.ci_base.release.short,
            compose.ci_base.release.version,
            compose.ci_base.base_product.short if compose.ci_base.release.is_layered else None,
            compose.ci_base.base_product.version if compose.ci_base.release.is_layered else None
        )
        if not old_compose_path:
            compose.log_info("No suitable old compose found in: %s" % compose.old_composes)
        else:
            rel_dir = relative_path(repo_dir, compose.topdir.rstrip('/') + '/')
            old_packages_dir = os.path.join(old_compose_path, rel_dir)

    comps_path = None
    if compose.has_comps and pkg_type == "rpm":
        comps_path = compose.paths.work.comps(arch=arch, variant=variant)
    cmd = repo.get_createrepo_cmd(repo_dir, update=True, database=True, skip_stat=True,
                                  pkglist=file_list, outputdir=repo_dir, workers=3,
                                  groupfile=comps_path, update_md_path=repo_dir_arch,
                                  checksum=createrepo_checksum, deltas=createrepo_deltas,
                                  oldpackagedirs=old_packages_dir)
    log_file = compose.paths.log.log_file(arch, "createrepo-%s.%s" % (variant, pkg_type))
    run(cmd, logfile=log_file, show_cmd=True)

    # call modifyrepo to inject productid
    product_id = compose.conf.get("product_id")
    if product_id and pkg_type == "rpm":
        # add product certificate to base (rpm) repo; skip source and debug
        product_id_path = compose.paths.work.product_id(arch, variant)
        if os.path.isfile(product_id_path):
            cmd = repo.get_modifyrepo_cmd(os.path.join(repo_dir, "repodata"), product_id_path, compress_type="gz")
            log_file = compose.paths.log.log_file(arch, "modifyrepo-%s" % variant)
            run(cmd, logfile=log_file, show_cmd=True)
            # productinfo is not supported by modifyrepo in any way
            # this is a HACK to make CDN happy (dmach: at least I think, need to confirm with dgregor)
            shutil.copy2(product_id_path, os.path.join(repo_dir, "repodata", "productid"))

    compose.log_info("[DONE ] %s" % msg)


class CreaterepoThread(WorkerThread):
    def process(self, item, num):
        compose, arch, variant, pkg_type = item
        create_variant_repo(compose, arch, variant, pkg_type=pkg_type)


def get_productids_from_scm(compose):
    # product_id is a scm_dict: {scm, repo, branch, dir}
    # expected file name format: $variant_uid-$arch-*.pem
    product_id = compose.conf.get("product_id")
    if not product_id:
        compose.log_info("No product certificates specified")
        return

    product_id_allow_missing = compose.conf["product_id_allow_missing"]

    msg = "Getting product certificates from SCM..."
    compose.log_info("[BEGIN] %s" % msg)

    tmp_dir = tempfile.mkdtemp(prefix="pungi_")
    get_dir_from_scm(product_id, tmp_dir)

    for arch in compose.get_arches():
        for variant in compose.get_variants(arch=arch):
            # some layered products may use base product name before variant
            pem_files = glob.glob("%s/*%s-%s-*.pem" % (tmp_dir, variant.uid, arch))
            # use for development:
            # pem_files = glob.glob("%s/*.pem" % tmp_dir)[-1:]
            if not pem_files:
                msg = "No product certificate found (arch: %s, variant: %s)" % (arch, variant.uid)
                if product_id_allow_missing:
                    compose.log_warning(msg)
                    continue
                else:
                    shutil.rmtree(tmp_dir)
                    raise RuntimeError(msg)
            if len(pem_files) > 1:
                shutil.rmtree(tmp_dir)
                raise RuntimeError("Multiple product certificates found (arch: %s, variant: %s): %s" % (arch, variant.uid, ", ".join(sorted([os.path.basename(i) for i in pem_files]))))
            product_id_path = compose.paths.work.product_id(arch, variant)
            shutil.copy2(pem_files[0], product_id_path)

    shutil.rmtree(tmp_dir)
    compose.log_info("[DONE ] %s" % msg)
