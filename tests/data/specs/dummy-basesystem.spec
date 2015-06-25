Name:           dummy-basesystem
Version:        10.0
Release:        6
License:        LGPLv2
Summary:        A dummy basesystem package
Requires:       dummy-filesystem

BuildArch:      noarch

%description
A dummy basesystem package


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
* Tue Oct 18 2011 Daniel Mach <dmach@redhat.com> - 10.0-6
- First release
