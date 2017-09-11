import mock
import unittest
import six
import pungi

from helpers import load_bin

cli = load_bin("pungi-koji")


class PungiKojiTestCase(unittest.TestCase):

    @mock.patch('sys.argv', new=['prog', '--version'])
    @mock.patch('sys.stderr', new_callable=six.StringIO)
    @mock.patch('pungi_cli_fake_pungi-koji.get_full_version', return_value='a-b-c.111')
    def test_version(self, get_full_version, stderr):
        with self.assertRaises(SystemExit):
            cli.main()
        self.assertMultiLineEqual(stderr.getvalue(), 'a-b-c.111\n')