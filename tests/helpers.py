# -*- coding: utf-8 -*-

import mock
import unittest
import tempfile
import shutil

from pungi.util import get_arch_variant_data
from pungi import paths


class PungiTestCase(unittest.TestCase):
    def setUp(self):
        self.topdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.topdir)


class _DummyCompose(object):
    def __init__(self, topdir, config):
        self.compose_date = '20151203'
        self.compose_type_suffix = '.t'
        self.compose_respin = 0
        self.compose_id = 'Test-20151203.0.t'
        self.ci_base = mock.Mock(
            release_id='Test-1.0',
            release=mock.Mock(
                short='test',
                version='1.0',
            ),
        )
        self.topdir = topdir
        self.conf = config
        self.paths = paths.Paths(self)
        self._logger = mock.Mock()
        self.variants = {
            'Server': mock.Mock(uid='Server', arches=['x86_64', 'amd64'],
                                type='variant', is_empty=False),
            'Client': mock.Mock(uid='Client', arches=['amd64'],
                                type='variant', is_empty=False),
            'Everything': mock.Mock(uid='Everything', arches=['x86_64', 'amd64'],
                                    type='variant', is_empty=False),
        }
        self.log_error = mock.Mock()
        self.get_image_name = mock.Mock(return_value='image-name')
        self.image = mock.Mock(path='Client/i386/iso/image.iso')
        self.im = mock.Mock(images={'Client': {'i386': [self.image]}})

    def get_variants(self, arch=None, types=None):
        return [v for v in self.variants.values() if not arch or arch in v.arches]

    def can_fail(self, variant, arch, deliverable):
        failable = get_arch_variant_data(self.conf, 'failable_deliverables', arch, variant)
        return deliverable in failable
