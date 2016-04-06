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


import os
import time
import pipes
import random
import shutil

import productmd.treeinfo
from productmd.images import Image
from kobo.threads import ThreadPool, WorkerThread
from kobo.shortcuts import run, relative_path

from pungi.wrappers.iso import IsoWrapper
from pungi.wrappers.createrepo import CreaterepoWrapper
from pungi.wrappers.kojiwrapper import KojiWrapper
from pungi.phases.base import PhaseBase
from pungi.util import (makedirs, get_volid, get_arch_variant_data, failable,
                        get_file_size, get_mtime)
from pungi.media_split import MediaSplitter
from pungi.compose_metadata.discinfo import read_discinfo, write_discinfo


class CreateisoPhase(PhaseBase):
    name = "createiso"

    config_options = (
        {
            "name": "createiso_skip",
            "expected_types": [list],
            "optional": True,
        },
    )

    def __init__(self, compose):
        PhaseBase.__init__(self, compose)
        self.pool = ThreadPool(logger=self.compose._logger)

    def _find_rpms(self, path):
        """Check if there are some RPMs in the path."""
        for _, _, files in os.walk(path):
            for fn in files:
                if fn.endswith(".rpm"):
                    return True
        return False

    def _is_bootable(self, variant, arch):
        if arch == "src":
            return False
        if variant.type != "variant":
            return False
        return self.compose.conf.get("bootable", False)

    def run(self):
        symlink_isos_to = self.compose.conf.get("symlink_isos_to", None)
        disc_type = self.compose.conf.get('disc_types', {}).get('dvd', 'dvd')
        deliverables = []

        commands = []
        for variant in self.compose.get_variants(types=["variant", "layered-product", "optional"], recursive=True):
            for arch in variant.arches + ["src"]:
                skip_iso = get_arch_variant_data(self.compose.conf, "createiso_skip", arch, variant)
                if skip_iso == [True]:
                    self.compose.log_info("Skipping createiso for %s.%s due to config option" % (variant, arch))
                    continue

                volid = get_volid(self.compose, arch, variant, disc_type=disc_type)
                os_tree = self.compose.paths.compose.os_tree(arch, variant)

                iso_dir = self.compose.paths.compose.iso_dir(arch, variant, symlink_to=symlink_isos_to)
                if not iso_dir:
                    continue

                if not self._find_rpms(os_tree):
                    self.compose.log_warning("No RPMs found for %s.%s, skipping ISO"
                                             % (variant.uid, arch))
                    continue

                split_iso_data = split_iso(self.compose, arch, variant)
                disc_count = len(split_iso_data)

                for disc_num, iso_data in enumerate(split_iso_data):
                    disc_num += 1

                    filename = self.compose.get_image_name(
                        arch, variant, disc_type=disc_type, disc_num=disc_num)
                    iso_path = self.compose.paths.compose.iso_path(
                        arch, variant, filename, symlink_to=symlink_isos_to)
                    if os.path.isfile(iso_path):
                        self.compose.log_warning("Skipping mkisofs, image already exists: %s" % iso_path)
                        continue
                    deliverables.append(iso_path)

                    graft_points = prepare_iso(self.compose, arch, variant,
                                               disc_num=disc_num, disc_count=disc_count,
                                               split_iso_data=iso_data)

                    bootable = self._is_bootable(variant, arch)

                    cmd = {
                        "iso_path": iso_path,
                        "bootable": bootable,
                        "cmd": [],
                        "label": "",  # currently not used
                        "disc_num": disc_num,
                        "disc_count": disc_count,
                    }

                    if os.path.islink(iso_dir):
                        cmd["mount"] = os.path.abspath(os.path.join(os.path.dirname(iso_dir),
                                                                    os.readlink(iso_dir)))

                    cmd['cmd'] = [
                        'pungi-createiso',
                        '--output-dir={}'.format(iso_dir),
                        '--iso-name={}'.format(filename),
                        '--volid={}'.format(volid),
                        '--graft-points={}'.format(graft_points),
                        '--arch={}'.format(arch),
                    ]

                    if bootable:
                        cmd['cmd'].append(
                            '--buildinstall-method={}'.format(self.compose.conf['buildinstall_method'])
                        )

                    if self.compose.supported:
                        cmd['cmd'].append('--supported')

                    if self.compose.conf.get('create_jigdo', True):
                        jigdo_dir = self.compose.paths.compose.jigdo_dir(arch, variant)
                        cmd['cmd'].extend([
                            '--jigdo-dir={}'.format(jigdo_dir),
                            '--os-tree={}'.format(os_tree),
                        ])

                    commands.append((cmd, variant, arch))

        if self.compose.notifier:
            self.compose.notifier.send('createiso-targets', deliverables=deliverables)

        for (cmd, variant, arch) in commands:
            self.pool.add(CreateIsoThread(self.pool))
            self.pool.queue_put((self.compose, cmd, variant, arch))

        self.pool.start()

    def stop(self, *args, **kwargs):
        PhaseBase.stop(self, *args, **kwargs)
        if self.skip():
            return


class CreateIsoThread(WorkerThread):
    def fail(self, compose, cmd, variant, arch):
        compose.log_error("CreateISO failed, removing ISO: %s" % cmd["iso_path"])
        try:
            # remove incomplete ISO
            os.unlink(cmd["iso_path"])
            # TODO: remove jigdo & template
        except OSError:
            pass
        if compose.notifier:
            compose.notifier.send('createiso-imagefail',
                                  file=cmd['iso_path'],
                                  arch=arch,
                                  variant=str(variant))

    def process(self, item, num):
        compose, cmd, variant, arch = item
        with failable(compose, variant, arch, 'iso', 'Creating ISO'):
            self.worker(compose, cmd, variant, arch, num)

    def worker(self, compose, cmd, variant, arch, num):
        mounts = [compose.topdir]
        if "mount" in cmd:
            mounts.append(cmd["mount"])

        runroot = compose.conf.get("runroot", False)
        bootable = cmd['bootable']
        log_file = compose.paths.log.log_file(
            arch, "createiso-%s" % os.path.basename(cmd["iso_path"]))

        msg = "Creating ISO (arch: %s, variant: %s): %s" % (
            arch, variant, os.path.basename(cmd["iso_path"]))
        self.pool.log_info("[BEGIN] %s" % msg)

        if runroot:
            # run in a koji build root
            packages = ["coreutils", "genisoimage", "isomd5sum", "jigdo", "pungi"]
            extra_packages = {
                'lorax': ['lorax'],
                'buildinstall': ['anaconda'],
            }
            if bootable:
                packages.extend(extra_packages[compose.conf["buildinstall_method"]])

            runroot_channel = compose.conf.get("runroot_channel", None)
            runroot_tag = compose.conf["runroot_tag"]

            # get info about build arches in buildroot_tag
            koji_wrapper = KojiWrapper(compose.conf["koji_profile"])
            koji_proxy = koji_wrapper.koji_proxy
            tag_info = koji_proxy.getTag(runroot_tag)
            tag_arches = tag_info["arches"].split(" ")

            build_arch = arch
            if not bootable:
                if "x86_64" in tag_arches:
                    # assign non-bootable images to x86_64 if possible
                    build_arch = "x86_64"
                elif build_arch == "src":
                    # pick random arch from available runroot tag arches
                    build_arch = random.choice(tag_arches)

            koji_cmd = koji_wrapper.get_runroot_cmd(
                runroot_tag, build_arch, cmd["cmd"],
                channel=runroot_channel, use_shell=True, task_id=True,
                packages=packages, mounts=mounts)

            # avoid race conditions?
            # Kerberos authentication failed: Permission denied in replay cache code (-1765328215)
            time.sleep(num * 3)

            output = koji_wrapper.run_runroot_cmd(koji_cmd, log_file=log_file)
            if output["retcode"] != 0:
                self.fail(compose, cmd, variant, arch)
                raise RuntimeError("Runroot task failed: %s. See %s for more details."
                                   % (output["task_id"], log_file))

        else:
            # run locally
            try:
                run(cmd["cmd"], show_cmd=True, logfile=log_file)
            except:
                self.fail(compose, cmd, variant, arch)
                raise

        iso = IsoWrapper()

        img = Image(compose.im)
        img.path = cmd["iso_path"].replace(compose.paths.compose.topdir(), '').lstrip('/')
        img.mtime = get_mtime(cmd["iso_path"])
        img.size = get_file_size(cmd["iso_path"])
        img.arch = arch
        # XXX: HARDCODED
        img.type = "dvd"
        img.format = "iso"
        img.disc_number = cmd["disc_num"]
        img.disc_count = cmd["disc_count"]
        img.bootable = cmd["bootable"]
        img.subvariant = variant.uid
        img.implant_md5 = iso.get_implanted_md5(cmd["iso_path"])
        try:
            img.volume_id = iso.get_volume_id(cmd["iso_path"])
        except RuntimeError:
            pass
        compose.im.add(variant.uid, arch, img)
        # TODO: supported_iso_bit
        # add: boot.iso

        self.pool.log_info("[DONE ] %s" % msg)
        if compose.notifier:
            compose.notifier.send('createiso-imagedone',
                                  file=cmd['iso_path'],
                                  arch=arch,
                                  variant=str(variant))


def split_iso(compose, arch, variant):
    # XXX: hardcoded
    media_size = 4700000000
    media_reserve = 10 * 1024 * 1024

    ms = MediaSplitter(str(media_size - media_reserve), compose)

    os_tree = compose.paths.compose.os_tree(arch, variant)
    extra_files_dir = compose.paths.work.extra_files_dir(arch, variant)

#    ti_path = os.path.join(os_tree, ".treeinfo")
#    ti = productmd.treeinfo.TreeInfo()
#    ti.load(ti_path)

    # scan extra files to mark them "sticky" -> they'll be on all media after split
    extra_files = set()
    for root, dirs, files in os.walk(extra_files_dir):
        for fn in files:
            path = os.path.join(root, fn)
            rel_path = relative_path(path, extra_files_dir.rstrip("/") + "/")
            extra_files.add(rel_path)

    packages = []
    all_files = []
    all_files_ignore = []

    ti = productmd.treeinfo.TreeInfo()
    ti.load(os.path.join(os_tree, ".treeinfo"))
    boot_iso_rpath = ti.images.images.get(arch, {}).get("boot.iso", None)
    if boot_iso_rpath:
        all_files_ignore.append(boot_iso_rpath)
    compose.log_debug("split_iso all_files_ignore = %s" % ", ".join(all_files_ignore))

    for root, dirs, files in os.walk(os_tree):
        for dn in dirs[:]:
            repo_dir = os.path.join(root, dn)
            if repo_dir == os.path.join(compose.paths.compose.repository(arch, variant), "repodata"):
                dirs.remove(dn)

        for fn in files:
            path = os.path.join(root, fn)
            rel_path = relative_path(path, os_tree.rstrip("/") + "/")
            sticky = rel_path in extra_files
            if rel_path in all_files_ignore:
                compose.log_info("split_iso: Skipping %s" % rel_path)
                continue
            if root == compose.paths.compose.packages(arch, variant):
                packages.append((path, os.path.getsize(path), sticky))
            else:
                all_files.append((path, os.path.getsize(path), sticky))

    for path, size, sticky in all_files + packages:
        ms.add_file(path, size, sticky)

    return ms.split()


def prepare_iso(compose, arch, variant, disc_num=1, disc_count=None, split_iso_data=None):
    tree_dir = compose.paths.compose.os_tree(arch, variant)
    filename = compose.get_image_name(arch, variant, disc_num=disc_num)
    iso_dir = compose.paths.work.iso_dir(arch, filename)

    # modify treeinfo
    ti_path = os.path.join(tree_dir, ".treeinfo")
    ti = productmd.treeinfo.TreeInfo()
    ti.load(ti_path)
    ti.media.totaldiscs = disc_count or 1
    ti.media.discnum = disc_num

    # remove boot.iso from all sections
    paths = set()
    for platform in ti.images.images:
        if "boot.iso" in ti.images.images[platform]:
            paths.add(ti.images.images[platform].pop("boot.iso"))

    # remove boot.iso from checksums
    for i in paths:
        if i in ti.checksums.checksums.keys():
            del ti.checksums.checksums[i]

    # make a copy of isolinux/isolinux.bin, images/boot.img - they get modified when mkisofs is called
    for i in ("isolinux/isolinux.bin", "images/boot.img"):
        src_path = os.path.join(tree_dir, i)
        dst_path = os.path.join(iso_dir, i)
        if os.path.exists(src_path):
            makedirs(os.path.dirname(dst_path))
            shutil.copy2(src_path, dst_path)

    if disc_count > 1:
        # remove repodata/repomd.xml from checksums, create a new one later
        if "repodata/repomd.xml" in ti.checksums.checksums:
            del ti.checksums.checksums["repodata/repomd.xml"]

        # rebuild repodata
        createrepo_c = compose.conf.get("createrepo_c", True)
        createrepo_checksum = compose.conf["createrepo_checksum"]
        repo = CreaterepoWrapper(createrepo_c=createrepo_c)

        file_list = "%s-file-list" % iso_dir
        packages_dir = compose.paths.compose.packages(arch, variant)
        file_list_content = []
        for i in split_iso_data["files"]:
            if not i.endswith(".rpm"):
                continue
            if not i.startswith(packages_dir):
                continue
            rel_path = relative_path(i, tree_dir.rstrip("/") + "/")
            file_list_content.append(rel_path)

        if file_list_content:
            # write modified repodata only if there are packages available
            run("cp -a %s/repodata %s/" % (pipes.quote(tree_dir), pipes.quote(iso_dir)))
            open(file_list, "w").write("\n".join(file_list_content))
            cmd = repo.get_createrepo_cmd(tree_dir, update=True, database=True, skip_stat=True, pkglist=file_list, outputdir=iso_dir, workers=3, checksum=createrepo_checksum)
            run(cmd)
            # add repodata/repomd.xml back to checksums
            ti.checksums.add("repodata/repomd.xml", "sha256", root_dir=iso_dir)

    new_ti_path = os.path.join(iso_dir, ".treeinfo")
    ti.dump(new_ti_path)

    # modify discinfo
    di_path = os.path.join(tree_dir, ".discinfo")
    data = read_discinfo(di_path)
    data["disc_numbers"] = [disc_num]
    new_di_path = os.path.join(iso_dir, ".discinfo")
    write_discinfo(new_di_path, **data)

    i = IsoWrapper()
    if not disc_count or disc_count == 1:
        data = i.get_graft_points([tree_dir, iso_dir])
    else:
        data = i.get_graft_points([i._paths_from_list(tree_dir, split_iso_data["files"]), iso_dir])

    # TODO: /content /graft-points
    gp = "%s-graft-points" % iso_dir
    i.write_graft_points(gp, data, exclude=["*/lost+found", "*/boot.iso"])
    return gp
