Name:           dummy-fcoe-target-utils
Version:        2.0
Release:        5
License:        LGPLv2
Summary:        A dummy fcoe-target-utils package

BuildArch:      noarch
ExcludeArch:    ppc s390 s390x

%description
A dummy fcoe-target-utils package


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
* Tue Oct 18 2011 Daniel Mach <dmach@redhat.com> - 2.0-5
- First release
