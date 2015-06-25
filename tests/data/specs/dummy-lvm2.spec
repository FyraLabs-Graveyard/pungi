Name:           dummy-lvm2
Version:        2.02.84
Release:        4
License:        LGPLv2
Summary:        A dummy lvm2 package

Requires:       dummy-glibc
Requires:       %{name}-libs = %{version}-%{release}

%description
A dummy glibc package

%package libs
Summary:        A dummy lvm2-libs package

%description libs
A dummy lvm2-libs package

%package cluster
Summary:        A dummy lvm2-cluster package
Requires:       %{name} = %{version}-%{release}

%description cluster
A dummy lvm2-cluster package

%package devel
Summary:        A dummy lvm2-devel package
Requires:       %{name} = %{version}-%{release}

%description devel
A dummy lvm2-devel package

%package debuginfo
Summary:        A dummy lvm2-debuginfo package
Group:          Development/Debug

%description debuginfo
A dummy lvm2-debuginfo package


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
%files libs
%files cluster
%files devel
%files debuginfo

%changelog
* Tue Oct 18 2011 Daniel Mach <dmach@redhat.com> - 2.02.84-4
- First release
