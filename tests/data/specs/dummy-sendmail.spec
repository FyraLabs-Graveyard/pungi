Name:           dummy-sendmail
Version:        8.14.5
Release:        12
License:        LGPLv2
Summary:        A dummy sendmail package
Requires:       dummy-glibc
Provides:       MTA
Provides:       server(smtp)
Provides:       smtpdaemon

%description
A dummy sendmail package

%package debuginfo
Summary:        A dummy sendmail-debuginfo package
Group:          Development/Debug

%description debuginfo
A dummy sendmail-debuginfo package


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
* Tue Oct 18 2011 Daniel Mach <dmach@redhat.com> - 8.14.5-12
- First release
