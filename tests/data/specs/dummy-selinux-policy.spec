Name:           dummy-selinux-policy
Version:        3.10.0
Release:        121
License:        LGPLv2
Summary:        A dummy selinux-policy package
BuildArch:      noarch

%description
A dummy selinux-policy package

%package targeted
Summary:        A dummy selinux-policy-targeted package
Provides:       dummy-selinux-policy-base
Requires:       %{name} = %{version}-%{release}

%description targeted
A dummy selinux-policy-targeted package

%package mls
Summary:        A dummy selinux-policy-mls package
Provides:       dummy-selinux-policy-base
Requires:       %{name} = %{version}-%{release}

%description mls
A dummy selinux-policy-mls package

%package minimal
Summary:        A dummy selinux-policy-minimal package
Provides:       dummy-selinux-policy-base
Requires:       %{name} = %{version}-%{release}

%description minimal
A dummy selinux-policy-minimal package

%package doc
Summary:        A dummy selinux-policy-doc package
Requires:       %{name} = %{version}-%{release}

%description doc
A dummy selinux-policy-doc package


#%prep
#%setup -q


%build
echo OK


%install
rm -rf $RPM_BUILD_ROOT
mkdir $RPM_BUILD_ROOT


%clean
rm -rf $RPM_BUILD_ROOT


%files targeted
%files mls
%files minimal
%files doc


%changelog
* Tue Oct 18 2011 Daniel Mach <dmach@redhat.com> - 3.10.0-121
- First release
