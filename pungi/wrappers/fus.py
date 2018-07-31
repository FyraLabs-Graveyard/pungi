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
This is a wrapper for a hybrid depsolver that understands how module
dependencies work. It's Funny Solver, because it does funny things.

https://github.com/fedora-modularity/fus

The executable basically provides one iteration of the traditional DNF based
depsolver. It has to be run multiple times to explicitly add multilib packages,
or source packages to include build dependencies (which is not yet supported in
Pungi).
"""


def get_cmd(
    arch,
    repos,
    lookasides,
    packages,
    modules,
    platform=None,
    filter_packages=None,  # TODO not supported yet
):
    cmd = ["fus", "--verbose", "--arch", arch]

    for idx, repo in enumerate(repos):
        cmd.append("--repo=repo-%s,repo,%s" % (idx, repo))
    for idx, repo in enumerate(lookasides):
        cmd.append("--repo=lookaside-%s,lookaside,%s" % (idx, repo))

    if platform:
        cmd.append("--platform=%s" % platform)

    for module in modules:
        cmd.append("module(%s)" % module)

    cmd.extend(packages)

    return cmd


def parse_output(output):
    """Read output of fus from the given filepath, and return a set of tuples
    (NVR, arch, flags) and a set of module NSVCs.
    """
    packages = set()
    with open(output) as f:
        for line in f:
            if " " in line or "@" not in line:
                continue
            nevra, _ = line.strip().rsplit("@", 1)
            if not nevra.startswith("module:"):
                flags = set()
                name, arch = nevra.rsplit(".", 1)
                if name.startswith("*"):
                    flags.add("modular")
                    name = name[1:]
                packages.add((name, arch, frozenset(flags)))
    return packages
