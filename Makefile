.PHONY: all clean doc log test

PKGNAME=pungi
VERSION=$(shell rpm -q --qf "%{VERSION}\n" --specfile ${PKGNAME}.spec | head -n1)
RELEASE=$(shell rpm -q --qf "%{RELEASE}\n" --specfile ${PKGNAME}.spec | head -n1)
GITTAG=${PKGNAME}-$(VERSION)
PKGRPMFLAGS=--define "_topdir ${PWD}" --define "_specdir ${PWD}" --define "_sourcedir ${PWD}/dist" --define "_srcrpmdir ${PWD}" --define "_rpmdir ${PWD}" --define "_builddir ${PWD}"

RPM="noarch/${PKGNAME}-$(VERSION)-$(RELEASE).noarch.rpm"
SRPM="${PKGNAME}-$(VERSION)-$(RELEASE).src.rpm"

PYTEST=pytest


all: help


help:
	@echo "Usage: make <target>"
	@echo
	@echo "Available targets are:"
	@echo " help                    show this text"
	@echo " clean                   remove python bytecode and temp files"
	@echo " doc                     build documentation"
	@echo " install                 install program on current system"
	@echo " test                    run tests"
	@echo " test-coverage           run tests and generate a coverage report"
	@echo " test-compose            run a small teest compose (requires test data)"
	@echo " test-data               build test data (requirement for running tests)"
	@echo
	@echo "Available rel-eng targets are:"
	@echo " archive                 create source tarball"
	@echo " log                     display changelog for spec file"
	@echo " tag                     create a git tag according to version and release from spec file"
	@echo " rpm                     build rpm"
	@echo " srpm                    build srpm"
	@echo " rpminstall              build rpm and install it"
	@echo " release                 build srpm and create git tag"


tag:
	@git tag -a -m "Tag as $(GITTAG)" -f $(GITTAG)
	@echo "Tagged as $(GITTAG)"


Changelog:
	(GIT_DIR=.git git log > .changelog.tmp && mv .changelog.tmp Changelog; rm -f .changelog.tmp) || (touch Changelog; echo 'git directory not found: installing possibly empty changelog.' >&2)


log:
	@(LC_ALL=C date +"* %a %b %e %Y `git config --get user.name` <`git config --get user.email`> - VERSION"; git log --pretty="format:- %s (%ae)" | sed -r 's/ \(([^@]+)@[^)]+\)/ (\1)/g' | cat) | less


archive:
	@rm -f Changelog
	@rm -f MANIFEST
	@make Changelog
	@rm -rf ${PKGNAME}-$(VERSION)/
	@python setup.py sdist --formats=bztar > /dev/null
	@echo "The archive is in dist/${PKGNAME}-$(VERSION).tar.bz2"


srpm: archive
	@rm -f $(SRPM)
	@rpmbuild -bs ${PKGRPMFLAGS} ${PKGNAME}.spec
	@echo "The srpm is in $(SRPM)"


rpm: archive
	@rpmbuild --clean -bb ${PKGRPMFLAGS} ${PKGNAME}.spec
	@echo "The rpm is in $(RPM)"


rpminstall: rpm
	@rpm -ivh --force $(RPM)


release: tag srpm


install:
	@python setup.py install


clean:
	@python setup.py clean
	@rm -vf *.rpm
	@rm -vrf noarch
	@rm -vf *.tar.gz
	@rm -vrf dist
	@rm -vf MANIFEST
	@rm -vf Changelog
	@find . -\( -name "*.pyc" -o -name '*.pyo' -o -name "*~" -o -name "__pycache__" -\) -delete
	@find . -depth -type d -a -name '*.egg-info' -exec rm -rf {} \;


test:
	$(PYTEST) $(PYTEST_OPTS)

test-coverage:
	$(PYTEST) --cov=pungi --cov-report term --cov-report html --cov-config tox.ini $(PYTEST_OPTS)

test-data:
	./tests/data/specs/build.sh

test-compose:
	cd tests && ./test_compose.sh

test-multi-compose:
	PYTHONPATH=$$(pwd) PATH=$$(pwd)/bin:$$PATH pungi-orchestrate --debug start tests/data/multi-compose.conf

doc:
	cd doc; make html
