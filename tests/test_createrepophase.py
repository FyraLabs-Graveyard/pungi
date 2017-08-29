#!/usr/bin/env python2
# -*- coding: utf-8 -*-


try:
    import unittest2 as unittest
except ImportError:
    import unittest
import mock

import glob
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi.phases.createrepo import (CreaterepoPhase,
                                     create_variant_repo,
                                     get_productids_from_scm)
from tests.helpers import DummyCompose, PungiTestCase, copy_fixture, touch


class TestCreaterepoPhase(PungiTestCase):
    @mock.patch('pungi.phases.createrepo.ThreadPool')
    def test_fails_deltas_without_old_compose(self, ThreadPoolCls):
        compose = DummyCompose(self.topdir, {
            'createrepo_checksum': 'sha256',
            'createrepo_deltas': True,
        })

        phase = CreaterepoPhase(compose)
        with self.assertRaises(ValueError) as ctx:
            phase.validate()

        self.assertIn('deltas', str(ctx.exception))

    @mock.patch('pungi.phases.createrepo.ThreadPool')
    def test_starts_jobs(self, ThreadPoolCls):
        compose = DummyCompose(self.topdir, {})

        pool = ThreadPoolCls.return_value

        phase = CreaterepoPhase(compose)
        phase.run()
        self.maxDiff = None

        self.assertEqual(len(pool.add.mock_calls), 3)
        self.assertItemsEqual(
            pool.queue_put.mock_calls,
            [mock.call((compose, 'x86_64', compose.variants['Server'], 'rpm')),
             mock.call((compose, 'x86_64', compose.variants['Server'], 'debuginfo')),
             mock.call((compose, 'amd64', compose.variants['Server'], 'rpm')),
             mock.call((compose, 'amd64', compose.variants['Server'], 'debuginfo')),
             mock.call((compose, None, compose.variants['Server'], 'srpm')),
             mock.call((compose, 'x86_64', compose.variants['Everything'], 'rpm')),
             mock.call((compose, 'x86_64', compose.variants['Everything'], 'debuginfo')),
             mock.call((compose, 'amd64', compose.variants['Everything'], 'rpm')),
             mock.call((compose, 'amd64', compose.variants['Everything'], 'debuginfo')),
             mock.call((compose, None, compose.variants['Everything'], 'srpm')),
             mock.call((compose, 'amd64', compose.variants['Client'], 'rpm')),
             mock.call((compose, 'amd64', compose.variants['Client'], 'debuginfo')),
             mock.call((compose, None, compose.variants['Client'], 'srpm'))])

    @mock.patch('pungi.phases.createrepo.ThreadPool')
    def test_skips_empty_variants(self, ThreadPoolCls):
        compose = DummyCompose(self.topdir, {})
        compose.variants['Client'].is_empty = True

        pool = ThreadPoolCls.return_value

        phase = CreaterepoPhase(compose)
        phase.run()
        self.maxDiff = None

        self.assertEqual(len(pool.add.mock_calls), 3)
        self.assertItemsEqual(
            pool.queue_put.mock_calls,
            [mock.call((compose, 'x86_64', compose.variants['Server'], 'rpm')),
             mock.call((compose, 'x86_64', compose.variants['Server'], 'debuginfo')),
             mock.call((compose, 'amd64', compose.variants['Server'], 'rpm')),
             mock.call((compose, 'amd64', compose.variants['Server'], 'debuginfo')),
             mock.call((compose, None, compose.variants['Server'], 'srpm')),
             mock.call((compose, 'x86_64', compose.variants['Everything'], 'rpm')),
             mock.call((compose, 'x86_64', compose.variants['Everything'], 'debuginfo')),
             mock.call((compose, 'amd64', compose.variants['Everything'], 'rpm')),
             mock.call((compose, 'amd64', compose.variants['Everything'], 'debuginfo')),
             mock.call((compose, None, compose.variants['Everything'], 'srpm'))])


class TestCreateVariantRepo(PungiTestCase):

    @mock.patch('pungi.phases.createrepo.run')
    @mock.patch('pungi.phases.createrepo.CreaterepoWrapper')
    def test_variant_repo_rpms(self, CreaterepoWrapperCls, run):
        compose = DummyCompose(self.topdir, {
            'createrepo_checksum': 'sha256',
        })
        compose.DEBUG = False
        compose.has_comps = False

        repo = CreaterepoWrapperCls.return_value
        copy_fixture('server-rpms.json', compose.paths.compose.metadata('rpms.json'))

        create_variant_repo(compose, 'x86_64', compose.variants['Server'], 'rpm')

        list_file = self.topdir + '/work/x86_64/repo_package_list/Server.x86_64.rpm.conf'
        self.assertEqual(CreaterepoWrapperCls.mock_calls[0],
                         mock.call(createrepo_c=True))
        self.assertItemsEqual(
            repo.get_createrepo_cmd.mock_calls,
            [mock.call(self.topdir + '/compose/Server/x86_64/os', checksum='sha256',
                       database=True, groupfile=None, workers=3,
                       outputdir=self.topdir + '/compose/Server/x86_64/os',
                       pkglist=list_file, skip_stat=True, update=True,
                       update_md_path=self.topdir + '/work/x86_64/repo',
                       deltas=False, oldpackagedirs=None, use_xz=False)])
        self.assertItemsEqual(
            repo.get_modifyrepo_cmd.mock_calls,
            [])
        with open(list_file) as f:
            self.assertEqual(f.read(), 'Packages/b/bash-4.3.30-2.fc21.x86_64.rpm\n')

    @mock.patch('pungi.phases.createrepo.run')
    @mock.patch('pungi.phases.createrepo.CreaterepoWrapper')
    def test_variant_repo_source(self, CreaterepoWrapperCls, run):
        compose = DummyCompose(self.topdir, {
            'createrepo_checksum': 'sha256',
        })
        compose.DEBUG = False
        compose.has_comps = False

        repo = CreaterepoWrapperCls.return_value
        copy_fixture('server-rpms.json', compose.paths.compose.metadata('rpms.json'))

        create_variant_repo(compose, None, compose.variants['Server'], 'srpm')

        list_file = self.topdir + '/work/global/repo_package_list/Server.None.srpm.conf'
        self.assertEqual(CreaterepoWrapperCls.mock_calls[0],
                         mock.call(createrepo_c=True))
        self.assertItemsEqual(
            repo.get_createrepo_cmd.mock_calls,
            [mock.call(self.topdir + '/compose/Server/source/tree', checksum='sha256',
                       database=True, groupfile=None, workers=3,
                       outputdir=self.topdir + '/compose/Server/source/tree',
                       pkglist=list_file, skip_stat=True, update=True,
                       update_md_path=self.topdir + '/work/global/repo',
                       deltas=False, oldpackagedirs=None, use_xz=False)])
        self.assertItemsEqual(
            repo.get_modifyrepo_cmd.mock_calls,
            [])
        with open(list_file) as f:
            self.assertItemsEqual(
                f.read().strip().split('\n'),
                ['Packages/b/bash-4.3.30-2.fc21.src.rpm'])

    @mock.patch('pungi.phases.createrepo.run')
    @mock.patch('pungi.phases.createrepo.CreaterepoWrapper')
    def test_variant_repo_debug(self, CreaterepoWrapperCls, run):
        compose = DummyCompose(self.topdir, {
            'createrepo_checksum': 'sha256',
        })
        compose.DEBUG = False
        compose.has_comps = False

        repo = CreaterepoWrapperCls.return_value
        copy_fixture('server-rpms.json', compose.paths.compose.metadata('rpms.json'))

        create_variant_repo(compose, 'x86_64', compose.variants['Server'], 'debuginfo')
        self.maxDiff = None

        list_file = self.topdir + '/work/x86_64/repo_package_list/Server.x86_64.debuginfo.conf'
        self.assertEqual(CreaterepoWrapperCls.mock_calls[0],
                         mock.call(createrepo_c=True))
        self.assertItemsEqual(
            repo.get_createrepo_cmd.mock_calls,
            [mock.call(self.topdir + '/compose/Server/x86_64/debug/tree', checksum='sha256',
                       database=True, groupfile=None, workers=3,
                       outputdir=self.topdir + '/compose/Server/x86_64/debug/tree',
                       pkglist=list_file, skip_stat=True, update=True,
                       update_md_path=self.topdir + '/work/x86_64/repo',
                       deltas=False, oldpackagedirs=None, use_xz=False)])
        self.assertItemsEqual(
            repo.get_modifyrepo_cmd.mock_calls,
            [])
        with open(list_file) as f:
            self.assertEqual(f.read(), 'Packages/b/bash-debuginfo-4.3.30-2.fc21.x86_64.rpm\n')

    @mock.patch('pungi.phases.createrepo.run')
    @mock.patch('pungi.phases.createrepo.CreaterepoWrapper')
    def test_variant_repo_no_createrepo_c(self, CreaterepoWrapperCls, run):
        compose = DummyCompose(self.topdir, {
            'createrepo_c': False,
            'createrepo_checksum': 'sha256',
        })
        compose.DEBUG = False
        compose.has_comps = False

        repo = CreaterepoWrapperCls.return_value
        copy_fixture('server-rpms.json', compose.paths.compose.metadata('rpms.json'))

        create_variant_repo(compose, 'x86_64', compose.variants['Server'], 'rpm')

        list_file = self.topdir + '/work/x86_64/repo_package_list/Server.x86_64.rpm.conf'
        self.assertEqual(CreaterepoWrapperCls.mock_calls[0],
                         mock.call(createrepo_c=False))
        self.assertItemsEqual(
            repo.get_createrepo_cmd.mock_calls,
            [mock.call(self.topdir + '/compose/Server/x86_64/os', checksum='sha256',
                       database=True, groupfile=None, workers=3,
                       outputdir=self.topdir + '/compose/Server/x86_64/os',
                       pkglist=list_file, skip_stat=True, update=True,
                       update_md_path=self.topdir + '/work/x86_64/repo',
                       deltas=False, oldpackagedirs=None, use_xz=False)])
        self.assertItemsEqual(
            repo.get_modifyrepo_cmd.mock_calls,
            [])
        with open(list_file) as f:
            self.assertEqual(f.read(), 'Packages/b/bash-4.3.30-2.fc21.x86_64.rpm\n')

    @mock.patch('pungi.phases.createrepo.run')
    @mock.patch('pungi.phases.createrepo.CreaterepoWrapper')
    def test_variant_repo_is_idepotent(self, CreaterepoWrapperCls, run):
        compose = DummyCompose(self.topdir, {
            'createrepo_checksum': 'sha256',
        })
        compose.DEBUG = False
        compose.has_comps = False

        repo = CreaterepoWrapperCls.return_value
        copy_fixture('server-rpms.json', compose.paths.compose.metadata('rpms.json'))

        # Running the same thing twice only creates repo once.
        create_variant_repo(compose, 'x86_64', compose.variants['Server'], 'rpm')
        create_variant_repo(compose, 'x86_64', compose.variants['Server'], 'rpm')

        list_file = self.topdir + '/work/x86_64/repo_package_list/Server.x86_64.rpm.conf'
        self.assertEqual(CreaterepoWrapperCls.mock_calls[0],
                         mock.call(createrepo_c=True))
        self.assertItemsEqual(
            repo.get_createrepo_cmd.mock_calls,
            [mock.call(self.topdir + '/compose/Server/x86_64/os', checksum='sha256',
                       database=True, groupfile=None, workers=3,
                       outputdir=self.topdir + '/compose/Server/x86_64/os',
                       pkglist=list_file, skip_stat=True, update=True,
                       update_md_path=self.topdir + '/work/x86_64/repo',
                       deltas=False, oldpackagedirs=None, use_xz=False)])
        self.assertItemsEqual(
            repo.get_modifyrepo_cmd.mock_calls,
            [])
        with open(list_file) as f:
            self.assertEqual(f.read(), 'Packages/b/bash-4.3.30-2.fc21.x86_64.rpm\n')

    @mock.patch('pungi.phases.createrepo.run')
    @mock.patch('pungi.phases.createrepo.CreaterepoWrapper')
    def test_variant_repo_rpms_with_xz(self, CreaterepoWrapperCls, run):
        compose = DummyCompose(self.topdir, {
            'createrepo_checksum': 'sha256',
            'createrepo_use_xz': True,
        })
        compose.DEBUG = False
        compose.has_comps = False

        repo = CreaterepoWrapperCls.return_value
        copy_fixture('server-rpms.json', compose.paths.compose.metadata('rpms.json'))

        create_variant_repo(compose, 'x86_64', compose.variants['Server'], 'rpm')

        list_file = self.topdir + '/work/x86_64/repo_package_list/Server.x86_64.rpm.conf'
        self.assertEqual(CreaterepoWrapperCls.mock_calls[0],
                         mock.call(createrepo_c=True))
        self.assertItemsEqual(
            repo.get_createrepo_cmd.mock_calls,
            [mock.call(self.topdir + '/compose/Server/x86_64/os', checksum='sha256',
                       database=True, groupfile=None, workers=3,
                       outputdir=self.topdir + '/compose/Server/x86_64/os',
                       pkglist=list_file, skip_stat=True, update=True,
                       update_md_path=self.topdir + '/work/x86_64/repo', deltas=False,
                       oldpackagedirs=None, use_xz=True)])
        self.assertItemsEqual(
            repo.get_modifyrepo_cmd.mock_calls,
            [])
        with open(list_file) as f:
            self.assertEqual(f.read(), 'Packages/b/bash-4.3.30-2.fc21.x86_64.rpm\n')

    @mock.patch('pungi.phases.createrepo.run')
    @mock.patch('pungi.phases.createrepo.CreaterepoWrapper')
    def test_variant_repo_rpms_with_deltas(self, CreaterepoWrapperCls, run):
        compose = DummyCompose(self.topdir, {
            'createrepo_checksum': 'sha256',
            'createrepo_deltas': True,
        })
        compose.DEBUG = False
        compose.has_comps = False
        compose.old_composes = [self.topdir + '/old']
        touch(os.path.join(self.topdir, 'old', 'test-1.0-20151203.0', 'STATUS'), 'FINISHED')

        repo = CreaterepoWrapperCls.return_value
        copy_fixture('server-rpms.json', compose.paths.compose.metadata('rpms.json'))

        create_variant_repo(compose, 'x86_64', compose.variants['Server'], 'rpm')

        list_file = self.topdir + '/work/x86_64/repo_package_list/Server.x86_64.rpm.conf'
        self.assertEqual(CreaterepoWrapperCls.mock_calls[0],
                         mock.call(createrepo_c=True))
        self.assertItemsEqual(
            repo.get_createrepo_cmd.mock_calls,
            [mock.call(self.topdir + '/compose/Server/x86_64/os', checksum='sha256',
                       database=True, groupfile=None, workers=3,
                       outputdir=self.topdir + '/compose/Server/x86_64/os',
                       pkglist=list_file, skip_stat=True, update=True,
                       update_md_path=None, deltas=True,
                       oldpackagedirs=self.topdir + '/old/test-1.0-20151203.0/compose/Server/x86_64/os/Packages',
                       use_xz=False)])
        self.assertItemsEqual(
            repo.get_modifyrepo_cmd.mock_calls,
            [])
        with open(list_file) as f:
            self.assertEqual(f.read(), 'Packages/b/bash-4.3.30-2.fc21.x86_64.rpm\n')

    @mock.patch('pungi.phases.createrepo.run')
    @mock.patch('pungi.phases.createrepo.CreaterepoWrapper')
    def test_variant_repo_rpms_with_deltas_hashed_dirs(self, CreaterepoWrapperCls, run):
        compose = DummyCompose(self.topdir, {
            'createrepo_checksum': 'sha256',
            'createrepo_deltas': True,
            'hashed_directories': True,
        })
        compose.DEBUG = False
        compose.has_comps = False
        compose.old_composes = [self.topdir + '/old']
        touch(os.path.join(self.topdir, 'old', 'test-1.0-20151203.0', 'STATUS'), 'FINISHED')
        self.maxDiff = None

        for f in ['a/a.rpm', 'b/b.rpm', 'foo']:
            touch(self.topdir + '/old/test-1.0-20151203.0/compose/Server/x86_64/os/Packages/' + f)

        repo = CreaterepoWrapperCls.return_value
        copy_fixture('server-rpms.json', compose.paths.compose.metadata('rpms.json'))

        create_variant_repo(compose, 'x86_64', compose.variants['Server'], 'rpm')

        list_file = self.topdir + '/work/x86_64/repo_package_list/Server.x86_64.rpm.conf'
        self.assertEqual(CreaterepoWrapperCls.mock_calls[0],
                         mock.call(createrepo_c=True))
        self.assertItemsEqual(
            repo.get_createrepo_cmd.mock_calls,
            [mock.call(self.topdir + '/compose/Server/x86_64/os', checksum='sha256',
                       database=True, groupfile=None, workers=3,
                       outputdir=self.topdir + '/compose/Server/x86_64/os',
                       pkglist=list_file, skip_stat=True, update=True,
                       update_md_path=None, deltas=True,
                       oldpackagedirs=[
                           self.topdir + '/old/test-1.0-20151203.0/compose/Server/x86_64/os/Packages/a',
                           self.topdir + '/old/test-1.0-20151203.0/compose/Server/x86_64/os/Packages/b',
                       ],
                       use_xz=False)])
        self.assertItemsEqual(
            repo.get_modifyrepo_cmd.mock_calls,
            [])
        with open(list_file) as f:
            self.assertEqual(f.read(), 'Packages/b/bash-4.3.30-2.fc21.x86_64.rpm\n')

    @mock.patch('pungi.phases.createrepo.run')
    @mock.patch('pungi.phases.createrepo.CreaterepoWrapper')
    def test_variant_repo_rpms_with_deltas_hashed_dirs_but_old_doesnt_exist(self, CreaterepoWrapperCls, run):
        compose = DummyCompose(self.topdir, {
            'createrepo_checksum': 'sha256',
            'createrepo_deltas': True,
            'hashed_directories': True,
        })
        compose.DEBUG = False
        compose.has_comps = False
        compose.old_composes = [self.topdir + '/old']
        touch(os.path.join(self.topdir, 'old', 'test-1.0-20151203.0', 'STATUS'), 'FINISHED')
        self.maxDiff = None

        repo = CreaterepoWrapperCls.return_value
        copy_fixture('server-rpms.json', compose.paths.compose.metadata('rpms.json'))

        create_variant_repo(compose, 'x86_64', compose.variants['Server'], 'rpm')

        list_file = self.topdir + '/work/x86_64/repo_package_list/Server.x86_64.rpm.conf'
        self.assertEqual(CreaterepoWrapperCls.mock_calls[0],
                         mock.call(createrepo_c=True))
        self.assertItemsEqual(
            repo.get_createrepo_cmd.mock_calls,
            [mock.call(self.topdir + '/compose/Server/x86_64/os', checksum='sha256',
                       database=True, groupfile=None, workers=3,
                       outputdir=self.topdir + '/compose/Server/x86_64/os',
                       pkglist=list_file, skip_stat=True, update=True,
                       update_md_path=self.topdir + '/work/x86_64/repo', deltas=True,
                       oldpackagedirs=[],
                       use_xz=False)])
        self.assertItemsEqual(
            repo.get_modifyrepo_cmd.mock_calls,
            [])
        with open(list_file) as f:
            self.assertEqual(f.read(), 'Packages/b/bash-4.3.30-2.fc21.x86_64.rpm\n')

    @mock.patch('pungi.phases.createrepo.run')
    @mock.patch('pungi.phases.createrepo.CreaterepoWrapper')
    def test_variant_repo_source_with_deltas(self, CreaterepoWrapperCls, run):
        # This should not actually create deltas, only binary repos do.
        compose = DummyCompose(self.topdir, {
            'createrepo_checksum': 'sha256',
            'createrepo_deltas': True,
        })
        compose.DEBUG = False
        compose.has_comps = False
        compose.old_composes = [self.topdir + '/old']
        touch(os.path.join(self.topdir, 'old', 'test-1.0-20151203.0', 'STATUS'), 'FINISHED')

        repo = CreaterepoWrapperCls.return_value
        copy_fixture('server-rpms.json', compose.paths.compose.metadata('rpms.json'))

        create_variant_repo(compose, None, compose.variants['Server'], 'srpm')

        list_file = self.topdir + '/work/global/repo_package_list/Server.None.srpm.conf'
        self.assertEqual(CreaterepoWrapperCls.mock_calls[0],
                         mock.call(createrepo_c=True))
        self.assertItemsEqual(
            repo.get_createrepo_cmd.mock_calls,
            [mock.call(self.topdir + '/compose/Server/source/tree', checksum='sha256',
                       database=True, groupfile=None, workers=3,
                       outputdir=self.topdir + '/compose/Server/source/tree',
                       pkglist=list_file, skip_stat=True, update=True,
                       update_md_path=self.topdir + '/work/global/repo',
                       deltas=False, oldpackagedirs=None, use_xz=False)])
        self.assertItemsEqual(
            repo.get_modifyrepo_cmd.mock_calls,
            [])
        with open(list_file) as f:
            self.assertItemsEqual(
                f.read().strip().split('\n'),
                ['Packages/b/bash-4.3.30-2.fc21.src.rpm'])

    @mock.patch('pungi.phases.createrepo.run')
    @mock.patch('pungi.phases.createrepo.CreaterepoWrapper')
    def test_variant_repo_debug_with_deltas(self, CreaterepoWrapperCls, run):
        # This should not actually create deltas, only binary repos do.
        compose = DummyCompose(self.topdir, {
            'createrepo_checksum': 'sha256',
            'createrepo_deltas': True,
        })
        compose.DEBUG = False
        compose.has_comps = False
        compose.old_composes = [self.topdir + '/old']
        touch(os.path.join(self.topdir, 'old', 'test-1.0-20151203.0', 'STATUS'), 'FINISHED')

        repo = CreaterepoWrapperCls.return_value
        copy_fixture('server-rpms.json', compose.paths.compose.metadata('rpms.json'))

        create_variant_repo(compose, 'x86_64', compose.variants['Server'], 'debuginfo')

        list_file = self.topdir + '/work/x86_64/repo_package_list/Server.x86_64.debuginfo.conf'
        self.assertEqual(CreaterepoWrapperCls.mock_calls[0],
                         mock.call(createrepo_c=True))
        self.assertItemsEqual(
            repo.get_createrepo_cmd.mock_calls,
            [mock.call(self.topdir + '/compose/Server/x86_64/debug/tree', checksum='sha256',
                       database=True, groupfile=None, workers=3,
                       outputdir=self.topdir + '/compose/Server/x86_64/debug/tree',
                       pkglist=list_file, skip_stat=True, update=True,
                       update_md_path=self.topdir + '/work/x86_64/repo',
                       deltas=False, oldpackagedirs=None, use_xz=False)])
        self.assertItemsEqual(
            repo.get_modifyrepo_cmd.mock_calls,
            [])
        with open(list_file) as f:
            self.assertEqual(f.read(), 'Packages/b/bash-debuginfo-4.3.30-2.fc21.x86_64.rpm\n')

    @mock.patch('pungi.phases.createrepo.run')
    @mock.patch('pungi.phases.createrepo.CreaterepoWrapper')
    def test_variant_repo_rpms_with_productid(self, CreaterepoWrapperCls, run):
        compose = DummyCompose(self.topdir, {
            'createrepo_checksum': 'sha256',
            'product_id': 'yes',    # Truthy value is enough for this test
        })
        compose.DEBUG = False
        compose.has_comps = False
        product_id = compose.paths.work.product_id('x86_64', compose.variants['Server'])
        repodata_dir = os.path.join(
            compose.paths.compose.os_tree('x86_64', compose.variants['Server']),
            'repodata')
        touch(product_id)
        os.mkdir(repodata_dir)

        repo = CreaterepoWrapperCls.return_value
        copy_fixture('server-rpms.json', compose.paths.compose.metadata('rpms.json'))

        create_variant_repo(compose, 'x86_64', compose.variants['Server'], 'rpm')

        self.maxDiff = None
        list_file = self.topdir + '/work/x86_64/repo_package_list/Server.x86_64.rpm.conf'
        self.assertEqual(CreaterepoWrapperCls.mock_calls[0],
                         mock.call(createrepo_c=True))
        self.assertItemsEqual(
            repo.get_createrepo_cmd.mock_calls,
            [mock.call(self.topdir + '/compose/Server/x86_64/os', checksum='sha256',
                       database=True, groupfile=None, workers=3,
                       outputdir=self.topdir + '/compose/Server/x86_64/os',
                       pkglist=list_file, skip_stat=True, update=True,
                       update_md_path=self.topdir + '/work/x86_64/repo', deltas=False,
                       oldpackagedirs=None,
                       use_xz=False)])
        self.assertItemsEqual(
            repo.get_modifyrepo_cmd.mock_calls,
            [mock.call(repodata_dir, product_id, compress_type='gz')])
        with open(list_file) as f:
            self.assertEqual(f.read(), 'Packages/b/bash-4.3.30-2.fc21.x86_64.rpm\n')

    @mock.patch('pungi.phases.createrepo.run')
    @mock.patch('pungi.phases.createrepo.CreaterepoWrapper')
    def test_variant_repo_debug_with_productid(self, CreaterepoWrapperCls, run):
        compose = DummyCompose(self.topdir, {
            'createrepo_checksum': 'sha256',
            'product_id': 'yes',    # Truthy value is enough for this test
        })
        compose.DEBUG = False
        compose.has_comps = False

        repo = CreaterepoWrapperCls.return_value
        copy_fixture('server-rpms.json', compose.paths.compose.metadata('rpms.json'))

        create_variant_repo(compose, 'x86_64', compose.variants['Server'], 'debuginfo')

        self.maxDiff = None
        list_file = self.topdir + '/work/x86_64/repo_package_list/Server.x86_64.debuginfo.conf'
        self.assertEqual(CreaterepoWrapperCls.mock_calls[0],
                         mock.call(createrepo_c=True))
        self.assertItemsEqual(
            repo.get_createrepo_cmd.mock_calls,
            [mock.call(self.topdir + '/compose/Server/x86_64/debug/tree', checksum='sha256',
                       database=True, groupfile=None, workers=3,
                       outputdir=self.topdir + '/compose/Server/x86_64/debug/tree',
                       pkglist=list_file, skip_stat=True, update=True,
                       update_md_path=self.topdir + '/work/x86_64/repo', deltas=False,
                       oldpackagedirs=None,
                       use_xz=False)])
        self.assertItemsEqual(repo.get_modifyrepo_cmd.mock_calls, [])
        with open(list_file) as f:
            self.assertEqual(f.read(), 'Packages/b/bash-debuginfo-4.3.30-2.fc21.x86_64.rpm\n')

    @mock.patch('pungi.phases.createrepo.run')
    @mock.patch('pungi.phases.createrepo.CreaterepoWrapper')
    def test_variant_repo_source_with_productid(self, CreaterepoWrapperCls, run):
        compose = DummyCompose(self.topdir, {
            'createrepo_checksum': 'sha256',
            'product_id': 'yes',    # Truthy value is enough for this test
        })
        compose.DEBUG = False
        compose.has_comps = False

        repo = CreaterepoWrapperCls.return_value
        copy_fixture('server-rpms.json', compose.paths.compose.metadata('rpms.json'))

        create_variant_repo(compose, None, compose.variants['Server'], 'srpm')

        self.maxDiff = None
        list_file = self.topdir + '/work/global/repo_package_list/Server.None.srpm.conf'
        self.assertEqual(CreaterepoWrapperCls.mock_calls[0],
                         mock.call(createrepo_c=True))
        self.assertItemsEqual(
            repo.get_createrepo_cmd.mock_calls,
            [mock.call(self.topdir + '/compose/Server/source/tree', checksum='sha256',
                       database=True, groupfile=None, workers=3,
                       outputdir=self.topdir + '/compose/Server/source/tree',
                       pkglist=list_file, skip_stat=True, update=True,
                       update_md_path=self.topdir + '/work/global/repo', deltas=False,
                       oldpackagedirs=None,
                       use_xz=False)])
        self.assertItemsEqual(repo.get_modifyrepo_cmd.mock_calls, [])
        with open(list_file) as f:
            self.assertEqual(f.read(), 'Packages/b/bash-4.3.30-2.fc21.src.rpm\n')


class ANYSingleton(object):
    """An object that is equal to anything."""
    def __eq__(self, another):
        return True

    def __repr__(self):
        return u'ANY'

ANY = ANYSingleton()


class TestGetProductIds(PungiTestCase):
    def mock_get(self, filenames):
        def _mock_get(scm, dest):
            for filename in filenames:
                touch(os.path.join(dest, filename))
        return _mock_get

    def assertProductIds(self, mapping):
        pids = glob.glob(self.compose.paths.work.product_id('*', '*'))
        expected = set()
        for variant, arches in mapping.iteritems():
            for arch in arches:
                expected.add(os.path.join(self.topdir, 'work', arch,
                                          'product_id',
                                          '%s.%s.pem' % (variant, arch),
                                          'productid'))
        self.assertItemsEqual(pids, expected)

    @mock.patch('pungi.phases.createrepo.get_dir_from_scm')
    def test_not_configured(self, get_dir_from_scm):
        self.compose = DummyCompose(self.topdir, {})
        get_productids_from_scm(self.compose)
        self.assertEqual(get_dir_from_scm.call_args_list, [])
        self.assertProductIds({})

    @mock.patch('pungi.phases.createrepo.get_dir_from_scm')
    def test_correct(self, get_dir_from_scm):
        cfg = mock.Mock()
        self.compose = DummyCompose(self.topdir, {
            'product_id': cfg,
        })
        get_dir_from_scm.side_effect = self.mock_get([
            'Client-amd64-cert.pem',
            'Everything-amd64-cert.pem',
            'Server-amd64-cert.pem',
            'Everything-x86_64-cert.pem',
            'Server-x86_64-cert.pem',
        ])

        get_productids_from_scm(self.compose)

        self.assertEqual(get_dir_from_scm.call_args_list, [mock.call(cfg, ANY)])
        self.assertProductIds({
            'Client': ['amd64'],
            'Everything': ['amd64', 'x86_64'],
            'Server': ['amd64', 'x86_64'],
        })

    @mock.patch('pungi.phases.createrepo.get_dir_from_scm')
    def test_allow_missing(self, get_dir_from_scm):
        cfg = mock.Mock()
        self.compose = DummyCompose(self.topdir, {
            'product_id': cfg,
            'product_id_allow_missing': True,
        })
        get_dir_from_scm.side_effect = self.mock_get([
            'Server-amd64-cert.pem',
            'Server-x86_64-cert.pem',
        ])

        get_productids_from_scm(self.compose)

        self.assertEqual(get_dir_from_scm.call_args_list, [mock.call(cfg, ANY)])
        self.assertProductIds({
            'Server': ['amd64', 'x86_64'],
        })

    @mock.patch('pungi.phases.createrepo.get_dir_from_scm')
    def test_missing_fails(self, get_dir_from_scm):
        cfg = mock.Mock()
        self.compose = DummyCompose(self.topdir, {
            'product_id': cfg,
        })
        get_dir_from_scm.side_effect = self.mock_get([
            'Server-amd64-cert.pem',
            'Server-x86_64-cert.pem',
        ])

        with self.assertRaises(RuntimeError) as ctx:
            get_productids_from_scm(self.compose)

        self.assertEqual(get_dir_from_scm.call_args_list, [mock.call(cfg, ANY)])
        self.assertEqual(str(ctx.exception),
                         'No product certificate found (arch: amd64, variant: Everything)')

    @mock.patch('pungi.phases.createrepo.get_dir_from_scm')
    def test_multiple_matching(self, get_dir_from_scm):
        cfg = mock.Mock()
        self.compose = DummyCompose(self.topdir, {
            'product_id': cfg,
        })
        get_dir_from_scm.side_effect = self.mock_get([
            'Client-amd64-cert.pem',
            'Client-amd64-cert-duplicate.pem',
            'Everything-amd64-cert.pem',
            'Server-amd64-cert.pem',
            'Everything-x86_64-cert.pem',
            'Server-x86_64-cert.pem',
        ])

        with self.assertRaises(RuntimeError) as ctx:
            get_productids_from_scm(self.compose)

        self.assertEqual(get_dir_from_scm.call_args_list, [mock.call(cfg, ANY)])
        self.assertRegexpMatches(str(ctx.exception),
                                 'Multiple product certificates found.+')


if __name__ == "__main__":
    unittest.main()
