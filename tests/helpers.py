# -*- coding: utf-8 -*-

import mock
import os
try:
    import unittest2 as unittest
except ImportError:
    import unittest
import tempfile
import shutil
import errno

from pungi.util import get_arch_variant_data
from pungi import paths, checks


class PungiTestCase(unittest.TestCase):
    def setUp(self):
        self.topdir = tempfile.mkdtemp()

    def tearDown(self):
        try:
            shutil.rmtree(self.topdir)
        except OSError as err:
            if err.errno != errno.ENOENT:
                raise

    def assertValidConfig(self, conf):
        self.assertEqual(checks.validate(conf), ([], []))


class MockVariant(mock.Mock):
    def __init__(self, *args, **kwargs):
        super(MockVariant, self).__init__(*args, **kwargs)
        self.parent = kwargs.get('parent', None)
        self.mmds = []

    def __str__(self):
        return self.uid


class IterableMock(mock.Mock):
    def __iter__(self):
        return iter([])


class DummyCompose(object):
    def __init__(self, topdir, config):
        self.supported = True
        self.compose_date = '20151203'
        self.compose_type_suffix = '.t'
        self.compose_type = 'test'
        self.compose_respin = 0
        self.compose_id = 'Test-20151203.0.t'
        self.compose_label = None
        self.compose_label_major_version = None
        self.image_release = '20151203.t.0'
        self.image_version = '25'
        self.ci_base = mock.Mock(
            release_id='Test-1.0',
            release=mock.Mock(
                short='test',
                version='1.0',
                is_layered=False,
            ),
        )
        self.topdir = topdir
        self.conf = load_config(PKGSET_REPOS, **config)
        checks.validate(self.conf)
        self.paths = paths.Paths(self)
        self._logger = mock.Mock()
        self.variants = {
            'Server': MockVariant(uid='Server', arches=['x86_64', 'amd64'],
                                  type='variant', is_empty=False),
            'Client': MockVariant(uid='Client', arches=['amd64'],
                                  type='variant', is_empty=False),
            'Everything': MockVariant(uid='Everything', arches=['x86_64', 'amd64'],
                                      type='variant', is_empty=False),
        }
        self.all_variants = self.variants.copy()

        # for PhaseLoggerMixin
        self._logger = mock.Mock()
        self._logger.handlers = [mock.Mock()]

        self.log_info = mock.Mock()
        self.log_error = mock.Mock()
        self.log_debug = mock.Mock()
        self.log_warning = mock.Mock()
        self.get_image_name = mock.Mock(return_value='image-name')
        self.image = mock.Mock(path='Client/i386/iso/image.iso', can_fail=False)
        self.im = mock.Mock(images={'Client': {'amd64': [self.image]}})
        self.old_composes = []
        self.config_dir = '/home/releng/config'
        self.notifier = None
        self.attempt_deliverable = mock.Mock()
        self.fail_deliverable = mock.Mock()
        self.require_deliverable = mock.Mock()

    def setup_optional(self):
        self.all_variants['Server-optional'] = MockVariant(
            uid='Server-optional', arches=['x86_64'], type='optional', is_empty=False)
        self.all_variants['Server-optional'].parent = self.variants['Server']
        self.variants['Server'].variants = {'optional': self.all_variants['Server-optional']}

    def get_variants(self, arch=None, types=None):
        return [v for v in self.all_variants.values() if not arch or arch in v.arches]

    def can_fail(self, variant, arch, deliverable):
        failable = get_arch_variant_data(self.conf, 'failable_deliverables', arch, variant)
        return deliverable in failable

    def get_arches(self):
        result = set()
        for variant in self.variants.itervalues():
            result |= set(variant.arches)
        return sorted(result)

    def mkdtemp(self, suffix="", prefix="tmp"):
        return tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=self.topdir)


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
    return path


FIXTURE_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


def copy_fixture(fixture_name, dest):
    src = os.path.join(FIXTURE_DIR, fixture_name)
    touch(dest)
    shutil.copy2(src, dest)


def boom(*args, **kwargs):
    raise Exception('BOOM')


PKGSET_REPOS = dict(
    pkgset_source='repos',
    pkgset_repos={},
)

BASE_CONFIG = dict(
    release_short='test',
    release_name='Test',
    release_version='1.0',
    release_is_layered=False,
    variants_file='variants.xml',
    runroot=False,
    createrepo_checksum='sha256',
    gather_method='deps',
    gather_source='none',
    sigkeys=[],
)


def load_config(data={}, **kwargs):
    conf = dict()
    conf.update(BASE_CONFIG)
    conf.update(data)
    conf.update(kwargs)
    return conf
