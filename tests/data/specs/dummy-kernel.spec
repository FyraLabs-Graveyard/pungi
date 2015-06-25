Name:           dummy-kernel
Version:        3.1.0
Release:        1
License:        LGPLv2
Summary:        A dummy kernel package

%description
A dummy kernel package

%package headers
Summary:        A dummy kernel-headers package

%description headers
A dummy kernel-headers package

%package doc
Summary:        A dummy kernel-doc package
BuildArch:      noarch

%description doc
A dummy kernel-doc package


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
%files headers
%files doc


%changelog
* Tue Oct 18 2011 Daniel Mach <dmach@redhat.com> - 3.1.0-1
- First release
