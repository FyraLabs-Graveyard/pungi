# -*- coding: utf-8 -*-

"""
This module contains functions required by pungi-make-atomic.
It is expected to be runnable in Koji runroot.
"""

import argparse
import os
from kobo import shortcuts
import tempfile
import shutil
import re

from .wrappers import scm


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
                      logfile=log_file)


def make_ostree_repo(repo, config, log_dir=None):
    log_file = make_log_file(log_dir, 'create-atomic-repo')
    shortcuts.run(['rpm-ostree', 'compose', 'tree', '--repo={}'.format(repo), config],
                  logfile=log_file)


def clone_repo(repodir, url, branch):
    scm.get_dir_from_scm(
        {'scm': 'git', 'repo': url, 'branch': branch, 'dir': '.'}, repodir)


def tweak_mirrorlist(repodir, source_repo):
    for file in os.listdir(repodir):
        if file.endswith('.repo'):
            tweak_file(os.path.join(repodir, file), source_repo)


def tweak_file(path, source_repo):
    """Replace mirrorlist line in repo file with baseurl pointing to source_repo."""
    with open(path, 'r') as f:
        contents = f.read()
    replacement = 'baseurl={}'.format(source_repo)
    contents = re.sub(r'^mirrorlist=.*$', replacement, contents)
    with open(path, 'w') as f:
        f.write(contents)


def prepare_config(workdir, config_url, config_branch, source_repo):
    repodir = os.path.join(workdir, 'config_repo')
    clone_repo(repodir, config_url, config_branch)
    tweak_mirrorlist(repodir, source_repo)
    return repodir


def run(opts):
    workdir = tempfile.mkdtemp()
    repodir = prepare_config(workdir, opts.config_url, opts.config_branch,
                             opts.source_repo)
    init_atomic_repo(opts.atomic_repo, log_dir=opts.log_dir)
    treefile = os.path.join(repodir, opts.treefile)
    make_ostree_repo(opts.atomic_repo, treefile, log_dir=opts.log_dir)
    shutil.rmtree(workdir)


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--log-dir',
                        help='where to log output')

    parser.add_argument('atomic_repo', metavar='ATOMIC_REPO',
                        help='where to put the atomic repo')
    parser.add_argument('--treefile', required=True,
                        help='treefile for rpm-ostree')
    parser.add_argument('--config-url', required=True,
                        help='git repository with the treefile')
    parser.add_argument('--config-branch', default='master',
                        help='git branch to be used')
    parser.add_argument('--source-repo', required=True,
                        help='yum repo used as source for')

    opts = parser.parse_args(args)

    run(opts)
