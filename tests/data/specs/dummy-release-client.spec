Name:           dummy-release-client
Version:        1.0.0
Release:        1
License:        LGPLv2
Summary:        A dummy release-client package
Provides:       system-release
Provides:       /etc/system-release
Provides:       /etc/%{name}

%description
A dummy release-client package


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
* Tue Oct 18 2011 Daniel Mach <dmach@redhat.com> - 1.0.0-1
- First release
