Name:           dummy-gfs2-utils
Version:        3.1.4
Release:        3
License:        LGPLv2
Summary:        A dummy gfs2-utils package
Requires:       dummy-glibc
Requires:       dummy-lvm2-devel

%description
A dummy gfs2-utils package

%package debuginfo
Summary:        A dummy gfs2-utils-debuginfo package
Group:          Development/Debug

%description debuginfo
A dummy gfs2-utils-debuginfo package


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
* Tue Oct 18 2011 Daniel Mach <dmach@redhat.com> - 3.1.4-3
- First release
