Name:           dummy-perl
Version:        1.0.0
Release:        1
License:        LGPLv2
Summary:        A dummy perl package
Requires(pre):  dummy-perl-macros
Requires(post): dummy-perl-utils

%description
A dummy perl package. This packages demonstrates a Requires(pre) and
Requires(post) dependencies.

%package macros
Summary:        A dummy perl-macros package

%description macros
A dummy perl-macros package

%package utils
Summary:        A dummy perl-utils package

%description utils
A dummy perl-utils package


%build
echo OK


%install
rm -rf $RPM_BUILD_ROOT
mkdir $RPM_BUILD_ROOT


%files
%files macros
%files utils


%changelog
* Mon Jan 23 2017 Lubomír Sedlář <lsedlar@redhat.com> - 1.0.0-1
- First release
