Name:           dummy-firefox
Version:        16.0.1
Release:        1
License:        LGPLv2
Summary:        A dummy firefox package
BuildRequires:  dummy-krb5-devel
BuildRequires:  dummy-xulrunner
Requires:       dummy-xulrunner

%description
A dummy firefox package

%package debuginfo
Summary:        A dummy firefox-debuginfo package
Group:          Development/Debug

%description debuginfo
A dummy firefox-debuginfo package


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


%changelog
* Tue Oct 18 2011 Daniel Mach <dmach@redhat.com> - 16.0.1-1
- First release
