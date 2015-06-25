Name:           dummy-vacation
Version:        1.2.7.1
Release:        1
License:        LGPLv2
Summary:        A dummy vacation package
Requires:       dummy-glibc
Requires:       smtpdaemon

%description
A dummy vacation package

%package debuginfo
Summary:        A dummy vacation-debuginfo package
Group:          Development/Debug

%description debuginfo
A dummy vacation-debuginfo package


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
* Tue Oct 18 2011 Daniel Mach <dmach@redhat.com> - 1.2.7.1-1
- First release
