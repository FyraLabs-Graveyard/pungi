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

from kobo.shortcuts import force_list

import pungi.phases.pkgset.pkgsets
from pungi.arch import get_valid_arches
from pungi.phases.base import PhaseBase
from pungi.util import is_arch_multilib


class PkgsetPhase(PhaseBase):
    """PKGSET"""
    name = "pkgset"

    config_options = (
        {
            "name": "pkgset_source",
            "expected_types": [str],
        },
    )

    def run(self):
        pkgset_source = "PkgsetSource%s" % self.compose.conf["pkgset_source"]
        from source import PkgsetSourceContainer
        import sources
        PkgsetSourceContainer.register_module(sources)
        container = PkgsetSourceContainer()
        SourceClass = container[pkgset_source]
        self.package_sets, self.path_prefix = SourceClass(self.compose)()
