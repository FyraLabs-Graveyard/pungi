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


__all__ = ("create_variant_repo",)

import copy
import errno
import glob
import os
import shutil
import threading
import xml.dom.minidom

import productmd.modules
import productmd.rpms
from kobo.shortcuts import relative_path, run
from kobo.threads import ThreadPool, WorkerThread

from ..module_util import Modulemd, collect_module_defaults
from ..util import (
    get_arch_variant_data,
    read_single_module_stream_from_file,
    temp_dir,
)
from ..wrappers.createrepo import CreaterepoWrapper
from ..wrappers.scm import get_dir_from_scm
from .base import PhaseBase

CACHE_TOPDIR = "/var/cache/pungi/createrepo_c/"
createrepo_lock = threading.Lock()
createrepo_dirs = set()


class CreaterepoPhase(PhaseBase):
    name = "createrepo"

    def __init__(self, compose, pkgset_phase=None):
        PhaseBase.__init__(self, compose)
        self.pool = ThreadPool(logger=self.compose._logger)
        self.modules_metadata = ModulesMetadata(compose)
        self.pkgset_phase = pkgset_phase

    def validate(self):
        errors = []

        if not self.compose.old_composes and self.compose.conf.get("createrepo_deltas"):
            errors.append("Can not generate deltas without old compose")

        if errors:
            raise ValueError("\n".join(errors))

    def run(self):
        get_productids_from_scm(self.compose)
        reference_pkgset = None
        if self.pkgset_phase and self.pkgset_phase.package_sets:
            reference_pkgset = self.pkgset_phase.package_sets[-1]
        for i in range(self.compose.conf["createrepo_num_threads"]):
            self.pool.add(
                CreaterepoThread(self.pool, reference_pkgset, self.modules_metadata)
            )

        for variant in self.compose.get_variants():
            if variant.is_empty:
                continue

            if variant.uid in self.compose.conf.get("createrepo_extra_modulemd", {}):
                # Clone extra modulemd repository if it's configured.
                get_dir_from_scm(
                    self.compose.conf["createrepo_extra_modulemd"][variant.uid],
                    self.compose.paths.work.tmp_dir(variant=variant, create_dir=False),
                    compose=self.compose,
                )

            self.pool.queue_put((self.compose, None, variant, "srpm"))
            for arch in variant.arches:
                self.pool.queue_put((self.compose, arch, variant, "rpm"))
                self.pool.queue_put((self.compose, arch, variant, "debuginfo"))

        self.pool.start()

    def stop(self):
        super(CreaterepoPhase, self).stop()
        self.modules_metadata.write_modules_metadata()


def create_variant_repo(
    compose, arch, variant, pkg_type, pkgset, modules_metadata=None
):
    types = {
        "rpm": (
            "binary",
            lambda **kwargs: compose.paths.compose.repository(
                arch=arch, variant=variant, **kwargs
            ),
        ),
        "srpm": (
            "source",
            lambda **kwargs: compose.paths.compose.repository(
                arch="src", variant=variant, **kwargs
            ),
        ),
        "debuginfo": (
            "debug",
            lambda **kwargs: compose.paths.compose.debug_repository(
                arch=arch, variant=variant, **kwargs
            ),
        ),
    }

    if variant.is_empty or (arch is None and pkg_type != "srpm"):
        compose.log_info(
            "[SKIP ] Creating repo (arch: %s, variant: %s)" % (arch, variant)
        )
        return

    createrepo_c = compose.conf["createrepo_c"]
    createrepo_checksum = compose.conf["createrepo_checksum"]
    repo = CreaterepoWrapper(createrepo_c=createrepo_c)
    repo_dir_arch = None
    if pkgset:
        repo_dir_arch = pkgset.paths["global" if pkg_type == "srpm" else arch]

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

    compose.log_info("[BEGIN] %s" % msg)

    # We only want delta RPMs for binary repos.
    with_deltas = pkg_type == "rpm" and _has_deltas(compose, variant, arch)

    rpms = set()
    rpm_nevras = set()

    # read rpms from metadata rather than guessing it by scanning filesystem
    manifest_file = compose.paths.compose.metadata("rpms.json")
    manifest = productmd.rpms.Rpms()
    manifest.load(manifest_file)

    for rpms_arch, data in manifest.rpms.get(variant.uid, {}).items():
        if arch is not None and arch != rpms_arch:
            continue
        for srpm_data in data.values():
            for rpm_nevra, rpm_data in srpm_data.items():
                if types[pkg_type][0] != rpm_data["category"]:
                    continue
                path = os.path.join(compose.topdir, "compose", rpm_data["path"])
                rel_path = relative_path(path, repo_dir.rstrip("/") + "/")
                rpms.add(rel_path)
                rpm_nevras.add(str(rpm_nevra))

    file_list = compose.paths.work.repo_package_list(arch, variant, pkg_type)
    with open(file_list, "w") as f:
        for rel_path in sorted(rpms):
            f.write("%s\n" % rel_path)

    # Only find last compose when we actually want delta RPMs.
    old_package_dirs = _get_old_package_dirs(compose, repo_dir) if with_deltas else None
    if old_package_dirs:
        # If we are creating deltas, we can not reuse existing metadata, as
        # that would stop deltas from being created.
        # This seems to only affect createrepo_c though.
        repo_dir_arch = None

    comps_path = None
    if compose.has_comps and pkg_type == "rpm":
        comps_path = compose.paths.work.comps(arch=arch, variant=variant)

    if compose.conf["createrepo_enable_cache"]:
        cachedir = os.path.join(
            CACHE_TOPDIR,
            "%s-%s" % (compose.conf["release_short"], os.getuid()),
        )
        if not os.path.exists(cachedir):
            try:
                os.makedirs(cachedir)
            except Exception as e:
                compose.log_warning(
                    "Cache disabled because cannot create cache dir %s %s"
                    % (cachedir, str(e))
                )
                cachedir = None
    else:
        cachedir = None
    cmd = repo.get_createrepo_cmd(
        repo_dir,
        update=True,
        database=compose.should_create_yum_database,
        skip_stat=True,
        pkglist=file_list,
        outputdir=repo_dir,
        workers=compose.conf["createrepo_num_workers"],
        groupfile=comps_path,
        update_md_path=repo_dir_arch,
        checksum=createrepo_checksum,
        deltas=with_deltas,
        oldpackagedirs=old_package_dirs,
        use_xz=compose.conf["createrepo_use_xz"],
        extra_args=compose.conf["createrepo_extra_args"],
        cachedir=cachedir,
    )
    log_file = compose.paths.log.log_file(
        arch, "createrepo-%s.%s" % (variant, pkg_type)
    )
    run(cmd, logfile=log_file, show_cmd=True)

    # call modifyrepo to inject productid
    product_id = compose.conf.get("product_id")
    if product_id and pkg_type == "rpm":
        # add product certificate to base (rpm) repo; skip source and debug
        product_id_path = compose.paths.work.product_id(arch, variant)
        if os.path.isfile(product_id_path):
            cmd = repo.get_modifyrepo_cmd(
                os.path.join(repo_dir, "repodata"), product_id_path, compress_type="gz"
            )
            log_file = compose.paths.log.log_file(arch, "modifyrepo-%s" % variant)
            run(cmd, logfile=log_file, show_cmd=True)
            # productinfo is not supported by modifyrepo in any way
            # this is a HACK to make CDN happy (dmach: at least I think,
            # need to confirm with dgregor)
            shutil.copy2(
                product_id_path, os.path.join(repo_dir, "repodata", "productid")
            )

    # call modifyrepo to inject modulemd if needed
    if pkg_type == "rpm" and arch in variant.arch_mmds and Modulemd is not None:
        mod_index = Modulemd.ModuleIndex()
        metadata = []

        for module_id, mmd in variant.arch_mmds.get(arch, {}).items():
            if modules_metadata:
                module_rpms = mmd.get_rpm_artifacts()
                metadata.append((module_id, module_rpms))
            mod_index.add_module_stream(mmd)

        module_names = set(mod_index.get_module_names())
        defaults_dir = compose.paths.work.module_defaults_dir()
        overrides_dir = compose.conf.get("module_defaults_override_dir")
        collect_module_defaults(
            defaults_dir, module_names, mod_index, overrides_dir=overrides_dir
        )

        # Add extra modulemd files
        if variant.uid in compose.conf.get("createrepo_extra_modulemd", {}):
            compose.log_debug("Adding extra modulemd for %s.%s", variant.uid, arch)
            dirname = compose.paths.work.tmp_dir(variant=variant, create_dir=False)
            for filepath in glob.glob(os.path.join(dirname, arch) + "/*.yaml"):
                module_stream = read_single_module_stream_from_file(filepath)
                if not mod_index.add_module_stream(module_stream):
                    raise RuntimeError(
                        "Failed parsing modulemd data from %s" % filepath
                    )
                # Add the module to metadata with dummy tag. We can't leave the
                # value empty, but we don't know what the correct tag is.
                nsvc = module_stream.get_nsvc()
                variant.module_uid_to_koji_tag[nsvc] = "DUMMY"
                metadata.append((nsvc, []))

        log_file = compose.paths.log.log_file(arch, "modifyrepo-modules-%s" % variant)
        add_modular_metadata(repo, repo_dir, mod_index, log_file)

        for module_id, module_rpms in metadata:
            modulemd_path = os.path.join(
                types[pkg_type][1](relative=True),
                find_file_in_repodata(repo_dir, "modules"),
            )
            modules_metadata.prepare_module_metadata(
                variant,
                arch,
                module_id,
                modulemd_path,
                types[pkg_type][0],
                list(module_rpms),
            )

    compose.log_info("[DONE ] %s" % msg)


def add_modular_metadata(repo, repo_path, mod_index, log_file):
    """Add modular metadata into a repository."""
    # Dumping empty index fails, we need to check for that.
    if not mod_index.get_module_names():
        return

    with temp_dir() as tmp_dir:
        modules_path = os.path.join(tmp_dir, "modules.yaml")
        with open(modules_path, "w") as f:
            f.write(mod_index.dump_to_string())

        cmd = repo.get_modifyrepo_cmd(
            os.path.join(repo_path, "repodata"),
            modules_path,
            mdtype="modules",
            compress_type="gz",
        )
        run(cmd, logfile=log_file, show_cmd=True)


def find_file_in_repodata(repo_path, type_):
    dom = xml.dom.minidom.parse(os.path.join(repo_path, "repodata", "repomd.xml"))
    for entry in dom.getElementsByTagName("data"):
        if entry.getAttribute("type") == type_:
            return entry.getElementsByTagName("location")[0].getAttribute("href")
        entry.unlink()
    raise RuntimeError("No such file in repodata: %s" % type_)


class CreaterepoThread(WorkerThread):
    def __init__(self, pool, reference_pkgset, modules_metadata):
        super(CreaterepoThread, self).__init__(pool)
        self.reference_pkgset = reference_pkgset
        self.modules_metadata = modules_metadata

    def process(self, item, num):
        compose, arch, variant, pkg_type = item
        create_variant_repo(
            compose,
            arch,
            variant,
            pkg_type=pkg_type,
            pkgset=self.reference_pkgset,
            modules_metadata=self.modules_metadata,
        )


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

    tmp_dir = compose.mkdtemp(prefix="pungi_")
    try:
        get_dir_from_scm(product_id, tmp_dir, compose=compose)
    except OSError as e:
        if e.errno == errno.ENOENT and product_id_allow_missing:
            compose.log_warning("No product IDs in %s" % product_id)
            return
        raise

    if compose.conf["product_id_allow_name_prefix"]:
        pattern = "%s/*%s-%s-*.pem"
    else:
        pattern = "%s/%s-%s-*.pem"

    for arch in compose.get_arches():
        for variant in compose.get_variants(arch=arch):
            # some layered products may use base product name before variant
            pem_files = glob.glob(pattern % (tmp_dir, variant.uid, arch))
            if not pem_files:
                warning = "No product certificate found (arch: %s, variant: %s)" % (
                    arch,
                    variant.uid,
                )
                if product_id_allow_missing:
                    compose.log_warning(warning)
                    continue
                else:
                    shutil.rmtree(tmp_dir)
                    raise RuntimeError(warning)
            if len(pem_files) > 1:
                shutil.rmtree(tmp_dir)
                raise RuntimeError(
                    "Multiple product certificates found (arch: %s, variant: %s): %s"
                    % (
                        arch,
                        variant.uid,
                        ", ".join(sorted([os.path.basename(i) for i in pem_files])),
                    )
                )
            product_id_path = compose.paths.work.product_id(arch, variant)
            shutil.copy2(pem_files[0], product_id_path)

    try:
        shutil.rmtree(tmp_dir)
    except Exception as e:
        compose.log_warning("Failed to clean up tmp dir: %s %s" % (tmp_dir, str(e)))
    compose.log_info("[DONE ] %s" % msg)


def _get_old_package_dirs(compose, repo_dir):
    """Given a compose and a path to a repo in it, try to find corresponding
    repo in an older compose and return a list of paths to directories with
    packages in it.
    """
    if not compose.conf["createrepo_deltas"]:
        return None
    old_package_dirs = compose.paths.old_compose_path(
        repo_dir, allowed_statuses=["FINISHED", "FINISHED_INCOMPLETE"]
    )
    if not old_package_dirs:
        compose.log_info("No suitable old compose found in: %s" % compose.old_composes)
        return None
    old_package_dirs = os.path.join(old_package_dirs, "Packages")
    if compose.conf["hashed_directories"]:
        old_package_dirs = _find_package_dirs(old_package_dirs)
    return old_package_dirs


def _find_package_dirs(base):
    """Assuming the packages are in directories hashed by first letter, find
    all the buckets in given base.
    """
    buckets = set()
    try:
        for subdir in os.listdir(base):
            bucket = os.path.join(base, subdir)
            if os.path.isdir(bucket):
                buckets.add(bucket)
    except OSError:
        # The directory does not exist, so no drpms for you!
        pass
    return sorted(buckets)


def _has_deltas(compose, variant, arch):
    """Check if delta RPMs are enabled for given variant and architecture."""
    key = "createrepo_deltas"
    if isinstance(compose.conf.get(key), bool):
        return compose.conf[key]
    return any(get_arch_variant_data(compose.conf, key, arch, variant))


class ModulesMetadata(object):
    def __init__(self, compose):
        # Prepare empty module metadata
        self.compose = compose
        self.modules_metadata_file = self.compose.paths.compose.metadata("modules.json")
        self.productmd_modules_metadata = productmd.modules.Modules()
        self.productmd_modules_metadata.compose.id = copy.copy(self.compose.compose_id)
        self.productmd_modules_metadata.compose.type = copy.copy(
            self.compose.compose_type
        )
        self.productmd_modules_metadata.compose.date = copy.copy(
            self.compose.compose_date
        )
        self.productmd_modules_metadata.compose.respin = copy.copy(
            self.compose.compose_respin
        )

    def write_modules_metadata(self):
        """
        flush modules metadata into file
        """
        self.compose.log_info(
            "Writing modules metadata: %s" % self.modules_metadata_file
        )
        self.productmd_modules_metadata.dump(self.modules_metadata_file)

    def prepare_module_metadata(
        self, variant, arch, nsvc, modulemd_path, category, module_rpms
    ):
        """
        Find koji tag which corresponds to the module and add record into
        module metadata structure.
        """
        koji_tag = variant.module_uid_to_koji_tag[nsvc]
        self.productmd_modules_metadata.add(
            variant.uid, arch, nsvc, koji_tag, modulemd_path, category, module_rpms
        )
