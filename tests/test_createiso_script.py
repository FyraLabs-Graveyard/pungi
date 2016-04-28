#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import mock

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tests import helpers
from pungi import createiso


class CreateIsoScriptTest(helpers.PungiTestCase):

    def assertEqualCalls(self, actual, expected):
        self.assertEqual(len(actual), len(expected))
        for x, y in zip(actual, expected):
            self.assertEqual(x, y)

    def setUp(self):
        super(CreateIsoScriptTest, self).setUp()
        self.outdir = os.path.join(self.topdir, 'isos')

    @mock.patch('kobo.shortcuts.run')
    def test_minimal_run(self, run):
        createiso.main([
            '--output-dir={}'.format(self.outdir),
            '--iso-name=DP-1.0-20160405.t.3-x86_64.iso',
            '--volid=DP-1.0-20160405.t.3',
            '--graft-points=graft-list',
            '--arch=x86_64',
        ])
        self.maxDiff = None
        self.assertEqual(
            run.call_args_list,
            [mock.call(['/usr/bin/genisoimage', '-untranslated-filenames',
                        '-volid', 'DP-1.0-20160405.t.3', '-J', '-joliet-long',
                        '-rational-rock', '-translation-table',
                        '-input-charset', 'utf-8', '-x', './lost+found',
                        '-o', 'DP-1.0-20160405.t.3-x86_64.iso',
                        '-graft-points', '-path-list', 'graft-list'],
                       show_cmd=True, stdout=True, workdir=self.outdir),
             mock.call(['/usr/bin/implantisomd5', 'DP-1.0-20160405.t.3-x86_64.iso'],
                       show_cmd=True, stdout=True, workdir=self.outdir),
             mock.call('isoinfo -R -f -i DP-1.0-20160405.t.3-x86_64.iso | grep -v \'/TRANS.TBL$\' | sort >> DP-1.0-20160405.t.3-x86_64.iso.manifest',
                       show_cmd=True, stdout=True, workdir=self.outdir)]
        )

    @mock.patch('kobo.shortcuts.run')
    def test_bootable_run(self, run):
        run.return_value = (0, '/usr/share/lorax')

        createiso.main([
            '--output-dir={}'.format(self.outdir),
            '--iso-name=DP-1.0-20160405.t.3-x86_64.iso',
            '--volid=DP-1.0-20160405.t.3',
            '--graft-points=graft-list',
            '--arch=x86_64',
            '--buildinstall-method=lorax',
        ])

        self.maxDiff = None
        self.assertItemsEqual(
            run.call_args_list,
            [mock.call(['/usr/bin/genisoimage', '-untranslated-filenames',
                        '-volid', 'DP-1.0-20160405.t.3', '-J', '-joliet-long',
                        '-rational-rock', '-translation-table',
                        '-input-charset', 'utf-8', '-x', './lost+found',
                        '-b', 'isolinux/isolinux.bin', '-c', 'isolinux/boot.cat',
                        '-no-emul-boot',
                        '-boot-load-size', '4', '-boot-info-table',
                        '-eltorito-alt-boot', '-e', 'images/efiboot.img',
                        '-no-emul-boot',
                        '-o', 'DP-1.0-20160405.t.3-x86_64.iso',
                        '-graft-points', '-path-list', 'graft-list'],
                       show_cmd=True, stdout=True, workdir=self.outdir),
             mock.call(['pungi-pylorax-find-templates', '/usr/share/lorax'],
                       show_cmd=True, stdout=True),
             mock.call(['/usr/bin/isohybrid', '--uefi', 'DP-1.0-20160405.t.3-x86_64.iso'],
                       show_cmd=True, stdout=True, workdir=self.outdir),
             mock.call(['/usr/bin/implantisomd5', 'DP-1.0-20160405.t.3-x86_64.iso'],
                       show_cmd=True, stdout=True, workdir=self.outdir),
             mock.call('isoinfo -R -f -i DP-1.0-20160405.t.3-x86_64.iso | grep -v \'/TRANS.TBL$\' | sort >> DP-1.0-20160405.t.3-x86_64.iso.manifest',
                       show_cmd=True, stdout=True, workdir=self.outdir)]
        )

    @mock.patch('kobo.shortcuts.run')
    def test_bootable_run_on_i386(self, run):
        # This will call isohybrid, but not with --uefi switch
        run.return_value = (0, '/usr/share/lorax')

        createiso.main([
            '--output-dir={}'.format(self.outdir),
            '--iso-name=DP-1.0-20160405.t.3-i386.iso',
            '--volid=DP-1.0-20160405.t.3',
            '--graft-points=graft-list',
            '--arch=i386',
            '--buildinstall-method=lorax',
        ])

        self.maxDiff = None
        self.assertItemsEqual(
            run.call_args_list,
            [mock.call(['/usr/bin/genisoimage', '-untranslated-filenames',
                        '-volid', 'DP-1.0-20160405.t.3', '-J', '-joliet-long',
                        '-rational-rock', '-translation-table',
                        '-input-charset', 'utf-8', '-x', './lost+found',
                        '-b', 'isolinux/isolinux.bin', '-c', 'isolinux/boot.cat',
                        '-no-emul-boot',
                        '-boot-load-size', '4', '-boot-info-table',
                        '-o', 'DP-1.0-20160405.t.3-i386.iso',
                        '-graft-points', '-path-list', 'graft-list'],
                       show_cmd=True, stdout=True, workdir=self.outdir),
             mock.call(['pungi-pylorax-find-templates', '/usr/share/lorax'],
                       show_cmd=True, stdout=True),
             mock.call(['/usr/bin/isohybrid', 'DP-1.0-20160405.t.3-i386.iso'],
                       show_cmd=True, stdout=True, workdir=self.outdir),
             mock.call(['/usr/bin/implantisomd5', 'DP-1.0-20160405.t.3-i386.iso'],
                       show_cmd=True, stdout=True, workdir=self.outdir),
             mock.call('isoinfo -R -f -i DP-1.0-20160405.t.3-i386.iso | grep -v \'/TRANS.TBL$\' | sort >> DP-1.0-20160405.t.3-i386.iso.manifest',
                       show_cmd=True, stdout=True, workdir=self.outdir)]
        )

    @mock.patch('kobo.shortcuts.run')
    def test_bootable_run_ppc64(self, run):
        run.return_value = (0, '/usr/share/lorax')

        createiso.main([
            '--output-dir={}'.format(self.outdir),
            '--iso-name=DP-1.0-20160405.t.3-ppc64.iso',
            '--volid=DP-1.0-20160405.t.3',
            '--graft-points=graft-list',
            '--arch=ppc64',
            '--buildinstall-method=lorax',
        ])

        self.maxDiff = None
        self.assertItemsEqual(
            run.call_args_list,
            [mock.call(['/usr/bin/genisoimage', '-untranslated-filenames',
                        '-volid', 'DP-1.0-20160405.t.3', '-J', '-joliet-long',
                        '-rational-rock', '-translation-table',
                        '-x', './lost+found',
                        '-part', '-hfs', '-r', '-l', '-sysid', 'PPC', '-no-desktop',
                        '-allow-multidot', '-chrp-boot', '-map', '/usr/share/lorax/config_files/ppc/mapping',
                        '-hfs-bless', '/ppc/mac',
                        '-o', 'DP-1.0-20160405.t.3-ppc64.iso',
                        '-graft-points', '-path-list', 'graft-list'],
                       show_cmd=True, stdout=True, workdir=self.outdir),
             mock.call(['pungi-pylorax-find-templates', '/usr/share/lorax'],
                       show_cmd=True, stdout=True),
             mock.call(['/usr/bin/implantisomd5', 'DP-1.0-20160405.t.3-ppc64.iso'],
                       show_cmd=True, stdout=True, workdir=self.outdir),
             mock.call('isoinfo -R -f -i DP-1.0-20160405.t.3-ppc64.iso | grep -v \'/TRANS.TBL$\' | sort >> DP-1.0-20160405.t.3-ppc64.iso.manifest',
                       show_cmd=True, stdout=True, workdir=self.outdir)]
        )

    @mock.patch('kobo.shortcuts.run')
    def test_bootable_run_buildinstall(self, run):
        createiso.main([
            '--output-dir={}'.format(self.outdir),
            '--iso-name=DP-1.0-20160405.t.3-ppc64.iso',
            '--volid=DP-1.0-20160405.t.3',
            '--graft-points=graft-list',
            '--arch=ppc64',
            '--buildinstall-method=buildinstall',
        ])

        self.maxDiff = None
        self.assertItemsEqual(
            run.call_args_list,
            [mock.call(['/usr/bin/genisoimage', '-untranslated-filenames',
                        '-volid', 'DP-1.0-20160405.t.3', '-J', '-joliet-long',
                        '-rational-rock', '-translation-table',
                        '-x', './lost+found',
                        '-part', '-hfs', '-r', '-l', '-sysid', 'PPC', '-no-desktop',
                        '-allow-multidot', '-chrp-boot',
                        '-map', '/usr/lib/anaconda-runtime/boot/mapping',
                        '-hfs-bless', '/ppc/mac',
                        '-o', 'DP-1.0-20160405.t.3-ppc64.iso',
                        '-graft-points', '-path-list', 'graft-list'],
                       show_cmd=True, stdout=True, workdir=self.outdir),
             mock.call(['/usr/bin/implantisomd5', 'DP-1.0-20160405.t.3-ppc64.iso'],
                       show_cmd=True, stdout=True, workdir=self.outdir),
             mock.call('isoinfo -R -f -i DP-1.0-20160405.t.3-ppc64.iso | grep -v \'/TRANS.TBL$\' | sort >> DP-1.0-20160405.t.3-ppc64.iso.manifest',
                       show_cmd=True, stdout=True, workdir=self.outdir)]
        )

    @mock.patch('sys.stderr')
    @mock.patch('kobo.shortcuts.run')
    def test_run_with_jigdo_bad_args(self, run, stderr):
        with self.assertRaises(SystemExit):
            createiso.main([
                '--output-dir={}'.format(self.outdir),
                '--iso-name=DP-1.0-20160405.t.3-x86_64.iso',
                '--volid=DP-1.0-20160405.t.3',
                '--graft-points=graft-list',
                '--arch=x86_64',
                '--jigdo-dir={}/jigdo'.format(self.topdir),
            ])

    @mock.patch('kobo.shortcuts.run')
    def test_run_with_jigdo(self, run):
        createiso.main([
            '--output-dir={}'.format(self.outdir),
            '--iso-name=DP-1.0-20160405.t.3-x86_64.iso',
            '--volid=DP-1.0-20160405.t.3',
            '--graft-points=graft-list',
            '--arch=x86_64',
            '--jigdo-dir={}/jigdo'.format(self.topdir),
            '--os-tree={}/os'.format(self.topdir),
        ])
        self.maxDiff = None
        self.assertItemsEqual(
            run.call_args_list,
            [mock.call(['/usr/bin/genisoimage', '-untranslated-filenames',
                        '-volid', 'DP-1.0-20160405.t.3', '-J', '-joliet-long',
                        '-rational-rock', '-translation-table',
                        '-input-charset', 'utf-8', '-x', './lost+found',
                        '-o', 'DP-1.0-20160405.t.3-x86_64.iso',
                        '-graft-points', '-path-list', 'graft-list'],
                       show_cmd=True, stdout=True, workdir=self.outdir),
             mock.call(['/usr/bin/implantisomd5', 'DP-1.0-20160405.t.3-x86_64.iso'],
                       show_cmd=True, stdout=True, workdir=self.outdir),
             mock.call('isoinfo -R -f -i DP-1.0-20160405.t.3-x86_64.iso | grep -v \'/TRANS.TBL$\' | sort >> DP-1.0-20160405.t.3-x86_64.iso.manifest',
                       show_cmd=True, stdout=True, workdir=self.outdir),
             mock.call(['jigdo-file', 'make-template', '--force',
                        '--image={}/isos/DP-1.0-20160405.t.3-x86_64.iso'.format(self.topdir),
                        '--jigdo={}/jigdo/DP-1.0-20160405.t.3-x86_64.iso.jigdo'.format(self.topdir),
                        '--template={}/jigdo/DP-1.0-20160405.t.3-x86_64.iso.template'.format(self.topdir),
                        '--no-servers-section', '--report=noprogress', self.topdir + '/os//'],
                       show_cmd=True, stdout=True, workdir=self.outdir)]
        )


if __name__ == '__main__':
    unittest.main()
