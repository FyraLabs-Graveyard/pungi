Name:           dummy-foo32
Version:        1
Release:        1
License:        LGPLv2
Summary:        A dummy foo32 package
ExclusiveArch:  i686 ppc s390

%description
A dummy foo32 package

%package doc
Summary:        A dummy foo32-doc package
BuildArch:      noarch

%description doc
A dummy foo32-doc package


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
%files doc


%changelog
* Tue Oct 18 2011 Daniel Mach <dmach@redhat.com> - 1-1
- First release
