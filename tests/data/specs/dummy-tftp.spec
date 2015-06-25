Name:           dummy-tftp
Version:        5.2
Release:        6
License:        LGPLv2
Summary:        A dummy tftp package
Requires:       dummy-glibc

%description
A dummy tftp package

%package debuginfo
Summary:        A dummy tftp-debuginfo package
Group:          Development/Debug

%description debuginfo
A dummy tftp-debuginfo package


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
* Tue Oct 18 2011 Daniel Mach <dmach@redhat.com> - 5.2-6
- First release
