# -*- coding: utf-8 -*-

import os
from kobo.threads import ThreadPool, WorkerThread
import re

from .base import ConfigGuardedPhase
from .. import util
from ..paths import translate_path
from ..wrappers import scm, kojiwrapper


class OSTreePhase(ConfigGuardedPhase):
    name = 'ostree'

    config_options = (
        {
            "name": "ostree",
            "expected_types": [dict],
            "optional": True,
        }
    )

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

        msg = 'OSTree phase for variant %s, arch %s' % (variant.uid, arch)
        self.pool.log_info('[BEGIN] %s' % msg)
        workdir = compose.paths.work.topdir('atomic')
        self.logdir = compose.paths.log.topdir('{}/atomic'.format(arch))
        repodir = os.path.join(workdir, 'config_repo')

        source_variant = compose.variants[config['source_repo_from']]
        source_repo = translate_path(compose, compose.paths.compose.repository(arch, source_variant))

        self._clone_repo(repodir, config['config_url'], config.get('config_branch', 'master'))
        self._tweak_mirrorlist(repodir, source_repo)
        self._run_atomic_cmd(compose, variant, arch, config, source_repo)

        self.pool.log_info('[DONE ] %s' % msg)

    def _run_atomic_cmd(self, compose, variant, arch, config, source_repo):
        cmd = [
            'pungi-make-ostree',
            '--log-dir={}'.format(self.logdir),
            '--treefile={}'.format(config['treefile']),
            config['atomic_repo']
        ]

        runroot_channel = compose.conf.get("runroot_channel", None)
        runroot_tag = compose.conf["runroot_tag"]

        packages = ['pungi', 'ostree', 'rpm-ostree']
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

    def _clone_repo(self, repodir, url, branch):
        scm.get_dir_from_scm({'scm': 'git', 'repo': url, 'branch': branch, 'dir': '.'},
                             repodir, logger=self.pool._logger)

    def _tweak_mirrorlist(self, repodir, source_repo):
        for file in os.listdir(repodir):
            if file.endswith('.repo'):
                tweak_file(os.path.join(repodir, file), source_repo)


def tweak_file(path, source_repo):
    """Replace mirrorlist line in repo file with baseurl pointing to source_repo."""
    with open(path, 'r') as f:
        contents = f.read()
    replacement = 'baseurl={}'.format(source_repo)
    contents = re.sub(r'^mirrorlist=.*$', replacement, contents)
    with open(path, 'w') as f:
        f.write(contents)
