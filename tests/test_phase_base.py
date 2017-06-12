#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import mock
try:
    import unittest2 as unittest
except ImportError:
    import unittest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi.phases import run_all, base
from tests.helpers import DummyCompose, PungiTestCase, boom


class Phase1(base.ImageConfigMixin, base.PhaseBase):
    name = 'phase1'


class Phase2(base.ImageConfigMixin, base.PhaseBase):
    name = 'phase2'


class Phase3(base.ImageConfigMixin, base.PhaseBase):
    name = 'phase3'


class DummyResolver(object):
    def __init__(self):
        self.num = 0

    def __call__(self, url):
        self.num += 1
        return url.replace('HEAD', 'RES' + str(self.num))


class ImageConfigMixinTestCase(PungiTestCase):

    @mock.patch('pungi.util.resolve_git_url', new_callable=DummyResolver)
    def test_git_url_resolved_once(self, resolve_git_url):
        compose = DummyCompose(self.topdir, {
            'global_ksurl': 'git://example.com/repo.git?#HEAD',
            'phase1_ksurl': 'git://example.com/another.git?#HEAD',
        })

        p1 = Phase1(compose)
        p2 = Phase2(compose)
        p3 = Phase3(compose)

        self.assertEqual(p1.get_ksurl({}),
                         'git://example.com/another.git?#RES1')
        # Phase-level setting retrieved second time.
        self.assertEqual(p1.get_ksurl({}),
                         'git://example.com/another.git?#RES1')

        self.assertEqual(p2.get_ksurl({}),
                         'git://example.com/repo.git?#RES2')
        # Global setting retrieved again from same phase.
        self.assertEqual(p2.get_ksurl({}),
                         'git://example.com/repo.git?#RES2')

        # Global setting retrieved from another phase.
        self.assertEqual(p3.get_ksurl({}),
                         'git://example.com/repo.git?#RES2')

        # Local setting ignores global ones.
        self.assertEqual(p3.get_ksurl({'ksurl': 'git://example.com/more.git?#HEAD'}),
                         'git://example.com/more.git?#RES3')

        self.assertEqual(resolve_git_url.num, 3, 'Resolver was not called three times')


class TestRunAll(unittest.TestCase):
    def assertFinalized(self, p):
        self.assertEqual(p.mock_calls, [mock.call.start(), mock.call.stop()])

    def test_calls_stop(self):
        p1 = mock.Mock()
        p2 = mock.Mock()

        run_all([p1, p2])

        self.assertFinalized(p1)
        self.assertFinalized(p2)

    def test_calls_stop_on_failure(self):
        p1 = mock.Mock()
        p2 = mock.Mock()
        p3 = mock.Mock()

        p2.stop.side_effect = boom

        with self.assertRaises(Exception) as ctx:
            run_all([p1, p2, p3])

        self.assertEqual('BOOM', str(ctx.exception))
        self.assertFinalized(p1)
        self.assertFinalized(p2)
        self.assertFinalized(p3)

    def test_multiple_fail(self):
        p1 = mock.Mock(name='p1')
        p2 = mock.Mock(name='p2')
        p3 = mock.Mock(name='p3')

        p2.stop.side_effect = boom
        p3.stop.side_effect = boom

        with self.assertRaises(Exception) as ctx:
            run_all([p1, p2, p3])

        self.assertEqual('BOOM', str(ctx.exception))
        self.assertFinalized(p1)
        self.assertFinalized(p2)
        self.assertFinalized(p3)


if __name__ == "__main__":
    unittest.main()
