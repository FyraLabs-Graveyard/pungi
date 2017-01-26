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

from kobo.shortcuts import force_list


def get_repoclosure_cmd(arch=None, builddeps=False,
                        repos=None, lookaside=None):

    cmd = ["/usr/bin/repoclosure"]
    # There are options that are not exposed here, because we don't need
    # them. These are:
    # --config
    # --basearch
    # --tempcache
    # --quiet
    # --newest
    # --pkg
    # --group

    for i in force_list(arch or []):
        cmd.append("--arch=%s" % i)

    if builddeps:
        cmd.append("--builddeps")

    repos = repos or {}
    for repo_id, repo_path in repos.iteritems():
        cmd.append("--repofrompath=%s,%s" % (repo_id, _to_url(repo_path)))
        cmd.append("--repoid=%s" % repo_id)

    lookaside = lookaside or {}
    for repo_id, repo_path in lookaside.iteritems():
        cmd.append("--repofrompath=%s,%s" % (repo_id, _to_url(repo_path)))
        cmd.append("--lookaside=%s" % repo_id)

    return cmd


def _to_url(path):
    if "://" not in path:
        return "file://%s" % os.path.abspath(path)
    return path
