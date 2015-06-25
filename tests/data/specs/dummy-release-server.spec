Name:           dummy-release-server
Version:        1.0.0
Release:        1
License:        LGPLv2
Summary:        A dummy release-server package
Provides:       system-release
Provides:       /etc/system-release
Provides:       /etc/%{name}

%description
A dummy release-server package


#%prep
#%setup -q


%build
echo OK


%install
rm -rf $RPM_BUILD_ROOT
mkdir $RPM_BUILD_ROOT
mkdir -p $RPM_BUILD_ROOT/usr/share/doc/dummy-relese-server/
touch $RPM_BUILD_ROOT/usr/share/doc/dummy-relese-server/EULA
touch $RPM_BUILD_ROOT/usr/share/doc/dummy-relese-server/EULA_cs
touch $RPM_BUILD_ROOT/usr/share/doc/dummy-relese-server/EULA_de

%clean
rm -rf $RPM_BUILD_ROOT


%files
/usr/share/doc/dummy-relese-server/EULA
/usr/share/doc/dummy-relese-server/EULA_cs
/usr/share/doc/dummy-relese-server/EULA_de

%changelog
* Tue Oct 18 2011 Daniel Mach <dmach@redhat.com> - 1.0.0-1
- First release
