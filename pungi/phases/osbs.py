# -*- coding: utf-8 -*-

import json
import os
from kobo.threads import ThreadPool, WorkerThread
from kobo import shortcuts

from .base import ConfigGuardedPhase, PhaseLoggerMixin
from .. import util
from ..wrappers import kojiwrapper


class OSBSPhase(PhaseLoggerMixin, ConfigGuardedPhase):
    name = 'osbs'

    def __init__(self, compose):
        super(OSBSPhase, self).__init__(compose)
        self.pool = ThreadPool(logger=self.logger)
        self.pool.metadata = {}

    def run(self):
        for variant in self.compose.get_variants():
            for conf in self.get_config_block(variant):
                self.pool.add(OSBSThread(self.pool))
                self.pool.queue_put((self.compose, variant, conf))

        self.pool.start()

    def dump_metadata(self):
        """Create a file with image metadata if the phase actually ran."""
        if self._skipped:
            return
        with open(self.compose.paths.compose.metadata('osbs.json'), 'w') as f:
            json.dump(self.pool.metadata, f, indent=4, sort_keys=True,
                      separators=(',', ': '))


class OSBSThread(WorkerThread):
    def process(self, item, num):
        compose, variant, config = item
        self.num = num
        with util.failable(compose, bool(config.pop('failable', None)), variant, '*', 'osbs',
                           logger=self.pool._logger):
            self.worker(compose, variant, config)

    def worker(self, compose, variant, config):
        msg = 'OSBS phase for variant %s' % variant.uid
        self.pool.log_info('[BEGIN] %s' % msg)
        koji = kojiwrapper.KojiWrapper(compose.conf['koji_profile'])
        koji.login()

        # Start task
        source = util.resolve_git_url(config.pop('url'))
        target = config.pop('target')
        priority = config.pop('priority', None)
        gpgkey = config.pop('gpgkey', None)
        repos = [self._get_repo(compose, v, gpgkey=gpgkey)
                 for v in [variant.uid] + shortcuts.force_list(config.pop('repo', []))]

        config['yum_repourls'] = repos

        task_id = koji.koji_proxy.buildContainer(source, target, config,
                                                 priority=priority)

        # Wait for it to finish and capture the output into log file (even
        # though there is not much there).
        log_dir = os.path.join(compose.paths.log.topdir(), 'osbs')
        util.makedirs(log_dir)
        log_file = os.path.join(log_dir, '%s-%s-watch-task.log'
                                % (variant.uid, self.num))
        if koji.watch_task(task_id, log_file) != 0:
            raise RuntimeError('OSBS: task %s failed: see %s for details'
                               % (task_id, log_file))

        scratch = config.get('scratch', False)
        self._add_metadata(koji.koji_proxy, variant, task_id, compose, scratch)

        self.pool.log_info('[DONE ] %s' % msg)

    def _add_metadata(self, koji_proxy, variant, task_id, compose, is_scratch):
        # Create metadata
        metadata = {
            'compose_id': compose.compose_id,
            'koji_task': task_id,
        }

        result = koji_proxy.getTaskResult(task_id)
        if is_scratch:
            metadata.update({
                'repositories': result['repositories'],
            })
            # add a fake arch of 'scratch', so we can construct the metadata
            # in same data structure as real builds.
            self.pool.metadata.setdefault(
                variant.uid, {}).setdefault('scratch', []).append(metadata)
        else:
            build_id = int(result['koji_builds'][0])
            buildinfo = koji_proxy.getBuild(build_id)
            archives = koji_proxy.listArchives(build_id)

            metadata.update({
                'name': buildinfo['name'],
                'version': buildinfo['version'],
                'release': buildinfo['release'],
                'creation_time': buildinfo['creation_time'],
            })
            for archive in archives:
                data = {
                    'filename': archive['filename'],
                    'size': archive['size'],
                    'checksum': archive['checksum'],
                }
                data.update(archive['extra'])
                data.update(metadata)
                arch = archive['extra']['image']['arch']
                self.pool.log_debug('Created Docker base image %s-%s-%s.%s' % (
                    metadata['name'], metadata['version'], metadata['release'], arch))
                self.pool.metadata.setdefault(
                    variant.uid, {}).setdefault(arch, []).append(data)

    def _get_repo(self, compose, repo, gpgkey=None):
        """
        Return repo file URL of repo, if repo contains "://", it's already
        a URL of repo file. Or it's a variant UID, then write a .repo file
        pointing to current variant and return the URL to .repo file.
        """
        if "://" in repo:
            return repo

        try:
            variant = compose.all_variants[repo]
        except KeyError:
            raise RuntimeError(
                'There is no variant %s to get repo from to pass to OSBS.'
                % (repo))
        os_tree = compose.paths.compose.os_tree('$basearch', variant,
                                                create_dir=False)
        repo_file = os.path.join(compose.paths.work.tmp_dir(None, variant),
                                 'compose-rpms-%s.repo' % self.num)

        gpgcheck = 1 if gpgkey else 0
        with open(repo_file, 'w') as f:
            f.write('[%s]\n' % compose.compose_id)
            f.write('name=Compose %s (RPMs)\n' % compose.compose_id)
            f.write('baseurl=%s\n' % util.translate_path(compose, os_tree))
            f.write('enabled=1\n')
            f.write('gpgcheck=%s\n' % gpgcheck)
            if gpgcheck:
                f.write('gpgkey=%s\n' % gpgkey)

        return util.translate_path(compose, repo_file)
