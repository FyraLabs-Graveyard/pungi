# -*- coding: utf-8 -*-

"""
This module contains functions required by pungi-make-ostree.
It is expected to be runnable in Koji runroot.
"""

import argparse
import os
from kobo import shortcuts
import errno


def ensure_dir(path):
    try:
        os.makedirs(path)
    except OSError as err:
        if err.errno != errno.EEXIST:
            raise
    return path


def make_log_file(log_dir, filename):
    """Return path to log file with given name, if log_dir is set."""
    if not log_dir:
        return None
    ensure_dir(log_dir)
    return os.path.join(log_dir, '{}.log'.format(filename))


def init_ostree_repo(repo, log_dir=None):
    """If the ostree repo does not exist, initialize it."""
    log_file = make_log_file(log_dir, 'init-ostree-repo')
    if not os.path.isdir(repo):
        ensure_dir(repo)
        shortcuts.run(['ostree', 'init', '--repo={}'.format(repo), '--mode=archive-z2'],
                      show_cmd=True, stdout=True, logfile=log_file)


def make_ostree_repo(repo, config, log_dir=None):
    log_file = make_log_file(log_dir, 'create-ostree-repo')
    shortcuts.run(['rpm-ostree', 'compose', 'tree', '--repo={}'.format(repo), config],
                  show_cmd=True, stdout=True, logfile=log_file)


def run(opts):
    init_ostree_repo(opts.ostree_repo, log_dir=opts.log_dir)
    make_ostree_repo(opts.ostree_repo, opts.treefile, log_dir=opts.log_dir)


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--log-dir',
                        help='where to log output')

    parser.add_argument('ostree_repo', metavar='OSTREE_REPO',
                        help='where to put the ostree repo')
    parser.add_argument('--treefile', required=True,
                        help='treefile for rpm-ostree')

    opts = parser.parse_args(args)

    run(opts)
