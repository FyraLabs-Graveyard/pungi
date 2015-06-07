Name:           pungi
Version:        4.0
Release:        0.9%{?dist}
Summary:        Distribution compose tool

Group:          Development/Tools
License:        GPLv2
URL:            https://fedorahosted.org/pungi
Source0:        https://fedorahosted.org/pungi/attachment/wiki/%{version}/%{name}-%{version}.tar.bz2
Requires:       createrepo >= 0.4.11
Requires:       yum => 3.4.3-28
Requires:       lorax >= 22.1
Requires:       repoview
Requires:       python-lockfile
Requires:       kobo
Requires:       python-productmd
Requires:       python-kickstart
Requires:       libselinux-python
Requires:       createrepo_c

BuildArch:      noarch

%description
A tool to create anaconda based installation trees/isos of a set of rpms.

%prep
%setup -q

%build
%{__python} setup.py build

%install
rm -rf $RPM_BUILD_ROOT
%{__python} setup.py install -O1 --skip-build --root $RPM_BUILD_ROOT
%{__install} -d $RPM_BUILD_ROOT/var/cache/pungi
%{__install} -d $RPM_BUILD_ROOT/%{_mandir}/man8
%{__install} doc/pungi.8 $RPM_BUILD_ROOT/%{_mandir}/man8/

%files
%defattr(-,root,root,-)
%license COPYING GPL
%doc AUTHORS doc/README
%{python_sitelib}/%{name}
%{python_sitelib}/%{name}-%{version}-py?.?.egg-info
%{_bindir}/*
%{_datadir}/pungi
%{_mandir}/man8/pungi.8.gz
/var/cache/pungi

%changelog
* Sun Jun 07 2015 Dennis Gilmore <dennis@ausil.us> - 4.0-0.9
- update docs now devel-4-pungi is merged to master, minor spelling fixes
  (pbrobinson)
- Fix remaining productmd issues. (dmach)
- Revert "refactor metadata.py to use productmd's compose.dump for composeinfo"
  (dmach)
- Fix LoraxTreeInfo class inheritance. (dmach)
- Fix pungi -> pungi_wrapper namespace issue. (dmach)
- fix arg order for checksums.add (admiller)
- update for productmd checksums.add to TreeInfo (admiller)
- fix product -> release namespace change for productmd (admiller)
- update arch manifest.add config order for productmd api call (admiller)
- update for new productmd named args to rpms (admiller)
- fix pungi vs pungi_wrapper namespacing in method_deps.py (admiller)
- add createrepo_c Requires to pungi.spec (admiller)
- add comps_filter (admiller)
- refactor metadata.py to use productmd's compose.dump for composeinfo instead
  of pungi compose_to_composeinfo (admiller)
- Update compose, phases{buildinstall,createiso,gather/__ini__} to use correct
  productmd API calls (admiller)
- Use libselinux-python instead of subprocess (lmacken)
- Add README for contributors (admiller)

* Wed May 20 2015 Dennis Gilmore <dennis@ausil.us> - 4.0-0.8
- fix up bad += from early test of implementing different iso labels based on
  if there is a variant or not (dennis)

* Wed May 20 2015 Dennis Gilmore <dennis@ausil.us> - 4.0-0.7
- make sure we treat the isfinal option as a boolean when fetching it (dennis)
- if there is a variant use it in the volume id and shorten it. this will make
  each producst install tree have different volume ids for their isos (dennis)
- fix up productmd import in the executable (dennis)
- fixup productmd imports for changes with open sourcing (dennis)
- tell the scm wrapper to do an absolute import otherwise we hit a circular dep
  issue and things go wonky (dennis)
- include the dtd files in /usr/share/pungi (dennis)
- add missing ) causing a syntax error (dennis)
- fix up the productmd imports to import the function from the common module
  (dennis)
- fix up typo in getting arch for the lorax log file (dennis)

* Sat Mar 14 2015 Dennis Gilmore <dennis@ausil.us> - 4.0-0.6.20150314.gitd337c34
- update the git snapshot to pick up some fixes

* Fri Mar 13 2015 Dennis Gilmore <dennis@ausil.us> - 4.0-0.5.git18d4d2e
- update Requires for rename of python-productmd

* Thu Mar 12 2015 Dennis Gilmore <dennis@ausil.us> - 4.0-0.4.git18d4d2e
- fix up the pungi logging by putting the arch in the log file name (dennis)
- change pypungi imports to pungi (dennis)
- spec file cleanups (dennis)

* Thu Mar 12 2015 Dennis Gilmore <dennis@ausil.us> - 4.0-0.3.gita3158ec
- rename binaries (dennis)
- Add the option to pass a custom path for the multilib config files (bcl)
- Call lorax as a process not a library (bcl)
- Close child fds when using subprocess (bcl)
- fixup setup.py and MANIFEST.in to make a useable tarball (dennis)
- switch to BSD style hashes for the iso checksums (dennis)
- refactor to get better data into .treeinfo (dennis)
- Initial code merge for Pungi 4.0. (dmach)
- Initial changes for Pungi 4.0. (dmach)
- Add --nomacboot option (csieh)

* Thu Mar 12 2015 Dennis Gilmore <dennis@ausil.us> - 4.0-0.2.git320724e
- update git snapshot to switch to executing lorax since it is using dnf

* Thu Mar 12 2015 Dennis Gilmore <dennis@ausil.us> - 4.0-0.1.git64b6c80
- update to the pungi 4.0 dev branch

