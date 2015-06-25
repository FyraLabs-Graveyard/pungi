Name:           dummy-bash
Version:        4.2.37
Release:        5
License:        LGPLv2
Summary:        A dummy bash package
Requires:       dummy-glibc

%description
A dummy bash package

%package debuginfo
Summary:        A dummy bash-debuginfo package
Group:          Development/Debug

%description debuginfo
A dummy bash-debuginfo package


%package doc
Summary:        A dummy bash-doc package
BuildArch:      noarch

%description doc
A dummy bash-doc package


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
%files doc


%changelog
* Tue Oct 18 2011 Daniel Mach <dmach@redhat.com> - 4.2.37-5
- First release
