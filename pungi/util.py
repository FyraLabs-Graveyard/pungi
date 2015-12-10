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


import subprocess
import os
import shutil
import sys
import hashlib
import errno
import pipes
import re
import urlparse

from kobo.shortcuts import run
from productmd.common import get_major_version


def _doRunCommand(command, logger, rundir='/tmp', output=subprocess.PIPE, error=subprocess.PIPE, env=None):
    """Run a command and log the output.  Error out if we get something on stderr"""


    logger.info("Running %s" % subprocess.list2cmdline(command))

    p1 = subprocess.Popen(command, cwd=rundir, stdout=output, stderr=error, universal_newlines=True, env=env,
                          close_fds=True)
    (out, err) = p1.communicate()

    if out:
        logger.debug(out)

    if p1.returncode != 0:
        logger.error("Got an error from %s" % command[0])
        logger.error(err)
        raise OSError, "Got an error (%d) from %s: %s" % (p1.returncode, command[0], err)

def _link(local, target, logger, force=False):
    """Simple function to link or copy a package, removing target optionally."""

    if os.path.exists(target) and force:
        os.remove(target)

    #check for broken links
    if force and os.path.islink(target):
        if not os.path.exists(os.readlink(target)):
            os.remove(target)

    try:
        os.link(local, target)
    except OSError, e:
        if e.errno != 18: # EXDEV
            logger.error('Got an error linking from cache: %s' % e)
            raise OSError, e

        # Can't hardlink cross file systems
        shutil.copy2(local, target)

def _ensuredir(target, logger, force=False, clean=False):
    """Ensure that a directory exists, if it already exists, only continue
    if force is set."""

    # We have to check existance of a logger, as setting the logger could
    # itself cause an issue.
    def whoops(func, path, exc_info):
        message = 'Could not remove %s' % path
        if logger:
            logger.error(message)
        else:
            sys.stderr(message)
        sys.exit(1)

    if os.path.exists(target) and not os.path.isdir(target):
        message = '%s exists but is not a directory.' % target
        if logger:
            logger.error(message)
        else:
            sys.stderr(message)
        sys.exit(1)

    if not os.path.isdir(target):
        os.makedirs(target)
    elif force and clean:
        shutil.rmtree(target, onerror=whoops)
        os.makedirs(target)
    elif force:
        return
    else:
        message = 'Directory %s already exists.  Use --force to overwrite.' % target
        if logger:
            logger.error(message)
        else:
            sys.stderr(message)
        sys.exit(1)

def _doCheckSum(path, hash, logger):
    """Generate a checksum hash from a provided path.
    Return a string of type:hash"""

    # Try to figure out what hash we want to do
    try:
        sum = hashlib.new(hash)
    except ValueError:
        logger.error("Invalid hash type: %s" % hash)
        return False

    # Try to open the file, using binary flag.
    try:
        myfile = open(path, 'rb')
    except IOError, e:
        logger.error("Could not open file %s: %s" % (path, e))
        return False

    # Loop through the file reading chunks at a time as to not
    # put the entire file in memory.  That would suck for DVDs
    while True:
        chunk = myfile.read(8192) # magic number!  Taking suggestions for better blocksize
        if not chunk:
            break # we're done with the file
        sum.update(chunk)
    myfile.close()

    return '%s:%s' % (hash, sum.hexdigest())


def makedirs(path, mode=0o775):
    mask = os.umask(0)
    try:
        os.makedirs(path, mode=mode)
    except OSError as ex:
        if ex.errno != errno.EEXIST:
            raise
    os.umask(mask)


def rmtree(path, ignore_errors=False, onerror=None):
    """shutil.rmtree ENOENT (ignoring no such file or directory) errors"""
    try:
        shutil.rmtree(path, ignore_errors, onerror)
    except OSError as ex:
        if ex.errno != errno.ENOENT:
            raise


def explode_rpm_package(pkg_path, target_dir):
    """Explode a rpm package into target_dir."""
    pkg_path = os.path.abspath(pkg_path)
    makedirs(target_dir)
    run("rpm2cpio %s | cpio -iuvmd && chmod -R a+rX ." % pipes.quote(pkg_path), workdir=target_dir)


def pkg_is_rpm(pkg_obj):
    if pkg_is_srpm(pkg_obj):
        return False
    if pkg_is_debug(pkg_obj):
        return False
    return True


def pkg_is_srpm(pkg_obj):
    if isinstance(pkg_obj, str):
        # string, probably N.A, N-V-R.A, N-V-R.A.rpm
        for i in (".src", ".nosrc", ".src.rpm", ".nosrc.rpm"):
            if pkg_obj.endswith(i):
                return True
    else:
        # package object
        if pkg_obj.arch in ("src", "nosrc"):
            return True
    return False


def pkg_is_debug(pkg_obj):
    if pkg_is_srpm(pkg_obj):
        return False
    if isinstance(pkg_obj, str):
        # string
        if "-debuginfo" in pkg_obj:
            return True
    else:
        # package object
        if "-debuginfo" in pkg_obj.name:
            return True
    return False


# fomat: [(variant_uid_regex, {arch|*: [data]})]
def get_arch_variant_data(conf, var_name, arch, variant):
    result = []
    for conf_variant, conf_data in conf.get(var_name, []):
        if variant is not None and not re.match(conf_variant, variant.uid):
            continue
        for conf_arch in conf_data:
            if conf_arch != "*" and conf_arch != arch:
                continue
            if conf_arch == "*" and arch == "src":
                # src is excluded from '*' and needs to be explicitly added to the mapping
                continue
            if isinstance(conf_data[conf_arch], list):
                result.extend(conf_data[conf_arch])
            else:
                result.append(conf_data[conf_arch])
    return result


def resolve_git_url(url):
    """Given a url to a Git repo specifying HEAD as a ref, replace that
    specifier with actual SHA1 of the commit.

    Otherwise, the original URL will be returned.

    Raises RuntimeError if there was an error. Most likely cause is failure to
    run git command.
    """
    r = urlparse.urlsplit(url)
    if r.fragment != 'HEAD':
        return url

    baseurl = urlparse.urlunsplit((r.scheme, r.netloc, r.path, '', ''))
    _, output = run(['git', 'ls-remote', baseurl, r.fragment])

    lines = [line for line in output.split('\n') if line]
    if len(lines) != 1:
        # This should never happen. HEAD can not match multiple commits in a
        # single repo, and there can not be a repo without a HEAD.
        raise RuntimeError('Failed to resolve %s', url)

    fragment = lines[0].split()[0]
    return urlparse.urlunsplit((r.scheme, r.netloc, r.path, r.query, fragment))


# fomat: {arch|*: [data]}
def get_arch_data(conf, var_name, arch):
    result = []
    for conf_arch, conf_data in conf.get(var_name, {}).items():
        if conf_arch != "*" and conf_arch != arch:
            continue
        if conf_arch == "*" and arch == "src":
            # src is excluded from '*' and needs to be explicitly added to the mapping
            continue
        if isinstance(conf_data, list):
            result.extend(conf_data)
        else:
            result.append(conf_data)
    return result


def get_buildroot_rpms(compose, task_id):
    """Get build root RPMs - either from runroot or local"""
    result = []
    if task_id:
        # runroot
        import koji
        koji_url = compose.conf["pkgset_koji_url"]
        koji_proxy = koji.ClientSession(koji_url)
        buildroot_infos = koji_proxy.listBuildroots(taskID=task_id)
        buildroot_info = buildroot_infos[-1]
        data = koji_proxy.listRPMs(componentBuildrootID=buildroot_info["id"])
        for rpm_info in data:
            fmt = "%(nvr)s.%(arch)s"
            result.append(fmt % rpm_info)
    else:
        # local
        retcode, output = run("rpm -qa --qf='%{name}-%{version}-%{release}.%{arch}\n'")
        for i in output.splitlines():
            if not i:
                continue
            result.append(i)
    result.sort()
    return result


def _apply_substitutions(compose, volid):
    for k, v in compose.conf.get('volume_id_substitutions', {}).iteritems():
        volid = volid.replace(k, v)
    return volid


def get_volid(compose, arch, variant=None, escape_spaces=False, disc_type=False):
    """Get ISO volume ID for arch and variant"""
    if variant and variant.type == "addon":
        # addons are part of parent variant media
        return None

    if variant and variant.type == "layered-product":
        release_short = variant.release_short
        release_version = variant.release_version
        release_is_layered = True
        base_product_short = compose.conf["release_short"]
        base_product_version = get_major_version(compose.conf["release_version"])
        variant_uid = variant.parent.uid
    else:
        release_short = compose.conf["release_short"]
        release_version = compose.conf["release_version"]
        release_is_layered = compose.conf["release_is_layered"]
        base_product_short = compose.conf.get("base_product_short", "")
        base_product_version = compose.conf.get("base_product_version", "")
        variant_uid = variant and variant.uid or None

    products = [
        "%(release_short)s-%(version)s %(variant)s.%(arch)s",
        "%(release_short)s-%(version)s %(arch)s",
    ]
    products = compose.conf.get('image_volid_formats', products)
    layered_products = [
        "%(release_short)s-%(version)s %(base_product_short)s-%(base_product_version)s %(variant)s.%(arch)s",
        "%(release_short)s-%(version)s %(base_product_short)s-%(base_product_version)s %(arch)s",
    ]
    layered_products = compose.conf.get('image_volid_layered_product_formats', layered_products)

    volid = None
    if release_is_layered:
        all_products = layered_products + products
    else:
        all_products = products

    for i in all_products:
        if not variant_uid and "%(variant)s" in i:
            continue
        volid = i % {
            'compose_id': compose.compose_id,
            'variant': variant_uid,
            'arch': arch,
            'disc_type': disc_type or '',
            'release_short': release_short,
            'version': release_version,
            'base_product_short': base_product_short,
            'base_product_version': base_product_version,
        }
        volid = _apply_substitutions(compose, volid)
        if len(volid) <= 32:
            break

    # from wrappers.iso import IsoWrapper
    # iso = IsoWrapper(logger=compose._logger)
    # volid = iso._truncate_volid(volid)

    if len(volid) > 32:
        raise ValueError("Could not create volume ID <= 32 characters")

    if escape_spaces:
        volid = volid.replace(" ", r"\x20")
    return volid
