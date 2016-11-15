# -*- coding: utf-8 -*-

import datetime
import json
import os
from kobo.threads import ThreadPool, WorkerThread

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

        source_variant = compose.all_variants[config['source_repo_from']]
        source_repo = translate_path(compose,
                                     compose.paths.compose.repository('$basearch',
                                                                      source_variant,
                                                                      create_dir=False))

        self._clone_repo(repodir, config['config_url'], config.get('config_branch', 'master'))

        treeconf = os.path.join(repodir, config['treefile'])
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

        keep_original_sources = config.get('keep_original_sources', False)
        self._tweak_treeconf(treeconf, source_repos=source_repos,
                             keep_original_sources=keep_original_sources)

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

    def _tweak_treeconf(self, treeconf, source_repos, keep_original_sources=False):
        """
        Update tree config file by adding new repos and remove existing repos
        from the tree config file if 'keep_original_sources' is not enabled.
        """
        # add this timestamp to repo name to get unique repo filename and repo name
        # should be safe enough
        time = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

        treeconf_dir = os.path.dirname(treeconf)
        with open(treeconf, 'r') as f:
            treeconf_content = json.load(f)

        # backup the old tree config
        os.rename(treeconf, '%s.%s.bak' % (treeconf, time))

        repos = []
        for repo in source_repos:
            name = "%s-%s" % (repo['name'], time)
            with open("%s/%s.repo" % (treeconf_dir, name), 'w') as f:
                f.write("[%s]\n" % name)
                f.write("name=%s\n" % name)
                f.write("baseurl=%s\n" % repo['baseurl'])
                exclude = repo.get('exclude', None)
                if exclude:
                    f.write("exclude=%s\n" % exclude)
                gpgcheck = '1' if repo.get('gpgcheck', False) else '0'
                f.write("gpgcheck=%s\n" % gpgcheck)
            repos.append(name)

        original_repos = treeconf_content.get('repos', [])
        if keep_original_sources:
            treeconf_content['repos'] = original_repos + repos
        else:
            treeconf_content['repos'] = repos

        # update tree config to add new repos
        with open(treeconf, 'w') as f:
            json.dump(treeconf_content, f, indent=4)
