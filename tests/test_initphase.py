#!/usr/bin/env python
# -*- coding: utf-8 -*-


import unittest
import mock

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi.phases import init
from tests.helpers import DummyCompose, PungiTestCase, touch, union

MIN_CONFIG = {
    'release_short': 'Fedora',
    'release_name': 'Fedora',
    'release_version': 'Rawhide',
    'release_is_layered': False,
    'variants_file': 'does-not-exist.xml',
    'sigkeys': [],
    'createrepo_checksum': 'sha256',
    'runroot': False,
}


class TestInitPhase(PungiTestCase):

    @mock.patch('pungi.phases.init.write_global_comps')
    @mock.patch('pungi.phases.init.write_arch_comps')
    @mock.patch('pungi.phases.init.create_comps_repo')
    @mock.patch('pungi.phases.init.write_variant_comps')
    @mock.patch('pungi.phases.init.write_prepopulate_file')
    def test_run(self, write_prepopulate, write_variant, create_comps, write_arch, write_global):
        compose = DummyCompose(self.topdir, {})
        phase = init.InitPhase(compose)
        phase.run()

        self.assertEqual(write_global.mock_calls, [mock.call(compose)])
        self.assertEqual(write_prepopulate.mock_calls, [mock.call(compose)])
        self.assertItemsEqual(write_arch.mock_calls,
                              [mock.call(compose, 'x86_64'), mock.call(compose, 'amd64')])
        self.assertItemsEqual(create_comps.mock_calls,
                              [mock.call(compose, 'x86_64'), mock.call(compose, 'amd64')])
        self.assertItemsEqual(write_variant.mock_calls,
                              [mock.call(compose, 'x86_64', compose.variants['Server']),
                               mock.call(compose, 'amd64', compose.variants['Server']),
                               mock.call(compose, 'amd64', compose.variants['Client']),
                               mock.call(compose, 'x86_64', compose.variants['Everything']),
                               mock.call(compose, 'amd64', compose.variants['Everything'])])

    @mock.patch('pungi.phases.init.copy_variant_comps')
    @mock.patch('pungi.phases.init.write_global_comps')
    @mock.patch('pungi.phases.init.write_arch_comps')
    @mock.patch('pungi.phases.init.create_comps_repo')
    @mock.patch('pungi.phases.init.write_variant_comps')
    @mock.patch('pungi.phases.init.write_prepopulate_file')
    def test_run_with_preserve(self, write_prepopulate, write_variant, create_comps,
                               write_arch, write_global, copy_comps):
        compose = DummyCompose(self.topdir, {
            'keep_original_comps': ['Everything'],
        })
        phase = init.InitPhase(compose)
        phase.run()

        self.assertEqual(write_global.mock_calls, [mock.call(compose)])
        self.assertEqual(write_prepopulate.mock_calls, [mock.call(compose)])
        self.assertItemsEqual(write_arch.mock_calls,
                              [mock.call(compose, 'x86_64'), mock.call(compose, 'amd64')])
        self.assertItemsEqual(create_comps.mock_calls,
                              [mock.call(compose, 'x86_64'), mock.call(compose, 'amd64')])
        self.assertItemsEqual(write_variant.mock_calls,
                              [mock.call(compose, 'x86_64', compose.variants['Server']),
                               mock.call(compose, 'amd64', compose.variants['Server']),
                               mock.call(compose, 'amd64', compose.variants['Client'])])
        self.assertItemsEqual(copy_comps.mock_calls,
                              [mock.call(compose, 'x86_64', compose.variants['Everything']),
                               mock.call(compose, 'amd64', compose.variants['Everything'])])

    def test_validate_keep_original_comps_missing(self):
        compose = DummyCompose(self.topdir, MIN_CONFIG)
        phase = init.InitPhase(compose)
        phase.validate()

    def test_validate_keep_original_comps_empty(self):
        config = union(MIN_CONFIG, {'keep_original_comps': []})
        compose = DummyCompose(self.topdir, config)
        phase = init.InitPhase(compose)
        phase.validate()

    def test_validate_keep_original_comps_filled_in(self):
        config = union(MIN_CONFIG, {'keep_original_comps': ['Everything']})
        compose = DummyCompose(self.topdir, config)
        phase = init.InitPhase(compose)
        phase.validate()


class TestWriteArchComps(PungiTestCase):

    @mock.patch('pungi.phases.init.run')
    def test_does_not_run_without_comps(self, run):
        compose = DummyCompose(self.topdir, {})
        compose.has_comps = False

        init.write_arch_comps(compose, 'x86_64')

        self.assertEqual(run.mock_calls, [])

    @mock.patch('pungi.phases.init.run')
    def test_run(self, run):
        compose = DummyCompose(self.topdir, {})
        compose.has_comps = True
        compose.DEBUG = False

        init.write_arch_comps(compose, 'x86_64')

        self.assertEqual(run.mock_calls,
                         [mock.call(['comps_filter', '--arch=x86_64', '--no-cleanup',
                                     '--output=%s/work/x86_64/comps/comps-x86_64.xml' % self.topdir,
                                     self.topdir + '/work/global/comps/comps-global.xml'])])

    @mock.patch('pungi.phases.init.run')
    def test_run_in_debug(self, run):
        compose = DummyCompose(self.topdir, {})
        compose.has_comps = True
        compose.DEBUG = True
        touch(self.topdir + '/work/x86_64/comps/comps-x86_64.xml')

        init.write_arch_comps(compose, 'x86_64')

        self.assertEqual(run.mock_calls, [])


class TestCreateCompsRepo(PungiTestCase):

    @mock.patch('pungi.phases.init.run')
    def test_does_not_run_without_comps(self, run):
        compose = DummyCompose(self.topdir, {})
        compose.has_comps = False

        init.create_comps_repo(compose, 'x86_64')

        self.assertEqual(run.mock_calls, [])

    @mock.patch('pungi.phases.init.run')
    def test_run(self, run):
        compose = DummyCompose(self.topdir, {
            'createrepo_checksum': 'sha256',
        })
        compose.has_comps = True
        compose.DEBUG = False

        init.create_comps_repo(compose, 'x86_64')

        self.assertEqual(run.mock_calls,
                         [mock.call(['createrepo_c', self.topdir + '/work/x86_64/comps_repo',
                                     '--outputdir=%s/work/x86_64/comps_repo' % self.topdir,
                                     '--groupfile=%s/work/x86_64/comps/comps-x86_64.xml' % self.topdir,
                                     '--update', '--skip-stat', '--database', '--checksum=sha256',
                                     '--unique-md-filenames'],
                                    logfile=self.topdir + '/logs/global/arch_repo.global.log',
                                    show_cmd=True)])

    @mock.patch('pungi.phases.init.run')
    def test_run_in_debug(self, run):
        compose = DummyCompose(self.topdir, {
            'createrepo_checksum': 'sha256',
        })
        compose.has_comps = True
        compose.DEBUG = True
        os.makedirs(self.topdir + '/work/x86_64/comps_repo/repodata')

        init.create_comps_repo(compose, 'x86_64')

        self.assertEqual(run.mock_calls, [])


class TestWriteGlobalComps(PungiTestCase):

    @mock.patch('shutil.copy2')
    @mock.patch('pungi.phases.init.get_file_from_scm')
    def test_does_not_run_without_comps(self, get_file, copy2):
        compose = DummyCompose(self.topdir, {'comps_file': 'some-file.xml'})
        compose.has_comps = False

        init.write_global_comps(compose)

        self.assertEqual(get_file.mock_calls, [])
        self.assertEqual(copy2.mock_calls, [])

    @mock.patch('shutil.copy2')
    @mock.patch('pungi.phases.init.get_file_from_scm')
    def test_run_in_debug(self, get_file, copy2):
        compose = DummyCompose(self.topdir, {'comps_file': 'some-file.xml'})
        compose.has_comps = True
        compose.DEBUG = True
        touch(self.topdir + '/work/global/comps/comps-global.xml')

        init.write_global_comps(compose)

        self.assertEqual(get_file.mock_calls, [])
        self.assertEqual(copy2.mock_calls, [])

    @mock.patch('pungi.phases.init.get_file_from_scm')
    def test_run_local_file(self, get_file):
        compose = DummyCompose(self.topdir, {'comps_file': 'some-file.xml'})
        compose.has_comps = True
        compose.DEBUG = False

        def gen_file(src, dest, logger=None):
            self.assertEqual(src, '/home/releng/config/some-file.xml')
            touch(os.path.join(dest, 'some-file.xml'))

        get_file.side_effect = gen_file

        init.write_global_comps(compose)

        self.assertTrue(os.path.isfile(self.topdir + '/work/global/comps/comps-global.xml'))


class TestWriteVariantComps(PungiTestCase):

    @mock.patch('pungi.phases.init.run')
    def test_does_not_run_without_comps(self, run):
        compose = DummyCompose(self.topdir, {})
        compose.has_comps = False

        init.write_variant_comps(compose, 'x86_64', compose.variants['Server'])

        self.assertEqual(run.mock_calls, [])

    @mock.patch('pungi.phases.init.run')
    @mock.patch('pungi.phases.init.CompsWrapper')
    def test_run(self, CompsWrapper, run):
        compose = DummyCompose(self.topdir, {})
        compose.has_comps = True
        compose.DEBUG = False
        variant = compose.variants['Server']

        init.write_variant_comps(compose, 'x86_64', variant)

        self.assertEqual(run.mock_calls,
                         [mock.call(['comps_filter', '--arch=x86_64', '--keep-empty-group=conflicts',
                                     '--keep-empty-group=conflicts-server',
                                     '--output=%s/work/x86_64/comps/comps-Server.x86_64.xml' % self.topdir,
                                     self.topdir + '/work/global/comps/comps-global.xml'])])
        self.assertEqual(CompsWrapper.call_args_list,
                         [mock.call(self.topdir + '/work/x86_64/comps/comps-Server.x86_64.xml')])
        comps = CompsWrapper.return_value
        self.assertEqual(comps.filter_groups.mock_calls, [mock.call(variant.groups)])
        self.assertEqual(comps.filter_environments.mock_calls,
                         [mock.call(variant.environments)])
        self.assertEqual(comps.write_comps.mock_calls, [mock.call()])

    @mock.patch('pungi.phases.init.run')
    @mock.patch('pungi.phases.init.CompsWrapper')
    def test_run_in_debug(self, CompsWrapper, run):
        compose = DummyCompose(self.topdir, {})
        compose.has_comps = True
        compose.DEBUG = True
        variant = compose.variants['Server']
        touch(self.topdir + '/work/x86_64/comps/comps-Server.x86_64.xml')

        init.write_variant_comps(compose, 'x86_64', variant)

        self.assertEqual(run.mock_calls, [])
        self.assertEqual(CompsWrapper.call_args_list,
                         [mock.call(self.topdir + '/work/x86_64/comps/comps-Server.x86_64.xml')])
        comps = CompsWrapper.return_value
        self.assertEqual(comps.filter_groups.mock_calls, [mock.call(variant.groups)])
        self.assertEqual(comps.filter_environments.mock_calls,
                         [mock.call(variant.environments)])
        self.assertEqual(comps.write_comps.mock_calls, [])


class TestCopyVariantComps(PungiTestCase):

    @mock.patch('shutil.copy')
    def test_does_not_run_without_comps(self, copy):
        compose = DummyCompose(self.topdir, {})
        compose.has_comps = False

        init.copy_variant_comps(compose, 'x86_64', compose.variants['Server'])

        self.assertEqual(copy.mock_calls, [])

    @mock.patch('shutil.copy')
    def test_run(self, copy):
        compose = DummyCompose(self.topdir, {})
        compose.has_comps = True
        variant = compose.variants['Server']

        init.copy_variant_comps(compose, 'x86_64', variant)

        self.assertEqual(copy.mock_calls,
                         [mock.call(self.topdir + '/work/global/comps/comps-global.xml',
                                    self.topdir + '/work/x86_64/comps/comps-Server.x86_64.xml')])


if __name__ == "__main__":
    unittest.main()
