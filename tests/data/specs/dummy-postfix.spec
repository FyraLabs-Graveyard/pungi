Name:           dummy-postfix
Version:        2.9.2
Release:        2
License:        LGPLv2
Summary:        A dummy postfix package
Requires:       dummy-glibc
Provides:       MTA
Provides:       server(smtp)
Provides:       smtpdaemon

%description
A dummy postfix package

%package debuginfo
Summary:        A dummy postfix-debuginfo package
Group:          Development/Debug

%description debuginfo
A dummy postfix-debuginfo package


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
%files debuginfo


%changelog
* Tue Oct 18 2011 Daniel Mach <dmach@redhat.com> - 2.9.2-2
- First release
