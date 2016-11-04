# -*- coding: utf-8 -*-

import json
import os
from kobo.threads import ThreadPool, WorkerThread
import re

from .base import ConfigGuardedPhase
from .. import util
from ..paths import translate_path
from ..wrappers import kojiwrapper, scm


class OSTreePhase(ConfigGuardedPhase):
    name = 'ostree'

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
        failable_arches = config.get('failable', [])
        with util.failable(compose, util.can_arch_fail(failable_arches, arch),
                           variant, arch, 'ostree'):
            self.worker(compose, variant, arch, config)

    def worker(self, compose, variant, arch, config):
        msg = 'OSTree phase for variant %s, arch %s' % (variant.uid, arch)
        self.pool.log_info('[BEGIN] %s' % msg)
        workdir = compose.paths.work.topdir('ostree-%d' % self.num)
        self.logdir = compose.paths.log.topdir('%s/%s/ostree-%d' %
                                               (arch, variant.uid, self.num))
        repodir = os.path.join(workdir, 'config_repo')

        source_variant = compose.variants[config['source_repo_from']]
        source_repo = translate_path(compose,
                                     compose.paths.compose.repository('$basearch',
                                                                      source_variant,
                                                                      create_dir=False))

        self._clone_repo(repodir, config['config_url'], config.get('config_branch', 'master'))
        self._tweak_mirrorlist(repodir, source_repo)

        # Ensure target directory exists, otherwise Koji task will fail to
        # mount it.
        util.makedirs(config['ostree_repo'])

        self._run_ostree_cmd(compose, variant, arch, config, repodir)
        ref, commitid = self._get_commit_info(config, repodir)
        if config.get('tag_ref', True) and ref and commitid:
            # Let's write the tag out ourselves
            heads_dir = os.path.join(config['ostree_repo'], 'refs', 'heads')
            if not os.path.exists(heads_dir):
                raise RuntimeError('Refs/heads did not exist in ostree repo')

            ref_path = os.path.join(heads_dir, ref)
            if not os.path.exists(os.path.dirname(ref_path)):
                os.makedirs(os.path.dirname(ref_path))

            with open(ref_path, 'w') as f:
                f.write(commitid + '\n')

        if compose.notifier:
            compose.notifier.send('ostree',
                                  variant=variant.uid,
                                  arch=arch,
                                  ref=ref,
                                  commitid=commitid)

        self.pool.log_info('[DONE ] %s' % msg)

    def _get_commit_info(self, config, config_repo):
        ref = None
        commitid = None
        with open(os.path.join(config_repo, config['treefile']), 'r') as f:
            try:
                parsed = json.loads(f.read())
                ref = parsed['ref']
            except ValueError:
                return None, None
        if os.path.exists(os.path.join(self.logdir, 'commitid')):
            with open(os.path.join(self.logdir, 'commitid'), 'r') as f:
                commitid = f.read().replace('\n', '')
        else:
            return None, None
        return ref, commitid

    def _run_ostree_cmd(self, compose, variant, arch, config, config_repo):
        cmd = [
            'pungi-make-ostree',
            '--log-dir=%s' % os.path.join(self.logdir),
            '--treefile=%s' % os.path.join(config_repo, config['treefile']),
        ]

        version = config.get('version', None)
        if version:
            cmd.append('--version=%s' % version)

        if config.get('update_summary', False):
            cmd.append('--update-summary')

        # positional argument: ostree_repo
        cmd.append(config['ostree_repo'])

        runroot_channel = compose.conf.get("runroot_channel")
        runroot_tag = compose.conf["runroot_tag"]

        packages = ['pungi', 'ostree', 'rpm-ostree']
        log_file = os.path.join(self.logdir, 'runroot.log')
        mounts = [compose.topdir, config['ostree_repo']]
        koji = kojiwrapper.KojiWrapper(compose.conf["koji_profile"])
        koji_cmd = koji.get_runroot_cmd(runroot_tag, arch, cmd,
                                        channel=runroot_channel,
                                        use_shell=True, task_id=True,
                                        packages=packages, mounts=mounts,
                                        new_chroot=True)
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
    """
    Ensure a given .repo file points to `source_repo`.

    This function replaces all lines starting with `mirrorlist`, `metalink` or
    `baseurl` with `baseurl` set to requested repository.
    """
    with open(path, 'r') as f:
        contents = f.read()
    replacement = 'baseurl=%s' % source_repo
    exp = re.compile(r'^(mirrorlist|metalink|baseurl)=.*$', re.MULTILINE)
    contents = exp.sub(replacement, contents)
    with open(path, 'w') as f:
        f.write(contents)
