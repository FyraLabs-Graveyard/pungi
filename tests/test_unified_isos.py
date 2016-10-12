#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import mock
import os
import shutil
import sys
from ConfigParser import SafeConfigParser

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tests.helpers import PungiTestCase, FIXTURE_DIR, touch
from pungi_utils import unified_isos


COMPOSE_ID = 'DP-1.0-20161013.t.4'


class TestUnifiedIsos(PungiTestCase):
    def setUp(self):
        super(TestUnifiedIsos, self).setUp()
        shutil.copytree(os.path.join(FIXTURE_DIR, COMPOSE_ID),
                        os.path.join(self.topdir, COMPOSE_ID))

    def test_can_init(self):
        compose_path = os.path.join(self.topdir, COMPOSE_ID, 'compose')
        isos = unified_isos.UnifiedISO(compose_path)
        self.assertEqual(isos.compose_path, compose_path)
        self.assertRegexpMatches(isos.temp_dir,
                                 '^%s/' % os.path.join(self.topdir, COMPOSE_ID, 'work'))

    def test_can_find_compose_subdir(self):
        isos = unified_isos.UnifiedISO(os.path.join(self.topdir, COMPOSE_ID))
        self.assertEqual(isos.compose_path, os.path.join(self.topdir, COMPOSE_ID, 'compose'))
        self.assertRegexpMatches(isos.temp_dir,
                                 '^%s/' % os.path.join(self.topdir, COMPOSE_ID, 'work'))


class TestCreate(PungiTestCase):
    def setUp(self):
        super(TestCreate, self).setUp()
        shutil.copytree(os.path.join(FIXTURE_DIR, COMPOSE_ID),
                        os.path.join(self.topdir, COMPOSE_ID))
        compose_path = os.path.join(self.topdir, COMPOSE_ID, 'compose')
        self.isos = unified_isos.UnifiedISO(compose_path)

    def test_create_method(self):
        methods = ('link_to_temp', 'createrepo', 'discinfo', 'createiso',
                   'link_to_compose', 'update_checksums')
        for attr in methods:
            setattr(self.isos, attr, mock.Mock())

        with mock.patch('shutil.rmtree') as rmtree:
            self.isos.create()

        for attr in methods:
            self.assertEqual(len(getattr(self.isos, attr).call_args_list), 1)
        self.assertEqual(rmtree.call_args_list,
                         [mock.call(self.isos.temp_dir)])


def get_comps_mapping(path):
    def _comps(variant, arch):
        return os.path.join(path, variant, arch, 'os', 'repodata',
                            'comps-%s.%s.xml' % (variant, arch))
    return {
        'i386': {'Client': _comps('Client', 'i386')},
        's390x': {'Server': _comps('Server', 's390x')},
        'x86_64': {'Client': _comps('Client', 'x86_64'),
                   'Server': _comps('Server', 'x86_64')}
    }


def get_productid_mapping(path):
    def _productid(variant, arch):
        return os.path.join(path, variant, arch, 'os', 'repodata', 'productid')
    return {
        'i386': {'Client': _productid('Client', 'i386')},
        's390x': {'Server': _productid('Server', 's390x')},
        'x86_64': {'Client': _productid('Client', 'x86_64'),
                   'Server': _productid('Server', 'x86_64')}
    }


def get_repos_mapping(path):
    def _repo(variant, arch):
        return os.path.join(path, 'trees', arch, variant)
    return {
        'i386': {'Client': _repo('Client', 'i386')},
        's390x': {'Server': _repo('Server', 's390x')},
        'src': {'Client': _repo('Client', 'src'),
                'Server': _repo('Server', 'src')},
        'x86_64': {'Client': _repo('Client', 'x86_64'),
                   'Server': _repo('Server', 'x86_64')}
    }


class TestLinkToTemp(PungiTestCase):
    def setUp(self):
        super(TestLinkToTemp, self).setUp()
        shutil.copytree(os.path.join(FIXTURE_DIR, COMPOSE_ID),
                        os.path.join(self.topdir, COMPOSE_ID))
        self.compose_path = os.path.join(self.topdir, COMPOSE_ID, 'compose')
        self.isos = unified_isos.UnifiedISO(self.compose_path)
        self.isos.linker = mock.Mock()

    def _linkCall(self, variant, arch, file):
        return mock.call(os.path.join(self.compose_path, variant,
                                      arch if arch != 'src' else 'source',
                                      'tree' if arch == 'src' else 'os',
                                      'Packages', file[0].lower(), file),
                         os.path.join(self.isos.temp_dir, 'trees', arch, variant, file))

    def test_link_to_temp(self):
        self.isos.link_to_temp()

        self.assertItemsEqual(self.isos.treeinfo.keys(),
                              ['i386', 's390x', 'src', 'x86_64'])
        self.assertEqual(self.isos.comps,
                         get_comps_mapping(self.compose_path))
        self.assertEqual(self.isos.productid,
                         get_productid_mapping(self.compose_path))
        self.assertEqual(self.isos.repos,
                         get_repos_mapping(self.isos.temp_dir))

        self.assertItemsEqual(self.isos.linker.link.call_args_list,
                              [self._linkCall('Server', 's390x', 'dummy-filesystem-4.2.37-6.s390x.rpm'),
                               self._linkCall('Server', 'x86_64', 'dummy-filesystem-4.2.37-6.x86_64.rpm'),
                               self._linkCall('Server', 'src', 'dummy-filesystem-4.2.37-6.src.rpm'),
                               self._linkCall('Server', 'src', 'dummy-filesystem-4.2.37-6.src.rpm'),
                               self._linkCall('Client', 'i386', 'dummy-bash-4.2.37-6.i686.rpm'),
                               self._linkCall('Client', 'x86_64', 'dummy-bash-4.2.37-6.x86_64.rpm'),
                               self._linkCall('Client', 'src', 'dummy-bash-4.2.37-6.src.rpm'),
                               self._linkCall('Client', 'src', 'dummy-bash-4.2.37-6.src.rpm')])

    def test_link_to_temp_without_treefile(self):
        os.remove(os.path.join(self.compose_path, 'Client', 'i386', 'os', '.treeinfo'))

        with mock.patch('sys.stderr'):
            self.isos.link_to_temp()

        self.assertItemsEqual(self.isos.treeinfo.keys(),
                              ['s390x', 'src', 'x86_64'])
        comps = get_comps_mapping(self.compose_path)
        comps.pop('i386')
        self.assertEqual(self.isos.comps, comps)
        productid = get_productid_mapping(self.compose_path)
        productid.pop('i386')
        self.assertEqual(self.isos.productid, productid)
        repos = get_repos_mapping(self.isos.temp_dir)
        repos.pop('i386')
        self.assertEqual(self.isos.repos, repos)

        self.assertItemsEqual(self.isos.linker.link.call_args_list,
                              [self._linkCall('Server', 's390x', 'dummy-filesystem-4.2.37-6.s390x.rpm'),
                               self._linkCall('Server', 'x86_64', 'dummy-filesystem-4.2.37-6.x86_64.rpm'),
                               self._linkCall('Server', 'src', 'dummy-filesystem-4.2.37-6.src.rpm'),
                               self._linkCall('Server', 'src', 'dummy-filesystem-4.2.37-6.src.rpm'),
                               self._linkCall('Client', 'x86_64', 'dummy-bash-4.2.37-6.x86_64.rpm'),
                               self._linkCall('Client', 'src', 'dummy-bash-4.2.37-6.src.rpm')])

    def test_link_to_temp_extra_file(self):
        gpl_file = touch(os.path.join(self.compose_path, 'Server', 'x86_64', 'os', 'GPL'))

        self.isos.link_to_temp()

        self.assertItemsEqual(self.isos.treeinfo.keys(),
                              ['i386', 's390x', 'src', 'x86_64'])
        self.assertEqual(self.isos.comps,
                         get_comps_mapping(self.compose_path))
        self.assertEqual(self.isos.productid,
                         get_productid_mapping(self.compose_path))
        self.assertEqual(self.isos.repos,
                         get_repos_mapping(self.isos.temp_dir))

        self.assertItemsEqual(self.isos.linker.link.call_args_list,
                              [self._linkCall('Server', 's390x', 'dummy-filesystem-4.2.37-6.s390x.rpm'),
                               self._linkCall('Server', 'x86_64', 'dummy-filesystem-4.2.37-6.x86_64.rpm'),
                               self._linkCall('Server', 'src', 'dummy-filesystem-4.2.37-6.src.rpm'),
                               self._linkCall('Server', 'src', 'dummy-filesystem-4.2.37-6.src.rpm'),
                               self._linkCall('Client', 'i386', 'dummy-bash-4.2.37-6.i686.rpm'),
                               self._linkCall('Client', 'x86_64', 'dummy-bash-4.2.37-6.x86_64.rpm'),
                               self._linkCall('Client', 'src', 'dummy-bash-4.2.37-6.src.rpm'),
                               self._linkCall('Client', 'src', 'dummy-bash-4.2.37-6.src.rpm'),
                               mock.call(os.path.join(gpl_file),
                                         os.path.join(self.isos.temp_dir, 'trees', 'x86_64', 'GPL'))])


class TestCreaterepo(PungiTestCase):
    def setUp(self):
        super(TestCreaterepo, self).setUp()
        shutil.copytree(os.path.join(FIXTURE_DIR, COMPOSE_ID),
                        os.path.join(self.topdir, COMPOSE_ID))
        self.compose_path = os.path.join(self.topdir, COMPOSE_ID, 'compose')
        self.isos = unified_isos.UnifiedISO(self.compose_path)
        self.isos.linker = mock.Mock()
        # TODO mock treeinfo and use mappings for other data
        self.isos.link_to_temp()
        self.maxDiff = None
        self.comps = get_comps_mapping(self.compose_path)

    def mock_cr(self, path, groupfile, update):
        self.assertTrue(update)
        touch(os.path.join(path, 'repodata', 'repomd.xml'))
        return ('/'.join(path.split('/')[-2:]), groupfile)

    def mock_mr(self, path, pid, compress_type):
        self.assertEqual(compress_type, 'gz')
        return ('/'.join(path.split('/')[-3:-1]), pid)

    @mock.patch('pungi.wrappers.createrepo.CreaterepoWrapper')
    @mock.patch('pungi_utils.unified_isos.run')
    def test_createrepo(self, run, cr):
        cr.return_value.get_createrepo_cmd.side_effect = self.mock_cr
        self.isos.createrepo()

        self.assertItemsEqual(
            run.call_args_list,
            [mock.call(('src/Client', None), show_cmd=True),
             mock.call(('src/Server', None), show_cmd=True),
             mock.call(('i386/Client', self.comps['i386']['Client']), show_cmd=True),
             mock.call(('s390x/Server', self.comps['s390x']['Server']), show_cmd=True),
             mock.call(('x86_64/Client', self.comps['x86_64']['Client']), show_cmd=True),
             mock.call(('x86_64/Server', self.comps['x86_64']['Server']), show_cmd=True)]
        )

        checksums = {}

        # treeinfo checksums
        for arch in self.isos.treeinfo.keys():
            parser = SafeConfigParser()
            parser.optionxform = str
            parser.read(os.path.join(self.isos.temp_dir, 'trees', arch, '.treeinfo'))
            checksums[arch] = [k for k, v in parser.items('checksums')]

        self.assertEqual(
            checksums,
            {'i386': ['Client/repodata/repomd.xml'],
             's390x': ['Server/repodata/repomd.xml'],
             'src': ['Client/repodata/repomd.xml', 'Server/repodata/repomd.xml'],
             'x86_64': ['Client/repodata/repomd.xml', 'Server/repodata/repomd.xml']}
        )

    @mock.patch('pungi.wrappers.createrepo.CreaterepoWrapper')
    @mock.patch('pungi_utils.unified_isos.run')
    def test_createrepo_with_productid(self, run, cr):
        for x in self.isos.productid.values():
            for f in x.values():
                touch(f)
        cr.return_value.get_createrepo_cmd.side_effect = self.mock_cr
        cr.return_value.get_modifyrepo_cmd.side_effect = self.mock_mr
        self.isos.createrepo()

        self.assertItemsEqual(
            run.call_args_list,
            [mock.call(('src/Client', None), show_cmd=True),
             mock.call(('src/Server', None), show_cmd=True),
             mock.call(('i386/Client', self.comps['i386']['Client']), show_cmd=True),
             mock.call(('s390x/Server', self.comps['s390x']['Server']), show_cmd=True),
             mock.call(('x86_64/Client', self.comps['x86_64']['Client']), show_cmd=True),
             mock.call(('x86_64/Server', self.comps['x86_64']['Server']), show_cmd=True),
             mock.call(('x86_64/Server', os.path.join(self.isos.temp_dir,
                                                      'trees/x86_64/Server/repodata/productid'))),
             mock.call(('x86_64/Client', os.path.join(self.isos.temp_dir,
                                                      'trees/x86_64/Client/repodata/productid'))),
             mock.call(('s390x/Server', os.path.join(self.isos.temp_dir,
                                                     'trees/s390x/Server/repodata/productid'))),
             mock.call(('i386/Client', os.path.join(self.isos.temp_dir,
                                                    'trees/i386/Client/repodata/productid')))]
        )

        checksums = {}

        # treeinfo checksums
        for arch in self.isos.treeinfo.keys():
            parser = SafeConfigParser()
            parser.optionxform = str
            parser.read(os.path.join(self.isos.temp_dir, 'trees', arch, '.treeinfo'))
            checksums[arch] = [k for k, v in parser.items('checksums')]

        self.assertEqual(
            checksums,
            {'i386': ['Client/repodata/repomd.xml'],
             's390x': ['Server/repodata/repomd.xml'],
             'src': ['Client/repodata/repomd.xml', 'Server/repodata/repomd.xml'],
             'x86_64': ['Client/repodata/repomd.xml', 'Server/repodata/repomd.xml']}
        )


class TestDiscinfo(PungiTestCase):
    def setUp(self):
        super(TestDiscinfo, self).setUp()
        shutil.copytree(os.path.join(FIXTURE_DIR, COMPOSE_ID),
                        os.path.join(self.topdir, COMPOSE_ID))
        self.compose_path = os.path.join(self.topdir, COMPOSE_ID, 'compose')
        self.isos = unified_isos.UnifiedISO(self.compose_path)
        self.isos.linker = mock.Mock()
        # TODO mock treeinfo and use mappings for other data
        self.isos.link_to_temp()
        self.maxDiff = None

    @mock.patch('pungi_utils.unified_isos.create_discinfo')
    def test_discinfo(self, create_discinfo):
        self.isos.discinfo()
        self.assertItemsEqual(
            create_discinfo.call_args_list,
            [mock.call(os.path.join(self.isos.temp_dir, 'trees', 'i386', '.discinfo'),
                       'Dummy Product 1.0', 'i386'),
             mock.call(os.path.join(self.isos.temp_dir, 'trees', 's390x', '.discinfo'),
                       'Dummy Product 1.0', 's390x'),
             mock.call(os.path.join(self.isos.temp_dir, 'trees', 'src', '.discinfo'),
                       'Dummy Product 1.0', 'src'),
             mock.call(os.path.join(self.isos.temp_dir, 'trees', 'x86_64', '.discinfo'),
                       'Dummy Product 1.0', 'x86_64')]
        )


CHECKSUMS = {
    'MD5': 'cbc3a5767b22babfe3578a2b82d83fcb',
    'SHA1': 'afaf8621bfbc22781edfc81b774a2b2f66fdc8b0',
    'SHA256': '84c1c8611b287209e1e76d657e7e69e6192ad72dd2531e0fb7a43b95070fabb1',
}


class TestCreateiso(PungiTestCase):
    def setUp(self):
        super(TestCreateiso, self).setUp()
        shutil.copytree(os.path.join(FIXTURE_DIR, COMPOSE_ID),
                        os.path.join(self.topdir, COMPOSE_ID))
        self.compose_path = os.path.join(self.topdir, COMPOSE_ID, 'compose')
        self.isos = unified_isos.UnifiedISO(self.compose_path)
        self.isos.linker = mock.Mock()
        # TODO mock treeinfo and use mappings for other data
        self.isos.link_to_temp()
        self.maxDiff = None
        self.mkisofs_cmd = None

    def mock_gmc(self, path, *args, **kwargs):
        touch(path, 'ISO FILE\n')
        self.mkisofs_cmd = self.mkisofs_cmd or mock.Mock(name='mkisofs cmd')
        return self.mkisofs_cmd

    def _img(self, arch, exts):
        exts = ['manifest'] + exts
        base_path = os.path.join(self.isos.temp_dir, 'iso', arch,
                                 u'DP-1.0-20161013.t.4-%s-dvd.iso' % arch)
        yield base_path
        for ext in exts:
            yield base_path + '.' + ext

    def _imgs(self, arches, exts):
        images = {}
        exts = [e + 'SUM' for e in exts]
        for arch in arches:
            images[arch] = set(self._img(arch if arch != 'src' else 'source', exts))
        return images

    def assertResults(self, iso, run, arches, checksums):
        self.assertEqual(
            run.mock_calls,
            [mock.call(self.mkisofs_cmd),
             mock.call(iso.get_implantisomd5_cmd.return_value),
             mock.call(iso.get_manifest_cmd.return_value)] * 2
        )

        self.assertEqual(
            self.isos.images,
            self._imgs(arches, checksums),
        )

        with open(os.path.join(self.compose_path, 'metadata', 'images.json')) as f:
            manifest = json.load(f)

        for v in ('Client', 'Server'):
            for a in arches:
                for image in manifest['payload']['images'][v]['x86_64']:
                    if image.get('unified', False) and image['arch'] == a:
                        arch = 'source' if image['arch'] == 'src' else image['arch']
                        self.assertEqual(image['path'],
                                         '{0}/{1}/iso/DP-1.0-20161013.t.4-{1}-dvd.iso'.format(v, arch))
                        checksum_file_base = os.path.join(self.isos.temp_dir, 'iso',
                                                          arch, os.path.basename(image['path']))
                        for ch in checksums:
                            fp = '%s.%sSUM' % (checksum_file_base, ch)
                            with open(fp) as f:
                                self.assertEqual(
                                    f.read(),
                                    '%s (%s) = %s\n' % (ch, os.path.basename(image['path']),
                                                        CHECKSUMS[ch])
                                )
                        break
                else:
                    self.fail('Image for %s.%s missing' % (v, a))

    @mock.patch('pungi_utils.unified_isos.iso')
    @mock.patch('pungi_utils.unified_isos.run')
    def test_createiso(self, run, iso):
        iso.get_mkisofs_cmd.side_effect = self.mock_gmc
        iso.get_implanted_md5.return_value = 'beefcafebabedeadbeefcafebabedead'
        iso.get_volume_id.return_value = 'VOLID'

        self.isos.treeinfo = {'x86_64': self.isos.treeinfo['x86_64'],
                              'src': self.isos.treeinfo['src']}

        self.isos.createiso()

        self.assertResults(iso, run, ['src', 'x86_64'], ['MD5', 'SHA1', 'SHA256'])

    @mock.patch('pungi_utils.unified_isos.iso')
    @mock.patch('pungi_utils.unified_isos.run')
    def test_createiso_checksum_one_file(self, run, iso):
        iso.get_mkisofs_cmd.side_effect = self.mock_gmc
        iso.get_implanted_md5.return_value = 'beefcafebabedeadbeefcafebabedead'
        iso.get_volume_id.return_value = 'VOLID'

        self.isos.conf['media_checksum_one_file'] = True

        self.isos.treeinfo = {'x86_64': self.isos.treeinfo['x86_64'],
                              'src': self.isos.treeinfo['src']}

        self.isos.createiso()

        self.assertResults(iso, run, ['src', 'x86_64'], [])

    @mock.patch('pungi_utils.unified_isos.iso')
    @mock.patch('pungi_utils.unified_isos.run')
    def test_createiso_single_checksum(self, run, iso):
        iso.get_mkisofs_cmd.side_effect = self.mock_gmc
        iso.get_implanted_md5.return_value = 'beefcafebabedeadbeefcafebabedead'
        iso.get_volume_id.return_value = 'VOLID'

        self.isos.conf['media_checksums'] = ['sha256']

        self.isos.treeinfo = {'x86_64': self.isos.treeinfo['x86_64'],
                              'src': self.isos.treeinfo['src']}

        self.isos.createiso()

        self.assertResults(iso, run, ['src', 'x86_64'], ['SHA256'])


class TestLinkToCompose(PungiTestCase):
    def setUp(self):
        super(TestLinkToCompose, self).setUp()
        shutil.copytree(os.path.join(FIXTURE_DIR, COMPOSE_ID),
                        os.path.join(self.topdir, COMPOSE_ID))
        self.compose_path = os.path.join(self.topdir, COMPOSE_ID, 'compose')
        self.isos = unified_isos.UnifiedISO(self.compose_path)
        self.isos.linker = mock.Mock()
        self.binary = os.path.join(self.isos.temp_dir, 'isos', 'x86_64', 'binary.iso')
        self.source = os.path.join(self.isos.temp_dir, 'isos', 'src', 'source.iso')
        self.isos.images = {
            'x86_64': set([self.binary]),
            'src': set([self.source]),
        }
        self.maxDiff = None

    def _iso(self, variant, arch, name):
        return os.path.join(self.compose_path, variant, arch, 'iso', name)

    def test_link_to_compose(self):
        self.isos.link_to_compose()

        self.assertItemsEqual(
            self.isos.linker.link.call_args_list,
            [mock.call(self.binary, self._iso('Client', 'x86_64', 'binary.iso')),
             mock.call(self.binary, self._iso('Server', 'x86_64', 'binary.iso')),
             mock.call(self.source, self._iso('Client', 'source', 'source.iso')),
             mock.call(self.source, self._iso('Server', 'source', 'source.iso'))]
        )


class MockImage(mock.Mock):
    def __eq__(self, another):
        return self.path == another.path


class TestUpdateChecksums(PungiTestCase):
    def setUp(self):
        super(TestUpdateChecksums, self).setUp()
        shutil.copytree(os.path.join(FIXTURE_DIR, COMPOSE_ID),
                        os.path.join(self.topdir, COMPOSE_ID))
        self.compose_path = os.path.join(self.topdir, COMPOSE_ID, 'compose')
        self.isos = unified_isos.UnifiedISO(self.compose_path)
        self.maxDiff = None

    def _isodir(self, variant, arch):
        return os.path.join(self.compose_path, variant, arch, 'iso')

    def _call(self, variant, arch, source=False, basename='', one_file=False):
        archdir = arch if not source else 'source'
        isodir = self._isodir(variant, archdir)
        filename = 'DP-1.0-20161013.t.4-%s-%s-dvd1.iso' % (variant, archdir)
        return mock.call(variant, arch, isodir,
                         [MockImage(path=os.path.join(variant, archdir, 'iso', filename))],
                         ['md5', 'sha1', 'sha256'], basename, one_file)

    @mock.patch('pungi_utils.unified_isos.make_checksums')
    def test_update_checksums(self, mmc):
        self.isos.update_checksums()
        self.assertItemsEqual(
            mmc.call_args_list,
            [self._call('Client', 'i386'),
             self._call('Client', 'x86_64'),
             self._call('Server', 's390x'),
             self._call('Server', 'x86_64'),
             self._call('Client', 'i386', source=True),
             self._call('Client', 'x86_64', source=True),
             self._call('Server', 's390x', source=True),
             self._call('Server', 'x86_64', source=True)]
        )

    @mock.patch('pungi_utils.unified_isos.make_checksums')
    def test_update_checksums_one_file(self, mmc):
        self.isos.conf['media_checksum_one_file'] = True
        self.isos.update_checksums()
        self.assertItemsEqual(
            mmc.call_args_list,
            [self._call('Client', 'i386', one_file=True),
             self._call('Client', 'x86_64', one_file=True),
             self._call('Server', 's390x', one_file=True),
             self._call('Server', 'x86_64', one_file=True),
             self._call('Client', 'i386', source=True, one_file=True),
             self._call('Client', 'x86_64', source=True, one_file=True),
             self._call('Server', 's390x', source=True, one_file=True),
             self._call('Server', 'x86_64', source=True, one_file=True)]
        )

    @mock.patch('pungi_utils.unified_isos.make_checksums')
    def test_update_checksums_basename(self, mmc):
        self.isos.conf['media_checksum_base_filename'] = '{variant}-{arch}'
        self.isos.update_checksums()
        self.assertItemsEqual(
            mmc.call_args_list,
            [self._call('Client', 'i386', basename='Client-i386-'),
             self._call('Client', 'x86_64', basename='Client-x86_64-'),
             self._call('Server', 's390x', basename='Server-s390x-'),
             self._call('Server', 'x86_64', basename='Server-x86_64-'),
             self._call('Client', 'i386', source=True, basename='Client-i386-'),
             self._call('Client', 'x86_64', source=True, basename='Client-x86_64-'),
             self._call('Server', 's390x', source=True, basename='Server-s390x-'),
             self._call('Server', 'x86_64', source=True, basename='Server-x86_64-')]
        )
