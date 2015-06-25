Name:           dummy-elinks
Version:        2.6
Release:        2
License:        LGPLv2
Summary:        A dummy elinks package
Requires:       dummy-glibc

%description
A dummy elinks package

%package debuginfo
Summary:        A dummy elinks-debuginfo package
Group:          Development/Debug

%description debuginfo
A dummy elinks-debuginfo package


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
* Tue Oct 18 2011 Daniel Mach <dmach@redhat.com> - 2.6-2
- First release
