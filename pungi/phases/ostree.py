# -*- coding: utf-8 -*-

import copy
import json
import os
from kobo.threads import ThreadPool, WorkerThread

from .base import ConfigGuardedPhase
from .. import util
from ..ostree.utils import get_ref_from_treefile, get_commitid_from_commitid_file
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

        source_variant = compose.all_variants[config['source_repo_from']]
        source_repo = translate_path(compose,
                                     compose.paths.compose.repository('$basearch',
                                                                      source_variant,
                                                                      create_dir=False))

        self._clone_repo(repodir, config['config_url'], config.get('config_branch', 'master'))

        source_repos = [{'name': '%s-%s' % (compose.compose_id, config['source_repo_from']),
                         'baseurl': source_repo}]

        extra_source_repos = config.get('extra_source_repos', None)
        if extra_source_repos:
            for extra in extra_source_repos:
                baseurl = extra['baseurl']
                if "://" not in baseurl:
                    # it's variant UID, translate to url
                    variant = compose.variants[baseurl]
                    url = translate_path(compose,
                                         compose.paths.compose.repository('$basearch',
                                                                          variant,
                                                                          create_dir=False))
                    extra['baseurl'] = url

            source_repos = source_repos + extra_source_repos

        # copy the original config and update before save to a json file
        new_config = copy.copy(config)

        # repos in configuration can have repo url set to variant UID,
        # update it to have the actual url that we just translated.
        new_config.update({'source_repo_from': source_repo})
        if extra_source_repos:
            new_config.update({'extra_source_repos': extra_source_repos})

        # remove unnecessary (for 'pungi-make-ostree tree' script ) elements
        # from config, it doesn't hurt to have them, however remove them can
        # reduce confusion
        for k in ['ostree_repo', 'treefile', 'config_url', 'config_branch',
                  'failable', 'version', 'update_summary']:
            new_config.pop(k, None)

        extra_config_file = None
        if new_config:
            # write a json file to save the configuration, so 'pungi-make-ostree tree'
            # can take use of it
            extra_config_file = os.path.join(workdir, 'extra_config.json')
            with open(extra_config_file, 'w') as f:
                json.dump(new_config, f, indent=4)

        # Ensure target directory exists, otherwise Koji task will fail to
        # mount it.
        util.makedirs(config['ostree_repo'])

        self._run_ostree_cmd(compose, variant, arch, config, repodir,
                             extra_config_file=extra_config_file)

        if compose.notifier:
            ref = get_ref_from_treefile(os.path.join(repodir, config['treefile']), arch)
            # 'pungi-make-ostree tree' writes commitid to commitid.log in logdir
            commitid = get_commitid_from_commitid_file(os.path.join(self.logdir, 'commitid.log'))
            compose.notifier.send('ostree',
                                  variant=variant.uid,
                                  arch=arch,
                                  ref=ref,
                                  commitid=commitid)

        self.pool.log_info('[DONE ] %s' % msg)

    def _run_ostree_cmd(self, compose, variant, arch, config, config_repo, extra_config_file=None):
        cmd = [
            'pungi-make-ostree',
            'tree',
            '--repo=%s' % config['ostree_repo'],
            '--log-dir=%s' % self.logdir,
            '--treefile=%s' % os.path.join(config_repo, config['treefile']),
        ]

        version = config.get('version', None)
        if version:
            cmd.append('--version=%s' % version)

        if extra_config_file:
            cmd.append('--extra-config=%s' % extra_config_file)

        if config.get('update_summary', False):
            cmd.append('--update-summary')

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
