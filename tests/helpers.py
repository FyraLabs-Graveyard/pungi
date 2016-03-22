# -*- coding: utf-8 -*-

import mock
import os
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


class DummyCompose(object):
    def __init__(self, topdir, config):
        self.supported = True
        self.compose_date = '20151203'
        self.compose_type_suffix = '.t'
        self.compose_respin = 0
        self.compose_id = 'Test-20151203.0.t'
        self.compose_label = None
        self.image_release = '20151203.t.0'
        self.ci_base = mock.Mock(
            release_id='Test-1.0',
            release=mock.Mock(
                short='test',
                version='1.0',
                is_layered=False,
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
        self.log_info = mock.Mock()
        self.log_error = mock.Mock()
        self.log_debug = mock.Mock()
        self.log_warning = mock.Mock()
        self.get_image_name = mock.Mock(return_value='image-name')
        self.image = mock.Mock(path='Client/i386/iso/image.iso')
        self.im = mock.Mock(images={'Client': {'i386': [self.image]}})
        self.old_composes = []
        self.config_dir = '/home/releng/config'

    def get_variants(self, arch=None, types=None):
        return [v for v in self.variants.values() if not arch or arch in v.arches]

    def can_fail(self, variant, arch, deliverable):
        failable = get_arch_variant_data(self.conf, 'failable_deliverables', arch, variant)
        return deliverable in failable

    def get_arches(self):
        result = set()
        for variant in self.variants.itervalues():
            result |= set(variant.arches)
        return result


def touch(path, content=None):
    """Helper utility that creates an dummy file in given location. Directories
    will be created."""
    content = content or (path + '\n')
    try:
        os.makedirs(os.path.dirname(path))
    except OSError:
        pass
    with open(path, 'w') as f:
        f.write(content)


def copy_fixture(fixture_name, dest):
    src = os.path.join(os.path.dirname(__file__), 'fixtures', fixture_name)
    touch(dest)
    shutil.copy2(src, dest)


def union(*args):
    """Create a new dict as a union of all arguments."""
    res = {}
    for arg in args:
        res.update(arg)
    return res
