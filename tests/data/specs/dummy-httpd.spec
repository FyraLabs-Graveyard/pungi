Name:           dummy-httpd
Version:        2.2.21
Release:        1
License:        LGPLv2
Summary:        A dummy httpd package
Requires:       dummy-glibc

%description
A dummy httpd package

%package debuginfo
Summary:        A dummy httpd-debuginfo package
Group:          Development/Debug

%description debuginfo
A dummy httpd-debuginfo package


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
* Tue Oct 18 2011 Daniel Mach <dmach@redhat.com> - 2.2.21-1
- First release
