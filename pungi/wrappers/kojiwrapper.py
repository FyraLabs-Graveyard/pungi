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
import pipes
import re

import koji
import rpmUtils.arch
from kobo.shortcuts import run
from ConfigParser import ConfigParser


class KojiWrapper(object):
    def __init__(self, profile):
        self.profile = profile
        # assumption: profile name equals executable name (it's a symlink -> koji)
        self.executable = self.profile.replace("_", "-")
        self.koji_module = koji.get_profile_module(profile)
        self.koji_proxy = koji.ClientSession(self.koji_module.config.server)

    def get_runroot_cmd(self, target, arch, command, quiet=False, use_shell=True, channel=None, packages=None, mounts=None, weight=None, task_id=True):
        cmd = [self.executable, "runroot"]

        if quiet:
            cmd.append("--quiet")

        if use_shell:
            cmd.append("--use-shell")

        if task_id:
            cmd.append("--task-id")

        if channel:
            cmd.append("--channel-override=%s" % channel)
        else:
            cmd.append("--channel-override=runroot-local")

        if weight:
            cmd.append("--weight=%s" % int(weight))

        for package in packages or []:
            cmd.append("--package=%s" % package)

        for mount in mounts or []:
            # directories are *not* created here
            cmd.append("--mount=%s" % mount)

        # IMPORTANT: all --opts have to be provided *before* args

        cmd.append(target)

        # i686 -> i386 etc.
        arch = rpmUtils.arch.getBaseArch(arch)
        cmd.append(arch)

        if isinstance(command, list):
            command = " ".join([pipes.quote(i) for i in command])

        # HACK: remove rpmdb and yum cache
        command = "rm -f /var/lib/rpm/__db*; rm -rf /var/cache/yum/*; set -x; " + command
        cmd.append(command)

        return cmd

    def run_runroot_cmd(self, command, log_file=None):
        """
        Run koji runroot command and wait for results.

        If the command specified --task-id, and the first line of output
        contains the id, it will be captured and returned.
        """
        task_id = None
        retcode, output = run(command, can_fail=True, logfile=log_file)
        if "--task-id" in command:
            first_line = output.splitlines()[0]
            if re.match(r'^\d+$', first_line):
                task_id = int(first_line)
                # Remove first line from the output, preserving any trailing newlines.
                output_ends_with_eol = output.endswith("\n")
                output = "\n".join(output.splitlines()[1:])
                if output_ends_with_eol:
                    output += "\n"

        return {
            "retcode": retcode,
            "output": output,
            "task_id": task_id,
        }

    def get_image_build_cmd(self, config_options, conf_file_dest, wait=True, scratch=False):
        """
        @param config_options
        @param conf_file_dest -  a destination in compose workdir for the conf file to be written
        @param wait=True
        @param scratch=False
        """
        # Usage: koji image-build [options] <name> <version> <target> <install-tree-url> <arch> [<arch>...]
        sub_command = "image-build"
        # The minimum set of options
        min_options = ("name", "version", "target", "install_tree", "arches", "format", "kickstart", "ksurl", "distro")
        assert set(min_options).issubset(set(config_options['image-build'].keys())), "image-build requires at least %s got '%s'" % (", ".join(min_options), config_options)
        cfg_parser = ConfigParser()
        for section, opts in config_options.iteritems():
            cfg_parser.add_section(section)
            for option, value in opts.iteritems():
                cfg_parser.set(section, option, value)

        fd = open(conf_file_dest, "w")
        cfg_parser.write(fd)
        fd.close()

        cmd = [self.executable, sub_command, "--config=%s" % conf_file_dest]
        if wait:
            cmd.append("--wait")
        if scratch:
            cmd.append("--scratch")

        return cmd

    def get_live_media_cmd(self, options, wait=True):
        # Usage: koji spin-livemedia [options] <name> <version> <target> <arch> <kickstart-file>
        cmd = ['koji', 'spin-livemedia']

        for key in ('name', 'version', 'target', 'arch', 'ksfile'):
            if key not in options:
                raise ValueError('Expected options to have key "%s"' % key)
            cmd.append(options[key])

        if 'install_tree' not in options:
            raise ValueError('Expected options to have key "install_tree"')
        cmd.append('--install-tree=%s' % options['install_tree'])

        for repo in options.get('repo', []):
            cmd.append('--repo=%s' % repo)

        if options.get('scratch'):
            cmd.append('--scratch')

        if options.get('skip_tag'):
            cmd.append('--skip-tag')

        if 'ksurl' in options:
            cmd.append('--ksurl=%s' % options['ksurl'])

        if wait:
            cmd.append('--wait')

        return cmd

    def get_create_image_cmd(self, name, version, target, arch, ks_file, repos, image_type="live", image_format=None, release=None, wait=True, archive=False, specfile=None, ksurl=None):
        # Usage: koji spin-livecd [options] <name> <version> <target> <arch> <kickstart-file>
        # Usage: koji spin-appliance [options] <name> <version> <target> <arch> <kickstart-file>
        # Examples:
        #  * name: RHEL-7.0
        #  * name: Satellite-6.0.1-RHEL-6
        #  ** -<type>.<arch>
        #  * version: YYYYMMDD[.n|.t].X
        #  * release: 1

        cmd = [self.executable]

        if image_type == "live":
            cmd.append("spin-livecd")
        elif image_type == "appliance":
            cmd.append("spin-appliance")
        else:
            raise ValueError("Invalid image type: %s" % image_type)

        if not archive:
            cmd.append("--scratch")

        cmd.append("--noprogress")

        if wait:
            cmd.append("--wait")
        else:
            cmd.append("--nowait")

        if specfile:
            cmd.append("--specfile=%s" % specfile)

        if ksurl:
            cmd.append("--ksurl=%s" % ksurl)

        if isinstance(repos, list):
            for repo in repos:
                cmd.append("--repo=%s" % repo)
        else:
            cmd.append("--repo=%s" % repos)

        if image_format:
            if image_type != "appliance":
                raise ValueError("Format can be specified only for appliance images'")
            supported_formats = ["raw", "qcow", "qcow2", "vmx"]
            if image_format not in supported_formats:
                raise ValueError("Format is not supported: %s. Supported formats: %s" % (image_format, " ".join(sorted(supported_formats))))
            cmd.append("--format=%s" % image_format)

        if release is not None:
            cmd.append("--release=%s" % release)

        # IMPORTANT: all --opts have to be provided *before* args
        # Usage: koji spin-livecd [options] <name> <version> <target> <arch> <kickstart-file>

        cmd.append(name)
        cmd.append(version)
        cmd.append(target)

        # i686 -> i386 etc.
        arch = rpmUtils.arch.getBaseArch(arch)
        cmd.append(arch)

        cmd.append(ks_file)

        return cmd

    def run_blocking_cmd(self, command, log_file=None):
        """
        Run a blocking koji command. Returns a dict with output of the command,
        its exit code and parsed task id. This method will block until the
        command finishes.
        """
        try:
            retcode, output = run(command, can_fail=True, logfile=log_file)
        except RuntimeError, e:
            raise RuntimeError("%s. %s failed with '%s'" % (e, command, output))

        match = re.search(r"Created task: (\d+)", output)
        if not match:
            raise RuntimeError("Could not find task ID in output. Command '%s' returned '%s'."
                               % (" ".join(command), output))

        result = {
            "retcode": retcode,
            "output": output,
            "task_id": int(match.groups()[0]),
        }
        return result

    def get_image_paths(self, task_id):
        """
        Given an image task in Koji, get a mapping from arches to a list of
        paths to results of the task.
        """
        result = {}

        # task = self.koji_proxy.getTaskInfo(task_id, request=True)
        children_tasks = self.koji_proxy.getTaskChildren(task_id, request=True)

        for child_task in children_tasks:
            if child_task['method'] not in ['createImage', 'createLiveMedia']:
                continue

            is_scratch = child_task['request'][-1].get('scratch', False)
            task_result = self.koji_proxy.getTaskResult(child_task['id'])

            if is_scratch:
                topdir = os.path.join(
                    self.koji_module.pathinfo.work(),
                    self.koji_module.pathinfo.taskrelpath(child_task['id'])
                )
            else:
                build = self.koji_proxy.getImageBuild("%(name)s-%(version)s-%(release)s" % task_result)
                build["name"] = task_result["name"]
                build["version"] = task_result["version"]
                build["release"] = task_result["release"]
                build["arch"] = task_result["arch"]
                topdir = self.koji_module.pathinfo.imagebuild(build)

            for i in task_result["files"]:
                result.setdefault(task_result['arch'], []).append(os.path.join(topdir, i))

        return result

    def get_image_path(self, task_id):
        result = []
        koji_proxy = self.koji_module.ClientSession(self.koji_module.config.server)
        task_info_list = []
        task_info_list.append(koji_proxy.getTaskInfo(task_id, request=True))
        task_info_list.extend(koji_proxy.getTaskChildren(task_id, request=True))

        # scan parent and child tasks for certain methods
        task_info = None
        for i in task_info_list:
            if i["method"] in ("createAppliance", "createLiveCD", 'createImage'):
                task_info = i
                break

        scratch = task_info["request"][-1].get("scratch", False)
        task_result = koji_proxy.getTaskResult(task_info["id"])
        task_result.pop("rpmlist", None)

        if scratch:
            topdir = os.path.join(self.koji_module.pathinfo.work(), self.koji_module.pathinfo.taskrelpath(task_info["id"]))
        else:
            build = koji_proxy.getImageBuild("%(name)s-%(version)s-%(release)s" % task_result)
            build["name"] = task_result["name"]
            build["version"] = task_result["version"]
            build["release"] = task_result["release"]
            build["arch"] = task_result["arch"]
            topdir = self.koji_module.pathinfo.imagebuild(build)
        for i in task_result["files"]:
            result.append(os.path.join(topdir, i))
        return result

    def get_wrapped_rpm_path(self, task_id, srpm=False):
        result = []
        parent_task = self.koji_proxy.getTaskInfo(task_id, request=True)
        task_info_list = []
        task_info_list.extend(self.koji_proxy.getTaskChildren(task_id, request=True))

        # scan parent and child tasks for certain methods
        task_info = None
        for i in task_info_list:
            if i["method"] in ("wrapperRPM"):
                task_info = i
                break

        # Check parent_task if it's scratch build
        scratch = parent_task["request"][-1].get("scratch", False)

        # Get results of wrapperRPM task
        # {'buildroot_id': 2479520,
        #  'logs': ['checkout.log', 'root.log', 'state.log', 'build.log'],
        #  'rpms': ['foreman-discovery-image-2.1.0-2.el7sat.noarch.rpm'],
        #  'srpm': 'foreman-discovery-image-2.1.0-2.el7sat.src.rpm'}
        task_result = self.koji_proxy.getTaskResult(task_info["id"])

        # Get koji dir with results (rpms, srpms, logs, ...)
        topdir = os.path.join(self.koji_module.pathinfo.work(), self.koji_module.pathinfo.taskrelpath(task_info["id"]))

        # TODO: Maybe use different approach for non-scratch builds - see get_image_path()

        # Get list of filenames that should be returned
        result_files = task_result["rpms"]
        if srpm:
            result_files += [task_result["srpm"]]

        # Prepare list with paths to the required files
        for i in result_files:
            result.append(os.path.join(topdir, i))

        return result

    def get_signed_wrapped_rpms_paths(self, task_id, sigkey, srpm=False):
        result = []
        parent_task = self.koji_proxy.getTaskInfo(task_id, request=True)
        task_info_list = []
        task_info_list.extend(self.koji_proxy.getTaskChildren(task_id, request=True))

        # scan parent and child tasks for certain methods
        task_info = None
        for i in task_info_list:
            if i["method"] in ("wrapperRPM"):
                task_info = i
                break

        # Check parent_task if it's scratch build
        scratch = parent_task["request"][-1].get("scratch", False)
        if scratch:
            raise RuntimeError("Scratch builds cannot be signed!")

        # Get results of wrapperRPM task
        # {'buildroot_id': 2479520,
        #  'logs': ['checkout.log', 'root.log', 'state.log', 'build.log'],
        #  'rpms': ['foreman-discovery-image-2.1.0-2.el7sat.noarch.rpm'],
        #  'srpm': 'foreman-discovery-image-2.1.0-2.el7sat.src.rpm'}
        task_result = self.koji_proxy.getTaskResult(task_info["id"])

        # Get list of filenames that should be returned
        result_files = task_result["rpms"]
        if srpm:
            result_files += [task_result["srpm"]]

        # Prepare list with paths to the required files
        for i in result_files:
            rpminfo = self.koji_proxy.getRPM(i)
            build = self.koji_proxy.getBuild(rpminfo["build_id"])
            path = os.path.join(self.koji_module.pathinfo.build(build), self.koji_module.pathinfo.signed(rpminfo, sigkey))
            result.append(path)

        return result

    def get_build_nvrs(self, task_id):
        builds = self.koji_proxy.listBuilds(taskID=task_id)
        return [build.get("nvr") for build in builds if build.get("nvr")]
