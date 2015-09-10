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
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.



# TODO: remove all DNF hacks, possibly this whole file


from distutils.version import LooseVersion
import os
import shutil
import tempfile

import dnf
import dnf.arch
import dnf.conf
import dnf.repo
import dnf.sack

import pungi.arch


class Conf(dnf.conf.Conf):
    # This is only modified to get our custom Substitutions class in.
    def __init__(self, arch, *args, **kwargs):
        super(Conf, self).__init__(*args, **kwargs)
        self.substitutions = Substitutions(arch)


class Substitutions(dict):
    # DNF version of Substitutions detects host arch. We don't want that.
    def __init__(self, arch):
        super(Substitutions, self).__init__()
        self['arch'] = arch
        self['basearch'] = dnf.arch.basearch(arch)


class DnfWrapper(dnf.Base):
    def __init__(self, *args, **kwargs):
        super(DnfWrapper, self).__init__(*args, **kwargs)
        self.arch_wrapper = ArchWrapper(self.conf.substitutions["arch"])
        self.comps_wrapper = CompsWrapper(self)
        # use a custom cachedir, delete it after use
        self.conf.cachedir = tempfile.mkdtemp(prefix="pungi_dnf_")

    def __del__(self):
        if self.conf.cachedir.startswith("/tmp/"):
            shutil.rmtree(self.conf.cachedir)

    def add_repo(self, repoid, baseurl=None, mirrorlist=None, ignoregroups=False, lookaside=False):
        if "://" not in baseurl:
            baseurl = "file://%s" % os.path.abspath(baseurl)
        if LooseVersion(dnf.__version__) < LooseVersion("2.0.0"):
            repo = dnf.repo.Repo(repoid, self.conf.cachedir)
        else:
            repo = dnf.repo.Repo(repoid, self.conf)
        repo.baseurl = baseurl
        repo.mirrorlist = mirrorlist
        repo.ignoregroups = ignoregroups
        repo.enable()
        self.repos.add(repo)
        repo.priority = 10 if lookaside else 20


class CompsWrapper(object):
    def __init__(self, dnf_obj):
        self.dnf = dnf_obj

    def __getitem__(self, name):
        return self.groups[name]

    @property
    def comps(self):
        return self.dnf.comps

    @property
    def groups(self):
        result = {}
        for i in self.comps.groups:
            result[i.id] = i
        return result

    def get_packages_from_group(self, group_id, include_default=True, include_optional=True, include_conditional=True):
        packages = []
        conditional = []

        group = self.groups[group_id]

        # add mandatory packages
        packages.extend([i.name for i in group.mandatory_packages])

        # add default packages
        if include_default:
            packages.extend([i.name for i in group.default_packages])

        # add optional packages
        if include_optional:
            packages.extend([i.name for i in group.optional_packages])

        for package in group.conditional_packages:
            conditional.append({"name": package.requires, "install": package.name})

        return packages, conditional

    def get_comps_packages(self, groups, exclude_groups):
        packages = set()
        conditional = []

        if isinstance(groups, list):
            groups = dict([(i, 1) for i in groups])

        for group_id, group_include in sorted(groups.items()):
            if group_id in exclude_groups:
                continue

            include_default = group_include in (1, 2)
            include_optional = group_include in (2, )
            include_conditional = True
            pkgs, cond = self.get_packages_from_group(group_id, include_default, include_optional, include_conditional)
            packages.update(pkgs)
            for i in cond:
                if i not in conditional:
                    conditional.append(i)
        return list(packages), conditional

    def get_langpacks(self):
        result = []
        for name, install in self.comps._i.langpacks.items():
            result.append({"name": name, "install": install})
        return result


class ArchWrapper(object):
    def __init__(self, arch):
        self.base_arch = dnf.arch.basearch(arch)
        self.all_arches = pungi.arch.get_valid_arches(self.base_arch, multilib=True, add_noarch=True)
        self.native_arches = pungi.arch.get_valid_arches(self.base_arch, multilib=False, add_noarch=True)
        self.multilib_arches = pungi.arch.get_valid_multilib_arches(self.base_arch)
        self.source_arches = ["src", "nosrc"]
