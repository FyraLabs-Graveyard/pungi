#!/usr/bin/env python2
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
import libcomps
from contextlib import contextmanager

#import pungi.phases.pkgsets.pkgsets
from rpmfluff import SimpleRpmBuild

# helpers for creating RPMs to test with
@contextmanager
def in_tempdir(outdir, prefix='_'):
    """
    py:class:: in_tempdir(prefix='_')

    Context manager for the rpmbuild tempdir
    """
    oldcwd = os.getcwd()
    tmpdir = tempfile.mkdtemp(prefix=prefix)
    os.chdir(tmpdir)
    yield
    os.chdir(oldcwd)
    shutil.rmtree(tmpdir)

@contextmanager
def in_dir(directory):
    """
    py:class:: in_dir(dir)

    Context manager to handle things in a generic method
    """
    oldcwd = os.getcwd()
    tmpdir = tempfile.mkdtemp()
    os.chdir(tmpdir)
    yield
    os.chdir(oldcwd)

def make_rpm(outdir, archlist, name, version='1.0', release='1'):
    """
    py:function:: make_rpm(outdir, name='test', version='1.0', release='1', archlist=None)

    Create the fake test rpms
    """

    if (archlist is None):
        raise TypeError( "No defined architectures for make_rpm")

    abs_outdir = os.path.abspath(outdir)

    if not os.path.isdir(abs_outdir):
        os.mkdir(abs_outdir)

    p = SimpleRpmBuild(name, version, release, archlist)
    with in_tempdir(abs_outdir, prefix="tmppkgs"):
        p.make()

        srpm_outdir = os.path.join(
            abs_outdir,
            "repo",
            "src",
        )

        if not os.path.isdir(srpm_outdir):
            os.makedirs(srpm_outdir)

        srpmfile = p.get_built_srpm()
        src_outfile = os.path.join(
            os.path.abspath(abs_outdir),
            "repo",
            'src',
            os.path.basename(srpmfile)
        )
        shutil.move(srpmfile, src_outfile)

        for arch in archlist:

            arch_outdir = os.path.join(
                abs_outdir,
                "repo",
                arch,
            )
            if not os.path.isdir(arch_outdir):
                os.makedirs(arch_outdir)


            rpmfile = p.get_built_rpm(arch)
            bin_outfile = os.path.join(
                os.path.abspath(abs_outdir),
                "repo",
                arch,
                os.path.basename(rpmfile)
            )
            shutil.move(rpmfile, bin_outfile)
    return p

def get_rpm_list_from_comps(compspath):
    """
    py:function:: get_rpm_list_from_comps(compspath)

    Return a list of rpms from a compsfile
    """

    pkg_list = []

    comps = libcomps.Comps()
    comps.fromxml_f(compspath)

    for group in comps.groups:
        for pkg in comps.groups[group.id].packages:
            pkg_list.append(pkg.name)

    return pkg_list


if __name__ == "__main__":
    import click
    import json

    @click.command()
    @click.option('--pkgfile', default=None, required=True,
                  help="Path to json pkg file")
    @click.option('--outdir', default=None, required=True,
                  help="Directory to create temp dummy repo")
    def createtestdata(pkgfile, outdir):
        pkgdata = json.loads(open(pkgfile,'r').read())
        for pkg in pkgdata['archpkgs']:
            make_rpm(outdir, pkgdata['archs'], pkg)
        for pkg in pkgdata['noarchpkgs']:
            make_rpm(outdir, ['noarch'], pkg)

        os.popen('/usr/bin/createrepo %s' % os.path.join(outdir, "repo"))

    createtestdata()
