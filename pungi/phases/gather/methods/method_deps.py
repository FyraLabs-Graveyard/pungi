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
# along with this program; if not, see <https://gnu.org/licenses/>.


import os

from kobo.shortcuts import run
from kobo.pkgset import SimpleRpmWrapper, RpmWrapper

from pungi.util import rmtree, get_arch_variant_data
from pungi.wrappers.pungi import PungiWrapper

from pungi.arch import tree_arch_to_yum_arch
import pungi.phases.gather

import pungi.phases.gather.method


class GatherMethodDeps(pungi.phases.gather.method.GatherMethodBase):
    enabled = True

    def __call__(self, arch, variant, packages, groups, filter_packages, multilib_whitelist, multilib_blacklist, package_sets, path_prefix=None, fulltree_excludes=None, prepopulate=None):
        # result = {
        #     "rpm": [],
        #     "srpm": [],
        #     "debuginfo": [],
        # }

        write_pungi_config(self.compose, arch, variant, packages, groups, filter_packages,
                           multilib_whitelist, multilib_blacklist,
                           fulltree_excludes=fulltree_excludes, prepopulate=prepopulate)
        result = resolve_deps(self.compose, arch, variant)
        check_deps(self.compose, arch, variant)
        return result


def _format_packages(pkgs):
    """Sort packages and merge name with arch."""
    for pkg, pkg_arch in sorted(pkgs):
        if type(pkg) in [SimpleRpmWrapper, RpmWrapper]:
            pkg_name = pkg.name
        else:
            pkg_name = pkg
        if pkg_arch:
            yield '%s.%s' % (pkg_name, pkg_arch)
        else:
            yield pkg_name


def write_pungi_config(compose, arch, variant, packages, groups, filter_packages,
                       multilib_whitelist, multilib_blacklist, fulltree_excludes=None,
                       prepopulate=None):
    """write pungi config (kickstart) for arch/variant"""
    pungi_wrapper = PungiWrapper()
    pungi_cfg = compose.paths.work.pungi_conf(variant=variant, arch=arch)
    msg = "Writing pungi config (arch: %s, variant: %s): %s" % (arch, variant, pungi_cfg)

    if compose.DEBUG and os.path.isfile(pungi_cfg):
        compose.log_warning("[SKIP ] %s" % msg)
        return

    compose.log_info(msg)

    repos = {"pungi-repo": compose.paths.work.arch_repo(arch=arch)}

    lookaside_repos = {}
    for i, repo_url in enumerate(pungi.phases.gather.get_lookaside_repos(compose, arch, variant)):
        lookaside_repos["lookaside-repo-%s" % i] = repo_url

    packages_str = list(_format_packages(packages))
    filter_packages_str = list(_format_packages(filter_packages))

    if not groups and not packages_str and not prepopulate:
        raise RuntimeError(
            'No packages included in %s.%s (no comps groups, no input packages, no prepopulate)'
            % (variant.uid, arch))

    pungi_wrapper.write_kickstart(
        ks_path=pungi_cfg, repos=repos, groups=groups, packages=packages_str,
        exclude_packages=filter_packages_str,
        lookaside_repos=lookaside_repos, fulltree_excludes=fulltree_excludes,
        multilib_whitelist=multilib_whitelist, multilib_blacklist=multilib_blacklist,
        prepopulate=prepopulate)


def resolve_deps(compose, arch, variant):
    pungi_wrapper = PungiWrapper()
    pungi_log = compose.paths.work.pungi_log(arch, variant)

    msg = "Running pungi (arch: %s, variant: %s)" % (arch, variant)
    if compose.DEBUG and os.path.exists(pungi_log):
        compose.log_warning("[SKIP ] %s" % msg)
        with open(pungi_log, "r") as f:
            return pungi_wrapper.get_packages(f)

    compose.log_info("[BEGIN] %s" % msg)
    pungi_conf = compose.paths.work.pungi_conf(arch, variant)

    multilib_methods = get_arch_variant_data(compose.conf, 'multilib', arch, variant)

    greedy_method = compose.conf["greedy_method"]

    # variant
    fulltree = compose.conf["gather_fulltree"]
    selfhosting = compose.conf["gather_selfhosting"]

    # optional
    if variant.type == "optional":
        fulltree = True
        selfhosting = True

    # addon
    if variant.type in ["addon", "layered-product"]:
        # packages having SRPM in parent variant are excluded from fulltree (via %fulltree-excludes)
        fulltree = True
        selfhosting = False

    lookaside_repos = {}
    for i, repo_url in enumerate(pungi.phases.gather.get_lookaside_repos(compose, arch, variant)):
        lookaside_repos["lookaside-repo-%s" % i] = repo_url

    yum_arch = tree_arch_to_yum_arch(arch)
    tmp_dir = compose.paths.work.tmp_dir(arch, variant)
    cache_dir = compose.paths.work.pungi_cache_dir(arch, variant)
    # TODO: remove YUM code, fully migrate to DNF
    backends = {
        'yum': pungi_wrapper.get_pungi_cmd,
        'dnf': pungi_wrapper.get_pungi_cmd_dnf,
    }
    get_cmd = backends[compose.conf['gather_backend']]
    cmd = get_cmd(pungi_conf, destdir=tmp_dir, name=variant.uid,
                  selfhosting=selfhosting, fulltree=fulltree, arch=yum_arch,
                  full_archlist=True, greedy=greedy_method, cache_dir=cache_dir,
                  lookaside_repos=lookaside_repos, multilib_methods=multilib_methods)
    # Use temp working directory directory as workaround for
    # https://bugzilla.redhat.com/show_bug.cgi?id=795137
    tmp_dir = compose.mkdtemp(prefix="pungi_")
    try:
        run(cmd, logfile=pungi_log, show_cmd=True, workdir=tmp_dir, env=os.environ)
    finally:
        rmtree(tmp_dir)

    with open(pungi_log, "r") as f:
        result = pungi_wrapper.get_packages(f)

    compose.log_info("[DONE ] %s" % msg)
    return result


def check_deps(compose, arch, variant):
    if not compose.conf["check_deps"]:
        return

    pungi_wrapper = PungiWrapper()
    pungi_log = compose.paths.work.pungi_log(arch, variant)
    with open(pungi_log, "r") as f:
        missing_deps = pungi_wrapper.get_missing_deps(f)
    if missing_deps:
        for pkg in sorted(missing_deps):
            compose.log_error("Unresolved dependencies in package %s: %s" % (pkg, sorted(missing_deps[pkg])))
        raise RuntimeError("Unresolved dependencies detected")
