#!/usr/bin/env python
# -*- coding: utf-8 -*-


try:
    import unittest2 as unittest
except ImportError:
    import unittest

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pungi import checks
from tests.helpers import load_config, PKGSET_REPOS


class PkgsetConfigTestCase(unittest.TestCase):

    def test_validate_minimal_pkgset_koji(self):
        cfg = load_config(
            pkgset_source='koji',
            pkgset_koji_tag="f25",
        )

        self.assertEqual(checks.validate(cfg), [])

    def test_validate_minimal_pkgset_repos(self):
        cfg = load_config(
            pkgset_source='repos',
            pkgset_repos={'x86_64': '/first', 'ppc64': '/second'},
        )

        self.assertEqual(checks.validate(cfg), [])

    def test_pkgset_mismatch_repos(self):
        cfg = load_config(
            pkgset_source='repos',
            pkgset_koji_tag='f25',
            pkgset_koji_inherit=False,
        )

        self.assertItemsEqual(
            checks.validate(cfg),
            [checks.REQUIRES.format('pkgset_source', 'repos', 'pkgset_repos'),
             checks.CONFLICTS.format('pkgset_source', 'repos', 'pkgset_koji_tag'),
             checks.CONFLICTS.format('pkgset_source', 'repos', 'pkgset_koji_inherit')])

    def test_pkgset_mismatch_koji(self):
        cfg = load_config(
            pkgset_source='koji',
            pkgset_repos={'whatever': '/foo'},
        )

        self.assertItemsEqual(
            checks.validate(cfg),
            [checks.REQUIRES.format('pkgset_source', 'koji', 'pkgset_koji_tag'),
             checks.CONFLICTS.format('pkgset_source', 'koji', 'pkgset_repos')])


class ReleaseConfigTestCase(unittest.TestCase):
    def test_layered_without_base_product(self):
        cfg = load_config(
            PKGSET_REPOS,
            release_is_layered=True
        )

        self.assertItemsEqual(
            checks.validate(cfg),
            [checks.REQUIRES.format('release_is_layered', 'True', 'base_product_name'),
             checks.REQUIRES.format('release_is_layered', 'True', 'base_product_short'),
             checks.REQUIRES.format('release_is_layered', 'True', 'base_product_version')])

    def test_not_layered_with_base_product(self):
        cfg = load_config(
            PKGSET_REPOS,
            base_product_name='Prod',
            base_product_short='bp',
            base_product_version='1.0',
            base_product_type='updates',
        )

        self.assertItemsEqual(
            checks.validate(cfg),
            [checks.CONFLICTS.format('release_is_layered', 'False', 'base_product_name'),
             checks.CONFLICTS.format('release_is_layered', 'False', 'base_product_short'),
             checks.CONFLICTS.format('release_is_layered', 'False', 'base_product_type'),
             checks.CONFLICTS.format('release_is_layered', 'False', 'base_product_version')])


class RunrootConfigTestCase(unittest.TestCase):
    def test_runroot_without_deps(self):
        cfg = load_config(
            PKGSET_REPOS,
            runroot=True,
        )

        self.assertItemsEqual(
            checks.validate(cfg),
            [checks.REQUIRES.format('runroot', 'True', 'koji_profile'),
             checks.REQUIRES.format('runroot', 'True', 'runroot_tag'),
             checks.REQUIRES.format('runroot', 'True', 'runroot_channel')])

    def test_koji_settings_without_runroot(self):
        cfg = load_config(
            PKGSET_REPOS,
            runroot=False,
            koji_profile='koji',
            runroot_tag='f25',
            runroot_channel='compose',
        )

        self.assertItemsEqual(
            checks.validate(cfg),
            [checks.CONFLICTS.format('runroot', 'False', 'runroot_tag'),
             checks.CONFLICTS.format('runroot', 'False', 'runroot_channel')])


class BuildinstallConfigTestCase(unittest.TestCase):
    def test_bootable_without_method(self):
        cfg = load_config(
            PKGSET_REPOS,
            bootable=True,
        )

        self.assertItemsEqual(
            checks.validate(cfg),
            [checks.REQUIRES.format('bootable', 'True', 'buildinstall_method')]
        )

    def test_non_bootable_with_method(self):
        cfg = load_config(
            PKGSET_REPOS,
            bootable=False,
            buildinstall_method='lorax',
        )

        self.assertItemsEqual(
            checks.validate(cfg),
            [checks.CONFLICTS.format('bootable', 'False', 'buildinstall_method')]
        )

    def test_buildinstall_method_without_bootable(self):
        cfg = load_config(
            PKGSET_REPOS,
            buildinstall_method='lorax',
        )

        self.assertItemsEqual(
            checks.validate(cfg),
            [checks.CONFLICTS.format('bootable', 'False', 'buildinstall_method')]
        )

    def test_buildinstall_with_lorax_options(self):
        cfg = load_config(
            PKGSET_REPOS,
            bootable=True,
            buildinstall_method='buildinstall',
            lorax_options=[('^Server$', {})]
        )

        self.assertItemsEqual(
            checks.validate(cfg),
            [checks.CONFLICTS.format('buildinstall_method', 'buildinstall', 'lorax_options')]
        )

    def test_lorax_with_lorax_options(self):
        cfg = load_config(
            PKGSET_REPOS,
            bootable=True,
            buildinstall_method='lorax',
            lorax_options=[]
        )

        self.assertItemsEqual(checks.validate(cfg), [])

    def test_lorax_options_without_bootable_and_method(self):
        cfg = load_config(
            PKGSET_REPOS,
            lorax_options=[('^Server$', {})],
            buildinstall_kickstart='foo',
        )

        self.assertItemsEqual(
            checks.validate(cfg),
            [checks.CONFLICTS.format('buildinstall_method', 'None', 'lorax_options'),
             checks.CONFLICTS.format('buildinstall_method', 'None', 'buildinstall_kickstart')]
        )

    def test_deprecated(self):
        cfg = load_config(
            PKGSET_REPOS,
            buildinstall_upgrade_image=True,
        )

        self.assertItemsEqual(
            checks.validate(cfg),
            [checks.DEPRECATED.format('buildinstall_upgrade_image', 'use lorax_options instead')]
        )


class CreaterepoConfigTestCase(unittest.TestCase):
    def test_validate_minimal_pkgset_koji(self):
        cfg = load_config(
            pkgset_source='koji',
            pkgset_koji_tag="f25",
            product_id_allow_missing=True,
        )

        self.assertEqual(
            checks.validate(cfg),
            [checks.CONFLICTS.format('product_id', 'None', 'product_id_allow_missing')]
        )


class GatherConfigTestCase(unittest.TestCase):
    def test_source_comps_requires_comps(self):
        cfg = load_config(
            pkgset_source='koji',
            pkgset_koji_tag="f25",
            gather_source='comps',
            gather_source_mapping='foo'
        )

        self.assertItemsEqual(
            checks.validate(cfg),
            [checks.REQUIRES.format('gather_source', 'comps', 'comps_file'),
             checks.CONFLICTS.format('gather_source', 'comps', 'gather_source_mapping')]
        )

    def test_source_json_requires_mapping(self):
        cfg = load_config(
            pkgset_source='koji',
            pkgset_koji_tag="f25",
            gather_source='json',
            comps_file='comps',
        )

        self.assertItemsEqual(
            checks.validate(cfg),
            [checks.REQUIRES.format('gather_source', 'json', 'gather_source_mapping'),
             checks.CONFLICTS.format('gather_source', 'json', 'comps_file')]
        )


class OSBSConfigTestCase(unittest.TestCase):
    def test_validate(self):
        cfg = load_config(
            PKGSET_REPOS,
            osbs={"^Server$": {
                'url': 'http://example.com',
                'target': 'f25-build',
            }}
        )

        self.assertItemsEqual(checks.validate(cfg), [])

    def test_validate_bad_conf(self):
        cfg = load_config(
            PKGSET_REPOS,
            osbs='yes please'
        )

        self.assertNotEqual(checks.validate(cfg), [])


class OstreeConfigTestCase(unittest.TestCase):
    def test_validate(self):
        cfg = load_config(
            PKGSET_REPOS,
            ostree=[
                ("^Atomic$", {
                    "x86_64": {
                        "treefile": "fedora-atomic-docker-host.json",
                        "config_url": "https://git.fedorahosted.org/git/fedora-atomic.git",
                        "source_repo_from": "Everything",
                        "ostree_repo": "/mnt/koji/compose/atomic/Rawhide/"
                    }
                })
            ]
        )

        self.assertEqual(checks.validate(cfg), [])

    def test_validate_bad_conf(self):
        cfg = load_config(
            PKGSET_REPOS,
            ostree='yes please'
        )

        self.assertNotEqual(checks.validate(cfg), [])


class OstreeInstallerConfigTestCase(unittest.TestCase):
    def test_validate(self):
        cfg = load_config(
            PKGSET_REPOS,
            ostree_installer=[
                ("^Atomic$", {
                    "x86_64": {
                        "source_repo_from": "Everything",
                        "release": None,
                        "installpkgs": ["fedora-productimg-atomic"],
                        "add_template": ["/spin-kickstarts/atomic-installer/lorax-configure-repo.tmpl"],
                        "add_template_var": [
                            "ostree_osname=fedora-atomic",
                            "ostree_ref=fedora-atomic/Rawhide/x86_64/docker-host",
                        ],
                        "add_arch_template": ["/spin-kickstarts/atomic-installer/lorax-embed-repo.tmpl"],
                        "add_arch_template_var": [
                            "ostree_repo=https://kojipkgs.fedoraproject.org/compose/atomic/Rawhide/",
                            "ostree_osname=fedora-atomic",
                            "ostree_ref=fedora-atomic/Rawhide/x86_64/docker-host",
                        ]
                    }
                })
            ]
        )

        self.assertEqual(checks.validate(cfg), [])

    def test_validate_bad_conf(self):
        cfg = load_config(
            PKGSET_REPOS,
            ostree_installer=[
                ("^Atomic$", {
                    "x86_64": {
                        "source_repo_from": "Everything",
                        "release": None,
                        "installpkgs": ["fedora-productimg-atomic"],
                        "add_template": ["/spin-kickstarts/atomic-installer/lorax-configure-repo.tmpl"],
                        "add_template_var": [
                            "ostree_osname=fedora-atomic",
                            "ostree_ref=fedora-atomic/Rawhide/x86_64/docker-host",
                        ],
                        "add_arch_template": 15,
                        "add_arch_template_var": [
                            "ostree_repo=https://kojipkgs.fedoraproject.org/compose/atomic/Rawhide/",
                            "ostree_osname=fedora-atomic",
                            "ostree_ref=fedora-atomic/Rawhide/x86_64/docker-host",
                        ]
                    }
                })
            ]
        )

        self.assertNotEqual(checks.validate(cfg), [])


class LiveMediaConfigTestCase(unittest.TestCase):
    def test_global_config_validation(self):
        cfg = load_config(
            PKGSET_REPOS,
            live_media_ksurl='git://example.com/repo.git#HEAD',
            live_media_target='f24',
            live_media_release='RRR',
            live_media_version='Rawhide',
        )

        self.assertEqual(checks.validate(cfg), [])

    def test_global_config_null_release(self):
        cfg = load_config(
            PKGSET_REPOS,
            live_media_release=None,
        )

        self.assertEqual(checks.validate(cfg), [])


class InitConfigTestCase(unittest.TestCase):
    def test_validate_keep_original_comps_empty(self):
        cfg = load_config(PKGSET_REPOS,
                          keep_original_comps=[])

        self.assertEqual(checks.validate(cfg), [])

    def test_validate_keep_original_comps_filled_in(self):
        cfg = load_config(PKGSET_REPOS,
                          keep_original_comps=['Everything'])

        self.assertEqual(checks.validate(cfg), [])


class TestSuggestions(unittest.TestCase):
    def test_validate_keep_original_comps_empty(self):
        cfg = load_config(PKGSET_REPOS,
                          product_pid=None)

        self.assertEqual(
            checks.validate(cfg),
            [checks.UNKNOWN_SUGGEST.format('product_pid', 'product_id')])


if __name__ == '__main__':
    unittest.main()
