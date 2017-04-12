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


"""
Get a package list based on comps.xml.

Input format:
see comps.dtd

Output:
set([(rpm_name, rpm_arch or None)])
"""


from pungi.wrappers.comps import CompsWrapper
import pungi.phases.gather.source


class GatherSourceComps(pungi.phases.gather.source.GatherSourceBase):
    enabled = True

    def __call__(self, arch, variant):
        groups = set()
        comps = CompsWrapper(self.compose.paths.work.comps(arch=arch))

        if variant is not None and (variant.groups or variant.type != 'variant'):
            # Get packages for a particular variant. We want to skip the
            # filtering if the variant is top-level and has no groups (to use
            # all of them).
            # For optional we always want to filter (and parent groups will be
            # added later), for addons and layered products it makes no sense
            # for the groups to be empty in the first place.
            comps.filter_groups(variant.groups)

        for i in comps.get_comps_groups():
            groups.add(i)
        return set(), groups
