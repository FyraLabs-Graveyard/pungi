#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import mock
import unittest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests import helpers

from pungi import metadata
from pungi.compose_metadata import discinfo


def mock_time():
    return 101010101.01


class DiscInfoTestCase(helpers.PungiTestCase):

    def setUp(self):
        super(DiscInfoTestCase, self).setUp()
        self.path = os.path.join(self.topdir, 'compose/Server/x86_64/os/.discinfo')

    @mock.patch('time.time', new=mock_time)
    def test_write_discinfo_variant(self):
        compose = helpers.DummyCompose(self.topdir, {
            'release_name': 'Test',
            'release_version': '1.0',
        })

        metadata.write_discinfo(compose, 'x86_64', compose.variants['Server'])

        with open(self.path) as f:
            self.assertEqual(f.read().strip().split('\n'),
                             ['101010101.010000',
                              'Test 1.0',
                              'x86_64',
                              'ALL'])

        self.assertEqual(discinfo.read_discinfo(self.path),
                         {'timestamp': '101010101.010000',
                          'description': 'Test 1.0',
                          'disc_numbers': ['ALL'],
                          'arch': 'x86_64'})

    @mock.patch('time.time', new=mock_time)
    def test_write_discinfo_custom_description(self):
        compose = helpers.DummyCompose(self.topdir, {
            'release_name': 'Test',
            'release_version': '1.0',
            'release_discinfo_description': 'Fuzzy %(variant_name)s.%(arch)s',
        })
        compose.variants['Server'].name = 'Server'

        metadata.write_discinfo(compose, 'x86_64', compose.variants['Server'])

        with open(self.path) as f:
            self.assertEqual(f.read().strip().split('\n'),
                             ['101010101.010000',
                              'Fuzzy Server.x86_64',
                              'x86_64',
                              'ALL'])

    @mock.patch('time.time', new=mock_time)
    def test_write_discinfo_layered_product(self):
        compose = helpers.DummyCompose(self.topdir, {
            'release_name': 'Test',
            'release_version': '1.0',
            'release_is_layered': True,
            'base_product_name': 'Base',
            'base_product_version': 42,
        })

        metadata.write_discinfo(compose, 'x86_64', compose.variants['Server'])

        with open(self.path) as f:
            self.assertEqual(f.read().strip().split('\n'),
                             ['101010101.010000',
                              'Test 1.0 for Base 42',
                              'x86_64',
                              'ALL'])

    @mock.patch('time.time', new=mock_time)
    def test_write_discinfo_integrated_layered_product(self):
        compose = helpers.DummyCompose(self.topdir, {
            'release_name': 'Test',
            'release_version': '1.0',
        })
        compose.variants['ILP'] = mock.Mock(uid='Server', arches=['x86_64'],
                                            type='layered-product', is_empty=False,
                                            release_name='Integrated',
                                            release_version='2.1',
                                            parent=compose.variants['Server'])

        metadata.write_discinfo(compose, 'x86_64', compose.variants['ILP'])

        with open(self.path) as f:
            self.assertEqual(f.read().strip().split('\n'),
                             ['101010101.010000',
                              'Integrated 2.1 for Test 1',
                              'x86_64',
                              'ALL'])

    @mock.patch('time.time', new=mock_time)
    def test_addons_dont_have_discinfo(self):
        compose = helpers.DummyCompose(self.topdir, {
            'release_name': 'Test',
            'release_version': '1.0',
        })
        compose.variants['ILP'] = mock.Mock(uid='Server', arches=['x86_64'],
                                            type='addon', is_empty=False,
                                            parent=compose.variants['Server'])

        metadata.write_discinfo(compose, 'x86_64', compose.variants['ILP'])

        self.assertFalse(os.path.isfile(self.path))


class MediaRepoTestCase(helpers.PungiTestCase):

    def setUp(self):
        super(MediaRepoTestCase, self).setUp()
        self.path = os.path.join(self.topdir, 'compose/Server/x86_64/os/media.repo')

    def test_write_media_repo(self):
        compose = helpers.DummyCompose(self.topdir, {
            'release_name': 'Test',
            'release_version': '1.0',
        })

        metadata.write_media_repo(compose, 'x86_64', compose.variants['Server'],
                                  timestamp=123456)

        with open(self.path) as f:
            lines = f.read().strip().split('\n')
            self.assertEqual(lines[0], '[InstallMedia]')
            self.assertItemsEqual(lines[1:],
                                  ['name=Test 1.0',
                                   'mediaid=123456',
                                   'metadata_expire=-1',
                                   'gpgcheck=0',
                                   'cost=500'])

    def test_addons_dont_have_media_repo(self):
        compose = helpers.DummyCompose(self.topdir, {
            'release_name': 'Test',
            'release_version': '1.0',
        })
        compose.variants['ILP'] = mock.Mock(uid='Server', arches=['x86_64'],
                                            type='addon', is_empty=False,
                                            parent=compose.variants['Server'])

        metadata.write_discinfo(compose, 'x86_64', compose.variants['ILP'])

        self.assertFalse(os.path.isfile(self.path))


if __name__ == "__main__":
    unittest.main()
