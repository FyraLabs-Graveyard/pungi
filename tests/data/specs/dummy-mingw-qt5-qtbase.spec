Name:           dummy-mingw-qt5-qtbase
Version:        5.6.0
Release:        1
License:        LGPLv2
Summary:        A dummy mingw qt5 qtbase package

%description
A dummy package with noarch debuginfo

%package -n dummy-mingw32-qt5-qtbase
Summary:        A dummy mingw32-qt5-qtbase package
BuildArch:      noarch

%description -n dummy-mingw32-qt5-qtbase
A dummy 32bit mingw-qt5-qtbase package

%package -n dummy-mingw32-qt5-qtbase-debuginfo
Summary:        A dummy mingw32-qt5-qtbase package debuginfo
BuildArch:      noarch

%description -n dummy-mingw32-qt5-qtbase-debuginfo
A dummy 32bit mingw-qt5-qtbase package debuginfo

#%prep
#%setup -q


%build
echo OK


%install
rm -rf $RPM_BUILD_ROOT
mkdir $RPM_BUILD_ROOT


%clean
rm -rf $RPM_BUILD_ROOT


%files -n dummy-mingw32-qt5-qtbase
%files -n dummy-mingw32-qt5-qtbase-debuginfo


%changelog
* Mon Nov 7 2016 Lubomír Sedlář <lsedlar@redhat.com> - 5.6.0-1
- First release
