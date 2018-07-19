#!/usr/bin/env python
# -*- coding: utf-8 -*-


try:
    import unittest2 as unittest
except ImportError:
    import unittest
import mock

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tests import helpers
from pungi.phases import extra_isos


@mock.patch('pungi.phases.extra_isos.ThreadPool')
class ExtraIsosPhaseTest(helpers.PungiTestCase):

    def test_logs_extra_arches(self, ThreadPool):
        cfg = {
            'include_variants': ['Client'],
            'arches': ['x86_64', 'ppc64le', 'aarch64'],
        }
        compose = helpers.DummyCompose(self.topdir, {
            'extra_isos': {
                '^Server$': [cfg]
            }
        })

        phase = extra_isos.ExtraIsosPhase(compose)
        phase.validate()

        self.assertEqual(len(compose.log_warning.call_args_list), 1)

    def test_one_task_for_each_arch(self, ThreadPool):
        cfg = {
            'include_variants': ['Client'],
        }
        compose = helpers.DummyCompose(self.topdir, {
            'extra_isos': {
                '^Server$': [cfg]
            }
        })

        phase = extra_isos.ExtraIsosPhase(compose)
        phase.run()

        self.assertEqual(len(ThreadPool.return_value.add.call_args_list), 3)
        self.assertItemsEqual(
            ThreadPool.return_value.queue_put.call_args_list,
            [mock.call((compose, cfg, compose.variants['Server'], 'x86_64')),
             mock.call((compose, cfg, compose.variants['Server'], 'amd64')),
             mock.call((compose, cfg, compose.variants['Server'], 'src'))]
        )

    def test_filter_arches(self, ThreadPool):
        cfg = {
            'include_variants': ['Client'],
            'arches': ['x86_64'],
        }
        compose = helpers.DummyCompose(self.topdir, {
            'extra_isos': {
                '^Server$': [cfg]
            }
        })

        phase = extra_isos.ExtraIsosPhase(compose)
        phase.run()

        self.assertEqual(len(ThreadPool.return_value.add.call_args_list), 2)
        self.assertItemsEqual(
            ThreadPool.return_value.queue_put.call_args_list,
            [mock.call((compose, cfg, compose.variants['Server'], 'x86_64')),
             mock.call((compose, cfg, compose.variants['Server'], 'src'))]
        )

    def test_skip_source(self, ThreadPool):
        cfg = {
            'include_variants': ['Client'],
            'skip_src': True,
        }
        compose = helpers.DummyCompose(self.topdir, {
            'extra_isos': {
                '^Server$': [cfg]
            }
        })

        phase = extra_isos.ExtraIsosPhase(compose)
        phase.run()

        self.assertEqual(len(ThreadPool.return_value.add.call_args_list), 2)
        self.assertItemsEqual(
            ThreadPool.return_value.queue_put.call_args_list,
            [mock.call((compose, cfg, compose.variants['Server'], 'x86_64')),
             mock.call((compose, cfg, compose.variants['Server'], 'amd64'))]
        )


@mock.patch('pungi.phases.extra_isos.get_volume_id')
@mock.patch('pungi.phases.extra_isos.get_filename')
@mock.patch('pungi.phases.extra_isos.get_iso_contents')
@mock.patch('pungi.phases.extra_isos.get_extra_files')
@mock.patch('pungi.phases.extra_isos.run_createiso_command')
@mock.patch('pungi.phases.extra_isos.add_iso_to_metadata')
class ExtraIsosThreadTest(helpers.PungiTestCase):

    def test_binary_bootable_image(self, aitm, rcc, gef, gic, gfn, gvi):
        compose = helpers.DummyCompose(self.topdir, {
            'bootable': True,
            'buildinstall_method': 'lorax'
        })
        server = compose.variants['Server']
        cfg = {
            'include_variants': ['Client'],
        }

        gfn.return_value = 'my.iso'
        gvi.return_value = 'my volume id'
        gic.return_value = '/tmp/iso-graft-points'

        t = extra_isos.ExtraIsosThread(mock.Mock())
        with mock.patch('time.sleep'):
            t.process((compose, cfg, server, 'x86_64'), 1)

        self.assertEqual(gfn.call_args_list,
                         [mock.call(compose, server, 'x86_64', None)])
        self.assertEqual(gvi.call_args_list,
                         [mock.call(compose, server, 'x86_64', [])])
        self.assertEqual(gef.call_args_list,
                         [mock.call(compose, server, 'x86_64', [])])
        self.assertEqual(gic.call_args_list,
                         [mock.call(compose, server, 'x86_64', ['Client'], 'my.iso', True)])
        self.assertEqual(
            rcc.call_args_list,
            [mock.call(False, 1, compose, True, 'x86_64',
                       ['bash', os.path.join(self.topdir, 'work/x86_64/tmp-Server/extraiso-my.iso.sh')],
                       [self.topdir],
                       log_file=os.path.join(self.topdir, 'logs/x86_64/extraiso-my.iso.x86_64.log'),
                       with_jigdo=False)]

        )
        self.assertEqual(
            aitm.call_args_list,
            [mock.call(compose, server, 'x86_64',
                       os.path.join(self.topdir, 'compose/Server/x86_64/iso/my.iso'),
                       True, 1, 1)]
        )

    def test_binary_image_custom_naming(self, aitm, rcc, gef, gic, gfn, gvi):
        compose = helpers.DummyCompose(self.topdir, {})
        server = compose.variants['Server']
        cfg = {
            'include_variants': ['Client'],
            'filename': 'fn',
            'volid': ['v1', 'v2'],
        }

        gfn.return_value = 'my.iso'
        gvi.return_value = 'my volume id'
        gic.return_value = '/tmp/iso-graft-points'

        t = extra_isos.ExtraIsosThread(mock.Mock())
        with mock.patch('time.sleep'):
            t.process((compose, cfg, server, 'x86_64'), 1)

        self.assertEqual(gfn.call_args_list,
                         [mock.call(compose, server, 'x86_64', 'fn')])
        self.assertEqual(gvi.call_args_list,
                         [mock.call(compose, server, 'x86_64', ['v1', 'v2'])])
        self.assertEqual(gef.call_args_list,
                         [mock.call(compose, server, 'x86_64', [])])
        self.assertEqual(gic.call_args_list,
                         [mock.call(compose, server, 'x86_64', ['Client'], 'my.iso', False)])
        self.assertEqual(
            rcc.call_args_list,
            [mock.call(False, 1, compose, False, 'x86_64',
                       ['bash', os.path.join(self.topdir, 'work/x86_64/tmp-Server/extraiso-my.iso.sh')],
                       [self.topdir],
                       log_file=os.path.join(self.topdir, 'logs/x86_64/extraiso-my.iso.x86_64.log'),
                       with_jigdo=False)]

        )
        self.assertEqual(
            aitm.call_args_list,
            [mock.call(compose, server, 'x86_64',
                       os.path.join(self.topdir, 'compose/Server/x86_64/iso/my.iso'),
                       False, 1, 1)]
        )

    def test_source_is_not_bootable(self, aitm, rcc, gef, gic, gfn, gvi):
        compose = helpers.DummyCompose(self.topdir, {
            'bootable': True,
            'buildinstall_method': 'lorax'
        })
        server = compose.variants['Server']
        cfg = {
            'include_variants': ['Client'],
        }

        gfn.return_value = 'my.iso'
        gvi.return_value = 'my volume id'
        gic.return_value = '/tmp/iso-graft-points'

        t = extra_isos.ExtraIsosThread(mock.Mock())
        with mock.patch('time.sleep'):
            t.process((compose, cfg, server, 'src'), 1)

        self.assertEqual(gfn.call_args_list,
                         [mock.call(compose, server, 'src', None)])
        self.assertEqual(gvi.call_args_list,
                         [mock.call(compose, server, 'src', [])])
        self.assertEqual(gef.call_args_list,
                         [mock.call(compose, server, 'src', [])])
        self.assertEqual(gic.call_args_list,
                         [mock.call(compose, server, 'src', ['Client'], 'my.iso', False)])
        self.assertEqual(
            rcc.call_args_list,
            [mock.call(False, 1, compose, False, 'src',
                       ['bash', os.path.join(self.topdir, 'work/src/tmp-Server/extraiso-my.iso.sh')],
                       [self.topdir],
                       log_file=os.path.join(self.topdir, 'logs/src/extraiso-my.iso.src.log'),
                       with_jigdo=False)]

        )
        self.assertEqual(
            aitm.call_args_list,
            [mock.call(compose, server, 'src',
                       os.path.join(self.topdir, 'compose/Server/source/iso/my.iso'),
                       False, 1, 1)]
        )

    def test_failable_failed(self, aitm, rcc, gef, gic, gfn, gvi):
        compose = helpers.DummyCompose(self.topdir, {})
        server = compose.variants['Server']
        cfg = {
            'include_variants': ['Client'],
            'failable_arches': ['x86_64'],
        }

        gfn.return_value = 'my.iso'
        gvi.return_value = 'my volume id'
        gic.return_value = '/tmp/iso-graft-points'
        rcc.side_effect = helpers.mk_boom()

        t = extra_isos.ExtraIsosThread(mock.Mock())
        with mock.patch('time.sleep'):
            t.process((compose, cfg, server, 'x86_64'), 1)

        self.assertEqual(aitm.call_args_list, [])

    def test_non_failable_failed(self, aitm, rcc, gef, gic, gfn, gvi):
        compose = helpers.DummyCompose(self.topdir, {})
        server = compose.variants['Server']
        cfg = {
            'include_variants': ['Client'],
        }

        gfn.return_value = 'my.iso'
        gvi.return_value = 'my volume id'
        gic.return_value = '/tmp/iso-graft-points'
        rcc.side_effect = helpers.mk_boom(RuntimeError)

        t = extra_isos.ExtraIsosThread(mock.Mock())
        with self.assertRaises(RuntimeError):
            with mock.patch('time.sleep'):
                t.process((compose, cfg, server, 'x86_64'), 1)

        self.assertEqual(aitm.call_args_list, [])


@mock.patch('pungi.phases.extra_isos.get_file_from_scm')
@mock.patch('pungi.phases.extra_isos.get_dir_from_scm')
class GetExtraFilesTest(helpers.PungiTestCase):

    def setUp(self):
        super(GetExtraFilesTest, self).setUp()
        self.compose = helpers.DummyCompose(self.topdir, {})
        self.variant = self.compose.variants['Server']
        self.arch = 'x86_64'

    def test_no_config(self, get_dir, get_file):
        extra_isos.get_extra_files(self.compose, self.variant, self.arch, [])

        self.assertEqual(get_dir.call_args_list, [])
        self.assertEqual(get_file.call_args_list, [])

    def test_get_file(self, get_dir, get_file):
        cfg = {
            'scm': 'git',
            'repo': 'https://pagure.io/pungi.git',
            'file': 'GPL',
            'target': 'legalese',
        }
        extra_isos.get_extra_files(self.compose, self.variant, self.arch, [cfg])

        self.assertEqual(get_dir.call_args_list, [])
        self.assertEqual(get_file.call_args_list,
                         [mock.call(cfg,
                                    os.path.join(self.topdir, 'work',
                                                 self.arch, self.variant.uid,
                                                 'extra-iso-extra-files/legalese'),
                                    logger=self.compose._logger)])

    def test_get_dir(self, get_dir, get_file):
        cfg = {
            'scm': 'git',
            'repo': 'https://pagure.io/pungi.git',
            'dir': 'docs',
            'target': 'foo',
        }
        extra_isos.get_extra_files(self.compose, self.variant, self.arch, [cfg])

        self.assertEqual(get_file.call_args_list, [])
        self.assertEqual(get_dir.call_args_list,
                         [mock.call(cfg,
                                    os.path.join(self.topdir, 'work',
                                                 self.arch, self.variant.uid,
                                                 'extra-iso-extra-files/foo'),
                                    logger=self.compose._logger)])


@mock.patch("pungi.phases.extra_isos.tweak_treeinfo")
@mock.patch('pungi.wrappers.iso.write_graft_points')
@mock.patch('pungi.wrappers.iso.get_graft_points')
class GetIsoContentsTest(helpers.PungiTestCase):

    def setUp(self):
        super(GetIsoContentsTest, self).setUp()
        self.compose = helpers.DummyCompose(self.topdir, {})
        self.variant = self.compose.variants['Server']

    def test_non_bootable_binary(self, ggp, wgp, tt):
        gp = {
            'compose/Client/x86_64/os/Packages': {'f/foo.rpm': '/mnt/f/foo.rpm'},
            'compose/Client/x86_64/os/repodata': {'primary.xml': '/mnt/repodata/primary.xml'},
            'compose/Server/x86_64/os/Packages': {'b/bar.rpm': '/mnt/b/bar.rpm'},
            'compose/Server/x86_64/os/repodata': {'repomd.xml': '/mnt/repodata/repomd.xml'},
            'work/x86_64/Client/extra-files': {'GPL': '/mnt/GPL'},
            'work/x86_64/Server/extra-files': {'AUTHORS': '/mnt/AUTHORS'},
            'work/x86_64/Server/extra-iso-extra-files': {'EULA': '/mnt/EULA'},
        }

        ggp.side_effect = lambda x: gp[x[0][len(self.topdir) + 1:]]
        gp_file = os.path.join(self.topdir, 'work/x86_64/iso/my.iso-graft-points')

        self.assertEqual(
            extra_isos.get_iso_contents(self.compose, self.variant, 'x86_64',
                                        ['Client'], 'my.iso', False),
            gp_file
        )

        expected = {
            'Client/GPL': '/mnt/GPL',
            'Client/Packages/f/foo.rpm': '/mnt/f/foo.rpm',
            'Client/repodata/primary.xml': '/mnt/repodata/primary.xml',
            'EULA': '/mnt/EULA',
            'Server/AUTHORS': '/mnt/AUTHORS',
            'Server/Packages/b/bar.rpm': '/mnt/b/bar.rpm',
            'Server/repodata/repomd.xml': '/mnt/repodata/repomd.xml',
        }

        self.assertItemsEqual(
            ggp.call_args_list,
            [mock.call([os.path.join(self.topdir, x)]) for x in gp]
        )
        self.assertEqual(len(wgp.call_args_list), 1)
        self.assertEqual(wgp.call_args_list[0][0][0], gp_file)
        self.assertDictEqual(dict(wgp.call_args_list[0][0][1]), expected)
        self.assertEqual(wgp.call_args_list[0][1], {'exclude': ["*/lost+found", "*/boot.iso"]})

        # Check correct call to tweak_treeinfo
        self.assertEqual(
            tt.call_args_list,
            [
                mock.call(
                    self.compose,
                    ["Client"],
                    os.path.join(self.topdir, "compose/Server/x86_64/os/.treeinfo"),
                    os.path.join(
                        self.topdir,
                        "work/x86_64/Server/extra-iso-extra-files/.treeinfo",
                    )
                ),
            ],
        )

    def test_source(self, ggp, wgp, tt):
        gp = {
            'compose/Client/source/tree/Packages': {'f/foo.rpm': '/mnt/f/foo.rpm'},
            'compose/Client/source/tree/repodata': {'primary.xml': '/mnt/repodata/primary.xml'},
            'compose/Server/source/tree/Packages': {'b/bar.rpm': '/mnt/b/bar.rpm'},
            'compose/Server/source/tree/repodata': {'repomd.xml': '/mnt/repodata/repomd.xml'},
            'work/src/Client/extra-files': {'GPL': '/mnt/GPL'},
            'work/src/Server/extra-files': {'AUTHORS': '/mnt/AUTHORS'},
            'work/src/Server/extra-iso-extra-files': {'EULA': '/mnt/EULA'},
        }

        ggp.side_effect = lambda x: gp[x[0][len(self.topdir) + 1:]]
        gp_file = os.path.join(self.topdir, 'work/src/iso/my.iso-graft-points')

        self.assertEqual(
            extra_isos.get_iso_contents(self.compose, self.variant, 'src',
                                        ['Client'], 'my.iso', False),
            gp_file
        )

        expected = {
            'Client/GPL': '/mnt/GPL',
            'Client/Packages/f/foo.rpm': '/mnt/f/foo.rpm',
            'Client/repodata/primary.xml': '/mnt/repodata/primary.xml',
            'EULA': '/mnt/EULA',
            'Server/AUTHORS': '/mnt/AUTHORS',
            'Server/Packages/b/bar.rpm': '/mnt/b/bar.rpm',
            'Server/repodata/repomd.xml': '/mnt/repodata/repomd.xml',
        }

        self.assertItemsEqual(
            ggp.call_args_list,
            [mock.call([os.path.join(self.topdir, x)]) for x in gp]
        )
        self.assertEqual(len(wgp.call_args_list), 1)
        self.assertEqual(wgp.call_args_list[0][0][0], gp_file)
        self.assertDictEqual(dict(wgp.call_args_list[0][0][1]), expected)
        self.assertEqual(wgp.call_args_list[0][1], {'exclude': ["*/lost+found", "*/boot.iso"]})

        # Check correct call to tweak_treeinfo
        self.assertEqual(
            tt.call_args_list,
            [
                mock.call(
                    self.compose,
                    ["Client"],
                    os.path.join(self.topdir, "compose/Server/source/tree/.treeinfo"),
                    os.path.join(
                        self.topdir,
                        "work/src/Server/extra-iso-extra-files/.treeinfo",
                    )
                ),
            ],
        )

    def test_bootable(self, ggp, wgp, tt):
        self.compose.conf['buildinstall_method'] = 'lorax'

        bi_dir = os.path.join(self.topdir, 'work/x86_64/buildinstall/Server')
        iso_dir = os.path.join(self.topdir, 'work/x86_64/iso/my.iso')
        helpers.touch(os.path.join(bi_dir, 'isolinux/isolinux.bin'))
        helpers.touch(os.path.join(bi_dir, 'images/boot.img'))

        gp = {
            'compose/Client/x86_64/os/Packages': {'f/foo.rpm': '/mnt/f/foo.rpm'},
            'compose/Client/x86_64/os/repodata': {'primary.xml': '/mnt/repodata/primary.xml'},
            'compose/Server/x86_64/os/Packages': {'b/bar.rpm': '/mnt/b/bar.rpm'},
            'compose/Server/x86_64/os/repodata': {'repomd.xml': '/mnt/repodata/repomd.xml'},
            'work/x86_64/Client/extra-files': {'GPL': '/mnt/GPL'},
            'work/x86_64/Server/extra-files': {'AUTHORS': '/mnt/AUTHORS'},
            'work/x86_64/Server/extra-iso-extra-files': {'EULA': '/mnt/EULA'},
        }
        bi_gp = {
            'isolinux/isolinux.bin': os.path.join(iso_dir, 'isolinux/isolinux.bin'),
            'images/boot.img': os.path.join(iso_dir, 'images/boot.img'),
        }

        ggp.side_effect = lambda x: gp[x[0][len(self.topdir) + 1:]] if len(x) == 1 else bi_gp
        gp_file = os.path.join(self.topdir, 'work/x86_64/iso/my.iso-graft-points')

        self.assertEqual(
            extra_isos.get_iso_contents(
                self.compose,
                self.variant,
                'x86_64',
                ['Client'],
                'my.iso',
                True),
            gp_file
        )

        self.maxDiff = None

        expected = {
            'Client/GPL': '/mnt/GPL',
            'Client/Packages/f/foo.rpm': '/mnt/f/foo.rpm',
            'Client/repodata/primary.xml': '/mnt/repodata/primary.xml',
            'EULA': '/mnt/EULA',
            'Server/AUTHORS': '/mnt/AUTHORS',
            'Server/Packages/b/bar.rpm': '/mnt/b/bar.rpm',
            'Server/repodata/repomd.xml': '/mnt/repodata/repomd.xml',
            'isolinux/isolinux.bin': os.path.join(iso_dir, 'isolinux/isolinux.bin'),
            'images/boot.img': os.path.join(iso_dir, 'images/boot.img'),
        }

        self.assertItemsEqual(
            ggp.call_args_list,
            [mock.call([os.path.join(self.topdir, x)]) for x in gp] + [mock.call([bi_dir, iso_dir])]
        )
        self.assertEqual(len(wgp.call_args_list), 1)
        self.assertEqual(wgp.call_args_list[0][0][0], gp_file)
        self.assertDictEqual(dict(wgp.call_args_list[0][0][1]), expected)
        self.assertEqual(wgp.call_args_list[0][1], {'exclude': ["*/lost+found", "*/boot.iso"]})

        # Check files were copied to temp directory
        self.assertTrue(os.path.exists(os.path.join(iso_dir, 'isolinux/isolinux.bin')))
        self.assertTrue(os.path.exists(os.path.join(iso_dir, 'images/boot.img')))

        # Check correct call to tweak_treeinfo
        self.assertEqual(
            tt.call_args_list,
            [
                mock.call(
                    self.compose,
                    ["Client"],
                    os.path.join(self.topdir, "compose/Server/x86_64/os/.treeinfo"),
                    os.path.join(
                        self.topdir,
                        "work/x86_64/Server/extra-iso-extra-files/.treeinfo",
                    )
                ),
            ],
        )


class GetFilenameTest(helpers.PungiTestCase):
    def test_use_original_name(self):
        compose = helpers.DummyCompose(self.topdir, {})

        fn = extra_isos.get_filename(compose, compose.variants['Server'], 'x86_64',
                                     'foo-{variant}-{arch}-{filename}')

        self.assertEqual(fn, 'foo-Server-x86_64-image-name')

    def test_use_default_without_format(self):
        compose = helpers.DummyCompose(self.topdir, {})

        fn = extra_isos.get_filename(compose, compose.variants['Server'], 'x86_64',
                                     None)

        self.assertEqual(fn, 'image-name')

    def test_reports_unknown_placeholder(self):
        compose = helpers.DummyCompose(self.topdir, {})

        with self.assertRaises(RuntimeError) as ctx:
            extra_isos.get_filename(compose, compose.variants['Server'], 'x86_64',
                                    'foo-{boom}')

        self.assertIn('boom', str(ctx.exception))


class GetVolumeIDTest(helpers.PungiTestCase):
    def test_use_original_volume_id(self):
        compose = helpers.DummyCompose(self.topdir, {})

        volid = extra_isos.get_volume_id(compose, compose.variants['Server'],
                                         'x86_64',
                                         'f-{volid}')

        self.assertEqual(volid, 'f-test-1.0 Server.x86_64')

    def test_falls_back_to_shorter(self):
        compose = helpers.DummyCompose(self.topdir, {})

        volid = extra_isos.get_volume_id(compose, compose.variants['Server'],
                                         'x86_64',
                                         ['long-foobar-{volid}', 'f-{volid}'])

        self.assertEqual(volid, 'f-test-1.0 Server.x86_64')

    def test_reports_unknown_placeholder(self):
        compose = helpers.DummyCompose(self.topdir, {})

        with self.assertRaises(RuntimeError) as ctx:
            extra_isos.get_volume_id(compose, compose.variants['Server'],
                                     'x86_64', 'f-{boom}')

        self.assertIn('boom', str(ctx.exception))


class TweakTreeinfoTest(helpers.PungiTestCase):
    def test_tweak(self):
        compose = helpers.DummyCompose(self.topdir, {})
        input = os.path.join(helpers.FIXTURE_DIR, "treeinfo")
        output = os.path.join(self.topdir, "actual-treeinfo")
        expected = os.path.join(helpers.FIXTURE_DIR, "treeinfo-expected")
        extra_isos.tweak_treeinfo(compose, ["Client"], input, output)

        with open(expected) as f:
            expected = f.read()
        with open(output) as f:
            actual = f.read()

        self.maxDiff = None
        self.assertEqual(expected, actual)


if __name__ == '__main__':
    unittest.main()
