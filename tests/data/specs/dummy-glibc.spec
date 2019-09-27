Name:           dummy-glibc
Version:        2.14
Release:        5
License:        LGPLv2
Summary:        A dummy glibc package
Requires:       %{name}-common = %{version}-%{release}
Requires:       dummy-basesystem
%if %__isa_bits == 32
Provides:       libc.so.6()
Provides:       libpthread.so.0(GLIBC_2.0)
%else
Provides:       libc.so.6()(64bit)
Provides:       libpthread.so.0(GLIBC_2.3)(64bit)
%endif

%description
A dummy glibc package

%package common
Summary:        A dummy glibc-common package

%description common
A dummy glibc-common package

%package -n dummy-nscd
Summary:        A dummy nscd package

%description -n dummy-nscd
A dummy nscd package

%package debuginfo
Summary:        A dummy glibc-debuginfo package
Group:          Development/Debug
Requires:	%{name}-debuginfo-common%{?_isa} = %{version}-%{release}

%description debuginfo
A dummy glibc-debuginfo package

%package debuginfo-common
Summary:        A dummy glibc-debuginfo-common package
Group:          Development/Debug

%description debuginfo-common
A dummy glibc-debuginfo-common package


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
%if %__isa_bits == 32
%ghost /lib/libc.so.6
%else
%ghost /lib64/libc.so.6
%endif

%files common
%files -n dummy-nscd
%files debuginfo
%files debuginfo-common


%changelog
* Tue Oct 18 2011 Daniel Mach <dmach@redhat.com> - 2.14-5
- First release
