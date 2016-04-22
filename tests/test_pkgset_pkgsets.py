#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import mock
import os
import sys
import unittest
import json
import functools

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi.phases.pkgset import pkgsets
from tests import helpers


class MockPathInfo(object):
    def __init__(self, topdir):
        self.topdir = topdir

    def build(self, build_info):
        return self.topdir

    def get_filename(self, rpm_info):
        return '{name}@{version}@{release}@{arch}'.format(**rpm_info)

    def signed(self, rpm_info, sigkey):
        return os.path.join('signed', sigkey, self.get_filename(rpm_info))

    def rpm(self, rpm_info):
        return os.path.join('rpms', self.get_filename(rpm_info))


@functools.total_ordering
class MockFile(object):
    def __init__(self, path):
        if path.startswith('/tmp'):
            # Drop /tmp/something/ from path
            path = path.split('/', 3)[-1]
        self.file_path = path
        self.file_name = os.path.basename(path)
        self.name, self.version, self.release, self.arch = self.file_name.split('@')
        self.sourcerpm = '{0.name}-{0.version}-{0.release}.{0.arch}'.format(self)
        self.exclusivearch = []
        self.excludearch = []

    def __hash__(self):
        return hash(self.file_path)

    def __repr__(self):
        return self.file_path

    def __eq__(self, other):
        try:
            return self.file_path == other.file_path
        except AttributeError:
            return self.file_path == other

    def __le__(self, other):
        try:
            return self.file_path < other.file_path
        except AttributeError:
            return self.file_path < other


class MockFileCache(dict):
    """Mock for kobo.pkgset.FileCache.
    It gets data from filename and does not touch filesystem.
    """
    def __init__(self, _wrapper):
        super(MockFileCache, self).__init__()

    def add(self, file_path):
        obj = MockFile(file_path)
        self[file_path] = obj
        return obj


class FakePool(object):
    """This class will be substituted for ReaderPool.
    It implements the same interface, but uses only the last added worker to
    process all tasks sequentially.
    """
    def __init__(self, package_set, logger=None):
        self.queue = []
        self.worker = None
        self.package_set = package_set

    def log_warning(self, *args, **kwargs):
        pass

    @property
    def queue_total(self):
        return len(self.queue)

    def queue_put(self, item):
        self.queue.append(item)

    def add(self, worker):
        self.worker = worker

    def start(self):
        for i, item in enumerate(self.queue):
            self.worker.process(item, i)

    def stop(self):
        pass


class PkgsetCompareMixin(object):
    def assertPkgsetEqual(self, actual, expected):
        for k, v1 in expected.iteritems():
            self.assertIn(k, actual)
            v2 = actual.pop(k)
            self.assertItemsEqual(v1, v2)
        self.assertEqual({}, actual)


@mock.patch('pungi.phases.pkgset.pkgsets.ReaderPool', new=FakePool)
@mock.patch('kobo.pkgset.FileCache', new=MockFileCache)
class TestKojiPkgset(PkgsetCompareMixin, helpers.PungiTestCase):

    def setUp(self):
        super(TestKojiPkgset, self).setUp()
        with open(os.path.join(helpers.FIXTURE_DIR, 'tagged-rpms.json')) as f:
            self.tagged_rpms = json.load(f)

        self.path_info = MockPathInfo(self.topdir)

        self.koji_wrapper = mock.Mock()
        self.koji_wrapper.koji_proxy.listTaggedRPMS.return_value = self.tagged_rpms
        self.koji_wrapper.koji_module.pathinfo = self.path_info

    def _touch_files(self, filenames):
        for filename in filenames:
            helpers.touch(os.path.join(self.topdir, filename))

    def assertPkgsetEqual(self, actual, expected):
        for k, v1 in expected.iteritems():
            self.assertIn(k, actual)
            v2 = actual.pop(k)
            self.assertItemsEqual(v1, v2)
        self.assertEqual({}, actual, msg='Some architectures were missing')

    def test_all_arches(self):
        self._touch_files([
            'rpms/pungi@4.1.3@3.fc25@noarch',
            'rpms/pungi@4.1.3@3.fc25@src',
            'rpms/bash@4.3.42@4.fc24@i686',
            'rpms/bash@4.3.42@4.fc24@x86_64',
            'rpms/bash@4.3.42@4.fc24@src',
            'rpms/bash-debuginfo@4.3.42@4.fc24@i686',
            'rpms/bash-debuginfo@4.3.42@4.fc24@x86_64',
        ])

        pkgset = pkgsets.KojiPackageSet(self.koji_wrapper, [None])

        result = pkgset.populate('f25')

        self.assertEqual(
            self.koji_wrapper.koji_proxy.mock_calls,
            [mock.call.listTaggedRPMS('f25', event=None, inherit=True, latest=True)])

        self.assertPkgsetEqual(result,
                               {'src': ['rpms/pungi@4.1.3@3.fc25@src',
                                        'rpms/bash@4.3.42@4.fc24@src'],
                                'noarch': ['rpms/pungi@4.1.3@3.fc25@noarch'],
                                'i686': ['rpms/bash@4.3.42@4.fc24@i686',
                                         'rpms/bash-debuginfo@4.3.42@4.fc24@i686'],
                                'x86_64': ['rpms/bash@4.3.42@4.fc24@x86_64',
                                           'rpms/bash-debuginfo@4.3.42@4.fc24@x86_64']})

    def test_only_one_arch(self):
        self._touch_files([
            'rpms/bash@4.3.42@4.fc24@x86_64',
            'rpms/bash-debuginfo@4.3.42@4.fc24@x86_64',
        ])

        pkgset = pkgsets.KojiPackageSet(self.koji_wrapper, [None], arches=['x86_64'])

        result = pkgset.populate('f25')

        self.assertEqual(
            self.koji_wrapper.koji_proxy.mock_calls,
            [mock.call.listTaggedRPMS('f25', event=None, inherit=True, latest=True)])

        self.assertPkgsetEqual(result,
                               {'x86_64': ['rpms/bash-debuginfo@4.3.42@4.fc24@x86_64',
                                           'rpms/bash@4.3.42@4.fc24@x86_64']})

    def test_find_signed_with_preference(self):
        self._touch_files([
            'signed/cafebabe/bash@4.3.42@4.fc24@x86_64',
            'signed/deadbeef/bash@4.3.42@4.fc24@x86_64',
            'signed/deadbeef/bash-debuginfo@4.3.42@4.fc24@x86_64',
        ])

        pkgset = pkgsets.KojiPackageSet(self.koji_wrapper, ['cafebabe', 'deadbeef'], arches=['x86_64'])

        result = pkgset.populate('f25')

        self.assertEqual(
            self.koji_wrapper.koji_proxy.mock_calls,
            [mock.call.listTaggedRPMS('f25', event=None, inherit=True, latest=True)])

        self.assertPkgsetEqual(result,
                               {'x86_64': ['signed/cafebabe/bash@4.3.42@4.fc24@x86_64',
                                           'signed/deadbeef/bash-debuginfo@4.3.42@4.fc24@x86_64']})

    def test_find_signed_fallback_unsigned(self):
        self._touch_files([
            'signed/cafebabe/bash@4.3.42@4.fc24@x86_64',
            'rpms/bash-debuginfo@4.3.42@4.fc24@x86_64',
        ])

        pkgset = pkgsets.KojiPackageSet(self.koji_wrapper, ['cafebabe', None], arches=['x86_64'])

        result = pkgset.populate('f25')

        self.assertEqual(
            self.koji_wrapper.koji_proxy.mock_calls,
            [mock.call.listTaggedRPMS('f25', event=None, inherit=True, latest=True)])

        self.assertPkgsetEqual(result,
                               {'x86_64': ['rpms/bash-debuginfo@4.3.42@4.fc24@x86_64',
                                           'signed/cafebabe/bash@4.3.42@4.fc24@x86_64']})


@mock.patch('kobo.pkgset.FileCache', new=MockFileCache)
class TestMergePackageSets(PkgsetCompareMixin, unittest.TestCase):
    def test_merge_in_another_arch(self):
        first = pkgsets.PackageSetBase([None])
        second = pkgsets.PackageSetBase([None])

        for name in ['rpms/pungi@4.1.3@3.fc25@noarch', 'rpms/pungi@4.1.3@3.fc25@src']:
            pkg = first.file_cache.add(name)
            first.rpms_by_arch.setdefault(pkg.arch, []).append(pkg)

        for name in ['rpms/bash@4.3.42@4.fc24@i686']:
            pkg = second.file_cache.add(name)
            second.rpms_by_arch.setdefault(pkg.arch, []).append(pkg)

        first.merge(second, 'i386', ['i686'])

        self.assertPkgsetEqual(first.rpms_by_arch,
                               {'src': ['rpms/pungi@4.1.3@3.fc25@src'],
                                'noarch': ['rpms/pungi@4.1.3@3.fc25@noarch'],
                                'i686': ['rpms/bash@4.3.42@4.fc24@i686']})

    def test_merge_includes_noarch_with_different_exclude_arch(self):
        first = pkgsets.PackageSetBase([None])
        second = pkgsets.PackageSetBase([None])

        pkg = first.file_cache.add('rpms/bash@4.3.42@4.fc24@i686')
        first.rpms_by_arch.setdefault(pkg.arch, []).append(pkg)

        pkg = second.file_cache.add('rpms/pungi@4.1.3@3.fc25@noarch')
        pkg.excludearch = ['x86_64']
        second.rpms_by_arch.setdefault(pkg.arch, []).append(pkg)

        first.merge(second, 'i386', ['i686', 'noarch'])

        self.assertPkgsetEqual(first.rpms_by_arch,
                               {'i686': ['rpms/bash@4.3.42@4.fc24@i686'],
                                'noarch': ['rpms/pungi@4.1.3@3.fc25@noarch']})

    def test_merge_excludes_noarch_exclude_arch(self):
        first = pkgsets.PackageSetBase([None])
        second = pkgsets.PackageSetBase([None])

        pkg = first.file_cache.add('rpms/bash@4.3.42@4.fc24@i686')
        first.rpms_by_arch.setdefault(pkg.arch, []).append(pkg)

        pkg = second.file_cache.add('rpms/pungi@4.1.3@3.fc25@noarch')
        pkg.excludearch = ['i686']
        second.rpms_by_arch.setdefault(pkg.arch, []).append(pkg)

        first.merge(second, 'i386', ['i686', 'noarch'])

        self.assertPkgsetEqual(first.rpms_by_arch,
                               {'i686': ['rpms/bash@4.3.42@4.fc24@i686'],
                                'noarch': []})

    def test_merge_excludes_noarch_exclusive_arch(self):
        first = pkgsets.PackageSetBase([None])
        second = pkgsets.PackageSetBase([None])

        pkg = first.file_cache.add('rpms/bash@4.3.42@4.fc24@i686')
        first.rpms_by_arch.setdefault(pkg.arch, []).append(pkg)

        pkg = second.file_cache.add('rpms/pungi@4.1.3@3.fc25@noarch')
        pkg.exclusivearch = ['x86_64']
        second.rpms_by_arch.setdefault(pkg.arch, []).append(pkg)

        first.merge(second, 'i386', ['i686', 'noarch'])

        self.assertPkgsetEqual(first.rpms_by_arch,
                               {'i686': ['rpms/bash@4.3.42@4.fc24@i686'],
                                'noarch': []})

    def test_merge_includes_noarch_with_same_exclusive_arch(self):
        first = pkgsets.PackageSetBase([None])
        second = pkgsets.PackageSetBase([None])

        pkg = first.file_cache.add('rpms/bash@4.3.42@4.fc24@i686')
        first.rpms_by_arch.setdefault(pkg.arch, []).append(pkg)

        pkg = second.file_cache.add('rpms/pungi@4.1.3@3.fc25@noarch')
        pkg.exclusivearch = ['i686']
        second.rpms_by_arch.setdefault(pkg.arch, []).append(pkg)

        first.merge(second, 'i386', ['i686', 'noarch'])

        self.assertPkgsetEqual(first.rpms_by_arch,
                               {'i686': ['rpms/bash@4.3.42@4.fc24@i686'],
                                'noarch': ['rpms/pungi@4.1.3@3.fc25@noarch']})

    def test_merge_skips_package_in_cache(self):
        first = pkgsets.PackageSetBase([None])
        second = pkgsets.PackageSetBase([None])

        pkg = first.file_cache.add('rpms/bash@4.3.42@4.fc24@i686')
        first.rpms_by_arch.setdefault(pkg.arch, []).append(pkg)

        pkg = second.file_cache.add('rpms/bash@4.3.42@4.fc24@i686')
        second.rpms_by_arch.setdefault(pkg.arch, []).append(pkg)

        first.merge(second, 'i386', ['i686'])

        self.assertPkgsetEqual(first.rpms_by_arch,
                               {'i686': ['rpms/bash@4.3.42@4.fc24@i686']})

    def test_merge_skips_src_without_binary(self):
        first = pkgsets.PackageSetBase([None])
        second = pkgsets.PackageSetBase([None])

        pkg = first.file_cache.add('rpms/bash@4.3.42@4.fc24@i686')
        first.rpms_by_arch.setdefault(pkg.arch, []).append(pkg)

        pkg = second.file_cache.add('rpms/pungi@4.1.3@3.fc25@src')
        second.rpms_by_arch.setdefault(pkg.arch, []).append(pkg)

        first.merge(second, 'i386', ['i686', 'src'])

        self.assertPkgsetEqual(first.rpms_by_arch,
                               {'i686': ['rpms/bash@4.3.42@4.fc24@i686'],
                                'src': [],
                                'nosrc': []})


if __name__ == "__main__":
    unittest.main()
