# -*- coding: utf-8 -*-

import copy
import os
import time

from pungi.util import get_arch_variant_data, resolve_git_url
from pungi.phases.base import PhaseBase
from pungi.linker import Linker
from pungi.paths import translate_path
from pungi.wrappers.kojiwrapper import KojiWrapper
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
                    # We will modify the data, so we need to make a copy to
                    # prevent problems in next iteration where the original
                    # value is needed.
                    image_conf = copy.deepcopy(image_conf)

                    # Replace possible ambiguous ref name with explicit hash.
                    if 'ksurl' in image_conf:
                        image_conf['ksurl'] = resolve_git_url(image_conf['ksurl'])
                    image_conf["arches"] = arch # passed to get_image_build_cmd as dict
                    image_conf["variant"] = variant # ^
                    image_conf["install_tree"] = translate_path(self.compose, self.compose.paths.compose.os_tree(arch, variant)) # ^
                    format = image_conf["format"] # transform format into right 'format' for image-build
                    image_conf["format"] = ",".join([x[0] for x in image_conf["format"]]) # 'docker,qcow2'

                    repos = image_conf.get('repos', [])
                    if isinstance(repos, str):
                        repos = [repos]
                    repos.append(translate_path(self.compose, self.compose.paths.compose.os_tree(arch, variant)))
                    image_conf['repos'] = ",".join(repos)  # supply repos as str separated by , instead of list

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
        mounts = [compose.paths.compose.topdir()]
        if "mount" in cmd:
            mounts.append(cmd["mount"])
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
            img.bootable = False
            # named keywords due portability (old productmd used arch, variant ... while new one uses variant, arch
            compose.im.add(variant=cmd["image_conf"]["variant"].uid, arch=cmd["image_conf"]["arches"], image=img)

        self.pool.log_info("[DONE ] %s" % msg)
