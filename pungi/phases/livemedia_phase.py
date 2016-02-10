# -*- coding: utf-8 -*-

import os
import time
from kobo import shortcuts

from pungi.util import get_variant_data, resolve_git_url, makedirs
from pungi.phases.base import PhaseBase
from pungi.linker import Linker
from pungi.paths import translate_path
from pungi.wrappers.kojiwrapper import KojiWrapper
from kobo.threads import ThreadPool, WorkerThread
from productmd.images import Image


class LiveMediaPhase(PhaseBase):
    """class for wrapping up koji spin-livemedia"""
    name = 'live_media'

    def __init__(self, compose):
        super(LiveMediaPhase, self).__init__(compose)
        self.pool = ThreadPool(logger=self.compose._logger)

    def skip(self):
        if super(LiveMediaPhase, self).skip():
            return True
        if not self.compose.conf.get(self.name):
            self.compose.log_info("Config section '%s' was not found. Skipping" % self.name)
            return True
        return False

    def _get_repos(self, image_conf, variant):
        """
        Get a comma separated list of repos. First included are those
        explicitly listed in config, followed by repos from other variants,
        finally followed by repo for current variant.

        The `repo_from` key is removed from the dict (if present).
        """
        repo = shortcuts.force_list(image_conf.get('repo', []))

        extras = shortcuts.force_list(image_conf.pop('repo_from', []))
        extras.append(variant.uid)

        for extra in extras:
            v = self.compose.variants.get(extra)
            if not v:
                raise RuntimeError(
                    'There is no variant %s to get repo from when building live media for %s.'
                    % (extra, variant.uid))
            repo.append(translate_path(
                self.compose,
                self.compose.paths.compose.repository('$arch', v, create_dir=False)))

        return repo

    def _get_arches(self, image_conf, arches):
        if 'arches' in image_conf:
            arches = set(image_conf.get('arches', [])) & arches
        return sorted(arches)

    def _get_release(self, image_conf):
        """If release is set explicitly to None, replace it with date and respin."""
        if 'release' in image_conf and image_conf['release'] is None:
            return '%s.%s' % (self.compose.compose_date, self.compose.compose_respin)
        return image_conf.get('release', None)

    def run(self):
        for variant in self.compose.get_variants():
            arches = set([x for x in variant.arches if x != 'src'])

            for image_conf in get_variant_data(self.compose.conf, self.name, variant):
                config = {
                    'target': image_conf['target'],
                    'arches': self._get_arches(image_conf, arches),
                    'kickstart': image_conf['kickstart'],
                    'ksurl': resolve_git_url(image_conf['ksurl']),
                    'ksversion': image_conf.get('ksversion'),
                    'scratch': image_conf.get('scratch', False),
                    'release': self._get_release(image_conf),
                    'skip_tag': image_conf.get('skip_tag'),
                    'name': image_conf['name'],
                    'title': image_conf.get('title'),
                    'repo': self._get_repos(image_conf, variant),
                    'install_tree': translate_path(
                        self.compose,
                        self.compose.paths.compose.os_tree('$arch', variant, create_dir=False)
                    ),
                    'version': image_conf['version'],
                }
                self.pool.add(LiveMediaThread(self.pool))
                self.pool.queue_put((self.compose, variant, config))

        self.pool.start()


class LiveMediaThread(WorkerThread):
    def process(self, item, num):
        compose, variant, config = item
        self.num = num
        try:
            self.worker(compose, variant, config)
        except Exception as exc:
            if not compose.can_fail(variant, '*', 'live-media'):
                raise
            else:
                msg = ('[FAIL] live-media for variant %s failed, but going on anyway.\n%s'
                       % (variant.uid, exc))
                self.pool.log_info(msg)

    def _get_log_file(self, compose, variant, config):
        arches = '-'.join(config['arches'])
        return compose.paths.log.log_file(arches, 'livemedia-%s' % variant)

    def _run_command(self, koji_wrapper, cmd, compose, log_file):
        time.sleep(self.num * 3)
        output = koji_wrapper.run_blocking_cmd(cmd, log_file=log_file)
        self.pool.log_debug('live media outputs: %s' % (output))
        if output['retcode'] != 0:
            compose.log_error('Live media task failed.')
            raise RuntimeError('Live media task failed: %s. See %s for more details.'
                               % (output['task_id'], log_file))
        return output

    def worker(self, compose, variant, config):
        msg = 'Live media: %s (arches: %s, variant: %s)' % (config['name'],
                                                            ' '.join(config['arches']),
                                                            variant.uid)
        self.pool.log_info('[BEGIN] %s' % msg)

        koji_wrapper = KojiWrapper(compose.conf['koji_profile'])
        cmd = koji_wrapper.get_live_media_cmd(config)

        log_file = self._get_log_file(compose, variant, config)
        output = self._run_command(koji_wrapper, cmd, compose, log_file)

        # collect results and update manifest
        image_infos = []

        paths = koji_wrapper.get_image_paths(output['task_id'])

        for arch, paths in paths.iteritems():
            for path in paths:
                if path.endswith('.iso'):
                    image_infos.append({'path': path, 'arch': arch})

        if len(image_infos) != len(config['arches']):
            self.pool.log_error(
                'Error in koji task %s. Expected to find one image for each arch (%s). Got %s.'
                % (output['task_id'], len(config['arches']), len(image_infos)))
            raise RuntimeError('Image count mismatch in task %s.' % output['task_id'])

        linker = Linker(logger=compose._logger)
        link_type = compose.conf.get("link_type", "hardlink-or-copy")
        for image_info in image_infos:
            image_dir = compose.paths.compose.image_dir(variant) % {"arch": image_info['arch']}
            makedirs(image_dir)
            relative_image_dir = (
                compose.paths.compose.image_dir(variant, relative=True) % {"arch": image_info['arch']}
            )

            # let's not change filename of koji outputs
            image_dest = os.path.join(image_dir, os.path.basename(image_info['path']))
            linker.link(image_info['path'], image_dest, link_type=link_type)

            # Update image manifest
            img = Image(compose.im)
            img.type = 'live'
            img.format = 'iso'
            img.path = os.path.join(relative_image_dir, os.path.basename(image_dest))
            img.mtime = int(os.stat(image_dest).st_mtime)
            img.size = os.path.getsize(image_dest)
            img.arch = image_info['arch']
            img.disc_number = 1     # We don't expect multiple disks
            img.disc_count = 1
            img.bootable = True
            compose.im.add(variant=variant.uid, arch=image_info['arch'], image=img)

        self.pool.log_info('[DONE ] %s' % msg)
