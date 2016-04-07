# -*- coding: utf-8 -*-

import os
from kobo.threads import ThreadPool, WorkerThread

from .base import ConfigGuardedPhase
from .. import util
from ..paths import translate_path
from ..wrappers import kojiwrapper


class OSTreePhase(ConfigGuardedPhase):
    name = 'ostree'

    config_options = [
        {
            "name": "ostree",
            "expected_types": [list],
            "optional": True,
        }
    ]

    def __init__(self, compose):
        super(OSTreePhase, self).__init__(compose)
        self.pool = ThreadPool(logger=self.compose._logger)

    def run(self):
        for variant in self.compose.get_variants():
            for arch in variant.arches:
                for conf in util.get_arch_variant_data(self.compose.conf, self.name, arch, variant):
                    self.pool.add(OSTreeThread(self.pool))
                    self.pool.queue_put((self.compose, variant, arch, conf))

        self.pool.start()


class OSTreeThread(WorkerThread):
    def process(self, item, num):
        compose, variant, arch, config = item
        self.num = num
        with util.failable(compose, variant, arch, 'ostree'):
            self.worker(compose, variant, arch, config)

    def worker(self, compose, variant, arch, config):
        msg = 'OSTree phase for variant %s, arch %s' % (variant.uid, arch)
        self.pool.log_info('[BEGIN] %s' % msg)
        self.logdir = compose.paths.log.topdir('{}/ostree'.format(arch))

        source_variant = compose.variants[config['source_repo_from']]
        source_repo = translate_path(compose, compose.paths.compose.repository(arch, source_variant))

        self._run_ostree_cmd(compose, variant, arch, config, source_repo)

        self.pool.log_info('[DONE ] %s' % msg)

    def _run_ostree_cmd(self, compose, variant, arch, config, source_repo):
        workdir = os.path.join(compose.paths.work.topdir(arch), 'ostree')
        cmd = [
            'pungi-make-ostree',
            '--log-dir={}'.format(self.logdir),
            '--work-dir={}'.format(workdir),
            '--treefile={}'.format(config['treefile']),
            '--config-url={}'.format(config['config_url']),
            '--config-branch={}'.format(config.get('config_branch', 'master')),
            '--source-repo={}'.format(source_repo),
            config['ostree_repo']
        ]

        runroot_channel = compose.conf.get("runroot_channel", None)
        runroot_tag = compose.conf["runroot_tag"]

        packages = ['pungi', 'ostree', 'rpm-ostree']
        log_file = os.path.join(self.logdir, 'runroot.log')
        mounts = [compose.topdir, config['ostree_repo']]
        koji = kojiwrapper.KojiWrapper(compose.conf["koji_profile"])
        koji_cmd = koji.get_runroot_cmd(runroot_tag, arch, cmd,
                                        channel=runroot_channel,
                                        use_shell=True, task_id=True,
                                        packages=packages, mounts=mounts)
        output = koji.run_runroot_cmd(koji_cmd, log_file=log_file)
        if output["retcode"] != 0:
            raise RuntimeError("Runroot task failed: %s. See %s for more details."
                               % (output["task_id"], log_file))
