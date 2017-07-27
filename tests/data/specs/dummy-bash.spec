Name:           dummy-bash
Version:        4.2.37
Release:        6
License:        LGPLv2
Summary:        A dummy bash package
Requires:       dummy-glibc
%if %__isa_bits == 32
Requires:       libpthread.so.0(GLIBC_2.0)
%else
Requires:       libpthread.so.0(GLIBC_2.3)(64bit)
%endif

%description
A dummy bash package

%package debuginfo
Summary:        A dummy bash-debuginfo package
Group:          Development/Debug

%description debuginfo
A dummy bash-debuginfo package


%package debugsource
Summary:        A dummy bash-debugsource package
Group:          Development/Debug

%description debugsource
A dummy bash-debugsource package


%package doc
Summary:        A dummy bash-doc package
BuildArch:      noarch
Requires:       %{name}

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
%files debugsource
%files doc


%changelog
* Tue Oct 18 2011 Daniel Mach <dmach@redhat.com> - 4.2.37-6
- First release
