=====================
Contributing to Pungi
=====================


Developing
==========

Currently the development workflow for Pungi is on master branch:

- Make your own fork at https://pagure.io/pungi
- Clone your fork locally (replacing $USERNAME with your own)::

    git clone git@pagure.io:forks/$USERNAME/pungi.git

- cd into your local clone and add the remote upstream for rebasing::

    cd pungi
    git remote add upstream git@pagure.io:pungi.git

    # NOTE: This workflow assumes that you never 'git commit' directly to
    # the master branch of your fork. This will make more sense when we
    # cover rebasing below.

- create a topic branch based on master::

    git branch my_topic_branch master
    git checkout my_topic_branch


- Make edits, changes, add new features, etc. and then make sure to pull
  from upstream master and rebase before submitting a pull request::

    # lets just say you edited setup.py for sake of argument
    git checkout my_topic_branch

    # make changes to setup.py
    git add setup.py
    git commit -m "added awesome feature to setup.py"

    # now we rebase
    git checkout master
    git fetch upstream
    git fetch upstream --tags
    git merge upstream/master
    git push origin master
    git push origin --tags
    git checkout my_topic_branch
    git rebase master

    # resolve merge conflicts if any as a result of your development in
    # your topic branch
    git push origin my_topic_branch

- Create pull request in the pagure.io web UI

- For convenience, here is a bash shell function that can be placed in your
  ~/.bashrc and called such as 'pullupstream pungi-4-devel' that will
  automate a large portion of the rebase steps from above::

    pullupstream () {
      if [[ -z "$1" ]]; then
        printf "Error: must specify a branch name (e.g. - master, devel)\n"
      else
        pullup_startbranch=$(git describe --contains --all HEAD)
        git checkout $1
        git fetch upstream
        git fetch upstream --tags
        git merge upstream/$1
        git push origin $1
        git push origin --tags
        git checkout ${pullup_startbranch}
      fi
    }


Testing
=======

You must write unit tests for any code but trivial changes.
Any code without sufficient test coverage may not be merged.


Documenting
===========

You must write documentation for any new features and functional changes.
Any code without sufficient documentation may not be merged.
