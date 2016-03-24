# -*- coding: utf-8 -*-

import os
from kobo.threads import ThreadPool, WorkerThread
import shutil
from productmd import images

from .base import ConfigGuardedPhase
from .. import util
from ..paths import translate_path
from ..wrappers import kojiwrapper, iso, lorax


class AtomicInstallerPhase(ConfigGuardedPhase):
    name = 'atomic'

    config_options = (
        {
            "name": "atomic",
            "expected_types": [dict],
            "optional": True,
        }
    )

    def __init__(self, compose):
        super(AtomicInstallerPhase, self).__init__(compose)
        self.pool = ThreadPool(logger=self.compose._logger)

    def run(self):
        for variant in self.compose.get_variants():
            for arch in variant.arches:
                for conf in util.get_arch_variant_data(self.compose.conf, self.name, arch, variant):
                    self.pool.add(AtomicInstallerThread(self.pool))
                    self.pool.queue_put((self.compose, variant, arch, conf))

        self.pool.start()


class AtomicInstallerThread(WorkerThread):
    def process(self, item, num):
        compose, variant, arch, config = item
        self.num = num
        with util.failable(compose, variant, arch, 'atomic_installer', 'Atomic'):
            self.worker(compose, variant, arch, config)

    def worker(self, compose, variant, arch, config):
        msg = 'Atomic phase for variant %s, arch %s' % (variant.uid, arch)
        self.pool.log_info('[BEGIN] %s' % msg)
        self.logdir = compose.paths.log.topdir('{}/atomic'.format(arch))

        source_variant = compose.variants[config['source_repo_from']]
        source_repo = translate_path(compose, compose.paths.compose.repository(arch, source_variant))

        self._run_atomic_cmd(compose, variant, arch, config, source_repo)

        disc_type = compose.conf.get('disc_types', {}).get('dvd', 'dvd')
        filename = compose.get_image_name(arch, variant, disc_type=disc_type,
                                          format=config.get('filename'))
        self._copy_image(compose, variant, arch, filename)
        self._add_to_manifest(compose, variant, arch, filename)
        self.pool.log_info('[DONE ] %s' % msg)

    def _get_release(self, compose, config):
        if 'release' in config and config['release'] is None:
            return compose.image_release
        return config.get('release', None)

    def _copy_image(self, compose, variant, arch, filename):
        iso_path = compose.paths.compose.iso_path(arch, variant, filename)
        source_dir = compose.paths.compose.os_tree(arch, variant)
        boot_iso = os.path.join(source_dir, 'images', 'boot.iso')

        try:
            os.link(boot_iso, iso_path)
        except OSError:
            shutil.copy2(boot_iso, iso_path)

    def _add_to_manifest(self, compose, variant, arch, filename):
        full_iso_path = compose.paths.compose.iso_path(arch, variant, filename)
        iso_path = compose.paths.compose.iso_path(arch, variant, filename, relative=True)
        iso_wrapper = iso.IsoWrapper()
        implant_md5 = iso_wrapper.get_implanted_md5(full_iso_path)

        img = images.Image(compose.im)
        img.path = iso_path
        img.mtime = util.get_mtime(full_iso_path)
        img.size = util.get_file_size(full_iso_path)
        img.arch = arch
        img.type = "boot"
        img.format = "iso"
        img.disc_number = 1
        img.disc_count = 1
        img.bootable = True
        img.subvariant = variant.name
        img.implant_md5 = implant_md5
        try:
            img.volume_id = iso_wrapper.get_volume_id(full_iso_path)
        except RuntimeError:
            pass
        compose.im.add(variant.uid, arch, img)

    def _run_atomic_cmd(self, compose, variant, arch, config, source_repo):
        image_dir = compose.paths.compose.os_tree(arch, variant)
        lorax_wrapper = lorax.LoraxWrapper()
        cmd = lorax_wrapper.get_lorax_cmd(
            compose.conf['release_name'],
            compose.conf["release_version"],
            self._get_release(compose, config),
            repo_baseurl=source_repo,
            output_dir=image_dir,
            variant=variant.uid,
            nomacboot=True,
            buildinstallpackages=config.get('installpkgs'),
            add_template=config.get('add_template'),
            add_arch_template=config.get('add_arch_template'),
            add_template_var=config.get('add_template_var'),
            add_arch_template_var=config.get('add_arch_template_var')
        )

        runroot_channel = compose.conf.get("runroot_channel", None)
        runroot_tag = compose.conf["runroot_tag"]

        packages = ['pungi', 'lorax']
        log_file = os.path.join(self.logdir, 'runroot.log')
        koji = kojiwrapper.KojiWrapper(compose.conf["koji_profile"])
        koji_cmd = koji.get_runroot_cmd(runroot_tag, arch, cmd,
                                        channel=runroot_channel,
                                        use_shell=True, task_id=True,
                                        packages=packages, mounts=[compose.topdir])
        output = koji.run_runroot_cmd(koji_cmd, log_file=log_file)
        if output["retcode"] != 0:
            raise RuntimeError("Runroot task failed: %s. See %s for more details."
                               % (output["task_id"], log_file))
