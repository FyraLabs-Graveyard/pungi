Name:           dummy-filesystem
Version:        4.2.37
Release:        6
License:        LGPLv2
Summary:        A dummy filesystem package


%description
A dummy filesystem package


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
* Tue Oct 18 2011 Daniel Mach <dmach@redhat.com> - 4.2.37-6
- First release
