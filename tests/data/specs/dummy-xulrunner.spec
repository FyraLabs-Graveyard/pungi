Name:           dummy-xulrunner
Version:        16.0.1
Release:        1
License:        LGPLv2
Summary:        A dummy xulrunner package
Requires:       dummy-glibc

%description
A dummy xulrunner package

%package debuginfo
Summary:        A dummy xulrunner-debuginfo package
Group:          Development/Debug

%description debuginfo
A dummy xulrunner-debuginfo package


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
* Tue Oct 18 2011 Daniel Mach <dmach@redhat.com> - 16.0.1-1
- First release
