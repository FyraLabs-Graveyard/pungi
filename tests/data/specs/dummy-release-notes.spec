Name:           dummy-release-notes
Version:        1.2
Release:        1
License:        LGPLv2
Summary:        A dummy release-notes package

BuildArch:      noarch

%description
A dummy release-notes package


#%prep
#%setup -q


%build
echo OK


%install
rm -rf $RPM_BUILD_ROOT
mkdir $RPM_BUILD_ROOT


%clean
rm -rf $RPM_BUILD_ROOT


%files


%changelog
* Tue Oct 18 2011 Daniel Mach <dmach@redhat.com> - 1.2-1
- First release
