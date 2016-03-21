# -*- coding: utf-8 -*-

"""
This module contains functions required by pungi-make-atomic.
It is expected to be runnable in Koji runroot.
"""

import argparse
import os
from kobo import shortcuts


def make_log_file(log_dir, filename):
    """Return path to log file with given name, if log_dir is set."""
    if not log_dir:
        return None
    return os.path.join(log_dir, '{}.log'.format(filename))


def init_atomic_repo(repo, log_dir=None):
    """If the atomic repo does not exist, initialize it."""
    log_file = make_log_file(log_dir, 'init-atomic-repo')
    if not os.path.isdir(repo):
        shortcuts.run(['ostree', 'init', '--repo={}'.format(repo), '--mode=archive-z2'],
                      log_file=log_file)


def make_ostree_repo(repo, config, log_dir=None):
    log_file = make_log_file(log_dir, 'create-atomic-repo')
    shortcuts.run(['rpm-ostree', 'compose', 'tree', '--repo={}'.format(repo), config],
                  log_file=log_file)


def run(opts):
    init_atomic_repo(opts.atomic_repo, log_dir=opts.log_dir)
    make_ostree_repo(opts.atomic_repo, opts.treefile, log_dir=opts.log_dir)


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--log-dir',
                        help='where to log output')

    parser.add_argument('atomic_repo', metavar='ATOMIC_REPO',
                        help='where to put the atomic repo')
    parser.add_argument('--treefile', required=True,
                        help='treefile for rpm-ostree')

    opts = parser.parse_args(args)

    run(opts)
