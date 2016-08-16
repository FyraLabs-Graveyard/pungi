# -*- coding: utf-8 -*-

import os
import re


def get_full_version():
    """
    Find full version of Pungi: if running from git, this will return cleaned
    output of `git describe`, otherwise it will look for installed version.
    """
    location = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..')
    if os.path.isdir(os.path.join(location, '.git')):
        import subprocess
        proc = subprocess.Popen(['git', '-C', location, 'describe', '--tags'],
                                stdout=subprocess.PIPE)
        output, _ = proc.communicate()
        return re.sub(r'-1.fc\d\d?', '', output.strip().replace('pungi-', ''))
    else:
        import pkg_resources
        try:
            return pkg_resources.get_distribution('pungi').version
        except pkg_resources.DistributionNotFound:
            return 'unknown'
