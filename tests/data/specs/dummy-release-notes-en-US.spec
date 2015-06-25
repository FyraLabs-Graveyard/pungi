Name:           dummy-release-notes-en-US
Version:        1.2
Release:        1
License:        LGPLv2
Summary:        A dummy release-notes-en-US package

BuildArch:      noarch

%description
A dummy release-notes-en-US package


#%prep
#%setup -q


%build
echo OK


%install
rm -rf $RPM_BUILD_ROOT
mkdir $RPM_BUILD_ROOT
mkdir -p $RPM_BUILD_ROOT/usr/share/doc/%{name}/
touch $RPM_BUILD_ROOT/usr/share/doc/%{name}/index.html


%clean
rm -rf $RPM_BUILD_ROOT


%files
%doc /usr/share/doc/%{name}/index.html


%changelog
* Tue Oct 18 2011 Daniel Mach <dmach@redhat.com> - 1.2-1
- First release
