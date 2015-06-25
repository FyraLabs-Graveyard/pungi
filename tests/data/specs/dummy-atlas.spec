Name:           dummy-atlas
Version:        3.8.4
Release:        7
License:        LGPLv2
Summary:        A dummy atlas package

%description
A dummy atlas package

%package devel
Summary:        A dummy atlas-devel package
Requires:       %{name} = %{version}-%{release}

%description devel
A dummy atlas-devel package


# ----------


%ifarch x86_64

%package sse3
Summary:        A dummy atlas-sse3 package
Provides:       %{name} = %{version}-%{release}

%description sse3
A dummy atlas-sse3 package

%package sse3-devel
Summary:        A dummy atlas-sse3-devel package
Requires:       %{name}-sse3 = %{version}-%{release}

%description sse3-devel
A dummy atlas-sse3-devel package

%endif


# ----------


%ifarch %{ix86}

%package 3dnow
Summary:        A dummy atlas-3dnow package
Provides:       %{name} = %{version}-%{release}

%description 3dnow
A dummy atlas-3dnow package

%package 3dnow-devel
Summary:        A dummy atlas-3dnow-devel package
Requires:       %{name}-3dnow = %{version}-%{release}

%description 3dnow-devel
A dummy atlas-3dnow-devel package

%package sse
Summary:        A dummy atlas-sse package
Provides:       %{name} = %{version}-%{release}

%description sse
A dummy atlas-sse package

%package sse-devel
Summary:        A dummy atlas-sse-devel package
Requires:       %{name}-sse = %{version}-%{release}

%description sse-devel
A dummy atlas-sse-devel package

%package sse2
Summary:        A dummy atlas-sse2 package
Provides:       %{name} = %{version}-%{release}

%description sse2
A dummy atlas-sse2 package

%package sse2-devel
Summary:        A dummy atlas-sse2-devel package
Requires:       %{name}-sse2 = %{version}-%{release}

%description sse2-devel
A dummy atlas-sse2-devel package

%package sse3
Summary:        A dummy atlas-sse3 package
Provides:       %{name} = %{version}-%{release}

%description sse3
A dummy atlas-sse3 package

%package sse3-devel
Summary:        A dummy atlas-sse3-devel package
Requires:       %{name}-sse3 = %{version}-%{release}

%description sse3-devel
A dummy atlas-sse3-devel package

%endif


# ----------


%ifarch s390 s390x

%package z196
Summary:        A dummy atlas-z196 package
Provides:       %{name} = %{version}-%{release}

%description z196
A dummy atlas-z196 package

%package z196-devel
Summary:        A dummy atlas-z196-devel package
Requires:       %{name}-z196 = %{version}-%{release}

%description z196-devel
A dummy atlas-z196-devel package

%package z10
Summary:        A dummy atlas-z10 package
Provides:       %{name} = %{version}-%{release}

%description z10
A dummy atlas-z10 package

%package z10-devel
Summary:        A dummy atlas-z10-devel package
Requires:       %{name}-z10 = %{version}-%{release}

%description z10-devel
A dummy atlas-z10-devel package

%endif



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
%files devel

%ifarch x86_64
%files sse3
%files sse3-devel
%endif

%ifarch %{ix86}
%files 3dnow
%files 3dnow-devel
%files sse
%files sse-devel
%files sse2
%files sse2-devel
%files sse3
%files sse3-devel
%endif

%ifarch s390 s390x
%files z196
%files z196-devel
%files z10
%files z10-devel
%endif


%changelog
* Tue Oct 18 2011 Daniel Mach <dmach@redhat.com> - 3.8.4-7
- First release
