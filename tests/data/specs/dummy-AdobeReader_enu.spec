Name:           dummy-AdobeReader_enu
Version:        9.5.1
Release:        1
License:        LGPLv2
Summary:        A dummy AdobeReader_enu package
Requires:       dummy-glibc
Source0:        %{name}-%{version}.tar.gz
NoSource:       0
ExclusiveArch:  i486

%description
A dummy AdobeReader_enu package


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
* Tue Oct 18 2011 Daniel Mach <dmach@redhat.com> - 9.5.1-1
- First release
