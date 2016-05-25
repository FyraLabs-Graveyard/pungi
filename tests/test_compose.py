#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import mock
try:
    import unittest2 as unittest
except ImportError:
    import unittest
import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi.compose import Compose


class ConfigWrapper(dict):
    def __init__(self, *args, **kwargs):
        super(ConfigWrapper, self).__init__(*args, **kwargs)
        self._open_file = '%s/fixtures/config.conf' % os.path.abspath(os.path.dirname(__file__))


class ComposeTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    @mock.patch('pungi.compose.ComposeInfo')
    def test_can_fail(self, ci):
        conf = {
            'failable_deliverables': [
                ('^.*$', {
                    '*': ['buildinstall'],
                    'i386': ['buildinstall', 'live', 'iso'],
                }),
            ]
        }
        compose = Compose(conf, self.tmp_dir)
        variant = mock.Mock(uid='Server')

        self.assertTrue(compose.can_fail(variant, 'x86_64', 'buildinstall'))
        self.assertFalse(compose.can_fail(variant, 'x86_64', 'live'))
        self.assertTrue(compose.can_fail(variant, 'i386', 'live'))

        self.assertFalse(compose.can_fail(None, 'x86_64', 'live'))
        self.assertTrue(compose.can_fail(None, 'i386', 'live'))

        self.assertTrue(compose.can_fail(variant, '*', 'buildinstall'))
        self.assertFalse(compose.can_fail(variant, '*', 'live'))

    @mock.patch('pungi.compose.ComposeInfo')
    def test_get_image_name(self, ci):
        conf = {}
        variant = mock.Mock(uid='Server', type='variant')
        ci.return_value.compose.respin = 2
        ci.return_value.compose.id = 'compose_id'
        ci.return_value.compose.date = '20160107'
        ci.return_value.compose.type = 'nightly'
        ci.return_value.compose.type_suffix = '.n'
        ci.return_value.compose.label = 'RC-1.0'
        ci.return_value.compose.label_major_version = '1'

        ci.return_value.release.version = '3.0'
        ci.return_value.release.short = 'rel_short'

        compose = Compose(conf, self.tmp_dir)

        keys = ['arch', 'compose_id', 'date', 'disc_num', 'disc_type',
                'label', 'label_major_version', 'release_short', 'respin',
                'suffix', 'type', 'type_suffix', 'variant', 'version']
        format = '-'.join(['%(' + k + ')s' for k in keys])
        name = compose.get_image_name('x86_64', variant, format=format,
                                      disc_num=7, disc_type='live', suffix='.iso')

        self.assertEqual(name, '-'.join(['x86_64', 'compose_id', '20160107', '7', 'live',
                                         'RC-1.0', '1', 'rel_short', '2', '.iso', 'nightly',
                                         '.n', 'Server', '3.0']))

    @mock.patch('pungi.compose.ComposeInfo')
    def test_get_image_name_type_netinst(self, ci):
        conf = {}
        variant = mock.Mock(uid='Server', type='variant')
        ci.return_value.compose.respin = 2
        ci.return_value.compose.id = 'compose_id'
        ci.return_value.compose.date = '20160107'
        ci.return_value.compose.type = 'nightly'
        ci.return_value.compose.type_suffix = '.n'
        ci.return_value.compose.label = 'RC-1.0'
        ci.return_value.compose.label_major_version = '1'

        ci.return_value.release.version = '3.0'
        ci.return_value.release.short = 'rel_short'

        compose = Compose(conf, self.tmp_dir)

        keys = ['arch', 'compose_id', 'date', 'disc_num', 'disc_type',
                'label', 'label_major_version', 'release_short', 'respin',
                'suffix', 'type', 'type_suffix', 'variant', 'version']
        format = '-'.join(['%(' + k + ')s' for k in keys])
        name = compose.get_image_name('x86_64', variant, format=format,
                                      disc_num=7, disc_type='netinst', suffix='.iso')

        self.assertEqual(name, '-'.join(['x86_64', 'compose_id', '20160107', '7', 'netinst',
                                         'RC-1.0', '1', 'rel_short', '2', '.iso', 'nightly',
                                         '.n', 'Server', '3.0']))

    @mock.patch('pungi.compose.ComposeInfo')
    def test_image_release(self, ci):
        conf = {}
        ci.return_value.compose.respin = 2
        ci.return_value.compose.date = '20160107'
        ci.return_value.compose.type = 'nightly'
        ci.return_value.compose.type_suffix = '.n'

        compose = Compose(conf, self.tmp_dir)

        self.assertEqual(compose.image_release, '20160107.n.2')

    @mock.patch('pungi.compose.ComposeInfo')
    def test_image_release_production(self, ci):
        conf = {}
        ci.return_value.compose.respin = 2
        ci.return_value.compose.date = '20160107'
        ci.return_value.compose.type = 'production'
        ci.return_value.compose.type_suffix = '.n'

        compose = Compose(conf, self.tmp_dir)

        self.assertEqual(compose.image_release, '20160107.n.2')

    @mock.patch('pungi.compose.ComposeInfo')
    def test_get_variant_arches_without_filter(self, ci):
        conf = ConfigWrapper(
            variants_file={'scm': 'file',
                           'repo': None,
                           'file': 'variants.xml'},
            release_name='Test',
            release_version='1.0',
            release_short='test',
        )

        compose = Compose(conf, self.tmp_dir)
        compose.read_variants()

        self.assertEqual(sorted([v.uid for v in compose.variants.itervalues()]),
                         ['Client', 'Crashy', 'Live', 'Server'])
        self.assertEqual(sorted([v.uid for v in compose.variants['Server'].variants.itervalues()]),
                         ['Server-Gluster', 'Server-ResilientStorage', 'Server-optional'])
        self.assertItemsEqual(compose.variants['Client'].arches,
                              ['i386', 'x86_64'])
        self.assertItemsEqual(compose.variants['Crashy'].arches,
                              ['ppc64le'])
        self.assertItemsEqual(compose.variants['Live'].arches,
                              ['x86_64'])
        self.assertItemsEqual(compose.variants['Server'].arches,
                              ['s390x', 'x86_64'])
        self.assertItemsEqual(compose.variants['Server'].variants['Gluster'].arches,
                              ['x86_64'])
        self.assertItemsEqual(compose.variants['Server'].variants['ResilientStorage'].arches,
                              ['x86_64'])
        self.assertItemsEqual(compose.variants['Server'].variants['optional'].arches,
                              ['s390x', 'x86_64'])

        self.assertEqual([v.uid for v in compose.get_variants()],
                         ['Client', 'Crashy', 'Live', 'Server', 'Server-Gluster',
                          'Server-ResilientStorage', 'Server-optional'])
        self.assertEqual(compose.get_arches(), ['i386', 'ppc64le', 's390x', 'x86_64'])

    @mock.patch('pungi.compose.ComposeInfo')
    def test_get_variant_arches_with_arch_filter(self, ci):
        conf = ConfigWrapper(
            variants_file={'scm': 'file',
                           'repo': None,
                           'file': 'variants.xml'},
            release_name='Test',
            release_version='1.0',
            release_short='test',
            tree_arches=['x86_64'],
        )

        compose = Compose(conf, self.tmp_dir)
        compose.read_variants()

        self.assertEqual(sorted([v.uid for v in compose.variants.itervalues()]),
                         ['Client', 'Live', 'Server'])
        self.assertEqual(sorted([v.uid for v in compose.variants['Server'].variants.itervalues()]),
                         ['Server-Gluster', 'Server-ResilientStorage', 'Server-optional'])
        self.assertItemsEqual(compose.variants['Client'].arches,
                              ['x86_64'])
        self.assertItemsEqual(compose.variants['Live'].arches,
                              ['x86_64'])
        self.assertItemsEqual(compose.variants['Server'].arches,
                              ['x86_64'])
        self.assertItemsEqual(compose.variants['Server'].variants['Gluster'].arches,
                              ['x86_64'])
        self.assertItemsEqual(compose.variants['Server'].variants['ResilientStorage'].arches,
                              ['x86_64'])
        self.assertItemsEqual(compose.variants['Server'].variants['optional'].arches,
                              ['x86_64'])

        self.assertEqual(compose.get_arches(), ['x86_64'])
        self.assertEqual([v.uid for v in compose.get_variants()],
                         ['Client', 'Live', 'Server', 'Server-Gluster',
                          'Server-ResilientStorage', 'Server-optional'])

    @mock.patch('pungi.compose.ComposeInfo')
    def test_get_variant_arches_with_variant_filter(self, ci):
        ci.return_value.compose.respin = 2
        ci.return_value.compose.date = '20160107'
        ci.return_value.compose.type = 'production'
        ci.return_value.compose.type_suffix = '.n'

        conf = ConfigWrapper(
            variants_file={'scm': 'file',
                           'repo': None,
                           'file': 'variants.xml'},
            release_name='Test',
            release_version='1.0',
            release_short='test',
            tree_variants=['Server', 'Client', 'Server-Gluster'],
        )

        compose = Compose(conf, self.tmp_dir)
        compose.read_variants()

        self.assertEqual(sorted([v.uid for v in compose.variants.itervalues()]),
                         ['Client', 'Server'])
        self.assertItemsEqual(compose.variants['Client'].arches,
                              ['i386', 'x86_64'])
        self.assertItemsEqual(compose.variants['Server'].arches,
                              ['s390x', 'x86_64'])
        self.assertItemsEqual(compose.variants['Server'].variants['Gluster'].arches,
                              ['x86_64'])

        self.assertEqual(compose.get_arches(), ['i386', 's390x', 'x86_64'])
        self.assertEqual([v.uid for v in compose.get_variants()],
                         ['Client', 'Server', 'Server-Gluster'])

    @mock.patch('pungi.compose.ComposeInfo')
    def test_get_variant_arches_with_both_filters(self, ci):
        ci.return_value.compose.respin = 2
        ci.return_value.compose.date = '20160107'
        ci.return_value.compose.type = 'production'
        ci.return_value.compose.type_suffix = '.n'

        logger = mock.Mock()

        conf = ConfigWrapper(
            variants_file={'scm': 'file',
                           'repo': None,
                           'file': 'variants.xml'},
            release_name='Test',
            release_version='1.0',
            release_short='test',
            tree_variants=['Server', 'Client', 'Server-optional'],
            tree_arches=['x86_64'],
        )

        compose = Compose(conf, self.tmp_dir, logger=logger)
        compose.read_variants()

        self.assertEqual(sorted([v.uid for v in compose.variants.itervalues()]),
                         ['Client', 'Server'])
        self.assertItemsEqual(compose.variants['Client'].arches,
                              ['x86_64'])
        self.assertItemsEqual(compose.variants['Server'].arches,
                              ['x86_64'])
        self.assertItemsEqual(compose.variants['Server'].variants['optional'].arches,
                              ['x86_64'])

        self.assertEqual(compose.get_arches(), ['x86_64'])
        self.assertEqual([v.uid for v in compose.get_variants()],
                         ['Client', 'Server', 'Server-optional'])

        self.assertItemsEqual(
            logger.info.call_args_list,
            [mock.call('Excluding variant Live: filtered by configuration.'),
             mock.call('Excluding variant Crashy: all its arches are filtered.'),
             mock.call('Excluding variant Server-ResilientStorage: filtered by configuration.'),
             mock.call('Excluding variant Server-Gluster: filtered by configuration.')]
        )


class StatusTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.logger = mock.Mock()
        with mock.patch('pungi.compose.ComposeInfo'):
            self.compose = Compose({}, self.tmp_dir, logger=self.logger)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_get_status_non_existing(self):
        status = self.compose.get_status()
        self.assertIsNone(status)

    def test_get_status_existing(self):
        with open(os.path.join(self.tmp_dir, 'STATUS'), 'w') as f:
            f.write('FOOBAR')

        self.assertEqual(self.compose.get_status(), 'FOOBAR')

    def test_get_status_is_dir(self):
        os.mkdir(os.path.join(self.tmp_dir, 'STATUS'))

        self.assertIsNone(self.compose.get_status())

    def test_write_status(self):
        self.compose.write_status('DOOMED')

        with open(os.path.join(self.tmp_dir, 'STATUS'), 'r') as f:
            self.assertEqual(f.read(), 'DOOMED\n')

    def test_write_non_standard_status(self):
        self.compose.write_status('FOOBAR')

        self.assertEqual(self.logger.log.call_count, 1)
        with open(os.path.join(self.tmp_dir, 'STATUS'), 'r') as f:
            self.assertEqual(f.read(), 'FOOBAR\n')

    def test_write_status_on_finished(self):
        self.compose.write_status('FINISHED')

        with self.assertRaises(RuntimeError):
            self.compose.write_status('NOT REALLY')

    def test_write_status_with_failed_deliverables(self):
        self.compose.conf = {
            'failable_deliverables': [
                ('^.+$', {
                    '*': ['live', 'build-image'],
                })
            ]
        }

        variant = mock.Mock(uid='Server')
        self.compose.can_fail(variant, 'x86_64', 'live')
        self.compose.can_fail(None, '*', 'build-image')

        self.compose.write_status('FINISHED')

        self.logger.log.assert_has_calls(
            [mock.call(20, 'Failed build-image on variant <>, arch <*>.'),
             mock.call(20, 'Failed live on variant <Server>, arch <x86_64>.')],
            any_order=True)

        with open(os.path.join(self.tmp_dir, 'STATUS'), 'r') as f:
            self.assertEqual(f.read(), 'FINISHED_INCOMPLETE\n')

    def test_calls_notifier(self):
        self.compose.notifier = mock.Mock()
        self.compose.write_status('FINISHED')

        self.assertTrue(self.compose.notifier.send.call_count, 1)


if __name__ == "__main__":
    unittest.main()
