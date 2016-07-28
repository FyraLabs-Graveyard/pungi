# -*- coding: utf-8 -*-

from __future__ import print_function

import os
import pipes
from collections import namedtuple

from .wrappers.iso import IsoWrapper
from .wrappers.jigdo import JigdoWrapper


CreateIsoOpts = namedtuple('CreateIsoOpts',
                           ['buildinstall_method', 'arch', 'output_dir', 'jigdo_dir',
                            'iso_name', 'volid', 'graft_points', 'supported', 'os_tree'])
CreateIsoOpts.__new__.__defaults__ = (None,) * len(CreateIsoOpts._fields)


def quote(str):
    """Quote an argument for shell, but make sure $TEMPLATE variable will be
    expanded.
    """
    if str.startswith('$TEMPLATE'):
        return '$TEMPLATE%s' % pipes.quote(str.replace('$TEMPLATE', '', 1))
    return pipes.quote(str)


def emit(f, cmd):
    """Print line of shell code into the stream."""
    if isinstance(cmd, basestring):
        print(cmd, file=f)
    else:
        print(' '.join([quote(x) for x in cmd]), file=f)


FIND_TEMPLATE_SNIPPET = """
if ! TEMPLATE="$(python3 -c 'import pylorax; print(pylorax.find_templates())')"; then
  TEMPLATE=/usr/share/lorax;
fi
""".replace('\n', '')


def make_image(f, iso, opts):
    mkisofs_kwargs = {}

    if opts.buildinstall_method:
        if opts.buildinstall_method == 'lorax':
            emit(f, FIND_TEMPLATE_SNIPPET)
            mkisofs_kwargs["boot_args"] = iso.get_boot_options(
                opts.arch, os.path.join('$TEMPLATE', 'config_files/ppc'))
        elif opts.buildinstall_method == 'buildinstall':
            mkisofs_kwargs["boot_args"] = iso.get_boot_options(
                opts.arch, "/usr/lib/anaconda-runtime/boot")

    # ppc(64) doesn't seem to support utf-8
    if opts.arch in ("ppc", "ppc64", "ppc64le"):
        mkisofs_kwargs["input_charset"] = None

    cmd = iso.get_mkisofs_cmd(opts.iso_name, None, volid=opts.volid,
                              exclude=["./lost+found"],
                              graft_points=opts.graft_points, **mkisofs_kwargs)
    emit(f, cmd)


def implant_md5(f, iso, opts):
    cmd = iso.get_implantisomd5_cmd(opts.iso_name, opts.supported)
    emit(f, cmd)


def run_isohybrid(f, iso, opts):
    """If the image is bootable, it should include an MBR or GPT so that it can
    be booted when written to USB disk. This is done by running isohybrid on
    the image.
    """
    if opts.buildinstall_method and opts.arch in ["x86_64", "i386"]:
        cmd = iso.get_isohybrid_cmd(opts.iso_name, opts.arch)
        emit(f, cmd)


def make_manifest(f, iso, opts):
    emit(f, iso.get_manifest_cmd(opts.iso_name))


def make_jigdo(f, opts):
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
    emit(f, cmd)


def write_script(opts, f):
    if bool(opts.jigdo_dir) != bool(opts.os_tree):
        raise RuntimeError('jigdo_dir must be used together with os_tree')

    emit(f, "#!/bin/bash")
    emit(f, "set -ex")
    emit(f, "cd %s" % opts.output_dir)
    iso = IsoWrapper()
    make_image(f, iso, opts)
    run_isohybrid(f, iso, opts)
    implant_md5(f, iso, opts)
    make_manifest(f, iso, opts)
    if opts.jigdo_dir:
        make_jigdo(f, opts)
