#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import mock
import os
import sys
import unittest
import json
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    import modulemd         # noqa
    import pdc_client       # noqa
    HAS_MODULE_SUPPORT = True
except ImportError:
    HAS_MODULE_SUPPORT = False

from pungi.phases.pkgset.sources import source_koji
from tests import helpers

EVENT_INFO = {'id': 15681980, 'ts': 1460956382.81936}
TAG_INFO = {
    "maven_support": False,
    "locked": False,
    "name": "f25",
    "extra": {
        "mock.package_manager": "dnf"
    },
    "perm": None,
    "id": 335,
    "arches": None,
    "maven_include_all": None,
    "perm_id": None
}


class TestGetKojiEvent(helpers.PungiTestCase):

    def setUp(self):
        super(TestGetKojiEvent, self).setUp()
        self.compose = helpers.DummyCompose(self.topdir, {})

        self.event_file = self.topdir + '/work/global/koji-event'

    def test_use_preconfigured_event(self):
        koji_wrapper = mock.Mock()
        self.compose.koji_event = 123456
        self.compose.DEBUG = False

        koji_wrapper.koji_proxy.getEvent.return_value = EVENT_INFO

        event = source_koji.get_koji_event_info(self.compose, koji_wrapper)

        self.assertEqual(event, EVENT_INFO)
        self.assertItemsEqual(
            koji_wrapper.mock_calls,
            [mock.call.koji_proxy.getEvent(123456)])
        with open(self.event_file) as f:
            self.assertEqual(json.load(f), EVENT_INFO)

    def test_gets_last_event(self):
        self.compose.DEBUG = False
        self.compose.koji_event = None
        koji_wrapper = mock.Mock()

        koji_wrapper.koji_proxy.getLastEvent.return_value = EVENT_INFO

        event = source_koji.get_koji_event_info(self.compose, koji_wrapper)

        self.assertEqual(event, EVENT_INFO)
        self.assertItemsEqual(
            koji_wrapper.mock_calls,
            [mock.call.koji_proxy.getLastEvent()])
        with open(self.event_file) as f:
            self.assertEqual(json.load(f), EVENT_INFO)

    def test_gets_last_event_in_debug_mode(self):
        self.compose.DEBUG = True
        self.compose.koji_event = None
        koji_wrapper = mock.Mock()
        helpers.touch(self.event_file, json.dumps(EVENT_INFO))

        event = source_koji.get_koji_event_info(self.compose, koji_wrapper)

        self.assertEqual(event, EVENT_INFO)
        self.assertItemsEqual(koji_wrapper.mock_calls, [])
        with open(self.event_file) as f:
            self.assertEqual(json.load(f), EVENT_INFO)


class TestPopulateGlobalPkgset(helpers.PungiTestCase):
    def setUp(self):
        super(TestPopulateGlobalPkgset, self).setUp()
        self.compose = helpers.DummyCompose(self.topdir, {
            'pkgset_koji_tag': 'f25',
            'sigkeys': mock.Mock(),
        })
        self.compose.DEBUG = False
        self.koji_wrapper = mock.Mock()
        self.pkgset_path = os.path.join(self.topdir, 'work', 'global', 'pkgset_global.pickle')
        self.pdc_module_path = os.path.join(self.topdir, 'work', 'global', 'pdc-module-Server.json')

    @mock.patch('six.moves.cPickle.dumps')
    @mock.patch('pungi.phases.pkgset.pkgsets.KojiPackageSet')
    def test_populate(self, KojiPackageSet, pickle_dumps):

        pickle_dumps.return_value = b'DATA'

        orig_pkgset = KojiPackageSet.return_value

        pkgset = source_koji.populate_global_pkgset(
            self.compose, self.koji_wrapper, '/prefix', 123456)

        self.assertIs(pkgset, orig_pkgset)
        self.assertEqual(
            pkgset.mock_calls,
            [mock.call.populate('f25', 123456, inherit=True,
                                logfile=self.topdir + '/logs/global/packages_from_f25.global.log'),
             mock.call.save_file_list(self.topdir + '/work/global/package_list/global.conf',
                                      remove_path_prefix='/prefix')])
        self.assertItemsEqual(pickle_dumps.call_args_list,
                              [mock.call(orig_pkgset)])
        with open(self.pkgset_path) as f:
            self.assertEqual(f.read(), 'DATA')

    @unittest.skipUnless(HAS_MODULE_SUPPORT, 'Modulemd/pdc_client are not available')   # noqa
    @mock.patch('six.moves.cPickle.dumps')
    @mock.patch('pungi.phases.pkgset.pkgsets.KojiPackageSet')
    @mock.patch('pungi.phases.pkgset.sources.source_koji.get_module')
    @mock.patch('pungi.phases.pkgset.sources.source_koji.get_pdc_client_session')
    @mock.patch('pungi.phases.pkgset.sources.source_koji.modulemd')
    def test_pdc_log(self, modulemd, get_pdc_client_session, get_module, KojiPackageSet, pickle_dumps):

        pickle_dumps.return_value = b'DATA'

        get_module.return_value = {'abc': 'def', 'modulemd': 'sth', 'rpms': ['dummy'], 'koji_tag': 'taggg'}
        for name, variant in self.compose.variants.items():
            variant.get_modules = mock.MagicMock()
            if name == 'Server':
                variant.get_modules.return_value = [{'name': 'a'}]

        source_koji.populate_global_pkgset(
            self.compose, self.koji_wrapper, '/prefix', 123456)
        with open(self.pdc_module_path, 'r') as pdc_f:
            self.assertEqual(json.load(pdc_f),
                             [{"rpms": ["dummy"], "abc": "def", "koji_tag": "taggg", "modulemd": "sth"}])

    @mock.patch('six.moves.cPickle.dumps')
    @mock.patch('pungi.phases.pkgset.pkgsets.KojiPackageSet')
    def test_populate_with_multiple_koji_tags(self, KojiPackageSet, pickle_dumps):
        self.compose = helpers.DummyCompose(self.topdir, {
            'pkgset_koji_tag': ['f25', 'f25-extra'],
            'sigkeys': mock.Mock(),
        })
        self.compose.DEBUG = False

        pickle_dumps.return_value = b'DATA'

        orig_pkgset = KojiPackageSet.return_value

        pkgset = source_koji.populate_global_pkgset(
            self.compose, self.koji_wrapper, '/prefix', 123456)

        self.assertIs(pkgset, orig_pkgset)
        pkgset.assert_has_calls([mock.call.populate('f25', 123456, inherit=True,
                                                    logfile=self.topdir + '/logs/global/packages_from_f25.global.log')])
        pkgset.assert_has_calls([mock.call.populate('f25-extra', 123456, inherit=True,
                                                    logfile=self.topdir + '/logs/global/packages_from_f25-extra.global.log')])
        pkgset.assert_has_calls([mock.call.save_file_list(self.topdir + '/work/global/package_list/global.conf',
                                                          remove_path_prefix='/prefix')])
        # for each tag, call pkgset.fast_merge once for each variant and once for global pkgset
        self.assertEqual(pkgset.fast_merge.call_count, 2 * (len(self.compose.all_variants.values()) + 1))
        self.assertItemsEqual(pickle_dumps.call_args_list,
                              [mock.call(orig_pkgset)])
        with open(self.pkgset_path) as f:
            self.assertEqual(f.read(), 'DATA')

    @mock.patch('six.moves.cPickle.load')
    def test_populate_in_debug_mode(self, pickle_load):
        helpers.touch(self.pkgset_path, 'DATA')
        self.compose.DEBUG = True

        pickle_load.return_value

        with mock.patch('pungi.phases.pkgset.sources.source_koji.open',
                        mock.mock_open(), create=True) as m:
            pkgset = source_koji.populate_global_pkgset(
                self.compose, self.koji_wrapper, '/prefix', 123456)

        self.assertEqual(pickle_load.call_args_list,
                         [mock.call(m.return_value)])
        self.assertIs(pkgset, pickle_load.return_value)
        self.assertEqual(
            pkgset.mock_calls,
            [mock.call.save_file_list(self.topdir + '/work/global/package_list/global.conf',
                                      remove_path_prefix='/prefix')])

    @mock.patch('six.moves.cPickle.dumps')
    @mock.patch('pungi.phases.pkgset.pkgsets.KojiPackageSet.populate')
    @mock.patch('pungi.phases.pkgset.pkgsets.KojiPackageSet.save_file_list')
    def test_populate_packages_to_gather(self, save_file_list, popuplate,
                                         pickle_dumps):
        self.compose = helpers.DummyCompose(self.topdir, {
            'gather_method': 'nodeps',
            'pkgset_koji_tag': 'f25',
            'sigkeys': mock.Mock(),
            'additional_packages': [
                ('.*', {'*': ['pkg', 'foo.x86_64']}),
            ]
        })
        self.compose.DEBUG = False
        pickle_dumps.return_value = b'DATA'

        pkgset = source_koji.populate_global_pkgset(
            self.compose, self.koji_wrapper, '/prefix', 123456)
        self.assertItemsEqual(pkgset.packages, ["pkg", "foo"])


class TestGetPackageSetFromKoji(helpers.PungiTestCase):
    def setUp(self):
        super(TestGetPackageSetFromKoji, self).setUp()
        self.compose = helpers.DummyCompose(self.topdir, {
            'pkgset_koji_tag': 'f25',
        })
        self.compose.koji_event = None
        self.compose.DEBUG = False
        self.koji_wrapper = mock.Mock()
        self.koji_wrapper.koji_proxy.getLastEvent.return_value = EVENT_INFO
        self.koji_wrapper.koji_proxy.getTag.return_value = TAG_INFO

    @mock.patch('pungi.phases.pkgset.sources.source_koji.create_arch_repos')
    @mock.patch('pungi.phases.pkgset.sources.source_koji.create_global_repo')
    @mock.patch('pungi.phases.pkgset.sources.source_koji.populate_arch_pkgsets')
    @mock.patch('pungi.phases.pkgset.sources.source_koji.populate_global_pkgset')
    def test_get_package_sets(self, pgp, pap, cgr, car):
        expected = {'x86_64': mock.Mock()}
        pap.return_value = expected
        expected['global'] = pgp.return_value

        pkgsets = source_koji.get_pkgset_from_koji(self.compose, self.koji_wrapper, '/prefix')

        self.assertItemsEqual(
            self.koji_wrapper.koji_proxy.mock_calls,
            [mock.call.getLastEvent()]
        )

        self.assertEqual(pgp.call_args_list,
                         [mock.call(self.compose, self.koji_wrapper, '/prefix',
                                    EVENT_INFO)])
        self.assertEqual(pap.call_args_list,
                         [mock.call(self.compose, '/prefix', pgp.return_value)])
        self.assertEqual(cgr.call_args_list,
                         [mock.call(self.compose, '/prefix')])
        self.assertItemsEqual(car.call_args_list,
                              [mock.call(self.compose, 'x86_64', '/prefix'),
                               mock.call(self.compose, 'amd64', '/prefix')])

        self.assertEqual(pkgsets, expected)


class TestSourceKoji(helpers.PungiTestCase):

    @mock.patch('pungi.phases.pkgset.sources.source_koji.get_pkgset_from_koji')
    @mock.patch('pungi.wrappers.kojiwrapper.KojiWrapper')
    def test_run(self, KojiWrapper, gpfk):
        compose = helpers.DummyCompose(self.topdir, {
            'koji_profile': 'koji'
        })
        KojiWrapper.return_value.koji_module.config.topdir = '/prefix'

        phase = source_koji.PkgsetSourceKoji(compose)
        pkgsets, path_prefix = phase()

        self.assertEqual(pkgsets, gpfk.return_value)
        self.assertEqual(path_prefix, '/prefix/')
        self.assertItemsEqual(KojiWrapper.mock_calls,
                              [mock.call('koji')])


class TestCorrectNVR(helpers.PungiTestCase):

    def setUp(self):
        super(TestCorrectNVR, self).setUp()
        self.compose = helpers.DummyCompose(self.topdir, {})
        self.nv = "base-runtime-f26"
        self.nvr = "base-runtime-f26-20170502134116"
        self.release_regex = re.compile("^(\d){14}$")
        self.new_nv = "base-runtime:f26"
        self.new_nvr = "base-runtime:f26:20170502134116"
        self.new_nvrc = "base-runtime:f26:20170502134116:0123abcd"

    def test_nv(self):
        module_info = source_koji.variant_dict_from_str(self.compose, self.nv)
        expectedKeys = ["variant_version", "variant_id", "variant_type"]
        self.assertItemsEqual(module_info.keys(), expectedKeys)

    def test_nvr(self):
        module_info = source_koji.variant_dict_from_str(self.compose, self.nvr)
        expectedKeys = ["variant_version", "variant_id", "variant_type", "variant_release"]
        self.assertItemsEqual(module_info.keys(), expectedKeys)

    def test_correct_release(self):
        module_info = source_koji.variant_dict_from_str(self.compose, self.nvr)
        self.assertIsNotNone(self.release_regex.match(module_info["variant_release"]))

    def test_new_nv(self):
        module_info = source_koji.variant_dict_from_str(self.compose, self.new_nv)
        expected = {
            'variant_id': 'base-runtime',
            'variant_type': 'module',
            'variant_version': 'f26'}

        self.assertEqual(module_info, expected)

    def test_new_nvr(self):
        module_info = source_koji.variant_dict_from_str(self.compose, self.new_nvr)
        expected = {
            'variant_id': 'base-runtime',
            'variant_type': 'module',
            'variant_version': 'f26',
            'variant_release': '20170502134116'}
        self.assertEqual(module_info, expected)

    def test_new_nvrc(self):
        self.assertRaises(ValueError, source_koji.variant_dict_from_str,
                          self.compose, self.new_nvrc)

if __name__ == "__main__":
    unittest.main()
