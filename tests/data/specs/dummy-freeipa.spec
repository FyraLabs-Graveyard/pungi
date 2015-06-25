Name:           dummy-freeipa
Version:        2.2.0
Release:        1
License:        LGPLv2
Summary:        A dummy freeipa package

%description
A dummy freeipa package

%package server
Summary:        A dummy freeipa-server package
Requires:       dummy-selinux-policy-base

%description server
A dummy freeipa-server package


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
%files server


%changelog
* Tue Oct 18 2011 Daniel Mach <dmach@redhat.com> - 2.2.0-1
- First release
