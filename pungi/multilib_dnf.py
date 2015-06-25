#!/usr/bin/python
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


import re
import fnmatch


DEVEL_BLACKLIST = [
    "dmraid-devel",
    "ghc-*",
    "java-*-gcj-devel",
    "java-*-icedtea-devel",
    "java-*-openjdk-devel",
    "kdeutils-devel",
    "kernel-devel",
    "mkinitrd-devel",
    "php-devel",
]


DEVEL_WHITELIST = [
    "glibc-static",
    "libstdc++-static",
]


RUNTIME_BLACKLIST = [
    "gcc",
    "kernel",
    "tomcat-native",
]


RUNTIME_WHITELIST = [
    "glibc-static",
    "libflashsupport",
    "libgnat",
    "lmms-vst",
    "nspluginwrapper",
    "perl-libs",
    "redhat-lsb",
    "valgrind",
    "wine",
    "wine-arts",
    "yaboot",
]


class Multilib(object):
    def __init__(self, sack, methods, blacklist=None, whitelist=None):
        self.sack = sack
        self.methods = []
        self.blacklist = blacklist or []
        self.whitelist = whitelist or []
        self.use_default_blacklists = True  # use *_BLACKLIST and *_WHITELIST lists

        for i in methods:
            name = "method_%s" % i
            func = getattr(self, name)
            self.methods.append(func)

    def _match_one(self, pkg, pattern):
        return fnmatch.fnmatch(pkg.name, pattern)

    def _match_any(self, pkg, pattern_list):
        for i in pattern_list:
            if self._match_one(pkg, i):
                return True
        return False

    def method_none(self, pkg):
        return False

    def method_all(self, pkg):
        return True

    def method_devel(self, pkg):
        if self.use_default_blacklists:
            if self._match_any(pkg, DEVEL_BLACKLIST):
                return False
            if self._match_any(pkg, DEVEL_WHITELIST):
                return True
        if pkg.name.endswith("-devel"):
            return True
        if pkg.name.endswith("-static"):
            return True
        for prov in pkg.provides:
            # TODO: split reldep to name/flag/value
            prov = str(prov).split(" ")[0]
            if "-devel" in prov:
                return True
            if "-static" in prov:
                return True
        return False

    def method_runtime(self, pkg):
        if self.use_default_blacklists:
            if self._match_any(pkg, RUNTIME_BLACKLIST):
                return False
            if self._match_any(pkg, RUNTIME_WHITELIST):
                return True
        so = re.compile(r"^.*\.so\.\d+.*$")
        for prov in pkg.provides:
            prov = str(prov)
            if so.match(prov):
                return True
        return False

    def is_multilib(self, pkg):
        if self._match_any(pkg, self.blacklist):
            return False
        if self._match_any(pkg, self.whitelist):
            return True
        for i in self.methods:
            if i(pkg):
                return True
        return False
