Name:           dummy-imsettings
Version:        1.2.9
Release:        1
License:        LGPLv2
Summary:        A dummy imsettings package
Requires:       dummy-imsettings-desktop-module = %{version}-%{release}

%description
A dummy imsettings package

%package gnome
Summary:        A dummy imsettings-gnome package
Provides:       dummy-imsettings-desktop-module = %{version}-%{release}

%description gnome
A dummy imsettings-gnome package

%package qt
Summary:        A dummy imsettings-qt package
Provides:       dummy-imsettings-desktop-module = %{version}-%{release}

%description qt
A dummy imsettings-qt package


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
%files gnome
%files qt


%changelog
* Tue Oct 18 2011 Daniel Mach <dmach@redhat.com> - 5.2-6
- First release
