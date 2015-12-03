#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import unittest

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi.wrappers.lorax import LoraxWrapper


class LoraxWrapperTest(unittest.TestCase):

    def setUp(self):
        self.lorax = LoraxWrapper()

    def test_get_command_with_minimal_arguments(self):
        cmd = self.lorax.get_lorax_cmd("product", "version", "release",
                                       "/mnt/repo_baseurl", "/mnt/output_dir")

        self.assertEqual(cmd[0], 'lorax')
        self.assertItemsEqual(cmd[1:],
                              ['--product=product',
                               '--version=version',
                               '--release=release',
                               '--source=file:///mnt/repo_baseurl',
                               '/mnt/output_dir'])

    def test_get_command_with_all_arguments(self):
        cmd = self.lorax.get_lorax_cmd("product", "version", "release",
                                       "/mnt/repo_baseurl", "/mnt/output_dir",
                                       variant="Server", bugurl="http://example.com/",
                                       nomacboot=True, noupgrade=True, is_final=True,
                                       buildarch='x86_64', volid='VOLUME_ID',
                                       buildinstallpackages=['bash', 'vim'])

        self.assertEqual(cmd[0], 'lorax')
        self.assertItemsEqual(cmd[1:],
                              ['--product=product', '--version=version',
                               '--release=release', '--variant=Server',
                               '--source=file:///mnt/repo_baseurl',
                               '--bugurl=http://example.com/',
                               '--buildarch=x86_64', '--volid=VOLUME_ID',
                               '--nomacboot', '--noupgrade', '--isfinal',
                               '--installpkgs=bash', '--installpkgs=vim',
                               '/mnt/output_dir'])


if __name__ == "__main__":
    unittest.main()
