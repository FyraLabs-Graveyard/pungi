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


import errno
import os
import time
import shutil
import re

from kobo.threads import ThreadPool, WorkerThread
from kobo.shortcuts import run
from productmd.images import Image
from six.moves import shlex_quote

from pungi.arch import get_valid_arches
from pungi.util import get_volid, get_arch_variant_data
from pungi.util import get_file_size, get_mtime, failable, makedirs
from pungi.util import copy_all, translate_path
from pungi.wrappers.lorax import LoraxWrapper
from pungi.wrappers.kojiwrapper import get_buildroot_rpms, KojiWrapper
from pungi.wrappers import iso
from pungi.wrappers.scm import get_file_from_scm
from pungi.phases.base import PhaseBase


class BuildinstallPhase(PhaseBase):
    name = "buildinstall"

    def __init__(self, compose):
        PhaseBase.__init__(self, compose)
        self.pool = ThreadPool(logger=self.compose._logger)
        # A set of (variant_uid, arch) pairs that completed successfully. This
        # is needed to skip copying files for failed tasks.
        self.pool.finished_tasks = set()
        self.buildinstall_method = self.compose.conf.get("buildinstall_method")
        self.used_lorax = self.buildinstall_method == 'lorax'

    def skip(self):
        if PhaseBase.skip(self):
            return True
        if not self.compose.conf.get("bootable"):
            msg = "Not a bootable product. Skipping buildinstall."
            self.compose.log_debug(msg)
            return True
        return False

    def _get_lorax_cmd(self, repo_baseurl, output_dir, variant, arch, buildarch, volid, final_output_dir):
        noupgrade = True
        bugurl = None
        nomacboot = True
        add_template = []
        add_arch_template = []
        add_template_var = []
        add_arch_template_var = []
        for data in get_arch_variant_data(self.compose.conf, 'lorax_options', arch, variant):
            if not data.get('noupgrade', True):
                noupgrade = False
            if data.get('bugurl'):
                bugurl = data.get('bugurl')
            if not data.get('nomacboot', True):
                nomacboot = False
            add_template.extend(data.get('add_template', []))
            add_arch_template.extend(data.get('add_arch_template', []))
            add_template_var.extend(data.get('add_template_var', []))
            add_arch_template_var.extend(data.get('add_arch_template_var', []))
        output_dir = os.path.join(output_dir, variant.uid)
        output_topdir = output_dir

        # The paths module will modify the filename (by inserting arch). But we
        # only care about the directory anyway.
        log_filename = 'buildinstall-%s-logs/dummy' % variant.uid
        log_dir = os.path.dirname(self.compose.paths.log.log_file(arch, log_filename))
        makedirs(log_dir)

        # If the buildinstall_topdir is set, it means Koji is used for
        # buildinstall phase and the filesystem with Koji is read-only.
        # In that case, we have to write logs to buildinstall_topdir and
        # later copy them back to our local log directory.
        if self.compose.conf.get("buildinstall_topdir", None):
            log_dir = self.compose.paths.work.buildinstall_dir(
                arch, allow_topdir_override=True, variant=variant)
            log_dir = os.path.join(log_dir, "logs")
            output_dir = os.path.join(output_dir, "results")

        repos = [repo_baseurl] + get_arch_variant_data(self.compose.conf,
                                                       'lorax_extra_sources', arch, variant)
        if self.compose.has_comps:
            comps_repo = self.compose.paths.work.comps_repo(arch, variant)
            if final_output_dir != output_dir:
                comps_repo = translate_path(self.compose, comps_repo)
            repos.append(comps_repo)

        lorax = LoraxWrapper()
        lorax_cmd = lorax.get_lorax_cmd(self.compose.conf["release_name"],
                                        self.compose.conf["release_version"],
                                        self.compose.conf["release_version"],
                                        repos,
                                        output_dir,
                                        variant=variant.uid,
                                        buildinstallpackages=variant.buildinstallpackages,
                                        is_final=self.compose.supported,
                                        buildarch=buildarch,
                                        volid=volid,
                                        nomacboot=nomacboot,
                                        bugurl=bugurl,
                                        add_template=add_template,
                                        add_arch_template=add_arch_template,
                                        add_template_var=add_template_var,
                                        add_arch_template_var=add_arch_template_var,
                                        noupgrade=noupgrade,
                                        log_dir=log_dir)
        return 'rm -rf %s && %s' % (shlex_quote(output_topdir),
                                    ' '.join([shlex_quote(x) for x in lorax_cmd]))

    def run(self):
        lorax = LoraxWrapper()
        product = self.compose.conf["release_name"]
        version = self.compose.conf["release_version"]
        release = self.compose.conf["release_version"]
        disc_type = self.compose.conf['disc_types'].get('dvd', 'dvd')

        for arch in self.compose.get_arches():
            commands = []

            output_dir = self.compose.paths.work.buildinstall_dir(arch, allow_topdir_override=True)
            final_output_dir = self.compose.paths.work.buildinstall_dir(arch, allow_topdir_override=False)
            repo_baseurl = self.compose.paths.work.arch_repo(arch)
            if final_output_dir != output_dir:
                repo_baseurl = translate_path(self.compose, repo_baseurl)

            if self.buildinstall_method == "lorax":

                buildarch = get_valid_arches(arch)[0]
                for variant in self.compose.get_variants(arch=arch, types=['variant']):
                    if variant.is_empty:
                        continue

                    skip = get_arch_variant_data(self.compose.conf, "buildinstall_skip", arch, variant)
                    if skip == [True]:
                        self.compose.log_info(
                            'Skipping buildinstall for %s.%s due to config option' % (variant, arch))
                        continue

                    volid = get_volid(self.compose, arch, variant=variant, disc_type=disc_type)
                    commands.append(
                        (variant,
                         self._get_lorax_cmd(repo_baseurl, output_dir, variant, arch, buildarch, volid, final_output_dir))
                    )
            elif self.buildinstall_method == "buildinstall":
                volid = get_volid(self.compose, arch, disc_type=disc_type)
                commands.append(
                    (None,
                     lorax.get_buildinstall_cmd(product,
                                                version,
                                                release,
                                                repo_baseurl,
                                                output_dir,
                                                is_final=self.compose.supported,
                                                buildarch=arch,
                                                volid=volid))
                )
            else:
                raise ValueError("Unsupported buildinstall method: %s" % self.buildinstall_method)

            for (variant, cmd) in commands:
                self.pool.add(BuildinstallThread(self.pool))
                self.pool.queue_put((self.compose, arch, variant, cmd))

        self.pool.start()

    def succeeded(self, variant, arch):
        # If the phase is skipped, we can treat it as successful. Either there
        # will be no output, or it's a debug run of compose where anything can
        # happen.
        return (super(BuildinstallPhase, self).skip()
                or (variant.uid if self.used_lorax else None, arch) in self.pool.finished_tasks)

    def copy_files(self):
        disc_type = self.compose.conf['disc_types'].get('dvd', 'dvd')

        # copy buildinstall files to the 'os' dir
        kickstart_file = get_kickstart_file(self.compose)
        for arch in self.compose.get_arches():
            for variant in self.compose.get_variants(arch=arch, types=["self", "variant"]):
                if variant.is_empty:
                    continue
                if not self.succeeded(variant, arch):
                    self.compose.log_debug(
                        'Buildinstall: skipping copying files for %s.%s due to failed runroot task'
                        % (variant.uid, arch))
                    continue

                buildinstall_dir = self.compose.paths.work.buildinstall_dir(arch)

                # Lorax runs per-variant, so we need to tweak the source path
                # to include variant.
                if self.used_lorax:
                    buildinstall_dir = os.path.join(buildinstall_dir, variant.uid)

                if not os.path.isdir(buildinstall_dir) or not os.listdir(buildinstall_dir):
                    continue

                os_tree = self.compose.paths.compose.os_tree(arch, variant)
                # TODO: label is not used
                label = ""
                volid = get_volid(self.compose, arch, variant, escape_spaces=False, disc_type=disc_type)
                can_fail = self.compose.can_fail(variant, arch, 'buildinstall')
                with failable(self.compose, can_fail, variant, arch, 'buildinstall'):
                    tweak_buildinstall(self.compose, buildinstall_dir, os_tree, arch, variant.uid, label, volid, kickstart_file)
                    link_boot_iso(self.compose, arch, variant, can_fail)


def get_kickstart_file(compose):
    scm_dict = compose.conf.get("buildinstall_kickstart")
    if not scm_dict:
        compose.log_debug("Path to ks.cfg (buildinstall_kickstart) not specified.")
        return

    msg = "Getting ks.cfg"
    kickstart_path = os.path.join(compose.paths.work.topdir(arch="global"), "ks.cfg")
    if os.path.exists(kickstart_path):
        compose.log_warning("[SKIP ] %s" % msg)
        return kickstart_path

    compose.log_info("[BEGIN] %s" % msg)
    if isinstance(scm_dict, dict):
        kickstart_name = os.path.basename(scm_dict["file"])
        if scm_dict["scm"] == "file":
            scm_dict["file"] = os.path.join(compose.config_dir, scm_dict["file"])
    else:
        kickstart_name = os.path.basename(scm_dict)
        scm_dict = os.path.join(compose.config_dir, scm_dict)

    tmp_dir = compose.mkdtemp(prefix="buildinstall_kickstart_")
    get_file_from_scm(scm_dict, tmp_dir, logger=compose._logger)
    src = os.path.join(tmp_dir, kickstart_name)
    shutil.copy2(src, kickstart_path)
    compose.log_info("[DONE ] %s" % msg)
    return kickstart_path


BOOT_CONFIGS = [
    "isolinux/isolinux.cfg",
    "etc/yaboot.conf",
    "ppc/ppc64/yaboot.conf",
    "EFI/BOOT/BOOTX64.conf",
    "EFI/BOOT/grub.cfg",
]


def tweak_configs(path, volid, ks_file, configs=BOOT_CONFIGS):
    volid_escaped = volid.replace(" ", r"\x20").replace("\\", "\\\\")
    volid_escaped_2 = volid_escaped.replace("\\", "\\\\")
    found_configs = []
    for config in configs:
        config_path = os.path.join(path, config)
        if not os.path.exists(config_path):
            continue
        found_configs.append(config)

        with open(config_path, "r") as f:
            data = f.read()
        os.unlink(config_path)  # break hadlink by removing file writing a new one

        # double-escape volid in yaboot.conf
        new_volid = volid_escaped_2 if 'yaboot' in config else volid_escaped

        ks = (" ks=hd:LABEL=%s:/ks.cfg" % new_volid) if ks_file else ""

        # pre-f18
        data = re.sub(r":CDLABEL=[^ \n]*", r":CDLABEL=%s%s" % (new_volid, ks), data)
        # f18+
        data = re.sub(r":LABEL=[^ \n]*", r":LABEL=%s%s" % (new_volid, ks), data)
        data = re.sub(r"(search .* -l) '[^'\n]*'", r"\1 '%s'" % volid, data)

        with open(config_path, "w") as f:
            f.write(data)

    return found_configs


# HACK: this is a hack!
# * it's quite trivial to replace volids
# * it's not easy to replace menu titles
# * we probably need to get this into lorax
def tweak_buildinstall(compose, src, dst, arch, variant, label, volid, kickstart_file=None):
    tmp_dir = compose.mkdtemp(prefix="tweak_buildinstall_")

    # verify src
    if not os.path.isdir(src):
        raise OSError(errno.ENOENT, "Directory does not exist: %s" % src)

    # create dst
    try:
        os.makedirs(dst)
    except OSError as ex:
        if ex.errno != errno.EEXIST:
            raise

    # copy src to temp
    # TODO: place temp on the same device as buildinstall dir so we can hardlink
    cmd = "cp -av --remove-destination %s/* %s/" % (shlex_quote(src), shlex_quote(tmp_dir))
    run(cmd)

    found_configs = tweak_configs(tmp_dir, volid, kickstart_file)
    if kickstart_file and found_configs:
        shutil.copy2(kickstart_file, os.path.join(dst, "ks.cfg"))

    images = [
        os.path.join(tmp_dir, "images", "efiboot.img"),
    ]
    for image in images:
        if not os.path.isfile(image):
            continue

        with iso.mount(image, logger=compose._logger,
                       use_guestmount=compose.conf.get("buildinstall_use_guestmount")
                       ) as mount_tmp_dir:
            for config in BOOT_CONFIGS:
                config_path = os.path.join(tmp_dir, config)
                config_in_image = os.path.join(mount_tmp_dir, config)

                if os.path.isfile(config_in_image):
                    cmd = ["cp", "-v", "--remove-destination", config_path, config_in_image]
                    run(cmd)

    # HACK: make buildinstall files world readable
    run("chmod -R a+rX %s" % shlex_quote(tmp_dir))

    # copy temp to dst
    cmd = "cp -av --remove-destination %s/* %s/" % (shlex_quote(tmp_dir), shlex_quote(dst))
    run(cmd)

    shutil.rmtree(tmp_dir)


def link_boot_iso(compose, arch, variant, can_fail):
    if arch == "src":
        return

    disc_type = compose.conf['disc_types'].get('boot', 'boot')

    symlink_isos_to = compose.conf.get("symlink_isos_to")
    os_tree = compose.paths.compose.os_tree(arch, variant)
    # TODO: find in treeinfo?
    boot_iso_path = os.path.join(os_tree, "images", "boot.iso")
    if not os.path.isfile(boot_iso_path):
        return

    msg = "Linking boot.iso (arch: %s, variant: %s)" % (arch, variant)
    filename = compose.get_image_name(arch, variant, disc_type=disc_type,
                                      disc_num=None, suffix=".iso")
    new_boot_iso_path = compose.paths.compose.iso_path(arch, variant, filename,
                                                       symlink_to=symlink_isos_to)
    new_boot_iso_relative_path = compose.paths.compose.iso_path(arch,
                                                                variant,
                                                                filename,
                                                                relative=True)
    if os.path.exists(new_boot_iso_path):
        # TODO: log
        compose.log_warning("[SKIP ] %s" % msg)
        return

    compose.log_info("[BEGIN] %s" % msg)
    # Try to hardlink, and copy if that fails
    try:
        os.link(boot_iso_path, new_boot_iso_path)
    except OSError:
        shutil.copy2(boot_iso_path, new_boot_iso_path)

    implant_md5 = iso.get_implanted_md5(new_boot_iso_path)
    iso_name = os.path.basename(new_boot_iso_path)
    iso_dir = os.path.dirname(new_boot_iso_path)

    # create iso manifest
    run(iso.get_manifest_cmd(iso_name), workdir=iso_dir)

    img = Image(compose.im)
    img.path = new_boot_iso_relative_path
    img.mtime = get_mtime(new_boot_iso_path)
    img.size = get_file_size(new_boot_iso_path)
    img.arch = arch
    img.type = "boot"
    img.format = "iso"
    img.disc_number = 1
    img.disc_count = 1
    img.bootable = True
    img.subvariant = variant.uid
    img.implant_md5 = implant_md5
    setattr(img, 'can_fail', can_fail)
    setattr(img, 'deliverable', 'buildinstall')
    try:
        img.volume_id = iso.get_volume_id(new_boot_iso_path)
    except RuntimeError:
        pass
    compose.im.add(variant.uid, arch, img)
    compose.log_info("[DONE ] %s" % msg)


class BuildinstallThread(WorkerThread):
    def process(self, item, num):
        # The variant is None unless lorax is used as buildinstall method.
        compose, arch, variant, cmd = item
        can_fail = compose.can_fail(variant, arch, 'buildinstall')
        with failable(compose, can_fail, variant, arch, 'buildinstall'):
            self.worker(compose, arch, variant, cmd, num)

    def worker(self, compose, arch, variant, cmd, num):
        runroot = compose.conf["runroot"]
        buildinstall_method = compose.conf["buildinstall_method"]
        log_filename = ('buildinstall-%s' % variant.uid) if variant else 'buildinstall'
        log_file = compose.paths.log.log_file(arch, log_filename)

        msg = "Running buildinstall for arch %s, variant %s" % (arch, variant)

        output_dir = compose.paths.work.buildinstall_dir(
            arch, allow_topdir_override=True, variant=variant)
        final_output_dir = compose.paths.work.buildinstall_dir(
            arch, variant=variant)

        if (os.path.isdir(output_dir) and os.listdir(output_dir) or
                os.path.isdir(final_output_dir) and os.listdir(final_output_dir)):
            # output dir is *not* empty -> SKIP
            self.pool.log_warning(
                '[SKIP ] Buildinstall for arch %s, variant %s' % (arch, variant))
            return

        self.pool.log_info("[BEGIN] %s" % msg)

        task_id = None
        if runroot:
            # run in a koji build root
            packages = []
            if buildinstall_method == "lorax":
                packages += ["lorax"]
            elif buildinstall_method == "buildinstall":
                packages += ["anaconda"]
            runroot_channel = compose.conf.get("runroot_channel")
            runroot_tag = compose.conf["runroot_tag"]

            koji_wrapper = KojiWrapper(compose.conf["koji_profile"])
            koji_cmd = koji_wrapper.get_runroot_cmd(
                runroot_tag, arch, cmd,
                channel=runroot_channel,
                use_shell=True, task_id=True,
                packages=packages, mounts=[compose.topdir],
                weight=compose.conf['runroot_weights'].get('buildinstall'))

            # avoid race conditions?
            # Kerberos authentication failed: Permission denied in replay cache code (-1765328215)
            time.sleep(num * 3)

            output = koji_wrapper.run_runroot_cmd(koji_cmd, log_file=log_file)
            if output["retcode"] != 0:
                raise RuntimeError("Runroot task failed: %s. See %s for more details."
                                   % (output["task_id"], log_file))
            task_id = output["task_id"]

        else:
            # run locally
            run(cmd, show_cmd=True, logfile=log_file)

        if final_output_dir != output_dir:
            if not os.path.exists(final_output_dir):
                makedirs(final_output_dir)
            results_dir = os.path.join(output_dir, "results")
            copy_all(results_dir, final_output_dir)

            # Get the log_dir into which we should copy the resulting log files.
            log_fname = 'buildinstall-%s-logs/dummy' % variant.uid
            final_log_dir = os.path.dirname(compose.paths.log.log_file(arch, log_fname))
            if not os.path.exists(final_log_dir):
                makedirs(final_log_dir)
            log_dir = os.path.join(output_dir, "logs")
            copy_all(log_dir, final_log_dir)

        log_file = compose.paths.log.log_file(arch, log_filename + '-RPMs')
        rpms = get_buildroot_rpms(compose, task_id)
        with open(log_file, "w") as f:
            f.write("\n".join(rpms))

        self.pool.finished_tasks.add((variant.uid if variant else None, arch))
        self.pool.log_info("[DONE ] %s" % msg)
