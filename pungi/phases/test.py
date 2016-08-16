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


import tempfile
import os

from kobo.shortcuts import run

from pungi.wrappers.repoclosure import RepoclosureWrapper
from pungi.arch import get_valid_arches
from pungi.phases.base import PhaseBase
from pungi.phases.gather import get_lookaside_repos
from pungi.util import rmtree, is_arch_multilib, failable


class TestPhase(PhaseBase):
    name = "test"

    def run(self):
        run_repoclosure(self.compose)
        check_image_sanity(self.compose)


def run_repoclosure(compose):
    repoclosure = RepoclosureWrapper()

    # TODO: Special handling for src packages (use repoclosure param builddeps)

    msg = "Running repoclosure"
    compose.log_info("[BEGIN] %s" % msg)

    # Variant repos
    all_repos = {}  # to be used as lookaside for the self-hosting check
    all_arches = set()
    for arch in compose.get_arches():
        is_multilib = is_arch_multilib(compose.conf, arch)
        arches = get_valid_arches(arch, is_multilib)
        all_arches.update(arches)
        for variant in compose.get_variants(arch=arch):
            if variant.is_empty:
                continue
            lookaside = {}
            if variant.parent:
                repo_id = "repoclosure-%s.%s" % (variant.parent.uid, arch)
                repo_dir = compose.paths.compose.repository(arch=arch, variant=variant.parent)
                lookaside[repo_id] = repo_dir

            repos = {}
            repo_id = "repoclosure-%s.%s" % (variant.uid, arch)
            repo_dir = compose.paths.compose.repository(arch=arch, variant=variant)
            repos[repo_id] = repo_dir

            if compose.conf.get("release_is_layered", False):
                for i, lookaside_url in enumerate(get_lookaside_repos(compose, arch, variant)):
                    lookaside["lookaside-%s.%s-%s" % (variant.uid, arch, i)] = lookaside_url

            cmd = repoclosure.get_repoclosure_cmd(repos=repos, lookaside=lookaside, arch=arches)
            # Use temp working directory directory as workaround for
            # https://bugzilla.redhat.com/show_bug.cgi?id=795137
            tmp_dir = tempfile.mkdtemp(prefix="repoclosure_")
            try:
                run(cmd, logfile=compose.paths.log.log_file(arch, "repoclosure-%s" % variant), show_cmd=True, can_fail=True, workdir=tmp_dir)
            finally:
                rmtree(tmp_dir)

            all_repos.update(repos)
            all_repos.update(lookaside)
            repo_id = "repoclosure-%s.%s" % (variant.uid, "src")
            repo_dir = compose.paths.compose.repository(arch="src", variant=variant)
            all_repos[repo_id] = repo_dir

    # A SRPM can be built on any arch and is always rebuilt before building on the target arch.
    # This means the deps can't be always satisfied within one tree arch.
    # As a workaround, let's run the self-hosting check across all repos.

    # XXX: This doesn't solve a situation, when a noarch package is excluded due to ExcludeArch/ExclusiveArch and it's still required on that arch.
    # In this case, it's an obvious bug in the test.

    # check BuildRequires (self-hosting)
    cmd = repoclosure.get_repoclosure_cmd(repos=all_repos, arch=all_arches, builddeps=True)
    # Use temp working directory directory as workaround for
    # https://bugzilla.redhat.com/show_bug.cgi?id=795137
    tmp_dir = tempfile.mkdtemp(prefix="repoclosure_")
    try:
        run(cmd, logfile=compose.paths.log.log_file("global", "repoclosure-builddeps"), show_cmd=True, can_fail=True, workdir=tmp_dir)
    finally:
        rmtree(tmp_dir)

    compose.log_info("[DONE ] %s" % msg)


def check_image_sanity(compose):
    """
    Go through all images in manifest and make basic sanity tests on them. If
    any check fails for a failable deliverable, a message will be printed and
    logged. Otherwise the compose will be aborted.
    """
    im = compose.im
    for variant in compose.get_variants():
        if variant.uid not in im.images:
            continue
        for arch in variant.arches:
            if arch not in im.images[variant.uid]:
                continue
            for img in im.images[variant.uid][arch]:
                check(compose, variant, arch, img)


def check(compose, variant, arch, image):
    path = os.path.join(compose.paths.compose.topdir(), image.path)
    deliverable = getattr(image, 'deliverable')
    can_fail = getattr(image, 'can_fail', False)
    with failable(compose, can_fail, variant, arch, deliverable,
                  subvariant=image.subvariant):
        with open(path) as f:
            iso = is_iso(f)
            if image.format == 'iso' and not iso:
                raise RuntimeError('%s does not look like an ISO file' % path)
            if (image.arch in ('x86_64', 'i386') and
                    image.bootable and
                    not has_mbr(f) and
                    not has_gpt(f) and
                    not (iso and has_eltorito(f))):
                raise RuntimeError(
                    '%s is supposed to be bootable, but does not have MBR nor '
                    'GPT nor is it a bootable ISO' % path)
    # If exception is raised above, failable may catch it, in which case
    # nothing else will happen.


def _check_magic(f, offset, bytes):
    """Check that the file has correct magic number at correct offset."""
    f.seek(offset)
    return f.read(len(bytes)) == bytes


def is_iso(f):
    return _check_magic(f, 0x8001, 'CD001')


def has_mbr(f):
    return _check_magic(f, 0x1fe, '\x55\xAA')


def has_gpt(f):
    return _check_magic(f, 0x200, 'EFI PART')


def has_eltorito(f):
    return _check_magic(f, 0x8801, 'CD001\1EL TORITO SPECIFICATION')
