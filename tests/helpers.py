# -*- coding: utf-8 -*-

import mock
import os

from pungi.util import get_arch_variant_data


class _DummyCompose(object):
    def __init__(self, config):
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
        self.conf = config
        self.paths = mock.Mock(
            compose=mock.Mock(
                topdir=mock.Mock(return_value='/a/b'),
                os_tree=mock.Mock(
                    side_effect=lambda arch, variant, create_dir=False: os.path.join('/ostree', arch, variant.uid)
                ),
                repository=mock.Mock(
                    side_effect=lambda arch, variant, create_dir=False: os.path.join('/repo', arch, variant.uid)
                ),
                image_dir=mock.Mock(
                    side_effect=lambda variant, relative=False, symlink_to=None: os.path.join(
                        '' if relative else '/', 'image_dir', variant.uid, '%(arch)s'
                    )
                ),
                iso_dir=mock.Mock(
                    side_effect=lambda arch, variant, symlink_to=None, relative=False: os.path.join(
                        '' if relative else '/', 'iso_dir', arch, variant.uid
                    )
                ),
                iso_path=mock.Mock(
                    side_effect=lambda arch, variant, filename, symlink_to: os.path.join(
                        '/iso_dir', arch, variant.uid, filename
                    )
                )
            ),
            work=mock.Mock(
                image_build_conf=mock.Mock(
                    side_effect=lambda variant, image_name, image_type:
                        '-'.join([variant.uid, image_name, image_type])
                )
            ),
            log=mock.Mock(
                log_file=mock.Mock(return_value='/a/b/log/log_file')
            )
        )
        self._logger = mock.Mock()
        self.variants = {
            'Server': mock.Mock(uid='Server', arches=['x86_64', 'amd64'], is_empty=False),
            'Client': mock.Mock(uid='Client', arches=['amd64'], is_empty=False),
            'Everything': mock.Mock(uid='Everything', arches=['x86_64', 'amd64'], is_empty=False),
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
