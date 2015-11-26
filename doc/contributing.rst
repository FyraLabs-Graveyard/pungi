=====================
Contributing to Pungi
=====================


Set up development environment
==============================

In order to work on *Pungi*, you should install *Fedora 23*. These packages
will have to installed:

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
 * python-kickstart
 * python-lockfile
 * python-lxml
 * python-productmd
 * repoview
 * syslinux
 * yum
 * yum-utils

For running unit tests, these packages are recommended as well:

 * python-mock
 * python-nose
 * python-nose-cov

Technically, it is possible to work on *Fedora 22*, but setting it up is a
major headache. Packaged version of *productmd* is too old, and *Pungi* does
not easily work with *virtualenv*, mostly because many of its Python
dependencies are not available on PyPI. To get it working, you have to install
*kobo* and *productmd* directly from Git and provide symlinks to other packages
and files in ``$(virtualenvwrapper_get_site_packages_dir)``. You will still
need to install all of the non-Python packages above as they are used by
calling an executable. ::

    $ ln -vs "$(deactivate && python -c 'import os, koji; print os.path.dirname(koji.__file__)')" "$(virtualenvwrapper_get_site_packages_dir)"
    $ ln -vs "$(deactivate && python -c 'import os, rpm; print os.path.dirname(rpm.__file__)')" "$(virtualenvwrapper_get_site_packages_dir)"
    $ ln -vs "$(deactivate && python -c 'import os, rpmUtils; print os.path.dirname(rpmUtils.__file__)')" "$(virtualenvwrapper_get_site_packages_dir)"
    $ ln -vs "$(deactivate && python -c 'import os, yum; print os.path.dirname(yum.__file__)')" "$(virtualenvwrapper_get_site_packages_dir)"
    $ ln -vs "$(deactivate && python -c 'import os, urlgrabber; print os.path.dirname(urlgrabber.__file__)')" "$(virtualenvwrapper_get_site_packages_dir)"
    $ ln -vs "$(deactivate && python -c 'import os, krbV; print krbV.__file__')" "$(virtualenvwrapper_get_site_packages_dir)"
    $ ln -vs "$(deactivate && python -c 'import os, sqlitecachec; print sqlitecachec.__file__')" "$(virtualenvwrapper_get_site_packages_dir)"
    $ ln -vs "$(deactivate && python -c 'import os, _sqlitecache; print _sqlitecache.__file__')" "$(virtualenvwrapper_get_site_packages_dir)"
    $ PYCURL_SSL_LIBRARY=nss pip install pycurl
    $ pip install https://git.fedorahosted.org/cgit/kobo.git/snapshot/kobo-0.4.3.tar.gz#egg=kobo
    $ pip install https://github.com/release-engineering/productmd/archive/master.tar.gz#egg=productmd
    $ pip install lxml pyopenssl mock sphinx setuptools nose nose-cov


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

You must write unit tests for any code but trivial changes. Any code without
sufficient test coverage may not be merged.

To run all existing tests, suggested method is to use *nosetests*. With
additional options, it can generate code coverage. To make sure even tests from
executable files are run, don't forget to use the ``--exe`` option. ::

    $ nosetests --exe
    $ nosetests --exe --with-cov --cov pungi --cov-report html

    # Running single test file
    $ nosetests --exe test_arch

In the ``tests/`` directory there is a shell script ``test_compose.sh`` that
you can use to try and create a miniature compose on dummy data. The actual
data will be created by running ``make test-data`` in project root.

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
