# -*- coding: utf-8 -*-

import argparse
import os
from kobo import shortcuts

from .wrappers.iso import IsoWrapper
from .wrappers.jigdo import JigdoWrapper


def find_templates(fallback):
    """
    Helper for finding lorax templates. The called program needs to run with
    Python 3, while the rest of this script only supports Python 2.
    """
    _, output = shortcuts.run(['pungi-pylorax-find-templates', fallback],
                              stdout=True, show_cmd=True)
    return output.strip()


def make_image(iso, opts):
    mkisofs_kwargs = {}

    if opts.buildinstall_method:
        if opts.buildinstall_method == 'lorax':
            dir = find_templates('/usr/share/lorax')
            mkisofs_kwargs["boot_args"] = iso.get_boot_options(
                opts.arch, os.path.join(dir, 'config_files/ppc'))
        elif opts.buildinstall_method == 'buildinstall':
            mkisofs_kwargs["boot_args"] = iso.get_boot_options(
                opts.arch, "/usr/lib/anaconda-runtime/boot")

    # ppc(64) doesn't seem to support utf-8
    if opts.arch in ("ppc", "ppc64", "ppc64le"):
        mkisofs_kwargs["input_charset"] = None

    cmd = iso.get_mkisofs_cmd(opts.iso_name, None, volid=opts.volid,
                              exclude=["./lost+found"],
                              graft_points=opts.graft_points, **mkisofs_kwargs)
    shortcuts.run(cmd, stdout=True, show_cmd=True, workdir=opts.output_dir)


def implant_md5(iso, opts):
    cmd = iso.get_implantisomd5_cmd(opts.iso_name, opts.supported)
    shortcuts.run(cmd, stdout=True, show_cmd=True, workdir=opts.output_dir)


def run_isohybrid(iso, opts):
    """If the image is bootable, it needs to include an MBR or GPT so that it
    can actually be booted. This is done by running isohybrid on the image.
    """
    if opts.buildinstall_method and opts.arch in ["x86_64", "i386"]:
        cmd = iso.get_isohybrid_cmd(opts.iso_name, opts.arch)
        shortcuts.run(cmd, stdout=True, show_cmd=True, workdir=opts.output_dir)


def make_manifest(iso, opts):
    shortcuts.run(iso.get_manifest_cmd(opts.iso_name), stdout=True,
                  show_cmd=True, workdir=opts.output_dir)


def make_jigdo(opts):
    jigdo = JigdoWrapper()
    files = [
        {
            "path": opts.os_tree,
            "label": None,
            "uri": None,
        }
    ]
    cmd = jigdo.get_jigdo_cmd(os.path.join(opts.output_dir, opts.iso_name),
                              files, output_dir=opts.jigdo_dir,
                              no_servers=True, report="noprogress")
    shortcuts.run(cmd, stdout=True, show_cmd=True, workdir=opts.output_dir)


def run(opts):
    iso = IsoWrapper()
    make_image(iso, opts)
    run_isohybrid(iso, opts)
    implant_md5(iso, opts)
    make_manifest(iso, opts)
    if opts.jigdo_dir:
        make_jigdo(opts)


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', required=True,
                        help='where to put the final image')
    parser.add_argument('--iso-name', required=True,
                        help='filename for the created ISO image')
    parser.add_argument('--volid', required=True,
                        help='volume id for the image')
    parser.add_argument('--graft-points', required=True,
                        help='')
    parser.add_argument('--buildinstall-method',
                        choices=['lorax', 'buildinstall'],
                        help='how was the boot.iso created for bootable products')
    parser.add_argument('--arch', required=True,
                        help='what arch are we building the ISO for')
    parser.add_argument('--supported', action='store_true',
                        help='supported flag for implantisomd5')
    parser.add_argument('--jigdo-dir',
                        help='where to put jigdo files')
    parser.add_argument('--os-tree',
                        help='where to put jigdo files')

    opts = parser.parse_args(args)

    if bool(opts.jigdo_dir) != bool(opts.os_tree):
        parser.error('--jigdo-dir must be used together with --os-tree')
    run(opts)
