# -*- coding: utf-8 -*-


import os
import time
import pipes

from pungi.util import get_arch_variant_data
from pungi.phases.base import PhaseBase
from pungi.linker import Linker
from pungi.paths import translate_path
from pungi.wrappers.kojiwrapper import KojiWrapper
from pungi.wrappers.iso import IsoWrapper
from kobo.shortcuts import run, read_checksum_file
from kobo.threads import ThreadPool, WorkerThread
from productmd.images import Image

class ImageBuildPhase(PhaseBase):
    """class for wrapping up koji image-build"""
    name = "image_build"

    def __init__(self, compose):
        PhaseBase.__init__(self, compose)
        self.pool = ThreadPool(logger=self.compose._logger)

    def skip(self):
        if PhaseBase.skip(self):
            return True
        if not self.compose.conf.get(self.name):
            self.compose.log_info("Config section '%s' was not found. Skipping" % self.name)
            return True
        return False

    def run(self):
        for arch in self.compose.get_arches(): # src will be skipped
            for variant in self.compose.get_variants(arch=arch):
                image_build_data = get_arch_variant_data(self.compose.conf, self.name, arch, variant)
                for image_conf in image_build_data:
                    image_conf["arches"] = arch # passed to get_image_build_cmd as dict
                    image_conf["variant"] = variant # ^
                    image_conf["install_tree"] = translate_path(self.compose, self.compose.paths.compose.os_tree(arch, variant)) # ^
                    format = image_conf["format"] # transform format into right 'format' for image-build
                    image_conf["format"] = ",".join([x[0] for x in image_conf["format"]]) # 'docker,qcow2'
                    if image_conf.has_key("repos") and not isinstance(image_conf["repos"], str):
                        image_conf["repos"] = ",".join(image_conf["repos"]) # supply repos as str separated by , instead of list
                    cmd = {
                        "format": format,
                        "image_conf": image_conf,
                        "conf_file": self.compose.paths.work.image_build_conf(image_conf["arches"], image_conf['variant'], image_name=image_conf['name'], image_type=image_conf['format'].replace(",", "-")),
                        "image_dir": self.compose.paths.compose.image_dir(arch, variant),
                        "relative_image_dir": self.compose.paths.compose.image_dir(arch, variant, create_dir=False, relative=True),
                        "link_type": self.compose.conf.get("link_type", "hardlink-or-copy")
                    }
                    self.pool.add(CreateImageBuildThread(self.pool))
                    self.pool.queue_put((self.compose, cmd))
        self.pool.start()

    def stop(self, *args, **kwargs):
        PhaseBase.stop(self, *args, **kwargs)
        if self.skip():
            return

class CreateImageBuildThread(WorkerThread):
    def fail(self, compose, cmd):
        compose.log_error("CreateImageBuild failed.")

    def process(self, item, num):
        compose, cmd = item
        mounts = [compose.topdir]
        if "mount" in cmd:
            mounts.append(cmd["mount"])
        runroot = compose.conf.get("runroot", False)
        log_file = compose.paths.log.log_file(cmd["image_conf"]["arches"], "imagebuild-%s-%s-%s" % (cmd["image_conf"]["arches"], cmd["image_conf"]["variant"], cmd['image_conf']['format'].replace(",","-")))
        msg = "Creating %s image (arch: %s, variant: %s)" % (cmd["image_conf"]["format"].replace(",","-"), cmd["image_conf"]["arches"], cmd["image_conf"]["variant"])
        self.pool.log_info("[BEGIN] %s" % msg)

        koji_wrapper = KojiWrapper(compose.conf["koji_profile"])
        # paths module doesn't hold compose object, so we have to generate path here

        # writes conf file for koji image-build
        self.pool.log_info("Writing image-build config for %s.%s into %s" % (cmd["image_conf"]["variant"], cmd["image_conf"]["arches"], cmd["conf_file"]))
        koji_cmd = koji_wrapper.get_image_build_cmd(cmd['image_conf'], conf_file_dest=cmd["conf_file"], wait=True, scratch=False)

        # avoid race conditions?
        # Kerberos authentication failed: Permission denied in replay cache code (-1765328215)
        time.sleep(num * 3)
        output = koji_wrapper.run_create_image_cmd(koji_cmd, log_file=log_file)
        self.pool.log_debug("build-image outputs: %s" % (output))
        if output["retcode"] != 0:
            self.fail(compose, cmd)
            raise RuntimeError("ImageBuild task failed: %s. See %s for more details." % (output["task_id"], log_file))

        # copy image to images/
        image_infos = []

        for filename in koji_wrapper.get_image_path(output["task_id"]):
            # format is list of tuples [('qcow2', '.qcow2'), ('raw-xz', 'raw.xz'),]
            for format, suffix in cmd['format']:
                if filename.endswith(suffix):
                    image_infos.append({'filename': filename, 'suffix': suffix, 'type': format}) # the type/format ... image-build has it wrong

        if len(image_infos) != len(cmd['format']):
            self.pool.log_error("Error in koji task %s. Expected to find same amount of images as in suffixes attr in image-build (%s). Got '%s'." %
                (output["task_id"], len(cmd['image_conf']['format']), len(image_infos)))
            self.fail(compose, cmd)

        # The usecase here is that you can run koji image-build with multiple --format
        # It's ok to do it serialized since we're talking about max 2 images per single
        # image_build record
        linker = Linker(logger=compose._logger)
        for image_info in image_infos:
            # let's not change filename of koji outputs
            image_dest = os.path.join(cmd["image_dir"], os.path.basename(image_info['filename']))
            linker.link(image_info['filename'], image_dest, link_type=cmd["link_type"])

            iso = IsoWrapper(logger=compose._logger) # required for checksums only
            checksum_cmd = ["cd %s" % pipes.quote(os.path.dirname(image_dest))]
            checksum_cmd.extend(iso.get_checksum_cmds(os.path.basename(image_dest)))
            checksum_cmd = " && ".join(checksum_cmd)

            if runroot:
                packages = ["coreutils", "genisoimage", "isomd5sum", "jigdo", "strace", "lsof"]
                runroot_channel = compose.conf.get("runroot_channel", None)
                runroot_tag = compose.conf["runroot_tag"]
                koji_cmd = koji_wrapper.get_runroot_cmd(runroot_tag, cmd["image_conf"]["arches"], checksum_cmd, channel=runroot_channel, use_shell=True, task_id=True, packages=packages, mounts=mounts)

                # avoid race conditions?
                # Kerberos authentication failed: Permission denied in replay cache code (-1765328215)
                time.sleep(num * 3)

                output = koji_wrapper.run_runroot_cmd(koji_cmd, log_file=log_file)
                if output["retcode"] != 0:
                    self.fail(compose, cmd)
                    raise RuntimeError("Runroot task failed: %s. See %s for more details." % (output["task_id"], log_file))

            else:
                # run locally
                try:
                    run(checksum_cmd, show_cmd=True, logfile=log_file)
                except:
                    self.fail(compose, cmd)
                    raise

            # Update image manifest
            img = Image(compose.im)
            img.type = image_info['type']
            img.format = image_info['suffix']
            img.path = os.path.join(cmd["relative_image_dir"], os.path.basename(image_dest))
            img.mtime = int(os.stat(image_dest).st_mtime)
            img.size = os.path.getsize(image_dest)
            img.arch = cmd["image_conf"]["arches"] # arches should be always single arch
            img.disc_number = 1 # We don't expect multiple disks
            img.disc_count = 1
            for checksum_type in ("md5", "sha1", "sha256"):
                checksum_path = image_dest + ".%sSUM" % checksum_type.upper()
                checksum_value = None
                if os.path.isfile(checksum_path):
                    checksum_value, image_name = read_checksum_file(checksum_path)[0]
                    if image_name != os.path.basename(img.path):
                        raise ValueError("Image name doesn't match checksum: %s" % checksum_path)
                img.add_checksum(compose.paths.compose.topdir(), checksum_type=checksum_type, checksum_value=checksum_value)
            img.bootable = False
            # named keywords due portability (old productmd used arch, variant ... while new one uses variant, arch
            compose.im.add(variant=cmd["image_conf"]["variant"].uid, arch=cmd["image_conf"]["arches"], image=img)

        self.pool.log_info("[DONE ] %s" % msg)
