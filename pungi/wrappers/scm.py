from __future__ import absolute_import
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
import tempfile
import shutil
import pipes
import glob
import time
import contextlib

import kobo.log
from kobo.shortcuts import run, force_list
from pungi.util import explode_rpm_package, makedirs


class ScmBase(kobo.log.LoggingBase):
    def __init__(self, logger=None):
        kobo.log.LoggingBase.__init__(self, logger=logger)

    @contextlib.contextmanager
    def _temp_dir(self, tmp_dir=None):
        if tmp_dir is not None:
            makedirs(tmp_dir)
        path = tempfile.mkdtemp(prefix="cvswrapper_", dir=tmp_dir)

        yield path

        self.log_debug("Removing %s" % path)
        try:
            shutil.rmtree(path)
        except OSError as ex:
            self.log_warning("Error removing %s: %s" % (path, ex))

    def export_file(self, scm_root, scm_file, target_dir, scm_branch=None, tmp_dir=None, log_file=None):
        raise NotImplemented

    def retry_run(self, cmd, retries=5, timeout=60, **kwargs):
        """
        @param cmd - cmd passed to kobo.shortcuts.run()
        @param retries=5 - attempt to execute n times
        @param timeout=60 - seconds before next try
        @param **kwargs - args passed to kobo.shortcuts.run()
        """

        for n in range(1, retries + 1):
            try:
                self.log_debug("Retrying execution %s/%s of '%s'" % (n, retries, cmd))
                return run(cmd, **kwargs)
            except RuntimeError as ex:
                if n == retries:
                    raise ex
                self.log_debug("Waiting %s seconds to retry execution of '%s'" % (timeout, cmd))
                time.sleep(timeout)

        raise RuntimeError("Something went wrong during execution of '%s'" % cmd)


class FileWrapper(ScmBase):
    def export_dir(self, scm_root, scm_dir, target_dir, scm_branch=None, tmp_dir=None, log_file=None):
        if scm_root:
            raise ValueError("FileWrapper: 'scm_root' should be empty.")
        dirs = glob.glob(scm_dir)
        for i in dirs:
            _copy_all(i, target_dir)

    def export_file(self, scm_root, scm_file, target_dir, scm_branch=None, tmp_dir=None, log_file=None):
        if scm_root:
            raise ValueError("FileWrapper: 'scm_root' should be empty.")
        files = glob.glob(scm_file)
        for i in files:
            target_path = os.path.join(target_dir, os.path.basename(i))
            shutil.copy2(i, target_path)


class CvsWrapper(ScmBase):
    def export_dir(self, scm_root, scm_dir, target_dir, scm_branch=None, tmp_dir=None, log_file=None):
        scm_dir = scm_dir.lstrip("/")
        scm_branch = scm_branch or "HEAD"
        with self._temp_dir(tmp_dir=tmp_dir) as tmp_dir:
            self.log_debug("Exporting directory %s from CVS %s (branch %s)..."
                           % (scm_dir, scm_root, scm_branch))
            self.retry_run(["/usr/bin/cvs", "-q", "-d", scm_root, "export", "-r", scm_branch, scm_dir],
                           workdir=tmp_dir, show_cmd=True, logfile=log_file)
            _copy_all(os.path.join(tmp_dir, scm_dir), target_dir)

    def export_file(self, scm_root, scm_file, target_dir, scm_branch=None, tmp_dir=None, log_file=None):
        scm_file = scm_file.lstrip("/")
        scm_branch = scm_branch or "HEAD"
        with self._temp_dir(tmp_dir=tmp_dir) as tmp_dir:
            target_path = os.path.join(target_dir, os.path.basename(scm_file))
            self.log_debug("Exporting file %s from CVS %s (branch %s)..." % (scm_file, scm_root, scm_branch))
            self.retry_run(["/usr/bin/cvs", "-q", "-d", scm_root, "export", "-r", scm_branch, scm_file],
                           workdir=tmp_dir, show_cmd=True, logfile=log_file)

            makedirs(target_dir)
            shutil.copy2(os.path.join(tmp_dir, scm_file), target_path)


class GitWrapper(ScmBase):
    def export_dir(self, scm_root, scm_dir, target_dir, scm_branch=None, tmp_dir=None, log_file=None):
        scm_dir = scm_dir.lstrip("/")
        scm_branch = scm_branch or "master"

        with self._temp_dir(tmp_dir=tmp_dir) as tmp_dir:
            if "://" not in scm_root:
                scm_root = "file://%s" % scm_root

            self.log_debug("Exporting directory %s from git %s (branch %s)..."
                           % (scm_dir, scm_root, scm_branch))
            cmd = ("/usr/bin/git archive --remote=%s %s %s | tar xf -"
                   % (pipes.quote(scm_root), pipes.quote(scm_branch), pipes.quote(scm_dir)))
            # git archive is not supported by http/https
            # or by smart http https://git-scm.com/book/en/v2/Git-on-the-Server-Smart-HTTP
            if scm_root.startswith("http"):
                cmd = ("/usr/bin/git clone --depth 1 --branch=%s %s %s"
                       % (pipes.quote(scm_branch), pipes.quote(scm_root), pipes.quote(tmp_dir)))
            self.retry_run(cmd, workdir=tmp_dir, show_cmd=True, logfile=log_file)

            _copy_all(os.path.join(tmp_dir, scm_dir), target_dir)

    def export_file(self, scm_root, scm_file, target_dir, scm_branch=None, tmp_dir=None, log_file=None):
        scm_file = scm_file.lstrip("/")
        scm_branch = scm_branch or "master"

        with self._temp_dir(tmp_dir=tmp_dir) as tmp_dir:
            target_path = os.path.join(target_dir, os.path.basename(scm_file))

            if "://" not in scm_root:
                scm_root = "file://%s" % scm_root

            self.log_debug("Exporting file %s from git %s (branch %s)..."
                           % (scm_file, scm_root, scm_branch))
            cmd = ("/usr/bin/git archive --remote=%s %s %s | tar xf -"
                   % (pipes.quote(scm_root), pipes.quote(scm_branch), pipes.quote(scm_file)))
            # git archive is not supported by http/https
            # or by smart http https://git-scm.com/book/en/v2/Git-on-the-Server-Smart-HTTP
            if scm_root.startswith("http"):
                cmd = ("/usr/bin/git clone --depth 1 --branch=%s %s %s"
                       % (pipes.quote(scm_branch), pipes.quote(scm_root), pipes.quote(tmp_dir)))
            self.retry_run(cmd, workdir=tmp_dir, show_cmd=True, logfile=log_file)

            makedirs(target_dir)
            shutil.copy2(os.path.join(tmp_dir, scm_file), target_path)


class RpmScmWrapper(ScmBase):
    def _list_rpms(self, pats):
        for pat in force_list(pats):
            for rpm in glob.glob(pat):
                yield rpm

    def export_dir(self, scm_root, scm_dir, target_dir, scm_branch=None, tmp_dir=None, log_file=None):
        for rpm in self._list_rpms(scm_root):
            scm_dir = scm_dir.lstrip("/")
            with self._temp_dir(tmp_dir=tmp_dir) as tmp_dir:
                self.log_debug("Extracting directory %s from RPM package %s..." % (scm_dir, rpm))
                explode_rpm_package(rpm, tmp_dir)

                makedirs(target_dir)
                # "dir" includes the whole directory while "dir/" includes it's content
                if scm_dir.endswith("/"):
                    _copy_all(os.path.join(tmp_dir, scm_dir), target_dir)
                else:
                    run("cp -a %s %s/" % (pipes.quote(os.path.join(tmp_dir, scm_dir)),
                                          pipes.quote(target_dir)))

    def export_file(self, scm_root, scm_file, target_dir, scm_branch=None, tmp_dir=None, log_file=None):
        for rpm in self._list_rpms(scm_root):
            scm_file = scm_file.lstrip("/")
            with self._temp_dir(tmp_dir=tmp_dir) as tmp_dir:
                self.log_debug("Exporting file %s from RPM file %s..." % (scm_file, rpm))
                explode_rpm_package(rpm, tmp_dir)

                makedirs(target_dir)
                for src in glob.glob(os.path.join(tmp_dir, scm_file)):
                    dst = os.path.join(target_dir, os.path.basename(src))
                    shutil.copy2(src, dst)


def _get_wrapper(scm_type, *args, **kwargs):
    SCM_WRAPPERS = {
        "file": FileWrapper,
        "cvs": CvsWrapper,
        "git": GitWrapper,
        "rpm": RpmScmWrapper,
    }
    try:
        return SCM_WRAPPERS[scm_type](*args, **kwargs)
    except KeyError:
        raise ValueError("Unknown SCM type: %s" % scm_type)


def get_file_from_scm(scm_dict, target_path, logger=None):
    if isinstance(scm_dict, str):
        scm_type = "file"
        scm_repo = None
        scm_file = os.path.abspath(scm_dict)
        scm_branch = None
    else:
        scm_type = scm_dict["scm"]
        scm_repo = scm_dict["repo"]
        scm_file = scm_dict["file"]
        scm_branch = scm_dict.get("branch", None)

    scm = _get_wrapper(scm_type, logger=logger)

    for i in force_list(scm_file):
        tmp_dir = tempfile.mkdtemp(prefix="scm_checkout_")
        scm.export_file(scm_repo, i, scm_branch=scm_branch, target_dir=tmp_dir)
        _copy_all(tmp_dir, target_path)
        shutil.rmtree(tmp_dir)


def get_dir_from_scm(scm_dict, target_path, logger=None):
    if isinstance(scm_dict, str):
        scm_type = "file"
        scm_repo = None
        scm_dir = os.path.abspath(scm_dict)
        scm_branch = None
    else:
        scm_type = scm_dict["scm"]
        scm_repo = scm_dict.get("repo", None)
        scm_dir = scm_dict["dir"]
        scm_branch = scm_dict.get("branch", None)

    scm = _get_wrapper(scm_type, logger=logger)

    tmp_dir = tempfile.mkdtemp(prefix="scm_checkout_")
    scm.export_dir(scm_repo, scm_dir, scm_branch=scm_branch, target_dir=tmp_dir)
    _copy_all(tmp_dir, target_path)
    shutil.rmtree(tmp_dir)


def _copy_all(src, dest):
    """This function is equivalent to running `cp src/* dest`."""
    contents = os.listdir(src)
    if not contents:
        raise RuntimeError('Source directory %s is empty.' % src)
    makedirs(dest)
    for item in contents:
        source = os.path.join(src, item)
        destination = os.path.join(dest, item)
        if os.path.isdir(source):
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
