Name:           dummy-ipw3945-kmod
Version:        1.2.0
Release:        4.20
License:        LGPLv2
Summary:        A dummy ipw3945-kmod package

%description
A dummy ipw3945-kmod package

%package -n dummy-kmod-ipw3945
Summary:        A dummy kmod-ipw3945 package

%description -n dummy-kmod-ipw3945
A dummy kmod-ipw3945 package

%package -n dummy-kmod-ipw3945-xen
Summary:        A dummy kmod-ipw3945-xen package

%description -n dummy-kmod-ipw3945-xen
A dummy kmod-ipw3945-xen package

%package -n dummy-ipw3945-kmod-debuginfo
Summary:        A dummy ipw3945-kmod-debuginfo package
Group:          Development/Debug

%description -n dummy-ipw3945-kmod-debuginfo
A dummy ipw3945-kmod-debuginfo package


#%prep
#%setup -q


%build
echo OK


%install
rm -rf $RPM_BUILD_ROOT
mkdir $RPM_BUILD_ROOT


%clean
rm -rf $RPM_BUILD_ROOT


%files -n dummy-kmod-ipw3945
%files -n dummy-kmod-ipw3945-xen
%files -n dummy-ipw3945-kmod-debuginfo


%changelog
* Tue Oct 18 2011 Daniel Mach <dmach@redhat.com> - 1.2.0-4.20
- First release
