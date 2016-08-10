#!/usr/bin/env python
# -*- coding: utf-8 -*-


try:
    import unittest2 as unittest
except ImportError:
    import unittest

import mock
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pungi.phases.test as test_phase
from tests.helpers import DummyCompose, PungiTestCase, touch


PAD = '\0' * 100
UNBOOTABLE_ISO = ('\0' * 0x8001) + 'CD001' + PAD
ISO_WITH_MBR = ('\0' * 0x1fe) + '\x55\xAA' + ('\0' * 0x7e01) + 'CD001' + PAD
ISO_WITH_GPT = ('\0' * 0x200) + 'EFI PART' + ('\0' * 0x7df9) + 'CD001' + PAD
ISO_WITH_MBR_AND_GPT = ('\0' * 0x1fe) + '\x55\xAAEFI PART' + ('\0' * 0x7df9) + 'CD001' + PAD
ISO_WITH_TORITO = ('\0' * 0x8001) + 'CD001' + ('\0' * 0x7fa) + '\0CD001\1EL TORITO SPECIFICATION' + PAD


class TestCheckImageSanity(PungiTestCase):

    def test_missing_file_reports_error(self):
        compose = DummyCompose(self.topdir, {})

        with self.assertRaises(IOError):
            test_phase.check_image_sanity(compose)

    def test_missing_file_doesnt_report_if_failable(self):
        compose = DummyCompose(self.topdir, {})
        compose.image.deliverable = 'iso'
        compose.image.can_fail = True

        try:
            test_phase.check_image_sanity(compose)
        except:
            self.fail('Failable deliverable must not raise')

    def test_correct_iso_does_not_raise(self):
        compose = DummyCompose(self.topdir, {})
        compose.image.format = 'iso'
        compose.image.bootable = False
        touch(os.path.join(self.topdir, 'compose', compose.image.path), UNBOOTABLE_ISO)

        try:
            test_phase.check_image_sanity(compose)
        except:
            self.fail('Correct unbootable image must not raise')

    def test_incorrect_iso_raises(self):
        compose = DummyCompose(self.topdir, {})
        compose.image.format = 'iso'
        compose.image.bootable = False
        touch(os.path.join(self.topdir, 'compose', compose.image.path), 'Hey there')

        with self.assertRaises(RuntimeError) as ctx:
            test_phase.check_image_sanity(compose)

        self.assertIn('does not look like an ISO file', str(ctx.exception))

    def test_bootable_iso_without_mbr_or_gpt_raises_on_x86_64(self):
        compose = DummyCompose(self.topdir, {})
        compose.image.arch = 'x86_64'
        compose.image.format = 'iso'
        compose.image.bootable = True
        touch(os.path.join(self.topdir, 'compose', compose.image.path), UNBOOTABLE_ISO)

        with self.assertRaises(RuntimeError) as ctx:
            test_phase.check_image_sanity(compose)

        self.assertIn('is supposed to be bootable, but does not have MBR nor GPT',
                      str(ctx.exception))

    def test_bootable_iso_without_mbr_or_gpt_doesnt_raise_on_arm(self):
        compose = DummyCompose(self.topdir, {})
        compose.image.arch = 'armhfp'
        compose.image.format = 'iso'
        compose.image.bootable = True
        touch(os.path.join(self.topdir, 'compose', compose.image.path), UNBOOTABLE_ISO)

        try:
            test_phase.check_image_sanity(compose)
        except:
            self.fail('Failable deliverable must not raise')

    def test_failable_bootable_iso_without_mbr_gpt_doesnt_raise(self):
        compose = DummyCompose(self.topdir, {})
        compose.image.format = 'iso'
        compose.image.bootable = True
        compose.image.deliverable = 'iso'
        compose.image.can_fail = True
        touch(os.path.join(self.topdir, 'compose', compose.image.path), UNBOOTABLE_ISO)

        try:
            test_phase.check_image_sanity(compose)
        except:
            self.fail('Failable deliverable must not raise')

    def test_bootable_iso_with_mbr_does_not_raise(self):
        compose = DummyCompose(self.topdir, {})
        compose.image.format = 'iso'
        compose.image.bootable = True
        touch(os.path.join(self.topdir, 'compose', compose.image.path), ISO_WITH_MBR)

        try:
            test_phase.check_image_sanity(compose)
        except:
            self.fail('Bootable image with MBR must not raise')

    def test_bootable_iso_with_gpt_does_not_raise(self):
        compose = DummyCompose(self.topdir, {})
        compose.image.format = 'iso'
        compose.image.bootable = True
        touch(os.path.join(self.topdir, 'compose', compose.image.path), ISO_WITH_GPT)

        try:
            test_phase.check_image_sanity(compose)
        except:
            self.fail('Bootable image with GPT must not raise')

    def test_bootable_iso_with_mbr_and_gpt_does_not_raise(self):
        compose = DummyCompose(self.topdir, {})
        compose.image.format = 'iso'
        compose.image.bootable = True
        touch(os.path.join(self.topdir, 'compose', compose.image.path), ISO_WITH_MBR_AND_GPT)

        try:
            test_phase.check_image_sanity(compose)
        except:
            self.fail('Bootable image with MBR and GPT must not raise')

    def test_bootable_iso_with_el_torito_does_not_raise(self):
        compose = DummyCompose(self.topdir, {})
        compose.image.format = 'iso'
        compose.image.bootable = True
        touch(os.path.join(self.topdir, 'compose', compose.image.path), ISO_WITH_TORITO)

        try:
            test_phase.check_image_sanity(compose)
        except:
            self.fail('Bootable image with El Torito must not raise')

    def test_checks_with_optional_variant(self):
        compose = DummyCompose(self.topdir, {})
        compose.variants['Server'].variants = {
            'optional': mock.Mock(uid='Server-optional', arches=['x86_64'],
                                  type='optional', is_empty=False)
        }
        compose.image.format = 'iso'
        compose.image.bootable = True
        touch(os.path.join(self.topdir, 'compose', compose.image.path), ISO_WITH_MBR_AND_GPT)

        image = mock.Mock(path="Server/i386/optional/iso/image.iso",
                          format='iso', bootable=False)
        compose.im.images['Server-optional'] = {'i386': [image]}

        try:
            test_phase.check_image_sanity(compose)
        except:
            self.fail('Checking optional variant must not raise')


if __name__ == "__main__":
    unittest.main()
