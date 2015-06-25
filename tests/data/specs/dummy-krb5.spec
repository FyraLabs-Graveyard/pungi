Name:           dummy-krb5
Version:        1.10
Release:        5
License:        LGPLv2
Summary:        A dummy krb5 package

Requires:       dummy-glibc
Requires:       %{name}-libs = %{version}-%{release}
BuildRequires:  dummy-bash


%description
A dummy krb5 package

%package libs
Summary:        A dummy krb5-libs package

%description libs
A dummy krb5-libs package

%package workstation
Summary:        A dummy krb5-workstation package

%description workstation
A dummy krb5-workstation package

%package devel
Summary:        A dummy krb5-devel package
Requires:       %{name} = %{version}-%{release}

%description devel
A dummy krb5-devel package

%package debuginfo
Summary:        A dummy krb5-debuginfo package
Group:          Development/Debug

%description debuginfo
A dummy krb5-debuginfo package


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
%files devel
%files workstation
%files debuginfo

%changelog
* Tue Oct 18 2011 Daniel Mach <dmach@redhat.com> - 1.10-5
- First release
