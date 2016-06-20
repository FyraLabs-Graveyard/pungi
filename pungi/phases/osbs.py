# -*- coding: utf-8 -*-

import json
import os
from kobo.threads import ThreadPool, WorkerThread

from .base import ConfigGuardedPhase
from .. import util
from ..wrappers import kojiwrapper
from ..paths import translate_path


class OSBSPhase(ConfigGuardedPhase):
    name = 'osbs'

    config_options = [
        {
            "name": "osbs",
            "expected_types": [dict],
            "optional": True,
        }
    ]

    def __init__(self, compose):
        super(OSBSPhase, self).__init__(compose)
        self.pool = ThreadPool(logger=self.compose._logger)
        self.pool.metadata = {}

    def run(self):
        for variant in self.compose.get_variants():
            for conf in util.get_variant_data(self.compose.conf, self.name, variant):
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
        with util.failable(compose, variant, '*', 'osbs'):
            self.worker(compose, variant, config)

    def worker(self, compose, variant, config):
        msg = 'OSBS phase for variant %s' % variant.uid
        self.pool.log_info('[BEGIN] %s' % msg)
        koji = kojiwrapper.KojiWrapper(compose.conf['koji_profile'])
        koji.login()

        # Start task
        try:
            source = util.resolve_git_url(config.pop('url'))
            target = config.pop('target')

            # Set release dynamically
            if 'release' in config and config['release'] is None:
                config['release'] = self._get_release(koji, target, config['name'])
        except KeyError as exc:
            raise RuntimeError('OSBS: missing config key %s for %s'
                               % (exc, variant.uid))
        priority = config.pop('priority', None)

        config['yum_repourls'] = [self._get_repo(compose, variant)]

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

        # Only real builds get the metadata.
        if not config.get('scratch', False):
            self._add_metadata(koji.koji_proxy, variant, task_id)

        self.pool.log_info('[DONE ] %s' % msg)

    def _add_metadata(self, koji_proxy, variant, task_id):
        # Create metadata
        result = koji_proxy.getTaskResult(task_id)
        build_id = result['koji_builds'][0]
        buildinfo = koji_proxy.getBuild(build_id)
        archives = koji_proxy.listArchives(build_id)

        metadata = {
            'name': buildinfo['name'],
            'version': buildinfo['version'],
            'release': buildinfo['release'],
            'creation_time': buildinfo['creation_time'],
        }
        for archive in archives:
            data = {
                'filename': archive['filename'],
                'size': archive['size'],
                'checksum': archive['checksum'],
            }
            data.update(archive['extra'])
            data.update(metadata)
            arch = archive['extra']['image']['arch']
            self.pool.metadata.setdefault(
                variant.uid, {}).setdefault(arch, []).append(data)

    def _get_repo(self, compose, variant):
        """
        Write a .repo file pointing to current variant and return URL to the
        file.
        """
        os_tree = compose.paths.compose.os_tree('$basearch', variant,
                                                create_dir=False)
        repo_file = os.path.join(compose.paths.work.tmp_dir(None, variant),
                                 'compose-rpms-%s.repo' % self.num)

        with open(repo_file, 'w') as f:
            f.write('[%s]\n' % compose.compose_id)
            f.write('name=Compose %s (RPMs)\n' % compose.compose_id)
            f.write('baseurl=%s\n' % translate_path(compose, os_tree))
            f.write('enabled=1\n')
            f.write('gpgcheck=0\n')

        return translate_path(compose, repo_file)

    def _get_release(self, koji, target, name):
        """
        Get next release value based on last build. If no build has been done
        yet (in given target), use 1 as initial value.
        """
        latest_builds = koji.koji_proxy.getLatestBuilds(target, package=name)
        try:
            return koji.koji_proxy.getNextRelease(latest_builds[0])
        except IndexError:
            return 1
