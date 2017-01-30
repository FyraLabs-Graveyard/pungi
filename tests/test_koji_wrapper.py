#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import mock
try:
    import unittest2 as unittest
except ImportError:
    import unittest
import tempfile

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pungi.wrappers.kojiwrapper import KojiWrapper


class KojiWrapperBaseTestCase(unittest.TestCase):
    def setUp(self):
        _, self.tmpfile = tempfile.mkstemp()
        self.koji_profile = mock.Mock()
        with mock.patch('pungi.wrappers.kojiwrapper.koji') as koji:
            koji.krb_login = mock.Mock()
            koji.get_profile_module = mock.Mock(
                return_value=mock.Mock(
                    config=mock.Mock(
                        authtype='kerberos',
                        principal='testprincipal',
                        keytab='testkeytab',
                        krb_rdns=False,
                        cert=''),
                    pathinfo=mock.Mock(
                        work=mock.Mock(return_value='/koji'),
                        taskrelpath=mock.Mock(side_effect=lambda id: 'task/' + str(id)),
                        imagebuild=mock.Mock(side_effect=lambda id: '/koji/imagebuild/' + str(id)),
                    )
                )
            )
            self.koji_profile = koji.get_profile_module.return_value
            self.koji = KojiWrapper('custom-koji')

    def tearDown(self):
        os.remove(self.tmpfile)


class KojiWrapperTest(KojiWrapperBaseTestCase):
    def test_krb_login_krb(self):
        self.assertEquals(self.koji.koji_module.config.krb_rdns, False)
        self.koji.login()
        self.koji.koji_proxy.krb_login.assert_called_with('testprincipal',
                                                          'testkeytab')

    def test_get_image_build_cmd_without_required_data(self):
        with self.assertRaises(AssertionError):
            self.koji.get_image_build_cmd(
                {
                    'image-build': {
                        'name': 'test-name',
                    }
                },
                self.tmpfile
            )

    def test_get_image_build_cmd_correct(self):
        cmd = self.koji.get_image_build_cmd(
            {
                'image-build': {
                    'name': 'test-name',
                    'version': '1',
                    'target': 'test-target',
                    'install_tree': '/tmp/test/install_tree',
                    'arches': 'x86_64',
                    'format': 'docker,qcow2',
                    'kickstart': 'test-kickstart',
                    'ksurl': 'git://example.com/ks.git',
                    'distro': 'test-distro',
                    'release': '20160222.0',
                }
            },
            self.tmpfile
        )

        self.assertEqual(cmd[0], 'custom-koji')
        self.assertEqual(cmd[1], 'image-build')
        self.assertItemsEqual(cmd[2:],
                              ['--config=' + self.tmpfile, '--wait'])

        with open(self.tmpfile, 'r') as f:
            lines = f.read().strip().split('\n')
        self.assertEqual(lines[0], '[image-build]')
        self.assertItemsEqual(lines[1:],
                              ['name = test-name',
                               'version = 1',
                               'target = test-target',
                               'install_tree = /tmp/test/install_tree',
                               'arches = x86_64',
                               'format = docker,qcow2',
                               'kickstart = test-kickstart',
                               'ksurl = git://example.com/ks.git',
                               'distro = test-distro',
                               'release = 20160222.0'])

    def test_get_image_paths(self):

        # The data for this tests is obtained from the actual Koji build. It
        # includes lots of fields that are not used, but for the sake of
        # completeness is fully preserved.

        getTaskChildren_data = {
            12387273: [
                {
                    'arch': 'i386',
                    'awaited': False,
                    'channel_id': 12,
                    'completion_time': '2016-01-03 05:34:08.374262',
                    'completion_ts': 1451799248.37426,
                    'create_time': '2016-01-03 05:15:20.311599',
                    'create_ts': 1451798120.3116,
                    'host_id': 158,
                    'id': 12387276,
                    'label': 'i386',
                    'method': 'createImage',
                    'owner': 131,
                    'parent': 12387273,
                    'priority': 19,
                    'request': [
                        'Fedora-Cloud-Base',
                        '23',
                        '20160103',
                        'i386',
                        {
                            'build_tag': 299,
                            'build_tag_name': 'f23-build',
                            'dest_tag': 294,
                            'dest_tag_name': 'f23-updates-candidate',
                            'id': 144,
                            'name': 'f23-candidate'
                        },
                        299,
                        {
                            'create_event': 14011966,
                            'create_ts': 1451761803.33528,
                            'creation_time': '2016-01-02 19:10:03.335283',
                            'id': 563977,
                            'state': 1
                        },
                        'http://infrastructure.fedoraproject.org/pub/alt/releases/23/Cloud/i386/os/',
                        {
                            'disk_size': '3',
                            'distro': 'Fedora-20',
                            'format': ['qcow2', 'raw-xz'],
                            'kickstart': 'work/cli-image/1451798116.800155.wYJWTVHw/fedora-cloud-base-2878aa0.ks',
                            'release': '20160103',
                            'repo': ['http://infrastructure.fedoraproject.org/pub/alt/releases/23/Cloud/$arch/os/',
                                     'http://infrastructure.fedoraproject.org/pub/fedora/linux/updates/23/$arch/'],
                            'scratch': True
                        }
                    ],
                    'start_time': '2016-01-03 05:15:29.828081',
                    'start_ts': 1451798129.82808,
                    'state': 2,
                    'waiting': None,
                    'weight': 2.0
                }, {
                    'arch': 'x86_64',
                    'awaited': False,
                    'channel_id': 12,
                    'completion_time': '2016-01-03 05:33:20.066366',
                    'completion_ts': 1451799200.06637,
                    'create_time': '2016-01-03 05:15:20.754201',
                    'create_ts': 1451798120.7542,
                    'host_id': 156,
                    'id': 12387277,
                    'label': 'x86_64',
                    'method': 'createImage',
                    'owner': 131,
                    'parent': 12387273,
                    'priority': 19,
                    'request': [
                        'Fedora-Cloud-Base',
                        '23',
                        '20160103',
                        'x86_64',
                        {
                            'build_tag': 299,
                            'build_tag_name': 'f23-build',
                            'dest_tag': 294,
                            'dest_tag_name': 'f23-updates-candidate',
                            'id': 144,
                            'name': 'f23-candidate'
                        },
                        299,
                        {
                            'create_event': 14011966,
                            'create_ts': 1451761803.33528,
                            'creation_time': '2016-01-02 19:10:03.335283',
                            'id': 563977,
                            'state': 1
                        },
                        'http://infrastructure.fedoraproject.org/pub/alt/releases/23/Cloud/x86_64/os/',
                        {
                            'disk_size': '3',
                            'distro': 'Fedora-20',
                            'format': ['qcow2', 'raw-xz'],
                            'kickstart': 'work/cli-image/1451798116.800155.wYJWTVHw/fedora-cloud-base-2878aa0.ks',
                            'release': '20160103',
                            'repo': ['http://infrastructure.fedoraproject.org/pub/alt/releases/23/Cloud/$arch/os/',
                                     'http://infrastructure.fedoraproject.org/pub/fedora/linux/updates/23/$arch/'],
                            'scratch': True
                        }
                    ],
                    'start_time': '2016-01-03 05:15:35.196043',
                    'start_ts': 1451798135.19604,
                    'state': 2,
                    'waiting': None,
                    'weight': 2.0
                }
            ]
        }

        getTaskResult_data = {
            12387276: {
                'arch': 'i386',
                'files': ['tdl-i386.xml',
                          'fedora-cloud-base-2878aa0.ks',
                          'koji-f23-build-12387276-base.ks',
                          'libvirt-qcow2-i386.xml',
                          'Fedora-Cloud-Base-23-20160103.i386.qcow2',
                          'libvirt-raw-xz-i386.xml',
                          'Fedora-Cloud-Base-23-20160103.i386.raw.xz'],
                'logs': ['oz-i386.log'],
                'name': 'Fedora-Cloud-Base',
                'release': '20160103',
                'rpmlist': [],
                'task_id': 12387276,
                'version': '23'
            },
            12387277: {
                'arch': 'x86_64',
                'files': ['tdl-x86_64.xml',
                          'fedora-cloud-base-2878aa0.ks',
                          'koji-f23-build-12387277-base.ks',
                          'libvirt-qcow2-x86_64.xml',
                          'Fedora-Cloud-Base-23-20160103.x86_64.qcow2',
                          'libvirt-raw-xz-x86_64.xml',
                          'Fedora-Cloud-Base-23-20160103.x86_64.raw.xz'],
                'logs': ['oz-x86_64.log'],
                'name': 'Fedora-Cloud-Base',
                'release': '20160103',
                'rpmlist': [],
                'task_id': 12387277,
                'version': '23'
            }

        }

        self.koji.koji_proxy = mock.Mock(
            getTaskChildren=mock.Mock(side_effect=lambda task_id, request: getTaskChildren_data.get(task_id)),
            getTaskResult=mock.Mock(side_effect=lambda task_id: getTaskResult_data.get(task_id))
        )
        result = self.koji.get_image_paths(12387273)
        self.assertItemsEqual(result.keys(), ['i386', 'x86_64'])
        self.maxDiff = None
        self.assertItemsEqual(result['i386'],
                              ['/koji/task/12387276/tdl-i386.xml',
                               '/koji/task/12387276/fedora-cloud-base-2878aa0.ks',
                               '/koji/task/12387276/koji-f23-build-12387276-base.ks',
                               '/koji/task/12387276/libvirt-qcow2-i386.xml',
                               '/koji/task/12387276/Fedora-Cloud-Base-23-20160103.i386.qcow2',
                               '/koji/task/12387276/libvirt-raw-xz-i386.xml',
                               '/koji/task/12387276/Fedora-Cloud-Base-23-20160103.i386.raw.xz'])
        self.assertItemsEqual(result['x86_64'],
                              ['/koji/task/12387277/tdl-x86_64.xml',
                               '/koji/task/12387277/fedora-cloud-base-2878aa0.ks',
                               '/koji/task/12387277/koji-f23-build-12387277-base.ks',
                               '/koji/task/12387277/libvirt-qcow2-x86_64.xml',
                               '/koji/task/12387277/Fedora-Cloud-Base-23-20160103.x86_64.qcow2',
                               '/koji/task/12387277/libvirt-raw-xz-x86_64.xml',
                               '/koji/task/12387277/Fedora-Cloud-Base-23-20160103.x86_64.raw.xz'])


class LiveMediaTestCase(KojiWrapperBaseTestCase):
    def test_get_live_media_cmd_minimal(self):
        opts = {
            'name': 'name', 'version': '1', 'target': 'tgt', 'arch': 'x,y,z',
            'ksfile': 'kickstart', 'install_tree': '/mnt/os', 'koji_profile': 'koji',
        }
        cmd = self.koji.get_live_media_cmd(opts)
        self.assertEqual(cmd,
                         ['koji', '--profile=koji', 'spin-livemedia', 'name', '1', 'tgt', 'x,y,z', 'kickstart',
                          '--install-tree=/mnt/os', '--wait'])

    def test_get_live_media_cmd_full(self):
        opts = {
            'name': 'name', 'version': '1', 'target': 'tgt', 'arch': 'x,y,z',
            'ksfile': 'kickstart', 'install_tree': '/mnt/os', 'scratch': True,
            'repo': ['repo-1', 'repo-2'], 'skip_tag': True,
            'ksurl': 'git://example.com/ksurl.git', 'release': '20160222.1',
            'koji_profile': 'koji',
        }
        cmd = self.koji.get_live_media_cmd(opts)
        self.assertEqual(cmd[:9],
                         ['koji', '--profile=koji', 'spin-livemedia', 'name', '1', 'tgt', 'x,y,z', 'kickstart',
                          '--install-tree=/mnt/os'])
        self.assertItemsEqual(cmd[9:],
                              ['--repo=repo-1', '--repo=repo-2', '--skip-tag', '--scratch', '--wait',
                               '--ksurl=git://example.com/ksurl.git', '--release=20160222.1'])


class LiveImageKojiWrapperTest(KojiWrapperBaseTestCase):
    def test_get_create_image_cmd_minimal(self):
        cmd = self.koji.get_create_image_cmd('my_name', '1.0', 'f24-candidate',
                                             'x86_64', '/path/to/ks', ['/repo/1'])
        self.assertEqual(cmd[0:2], ['custom-koji', 'spin-livecd'])
        self.assertItemsEqual(cmd[2:6], ['--noprogress', '--scratch', '--wait', '--repo=/repo/1'])
        self.assertEqual(cmd[6:], ['my_name', '1.0', 'f24-candidate', 'x86_64', '/path/to/ks'])

    def test_get_create_image_cmd_full(self):
        cmd = self.koji.get_create_image_cmd('my_name', '1.0', 'f24-candidate',
                                             'x86_64', '/path/to/ks', ['/repo/1', '/repo/2'],
                                             release='1', wait=False, archive=True, specfile='foo.spec',
                                             ksurl='https://git.example.com/')
        self.assertEqual(cmd[0:2], ['custom-koji', 'spin-livecd'])
        self.assertEqual(cmd[-5:], ['my_name', '1.0', 'f24-candidate', 'x86_64', '/path/to/ks'])
        self.assertItemsEqual(cmd[2:-5],
                              ['--noprogress', '--nowait', '--repo=/repo/1', '--repo=/repo/2',
                               '--release=1', '--specfile=foo.spec', '--ksurl=https://git.example.com/'])

    def test_spin_livecd_with_format(self):
        with self.assertRaises(ValueError):
            self.koji.get_create_image_cmd('my_name', '1.0', 'f24-candidate',
                                           'x86_64', '/path/to/ks', [],
                                           image_format='qcow')

    def test_spin_appliance_with_format(self):
        cmd = self.koji.get_create_image_cmd('my_name', '1.0', 'f24-candidate',
                                             'x86_64', '/path/to/ks', [],
                                             image_type='appliance',
                                             image_format='qcow')
        self.assertEqual(cmd[0:2], ['custom-koji', 'spin-appliance'])
        self.assertItemsEqual(cmd[2:6], ['--noprogress', '--scratch', '--wait', '--format=qcow'])
        self.assertEqual(cmd[6:], ['my_name', '1.0', 'f24-candidate', 'x86_64', '/path/to/ks'])

    def test_spin_appliance_with_wrong_format(self):
        with self.assertRaises(ValueError):
            self.koji.get_create_image_cmd('my_name', '1.0', 'f24-candidate',
                                           'x86_64', '/path/to/ks', [],
                                           image_type='appliance',
                                           image_format='pretty')


class RunrootKojiWrapperTest(KojiWrapperBaseTestCase):
    def test_get_cmd_minimal(self):
        cmd = self.koji.get_runroot_cmd('tgt', 's390x', 'date', use_shell=False, task_id=False)
        self.assertEqual(len(cmd), 6)
        self.assertEqual(cmd[0], 'custom-koji')
        self.assertEqual(cmd[1], 'runroot')
        self.assertEqual(cmd[-3], 'tgt')
        self.assertEqual(cmd[-2], 's390x')
        self.assertEqual(cmd[-1], 'rm -f /var/lib/rpm/__db*; rm -rf /var/cache/yum/*; set -x; date')
        self.assertItemsEqual(cmd[2:-3],
                              ['--channel-override=runroot-local'])

    def test_get_cmd_full(self):
        cmd = self.koji.get_runroot_cmd('tgt', 's390x', ['/bin/echo', '&'],
                                        quiet=True, channel='chan',
                                        packages=['strace', 'lorax'],
                                        mounts=['/tmp'], weight=1000)
        self.assertEqual(len(cmd), 13)
        self.assertEqual(cmd[0], 'custom-koji')
        self.assertEqual(cmd[1], 'runroot')
        self.assertEqual(cmd[-3], 'tgt')
        self.assertEqual(cmd[-2], 's390x')
        self.assertEqual(cmd[-1], 'rm -f /var/lib/rpm/__db*; rm -rf /var/cache/yum/*; set -x; /bin/echo \'&\'')
        self.assertItemsEqual(cmd[2:-3],
                              ['--channel-override=chan', '--quiet', '--use-shell',
                               '--task-id', '--weight=1000', '--package=strace',
                               '--package=lorax', '--mount=/tmp'])

    @mock.patch('pungi.wrappers.kojiwrapper.run')
    def test_run_runroot_cmd_no_task_id(self, run):
        cmd = ['koji', 'runroot']
        output = 'Output ...'
        run.return_value = (0, output)

        result = self.koji.run_runroot_cmd(cmd)
        self.assertDictEqual(result, {'retcode': 0, 'output': output, 'task_id': None})

    @mock.patch('pungi.wrappers.kojiwrapper.run')
    def test_run_runroot_cmd_with_task_id(self, run):
        cmd = ['koji', 'runroot', '--task-id']
        output = 'Output ...\n'
        run.return_value = (0, '1234\n' + output)

        result = self.koji.run_runroot_cmd(cmd)
        self.assertDictEqual(result, {'retcode': 0, 'output': output, 'task_id': 1234})

    @mock.patch('pungi.wrappers.kojiwrapper.run')
    def test_run_runroot_cmd_with_task_id_and_fail(self, run):
        cmd = ['koji', 'runroot', '--task-id']
        output = 'You are not authorized to run this\n'
        run.return_value = (1, output)

        result = self.koji.run_runroot_cmd(cmd)
        self.assertDictEqual(result, {'retcode': 1, 'output': output, 'task_id': None})

    @mock.patch('pungi.wrappers.kojiwrapper.run')
    def test_run_runroot_cmd_with_task_id_and_fail_but_emit_id(self, run):
        cmd = ['koji', 'runroot', '--task-id']
        output = 'Nope, does not work.\n'
        run.return_value = (1, '12345\n' + output)

        result = self.koji.run_runroot_cmd(cmd)
        self.assertDictEqual(result, {'retcode': 1, 'output': output, 'task_id': 12345})


class RunBlockingCmdTest(KojiWrapperBaseTestCase):
    @mock.patch('pungi.wrappers.kojiwrapper.run')
    def test_minimal(self, run):
        output = 'Created task: 1234\nHello\n'
        run.return_value = (0, output)

        result = self.koji.run_blocking_cmd('cmd')

        self.assertDictEqual(result, {'retcode': 0, 'output': output, 'task_id': 1234})
        self.assertItemsEqual(run.mock_calls,
                              [mock.call('cmd', can_fail=True, logfile=None)])

    @mock.patch('pungi.wrappers.kojiwrapper.run')
    def test_with_log(self, run):
        output = 'Created task: 1234\nHello\n'
        run.return_value = (0, output)

        result = self.koji.run_blocking_cmd('cmd', log_file='logfile')

        self.assertDictEqual(result, {'retcode': 0, 'output': output, 'task_id': 1234})
        self.assertItemsEqual(run.mock_calls,
                              [mock.call('cmd', can_fail=True, logfile='logfile')])

    @mock.patch('pungi.wrappers.kojiwrapper.run')
    def test_fail_with_task_id(self, run):
        output = 'Created task: 1234\nBoom\n'
        run.return_value = (1, output)

        result = self.koji.run_blocking_cmd('cmd')

        self.assertDictEqual(result, {'retcode': 1, 'output': output, 'task_id': 1234})
        self.assertItemsEqual(run.mock_calls,
                              [mock.call('cmd', can_fail=True, logfile=None)])

    @mock.patch('pungi.wrappers.kojiwrapper.run')
    def test_fail_without_task_id(self, run):
        output = 'Not found\n'
        run.return_value = (1, output)

        with self.assertRaises(RuntimeError) as ctx:
            self.koji.run_blocking_cmd('cmd')

        self.assertItemsEqual(run.mock_calls,
                              [mock.call('cmd', can_fail=True, logfile=None)])
        self.assertIn('Could not find task ID', str(ctx.exception))

    @mock.patch('pungi.wrappers.kojiwrapper.run')
    def test_disconnect_and_retry(self, run):
        output = 'Created task: 1234\nerror: failed to connect\n'
        retry = 'Created task: 1234\nOook\n'
        run.side_effect = [(1, output), (0, retry)]

        result = self.koji.run_blocking_cmd('cmd')

        self.assertDictEqual(result, {'retcode': 0, 'output': retry, 'task_id': 1234})
        self.assertEqual(run.mock_calls,
                         [mock.call('cmd', can_fail=True, logfile=None),
                          mock.call(['custom-koji', 'watch-task', '1234'], can_fail=True, logfile=None)])

    @mock.patch('pungi.wrappers.kojiwrapper.run')
    def test_disconnect_and_retry_but_fail(self, run):
        output = 'Created task: 1234\nerror: failed to connect\n'
        retry = 'Created task: 1234\nNot working still\n'
        run.side_effect = [(1, output), (1, retry)]

        result = self.koji.run_blocking_cmd('cmd')

        self.assertDictEqual(result, {'retcode': 1, 'output': retry, 'task_id': 1234})
        self.assertEqual(run.mock_calls,
                         [mock.call('cmd', can_fail=True, logfile=None),
                          mock.call(['custom-koji', 'watch-task', '1234'], can_fail=True, logfile=None)])

    @mock.patch('time.sleep')
    @mock.patch('pungi.wrappers.kojiwrapper.run')
    def test_disconnect_and_retry_multiple_times(self, run, sleep):
        output = 'Created task: 1234\nerror: failed to connect\n'
        retry = 'Created task: 1234\nOK\n'
        run.side_effect = [(1, output), (1, output), (1, output), (0, retry)]

        result = self.koji.run_blocking_cmd('cmd')

        self.assertDictEqual(result, {'retcode': 0, 'output': retry, 'task_id': 1234})
        self.assertEqual(run.mock_calls,
                         [mock.call('cmd', can_fail=True, logfile=None),
                          mock.call(['custom-koji', 'watch-task', '1234'], can_fail=True, logfile=None),
                          mock.call(['custom-koji', 'watch-task', '1234'], can_fail=True, logfile=None),
                          mock.call(['custom-koji', 'watch-task', '1234'], can_fail=True, logfile=None)])
        self.assertEqual(sleep.mock_calls,
                         [mock.call(i * 10) for i in range(1, 3)])

    @mock.patch('time.sleep')
    @mock.patch('pungi.wrappers.kojiwrapper.run')
    def test_disconnect_and_never_reconnect(self, run, sleep):
        output = 'Created task: 1234\nerror: failed to connect\n'
        run.side_effect = [(1, output), (1, output), (1, output), (1, output)]

        with self.assertRaises(RuntimeError) as ctx:
            self.koji.run_blocking_cmd('cmd', max_retries=2)

        self.assertIn('Failed to wait', str(ctx.exception))
        self.assertEqual(run.mock_calls,
                         [mock.call('cmd', can_fail=True, logfile=None),
                          mock.call(['custom-koji', 'watch-task', '1234'], can_fail=True, logfile=None),
                          mock.call(['custom-koji', 'watch-task', '1234'], can_fail=True, logfile=None)])
        self.assertEqual(sleep.mock_calls, [mock.call(i * 10) for i in range(1, 2)])


if __name__ == "__main__":
    unittest.main()
