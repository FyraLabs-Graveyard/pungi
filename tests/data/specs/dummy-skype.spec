Name:           dummy-skype
Version:        4.2.0.13
Release:        1
License:        LGPLv2
Summary:        A dummy skype package
ExclusiveArch:  i586

%if %__isa_bits == 32
Requires:       libc.so.6()
%else
Requires:       libc.so.6()(64bit)
%endif

%description
A dummy skype package


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


%changelog
* Tue Oct 18 2011 Daniel Mach <dmach@redhat.com> - 4.2.0.13-1
- First release
