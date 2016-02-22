# -*- coding: utf-8 -*-


# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.


import os
import sys
import time
import pipes
import shutil

from kobo.threads import ThreadPool, WorkerThread
from kobo.shortcuts import run, save_to_file

from pungi.wrappers.kojiwrapper import KojiWrapper
from pungi.wrappers.iso import IsoWrapper
from pungi.phases.base import PhaseBase
from pungi.util import get_arch_variant_data, resolve_git_url
from pungi.paths import translate_path


# HACK: define cmp in python3
if sys.version_info[0] == 3:
    def cmp(a, b):
        return (a > b) - (a < b)


class LiveImagesPhase(PhaseBase):
    name = "liveimages"

    config_options = (
        {
            "name": "live_target",
            "expected_types": [str],
            "optional": True,
        },
        {
            "name": "live_images",
            "expected_types": [list],
            "optional": True,
        },
        {
            "name": "signing_key_id",
            "expected_types": [str],
            "optional": True,
        },
        {
            "name": "signing_key_password_file",
            "expected_types": [str],
            "optional": True,
        },
        {
            "name": "signing_command",
            "expected_types": [str],
            "optional": True,
        },
    )

    def __init__(self, compose):
        PhaseBase.__init__(self, compose)
        self.pool = ThreadPool(logger=self.compose._logger)

    def skip(self):
        if PhaseBase.skip(self):
            return True
        if not self.compose.conf.get("live_images"):
            return True
        return False

    def _get_extra_repos(self, arch, variant, extras):
        repo = []
        for extra in extras:
            v = self.compose.variants.get(extra)
            if not v:
                raise RuntimeError(
                    'There is no variant %s to get repo from when building live image for %s.'
                    % (extra, variant.uid))
            repo.append(translate_path(
                self.compose, self.compose.paths.compose.repository(arch, v, create_dir=False)))

        return repo

    def _get_release(self, image_conf):
        """If release is set explicitly to None, replace it with date and respin."""
        if 'release' in image_conf and image_conf['release'] is None:
            return '%s.%s' % (self.compose.compose_date, self.compose.compose_respin)
        return image_conf.get('release', None)

    def run(self):
        symlink_isos_to = self.compose.conf.get("symlink_isos_to", None)
        commands = []

        for variant in self.compose.variants.values():
            for arch in variant.arches + ["src"]:
                for data in get_arch_variant_data(self.compose.conf, "live_images", arch, variant):
                    iso_dir = self.compose.paths.compose.iso_dir(arch, variant, symlink_to=symlink_isos_to)
                    if not iso_dir:
                        continue

                    cmd = {
                        "name": None,
                        "version": None,
                        "iso_path": None,
                        "wrapped_rpms_path": iso_dir,
                        "build_arch": arch,
                        "ks_file": data['kickstart'],
                        "ksurl": None,
                        "specfile": None,
                        "scratch": False,
                        "sign": False,
                        "label": "",  # currently not used
                    }

                    if 'ksurl' in data:
                        cmd['ksurl'] = resolve_git_url(data['ksurl'])

                    cmd["repos"] = []
                    if not variant.is_empty:
                        cmd["repos"].append(translate_path(
                            self.compose, self.compose.paths.compose.repository(arch, variant, create_dir=False)))

                    # additional repos
                    cmd["repos"].extend(data.get("additional_repos", []))
                    cmd['repos'].extend(self._get_extra_repos(arch, variant, data.get('repos_from', [])))

                    # Explicit name and version
                    cmd["name"] = data.get("name", None)
                    cmd["version"] = data.get("version", None)

                    cmd['type'] = data.get('type', 'live')
                    cmd['release'] = self._get_release(data)

                    # Specfile (for images wrapped in rpm)
                    cmd["specfile"] = data.get("specfile", None)

                    # Scratch (only taken in consideration if specfile specified)
                    # For images wrapped in rpm is scratch disabled by default
                    # For other images is scratch always on
                    cmd["scratch"] = data.get("scratch", False)

                    # Signing of the rpm wrapped image
                    if not cmd["scratch"] and data.get("sign"):
                        cmd["sign"] = True

                    format = "%(compose_id)s-%(variant)s-%(arch)s-%(disc_type)s%(disc_num)s%(suffix)s"
                    # Custom name (prefix)
                    if cmd["name"]:
                        custom_iso_name = cmd["name"]
                        if cmd["version"]:
                            custom_iso_name += "-%s" % cmd["version"]
                        format = custom_iso_name + "-%(variant)s-%(arch)s-%(disc_type)s%(disc_num)s%(suffix)s"

                    # XXX: hardcoded disc_type and disc_num
                    filename = self.compose.get_image_name(arch, variant, disc_type="live",
                                                           disc_num=None, format=format)
                    iso_path = self.compose.paths.compose.iso_path(arch, variant, filename,
                                                                   symlink_to=symlink_isos_to)
                    if os.path.isfile(iso_path):
                        self.compose.log_warning("Skipping creating live image, it already exists: %s" % iso_path)
                        continue
                    cmd["iso_path"] = iso_path

                    commands.append((cmd, variant, arch))

        for (cmd, variant, arch) in commands:
            self.pool.add(CreateLiveImageThread(self.pool))
            self.pool.queue_put((self.compose, cmd, variant, arch))

        self.pool.start()

    def stop(self, *args, **kwargs):
        PhaseBase.stop(self, *args, **kwargs)
        if self.skip():
            return


class CreateLiveImageThread(WorkerThread):
    def fail(self, compose, cmd):
        compose.log_error("LiveImage failed, removing ISO: %s" % cmd["iso_path"])
        try:
            # remove (possibly?) incomplete ISO
            os.unlink(cmd["iso_path"])
        except OSError:
            pass

    def process(self, item, num):
        compose, cmd, variant, arch = item
        try:
            self.worker(compose, cmd, variant, arch, num)
        except Exception as exc:
            if not compose.can_fail(variant, arch, 'live'):
                raise
            else:
                msg = ('[FAIL] Creating live image for variant %s, arch %s failed, but going on anyway.\n%s'
                       % (variant.uid, arch, exc))
                self.pool.log_info(msg)

    def worker(self, compose, cmd, variant, arch, num):
        log_file = compose.paths.log.log_file(arch, "createiso-%s" % os.path.basename(cmd["iso_path"]))

        msg = "Creating ISO (arch: %s, variant: %s): %s" % (arch, variant, os.path.basename(cmd["iso_path"]))
        self.pool.log_info("[BEGIN] %s" % msg)

        koji_wrapper = KojiWrapper(compose.conf["koji_profile"])
        name, version = compose.compose_id.rsplit("-", 1)
        name = cmd["name"] or name
        version = cmd["version"] or version
        archive = False
        if cmd["specfile"] and not cmd["scratch"]:
            # Non scratch build are allowed only for rpm wrapped images
            archive = True
        target = compose.conf.get("live_target", "rhel-7.0-candidate")  # compatability for hardcoded target
        koji_cmd = koji_wrapper.get_create_image_cmd(name, version, target,
                                                     cmd["build_arch"],
                                                     cmd["ks_file"],
                                                     cmd["repos"],
                                                     image_type=cmd['type'],
                                                     wait=True,
                                                     archive=archive,
                                                     specfile=cmd["specfile"],
                                                     release=cmd['release'],
                                                     ksurl=cmd['ksurl'])

        # avoid race conditions?
        # Kerberos authentication failed: Permission denied in replay cache code (-1765328215)
        time.sleep(num * 3)

        output = koji_wrapper.run_blocking_cmd(koji_cmd, log_file=log_file)
        if output["retcode"] != 0:
            self.fail(compose, cmd)
            raise RuntimeError("LiveImage task failed: %s. See %s for more details." % (output["task_id"], log_file))

        # copy finished image to isos/
        image_path = koji_wrapper.get_image_path(output["task_id"])
        # TODO: assert len == 1
        image_path = image_path[0]
        shutil.copy2(image_path, cmd["iso_path"])

        # copy finished rpm to isos/ (if rpm wrapped ISO was built)
        if cmd["specfile"]:
            rpm_paths = koji_wrapper.get_wrapped_rpm_path(output["task_id"])

            if cmd["sign"]:
                # Sign the rpm wrapped images and get their paths
                compose.log_info("Signing rpm wrapped images in task_id: %s (expected key ID: %s)" % (output["task_id"], compose.conf.get("signing_key_id")))
                signed_rpm_paths = self._sign_image(koji_wrapper, compose, cmd, output["task_id"])
                if signed_rpm_paths:
                    rpm_paths = signed_rpm_paths

            for rpm_path in rpm_paths:
                shutil.copy2(rpm_path, cmd["wrapped_rpms_path"])

        self._write_manifest(cmd['iso_path'])

        self.pool.log_info("[DONE ] %s" % msg)

    def _write_manifest(self, iso_path):
        """Generate manifest for ISO at given path.

        :param iso_path: (str) absolute path to the ISO
        """
        dir, filename = os.path.split(iso_path)
        iso = IsoWrapper()
        run("cd %s && %s" % (pipes.quote(dir), iso.get_manifest_cmd(filename)))

    def _sign_image(self, koji_wrapper, compose, cmd, koji_task_id):
        signing_key_id = compose.conf.get("signing_key_id")
        signing_command = compose.conf.get("signing_command")

        if not signing_key_id:
            compose.log_warning("Signing is enabled but signing_key_id is not specified")
            compose.log_warning("Signing skipped")
            return None
        if not signing_command:
            compose.log_warning("Signing is enabled but signing_command is not specified")
            compose.log_warning("Signing skipped")
            return None

        # Prepare signing log file
        signing_log_file = compose.paths.log.log_file(cmd["build_arch"], "live_images-signing-%s" % os.path.basename(cmd["iso_path"]))

        # Sign the rpm wrapped images
        try:
            sign_builds_in_task(koji_wrapper, koji_task_id, signing_command, log_file=signing_log_file, signing_key_password=compose.conf.get("signing_key_password"))
        except RuntimeError:
            compose.log_error("Error while signing rpm wrapped images. See log: %s" % signing_log_file)
            raise

        # Get pats to the signed rpms
        signing_key_id = signing_key_id.lower()  # Koji uses lowercase in paths
        rpm_paths = koji_wrapper.get_signed_wrapped_rpms_paths(koji_task_id, signing_key_id)

        # Wait untill files are available
        if wait_paths(rpm_paths, 60*15):
            # Files are ready
            return rpm_paths

        # Signed RPMs are not available
        compose.log_warning("Signed files are not available: %s" % rpm_paths)
        compose.log_warning("Unsigned files will be used")
        return None


def wait_paths(paths, timeout=60):
    started = time.time()
    remaining = paths[:]
    while True:
        for path in remaining[:]:
            if os.path.exists(path):
                remaining.remove(path)
        if not remaining:
            break
        time.sleep(1)
        if timeout >= 0 and (time.time() - started) > timeout:
            return False
    return True


def sign_builds_in_task(koji_wrapper, task_id, signing_command, log_file=None, signing_key_password=None):
    # Get list of nvrs that should be signed
    nvrs = koji_wrapper.get_build_nvrs(task_id)
    if not nvrs:
        # No builds are available (scratch build, etc.?)
        return

    # Append builds to sign_cmd
    for nvr in nvrs:
        signing_command += " '%s'" % nvr

    # Log signing command before password is filled in it
    if log_file:
        save_to_file(log_file, signing_command, append=True)

    # Fill password into the signing command
    if signing_key_password:
        signing_command = signing_command % {"signing_key_password": signing_key_password}

    # Sign the builds
    run(signing_command, can_fail=False, show_cmd=False, logfile=log_file)
