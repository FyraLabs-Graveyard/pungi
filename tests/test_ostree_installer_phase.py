#!/usr/bin/env python
# -*- coding: utf-8 -*-


import unittest
import mock

import os
import sys

from kobo.shortcuts import force_list

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tests import helpers
from pungi.phases import ostree_installer as ostree


class OstreeInstallerPhaseTest(helpers.PungiTestCase):

    @mock.patch('pungi.phases.ostree_installer.ThreadPool')
    def test_run(self, ThreadPool):
        cfg = mock.Mock()
        compose = helpers.DummyCompose(self.topdir, {
            'ostree_installer': [
                ('^Everything$', {'x86_64': cfg})
            ]
        })

        pool = ThreadPool.return_value

        phase = ostree.OstreeInstallerPhase(compose)
        phase.run()

        self.assertEqual(len(pool.add.call_args_list), 1)
        self.assertEqual(pool.queue_put.call_args_list,
                         [mock.call((compose, compose.variants['Everything'], 'x86_64', cfg))])

    @mock.patch('pungi.phases.ostree_installer.ThreadPool')
    def test_skip_without_config(self, ThreadPool):
        compose = helpers.DummyCompose(self.topdir, {})
        compose.just_phases = None
        compose.skip_phases = []
        phase = ostree.OstreeInstallerPhase(compose)
        self.assertTrue(phase.skip())


class OstreeThreadTest(helpers.PungiTestCase):

    def setUp(self):
        super(OstreeThreadTest, self).setUp()
        self.compose = helpers.DummyCompose(self.topdir, {
            'release_name': 'Fedora',
            'release_version': 'Rawhide',
            'koji_profile': 'koji',
            'runroot_tag': 'rrt',
            'image_volid_formats': ['{release_short}-{variant}-{arch}'],
        })

    def assertImageAdded(self, compose, ImageCls, iso):
        image = ImageCls.return_value
        self.assertEqual(image.path, 'Everything/x86_64/iso/image-name')
        self.assertEqual(image.mtime, 13579)
        self.assertEqual(image.size, 1024)
        self.assertEqual(image.arch, 'x86_64')
        self.assertEqual(image.type, "dvd-ostree")
        self.assertEqual(image.format, "iso")
        self.assertEqual(image.disc_number, 1)
        self.assertEqual(image.disc_count, 1)
        self.assertEqual(image.bootable, True)
        self.assertEqual(image.implant_md5, iso.get_implanted_md5.return_value)
        self.assertEqual(compose.im.add.mock_calls,
                         [mock.call('Everything', 'x86_64', image)])

    def assertRunrootCall(self, koji, sources, release, isfinal=False, extra=[], weight=None):
        lorax_cmd = [
            'lorax',
            '--product=Fedora',
            '--version=Rawhide',
            '--release=%s' % release,
        ]

        for s in force_list(sources):
            lorax_cmd.append('--source=%s' % s)

        lorax_cmd.append('--variant=Everything')
        lorax_cmd.append('--nomacboot')

        if isfinal:
            lorax_cmd.append('--isfinal')

        lorax_cmd.append('--volid=test-Everything-x86_64')

        if extra:
            lorax_cmd.extend(extra)

        lorax_cmd.append(self.topdir + '/work/x86_64/Everything/ostree_installer')

        self.assertEqual(koji.get_runroot_cmd.call_args_list,
                         [mock.call('rrt', 'x86_64',
                                    lorax_cmd,
                                    channel=None, mounts=[self.topdir],
                                    packages=['pungi', 'lorax', 'ostree'],
                                    task_id=True, use_shell=True, weight=weight)])
        self.assertEqual(koji.run_runroot_cmd.call_args_list,
                         [mock.call(koji.get_runroot_cmd.return_value,
                                    log_file=self.topdir + '/logs/x86_64/ostree_installer/runroot.log')])

    def assertIsoLinked(self, link, get_file_size, get_mtime, final_iso_path):
        self.assertEqual(link.call_args_list,
                         [mock.call(self.topdir + '/work/x86_64/Everything/ostree_installer/images/boot.iso',
                                    final_iso_path)])
        self.assertEqual(get_file_size.call_args_list, [mock.call(final_iso_path)])
        self.assertEqual(get_mtime.call_args_list, [mock.call(final_iso_path)])

    def assertAllCopied(self, run):
        self.assertEqual(self.compose.get_image_name.call_args_list,
                         [mock.call('x86_64', self.compose.variants['Everything'], disc_type='ostree')])
        self.assertTrue(os.path.isdir(self.topdir + '/work/x86_64/Everything/'))
        self.assertFalse(os.path.isdir(self.topdir + '/work/x86_64/Everything/ostree_installer'))
        self.assertEqual(run.call_args_list,
                         [mock.call('cp -av {0}/work/x86_64/Everything/ostree_installer/* {0}/compose/Everything/x86_64/os/'.format(self.topdir))])

    @mock.patch('kobo.shortcuts.run')
    @mock.patch('productmd.images.Image')
    @mock.patch('pungi.util.get_mtime')
    @mock.patch('pungi.util.get_file_size')
    @mock.patch('pungi.phases.ostree_installer.iso')
    @mock.patch('os.link')
    @mock.patch('pungi.wrappers.kojiwrapper.KojiWrapper')
    def test_run(self, KojiWrapper, link, iso,
                 get_file_size, get_mtime, ImageCls, run):
        self.compose.supported = False
        pool = mock.Mock()
        cfg = {
            'source_repo_from': 'Everything',
            'release': '20160321.n.0',
        }
        koji = KojiWrapper.return_value
        koji.run_runroot_cmd.return_value = {
            'task_id': 1234,
            'retcode': 0,
            'output': 'Foo bar\n',
        }
        get_file_size.return_value = 1024
        get_mtime.return_value = 13579
        final_iso_path = self.topdir + '/compose/Everything/x86_64/iso/image-name'

        t = ostree.OstreeInstallerThread(pool)

        t.process((self.compose, self.compose.variants['Everything'], 'x86_64', cfg), 1)

        self.assertRunrootCall(koji,
                               'file://%s/compose/Everything/x86_64/os' % self.topdir,
                               cfg['release'],
                               extra=['--logfile=%s/logs/x86_64/ostree_installer/lorax.log' % self.topdir])
        self.assertIsoLinked(link, get_file_size, get_mtime, final_iso_path)
        self.assertImageAdded(self.compose, ImageCls, iso)
        self.assertAllCopied(run)

    @mock.patch('kobo.shortcuts.run')
    @mock.patch('productmd.images.Image')
    @mock.patch('pungi.util.get_mtime')
    @mock.patch('pungi.util.get_file_size')
    @mock.patch('pungi.phases.ostree_installer.iso')
    @mock.patch('os.link')
    @mock.patch('pungi.wrappers.kojiwrapper.KojiWrapper')
    def test_run_external_source(self, KojiWrapper, link, iso,
                                 get_file_size, get_mtime, ImageCls, run):
        pool = mock.Mock()
        cfg = {
            'source_repo_from': 'http://example.com/repo/$arch/',
            'release': '20160321.n.0',
        }
        koji = KojiWrapper.return_value
        koji.run_runroot_cmd.return_value = {
            'task_id': 1234,
            'retcode': 0,
            'output': 'Foo bar\n',
        }
        get_file_size.return_value = 1024
        get_mtime.return_value = 13579
        final_iso_path = self.topdir + '/compose/Everything/x86_64/iso/image-name'

        t = ostree.OstreeInstallerThread(pool)

        t.process((self.compose, self.compose.variants['Everything'], 'x86_64', cfg), 1)

        self.assertRunrootCall(koji, 'http://example.com/repo/x86_64/', cfg['release'], isfinal=True,
                               extra=['--logfile=%s/logs/x86_64/ostree_installer/lorax.log' % self.topdir])
        self.assertIsoLinked(link, get_file_size, get_mtime, final_iso_path)
        self.assertImageAdded(self.compose, ImageCls, iso)
        self.assertAllCopied(run)

    @mock.patch('kobo.shortcuts.run')
    @mock.patch('productmd.images.Image')
    @mock.patch('pungi.util.get_mtime')
    @mock.patch('pungi.util.get_file_size')
    @mock.patch('pungi.phases.ostree_installer.iso')
    @mock.patch('os.link')
    @mock.patch('pungi.wrappers.kojiwrapper.KojiWrapper')
    def test_run_with_repo_key(self, KojiWrapper, link, iso,
                               get_file_size, get_mtime, ImageCls, run):
        pool = mock.Mock()
        cfg = {
            'source_repo_from': 'Everything',
            'release': '20160321.n.0',
            'repo': [
                'https://example.com/extra-repo1.repo',
                'https://example.com/extra-repo2.repo',
            ],
        }
        koji = KojiWrapper.return_value
        koji.run_runroot_cmd.return_value = {
            'task_id': 1234,
            'retcode': 0,
            'output': 'Foo bar\n',
        }

        t = ostree.OstreeInstallerThread(pool)

        t.process((self.compose, self.compose.variants['Everything'], 'x86_64', cfg), 1)

        sources = [
            'file://%s/compose/Everything/x86_64/os' % self.topdir,
            'https://example.com/extra-repo1.repo',
            'https://example.com/extra-repo2.repo'
        ]

        self.assertRunrootCall(koji, sources, cfg['release'], isfinal=True,
                               extra=['--logfile=%s/logs/x86_64/ostree_installer/lorax.log' % self.topdir])

    @mock.patch('kobo.shortcuts.run')
    @mock.patch('productmd.images.Image')
    @mock.patch('pungi.util.get_mtime')
    @mock.patch('pungi.util.get_file_size')
    @mock.patch('pungi.phases.ostree_installer.iso')
    @mock.patch('os.link')
    @mock.patch('pungi.wrappers.kojiwrapper.KojiWrapper')
    def test_run_with_multiple_variant_repos(self, KojiWrapper, link, iso,
                                             get_file_size, get_mtime, ImageCls, run):
        pool = mock.Mock()
        cfg = {
            'source_repo_from': ['Everything', 'Server'],
            'release': '20160321.n.0',
            'repo': [
                'https://example.com/extra-repo1.repo',
                'https://example.com/extra-repo2.repo',
            ],
        }
        koji = KojiWrapper.return_value
        koji.run_runroot_cmd.return_value = {
            'task_id': 1234,
            'retcode': 0,
            'output': 'Foo bar\n',
        }

        t = ostree.OstreeInstallerThread(pool)

        t.process((self.compose, self.compose.variants['Everything'], 'x86_64', cfg), 1)

        sources = [
            'file://%s/compose/Everything/x86_64/os' % self.topdir,
            'file://%s/compose/Server/x86_64/os' % self.topdir,
            'https://example.com/extra-repo1.repo',
            'https://example.com/extra-repo2.repo'
        ]

        self.assertRunrootCall(koji, sources, cfg['release'], isfinal=True,
                               extra=['--logfile=%s/logs/x86_64/ostree_installer/lorax.log' % self.topdir])

    @mock.patch('kobo.shortcuts.run')
    @mock.patch('productmd.images.Image')
    @mock.patch('pungi.util.get_mtime')
    @mock.patch('pungi.util.get_file_size')
    @mock.patch('pungi.wrappers.iso')
    @mock.patch('os.link')
    @mock.patch('pungi.wrappers.kojiwrapper.KojiWrapper')
    def test_fail_with_relative_template_path_but_no_repo(self, KojiWrapper, link,
                                                          iso, get_file_size,
                                                          get_mtime, ImageCls, run):
        pool = mock.Mock()
        cfg = {
            'source_repo_from': 'Everything',
            'release': '20160321.n.0',
            'add_template': ['some-file.txt'],
        }
        koji = KojiWrapper.return_value
        koji.run_runroot_cmd.return_value = {
            'task_id': 1234,
            'retcode': 0,
            'output': 'Foo bar\n',
        }
        get_file_size.return_value = 1024
        get_mtime.return_value = 13579

        t = ostree.OstreeInstallerThread(pool)

        with self.assertRaises(RuntimeError) as ctx:
            t.process((self.compose, self.compose.variants['Everything'], 'x86_64', cfg), 1)

        self.assertIn('template_repo', str(ctx.exception))

    @mock.patch('pungi.wrappers.scm.get_dir_from_scm')
    @mock.patch('kobo.shortcuts.run')
    @mock.patch('productmd.images.Image')
    @mock.patch('pungi.util.get_mtime')
    @mock.patch('pungi.util.get_file_size')
    @mock.patch('pungi.phases.ostree_installer.iso')
    @mock.patch('os.link')
    @mock.patch('pungi.wrappers.kojiwrapper.KojiWrapper')
    def test_run_clone_templates(self, KojiWrapper, link, iso,
                                 get_file_size, get_mtime, ImageCls, run,
                                 get_dir_from_scm):
        pool = mock.Mock()
        cfg = {
            'source_repo_from': 'Everything',
            'release': '20160321.n.0',
            'add_template': ['some_file.txt'],
            'add_arch_template': ['other_file.txt'],
            'template_repo': 'git://example.com/templates.git',
            'template_branch': 'f24',
        }
        koji = KojiWrapper.return_value
        koji.run_runroot_cmd.return_value = {
            'task_id': 1234,
            'retcode': 0,
            'output': 'Foo bar\n',
        }
        get_file_size.return_value = 1024
        get_mtime.return_value = 13579
        final_iso_path = self.topdir + '/compose/Everything/x86_64/iso/image-name'
        templ_dir = self.topdir + '/work/x86_64/Everything/lorax_templates'

        t = ostree.OstreeInstallerThread(pool)

        t.process((self.compose, self.compose.variants['Everything'], 'x86_64', cfg), 1)

        self.assertEqual(get_dir_from_scm.call_args_list,
                         [mock.call({'scm': 'git', 'repo': 'git://example.com/templates.git',
                                     'branch': 'f24', 'dir': '.'},
                                    templ_dir, logger=pool._logger)])
        self.assertRunrootCall(koji,
                               'file://%s/compose/Everything/x86_64/os' % self.topdir,
                               cfg['release'],
                               isfinal=True,
                               extra=['--add-template=%s/some_file.txt' % templ_dir,
                                      '--add-arch-template=%s/other_file.txt' % templ_dir,
                                      '--logfile=%s/logs/x86_64/ostree_installer/lorax.log' % self.topdir])
        self.assertIsoLinked(link, get_file_size, get_mtime, final_iso_path)
        self.assertImageAdded(self.compose, ImageCls, iso)
        self.assertAllCopied(run)

    @mock.patch('kobo.shortcuts.run')
    @mock.patch('productmd.images.Image')
    @mock.patch('pungi.util.get_mtime')
    @mock.patch('pungi.util.get_file_size')
    @mock.patch('pungi.phases.ostree_installer.iso')
    @mock.patch('os.link')
    @mock.patch('pungi.wrappers.kojiwrapper.KojiWrapper')
    def test_run_with_implicit_release(self, KojiWrapper, link, iso,
                                       get_file_size, get_mtime, ImageCls, run):
        pool = mock.Mock()
        cfg = {
            'source_repo_from': 'Everything',
            'release': None,
            "installpkgs": ["fedora-productimg-atomic"],
            "add_template": ["/spin-kickstarts/atomic-installer/lorax-configure-repo.tmpl"],
            "add_template_var": [
                "ostree_osname=fedora-atomic",
                "ostree_ref=fedora-atomic/Rawhide/x86_64/docker-host",
            ],
            "add_arch_template": ["/spin-kickstarts/atomic-installer/lorax-embed-repo.tmpl"],
            "add_arch_template_var": [
                "ostree_repo=https://kojipkgs.fedoraproject.org/compose/atomic/Rawhide/",
                "ostree_osname=fedora-atomic",
                "ostree_ref=fedora-atomic/Rawhide/x86_64/docker-host",
            ],
        }
        self.compose.conf['runroot_weights'] = {'ostree_installer': 123}
        koji = KojiWrapper.return_value
        koji.run_runroot_cmd.return_value = {
            'task_id': 1234,
            'retcode': 0,
            'output': 'Foo bar\n',
        }
        get_file_size.return_value = 1024
        get_mtime.return_value = 13579
        final_iso_path = self.topdir + '/compose/Everything/x86_64/iso/image-name'

        t = ostree.OstreeInstallerThread(pool)

        t.process((self.compose, self.compose.variants['Everything'], 'x86_64', cfg), 1)

        self.assertRunrootCall(
            koji,
            'file://%s/compose/Everything/x86_64/os' % self.topdir,
            '20151203.t.0',
            isfinal=True,
            extra=['--installpkgs=fedora-productimg-atomic',
                   '--add-template=/spin-kickstarts/atomic-installer/lorax-configure-repo.tmpl',
                   '--add-arch-template=/spin-kickstarts/atomic-installer/lorax-embed-repo.tmpl',
                   '--add-template-var=ostree_osname=fedora-atomic',
                   '--add-template-var=ostree_ref=fedora-atomic/Rawhide/x86_64/docker-host',
                   '--add-arch-template-var=ostree_repo=https://kojipkgs.fedoraproject.org/compose/atomic/Rawhide/',
                   '--add-arch-template-var=ostree_osname=fedora-atomic',
                   '--add-arch-template-var=ostree_ref=fedora-atomic/Rawhide/x86_64/docker-host',
                   '--logfile=%s/logs/x86_64/ostree_installer/lorax.log' % self.topdir],
            weight=123,
        )
        self.assertIsoLinked(link, get_file_size, get_mtime, final_iso_path)
        self.assertImageAdded(self.compose, ImageCls, iso)
        self.assertAllCopied(run)

    @mock.patch('kobo.shortcuts.run')
    @mock.patch('productmd.images.Image')
    @mock.patch('pungi.util.get_mtime')
    @mock.patch('pungi.util.get_file_size')
    @mock.patch('pungi.phases.ostree_installer.iso')
    @mock.patch('os.link')
    @mock.patch('pungi.wrappers.kojiwrapper.KojiWrapper')
    def test_fail_crash(self, KojiWrapper, link, iso, get_file_size,
                        get_mtime, ImageCls, run):
        pool = mock.Mock()
        cfg = {
            'source_repo_from': 'Everything',
            'release': None,
            'failable': ['x86_64']
        }
        koji = KojiWrapper.return_value
        koji.run_runroot_cmd.side_effect = helpers.boom

        t = ostree.OstreeInstallerThread(pool)

        t.process((self.compose, self.compose.variants['Everything'], 'x86_64', cfg), 1)
        pool._logger.info.assert_has_calls([
            mock.call('[FAIL] Ostree installer (variant Everything, arch x86_64) failed, but going on anyway.'),
            mock.call('BOOM')
        ])

    @mock.patch('kobo.shortcuts.run')
    @mock.patch('productmd.images.Image')
    @mock.patch('pungi.util.get_mtime')
    @mock.patch('pungi.util.get_file_size')
    @mock.patch('pungi.phases.ostree_installer.iso')
    @mock.patch('os.link')
    @mock.patch('pungi.wrappers.kojiwrapper.KojiWrapper')
    def test_fail_runroot_fail(self, KojiWrapper, link, iso,
                               get_file_size, get_mtime, ImageCls, run):
        pool = mock.Mock()
        cfg = {
            'source_repo_from': 'Everything',
            'release': None,
            'failable': ['*'],
        }
        koji = KojiWrapper.return_value
        koji.run_runroot_cmd.return_value = {
            'output': 'Failed',
            'task_id': 1234,
            'retcode': 1,
        }

        t = ostree.OstreeInstallerThread(pool)

        t.process((self.compose, self.compose.variants['Everything'], 'x86_64', cfg), 1)
        pool._logger.info.assert_has_calls([
            mock.call('[FAIL] Ostree installer (variant Everything, arch x86_64) failed, but going on anyway.'),
            mock.call('Runroot task failed: 1234. See %s/logs/x86_64/ostree_installer/runroot.log for more details.'
                      % self.topdir)
        ])


if __name__ == '__main__':
    unittest.main()
