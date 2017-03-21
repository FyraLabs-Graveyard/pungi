=====================
Contributing to Pungi
=====================


Set up development environment
==============================

In order to work on *Pungi*, you should install recent version of *Fedora*.
These packages will have to installed:

 * createrepo
 * createrepo_c
 * cvs
 * genisoimage
 * gettext
 * git
 * isomd5sum
 * jigdo
 * kobo
 * kobo-rpmlib
 * koji
 * libselinux-python
 * lorax
 * python-jsonschema
 * python-kickstart
 * python-lockfile
 * python-lxml
 * python2-multilib
 * python-productmd
 * repoview
 * syslinux
 * yum
 * yum-utils

For running unit tests, these packages are recommended as well:

 * python-mock
 * python-nose
 * python-nose-cov

While being difficult, it is possible to work on *Pungi* using *virtualenv*.
Install *python-virtualenvwrapper* and use following steps. It will link system
libraries into the virtual environment and install all packages preferably from
PyPI or from tarball. You will still need to install all of the non-Python
packages above as they are used by calling an executable. ::

    $ mkvirtualenv pungienv
    $ for pkg in koji rpm pykickstart selinux createrepo yum urlgrabber; do ln -vs "$(deactivate && python -c 'import os, '$pkg'; print os.path.dirname('$pkg'.__file__)')" "$(virtualenvwrapper_get_site_packages_dir)"; done
    $ for pkg in _selinux deltarpm _deltarpm krbV sqlitecachec _sqlitecache; do ln -vs "$(deactivate && python -c 'import os, '$pkg'; print '$pkg'.__file__')" "$(virtualenvwrapper_get_site_packages_dir)"; done
    $ PYCURL_SSL_LIBRARY=nss pip install pycurl --no-binary :all:
    $ pip install lxml pyopenssl mock sphinx setuptools nose nose-cov productmd jsonschema requests lockfile python-multilib kobo

Now you should be able to run all existing tests.


Developing
==========

Currently the development workflow for Pungi is on master branch:

- Make your own fork at https://pagure.io/pungi
- Clone your fork locally (replacing $USERNAME with your own)::

    git clone git@pagure.io:forks/$USERNAME/pungi.git

- cd into your local clone and add the remote upstream for rebasing::

    cd pungi
    git remote add upstream git@pagure.io:pungi.git

  .. note::
      This workflow assumes that you never ``git commit`` directly to the master
      branch of your fork. This will make more sense when we cover rebasing
      below.

- create a topic branch based on master::

    git branch my_topic_branch master
    git checkout my_topic_branch


- Make edits, changes, add new features, etc. and then make sure to pull
  from upstream master and rebase before submitting a pull request::

    # lets just say you edited setup.py for sake of argument
    git checkout my_topic_branch

    # make changes to setup.py
    git add setup.py
    git commit -s -m "added awesome feature to setup.py"

    # now we rebase
    git checkout master
    git pull --rebase upstream master
    git push origin master
    git push origin --tags
    git checkout my_topic_branch
    git rebase master

    # resolve merge conflicts if any as a result of your development in
    # your topic branch
    git push origin my_topic_branch

  .. note::
      In order to for your commit to be merged, you must sign-off on it. Use
      ``-s`` option when running ``git commit``.

- Create pull request in the pagure.io web UI

- For convenience, here is a bash shell function that can be placed in your
  ~/.bashrc and called such as ``pullupstream pungi-4-devel`` that will
  automate a large portion of the rebase steps from above::

    pullupstream () {
      if [[ -z "$1" ]]; then
        printf "Error: must specify a branch name (e.g. - master, devel)\n"
      else
        pullup_startbranch=$(git describe --contains --all HEAD)
        git checkout $1
        git pull --rebase upstream master
        git push origin $1
        git push origin --tags
        git checkout ${pullup_startbranch}
      fi
    }


Testing
=======

You must write unit tests for any new code (except for trivial changes). Any
code without sufficient test coverage may not be merged.

To run all existing tests, suggested method is to use *nosetests*. With
additional options, it can generate code coverage. To make sure even tests from
executable files are run, don't forget to use the ``--exe`` option. ::

    $ make test
    $ make test-cover

    # Running single test file
    $ python tests/test_arch.py [TestCase...]

In the ``tests/`` directory there is a shell script ``test_compose.sh`` that
you can use to try and create a miniature compose on dummy data. The actual
data will be created by running ``make test-data`` in project root. ::

    $ make test-data
    $ make test-commpose

This testing compose does not actually use all phases that are available, and
there is no checking that the result is correct. It only tells you whether it
crashed or not.

.. note::
   Even when it finishes successfully, it may print errors about
   ``repoclosure`` on *Server-Gluster.x86_64* in *test* phase. This is not a
   bug.


Documenting
===========

You must write documentation for any new features and functional changes.
Any code without sufficient documentation may not be merged.

To generate the documentation, run ``make doc`` in project root.
