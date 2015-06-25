Name:           dummy-resource-agents
Version:        3.9.5
Release:        8
License:        LGPLv2
Summary:        A dummy resource-agents package

%description
A dummy resource-agents package

%package -n dummy-glusterfs-resource-agents
Summary:        A dummy glusterfs-resource-agents package
Requires:       %{name} = %{version}-%{release}

%description -n dummy-glusterfs-resource-agents
A dummy glusterfs-resource-agents package

%package debuginfo
Summary:        A dummy resource-agents-debuginfo package
Group:          Development/Debug

%description debuginfo
A dummy resource-agents-debuginfo package


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
%files -n dummy-glusterfs-resource-agents
%files debuginfo


%changelog
* Tue Oct 18 2011 Daniel Mach <dmach@redhat.com> - 3.9.5-8
- First release
