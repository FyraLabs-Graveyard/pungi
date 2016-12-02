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


import argparse

from .tree import Tree


def main(args=None):
    parser = argparse.ArgumentParser()
    subparser = parser.add_subparsers(help="Sub commands")

    treep = subparser.add_parser("tree", help="Compose OSTree repository")
    treep.set_defaults(_class=Tree, func='run')
    treep.add_argument('--repo', metavar='PATH', required=True,
                       help='where to put the OSTree repo (required)')
    treep.add_argument('--treefile', metavar="FILE", required=True,
                       help='treefile for rpm-ostree (required)')
    treep.add_argument('--log-dir', metavar="DIR",
                       help='where to log output')
    treep.add_argument('--extra-config', metavar="FILE",
                       help='JSON file contains extra configurations')
    treep.add_argument('--version', metavar="VERSION",
                       help='version string to be added as versioning metadata')
    treep.add_argument('--update-summary', action='store_true',
                       help='update summary metadata')

    args = parser.parse_args(args)
    _class = args._class()
    _class.set_args(args)
    func = getattr(_class, args.func)
    func()
