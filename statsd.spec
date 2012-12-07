Name:           statsd
##latest released version # found here https://github.com/etsy/statsd/tags
#fetch the tarball from here too
#wget --no-check-certificate https://github.com/etsy/statsd/archive/v0.5.0.tar.gz -O statsd-0.5.0.tar.gz
Version:        0.5.0
Release:        3%{?dist}
Summary:        monitoring daemon for graphite and others, that aggregates events received by udp in 10 second intervals
Group:          Applications/Internet
License:        Etsy open source license
URL:            https://github.com/etsy/statsd
Vendor:         Etsy
Packager:       keen99
Source0:        %{name}-%{version}.tar.gz
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildArch:      noarch
Requires:       nodejs 

%description
Simple daemon for easy stats aggregation 

%prep
if [ -e %{buildroot} ] 
 then
	#make sure we always get a clean output target
	echo "deleting existing buildroot: %{buildroot}"
	%{__rm} -rf %{buildroot}
fi

%setup -q

%build
#echo "build not needed" 

%install

# install the js files which do the work
%{__mkdir_p} %{buildroot}/usr/share/%{name}
#this is horridly ugly, but it works anyway.
#remove files we dont want first
%{__rm} .gitignore .travis*
#now find all the files and dirs and put them in place
%{__install} -Dp -m0644 $(find  ./ -maxdepth 1 -type f) %{buildroot}/usr/share/%{name}
for dir in $(find  ./ -maxdepth 1 -type d|sed 's|./||g')
 do
	%{__install} -Dp -m0755 -d $dir %{buildroot}/usr/share/%{name}/$dir/
	%{__install} -Dp -m0644 $(find  ./$dir -maxdepth 1 -type f) %{buildroot}/usr/share/%{name}/$dir
done

# Install init script
%{__install} -Dp -m0755 $RPM_SOURCE_DIR/%{name}-initd %{buildroot}%{_initrddir}/%{name}

# Install default configuration files
#create our default config from the example config
sed 's|graphite.host.com|localhost|g' exampleConfig.js > %{buildroot}-config.js
%{__install} -Dp -m0644 %{buildroot}-config.js %{buildroot}%{_sysconfdir}/%{name}/config.js

#and create the lockfile dir/file so we can %ghost it to register ownership
%{__mkdir_p} %{buildroot}%{_localstatedir}/lock/subsys
touch %{buildroot}%{_localstatedir}/lock/subsys/%{name}
exit 0

%pre
getent group %{name} >/dev/null || groupadd -g 306 -r %{name}
getent passwd %{name} >/dev/null || \
    useradd -r -g %{name} -u 306 -d %{_localstatedir}/lib/%{name} \
    -s /sbin/nologin -c "%{name} daemon" %{name}
exit 0

%preun
#final uninstall will stop service now, update keeps service running to remember service state for restart in post
if [ $1 = 0 ]; then
	service %{name} stop
	#do this in pre, not post - it errors if the init.d script has been removed
	chkconfig --del %{name}
fi
exit 0

%postun
if [ $1 = 0 ]; then
	getent passwd %{name} >/dev/null && \
	userdel -r %{name} 2>/dev/null
fi
exit 0

%post
#before we start statds
##update carbon configs if they exist to match up to default settings for statsd
if [ -d %{_sysconfdir}/carbon ]
 then
	echo "NOTICE: updating graphite configs in %{_sysconfdir}/carbon for statsd defaults"

	echo "updating storage-aggregation.conf"
	if [ -e %{_sysconfdir}/carbon/storage-aggregation.conf ]
	 then
		targetfile=%{_sysconfdir}/carbon/storage-aggregation.conf
		srcfile=%{_sysconfdir}/carbon/storage-aggregation.conf.before-%{name}
		cp $targetfile $srcfile
		echo "updating existing $targetfile"
	else
		examplefile=$(ls -1 /usr/share/doc/carbon-*/storage-aggregation.conf.example)
		if [ -e $examplefile ]
		 then
			srcfile=$examplefile
			targetfile=%{_sysconfdir}/carbon/storage-aggregation.conf
			echo "creating new $targetfile from $examplefile"
		else
			echo "WARNING: no example file at $examplefile"
			echo "cannot install our config, sorry."
		fi
	fi

	if [ ! "x$targetfile" = "x" ] 
	 then
		if [ ! -e $targetfile ] || ! grep -qF '^stats' $targetfile
		 then
			## locate [default_average] and insert above there
#dont indent please
aggstuff='
##for statsd from etsy/statsd readme
#for statsd - must be before the default
[min]
pattern = ^stats.*\.min$
xFilesFactor = 0.1
aggregationMethod = min

[max]
pattern = ^stats.*\.max$
xFilesFactor = 0.1
aggregationMethod = max

[sum]
pattern = ^stats.*\.count$
xFilesFactor = 0
aggregationMethod = sum
#end statsd
'
			while read line
			 do
				echo $line | grep -q '\[default_average\]'
				[ $? -eq 0 ] && echo "$aggstuff"
				echo "$line"
			done < ${srcfile} > ${targetfile}
		else
			echo "Found ^stats in $targetfile, not updating"
		fi
	fi


	echo "updating storage-schemas.conf"
	if [ -e %{_sysconfdir}/carbon/storage-schemas.conf ]
	 then
		targetfile=%{_sysconfdir}/carbon/storage-schemas.conf
		srcfile=%{_sysconfdir}/carbon/storage-schemas.conf.before-%{name}
		cp $targetfile $srcfile
		echo "updating existing $targetfile"
	else
		examplefile=$(ls -1 /usr/share/doc/carbon-*/storage-schemas.conf.example)
		if [ -e $examplefile ]
		 then
			srcfile=$examplefile
			targetfile=%{_sysconfdir}/carbon/storage-schemas.conf
			echo "creating new $targetfile from $examplefile"
		else
			echo "WARNING: no example file at $examplefile"
			echo "cannot install our config, sorry."
		fi
	fi
	if [ ! "x$targetfile" = "x" ]
	 then	
		if [ ! -e $targetfile ] || ! grep -qF '^stats' $targetfile
		 then
			## locate [default_1min_for_1day] and insert above there
#dont indent please
schemastuff='
##for statsd from etsy/statsd readme
#for statsd - must be before the default
[stats]
pattern = ^stats.*
retentions = 10:2160,60:10080,600:262974
#end statsd
'
			while read line
			 do
				echo $line | grep -q '\[default_1min_for_1day\]'
				[ $? -eq 0 ] && echo "$schemastuff"
				echo "$line"
			done < ${srcfile} > ${targetfile}
		else
			echo "Found ^stats in $targetfile, not updating"
		fi
	fi

	echo "Restarting carbon-aggregator to apply changes"
	sbin/service carbon-aggregator restart
else
	echo "WARNING: %{_sysconfdir}/carbon not found, assuming you don't have graphite installed here"
	echo "not performing graphite setup"
fi

#now after we've got carbon updated...
chkconfig --add %{name}
##while this seems a bit overkill, it's to handle the yum upgrade case and preserve running/not running state
if [ $1 -gt 1 ]; then
    # restart service if it was running
    if /sbin/service %{name} status > /dev/null 2>&1; then
        echo "Restarting %{name} service because it was running."
        if ! /sbin/service %{name} restart ; then
                logger -s -t "%name" -- "Installation failure. Not able to restart the service." 
                exit 1
        fi
    else
	echo "Starting ${name}"
        if ! /sbin/service %{name} start ; then
                logger -s -t "%name" -- "Installation failure. Not able to start the service." 
                exit 1
        fi
    fi
else
#go ahead and start it if we didn't hit the above case - we chkconfig'd it on after all.
	echo "Starting ${name}"
        if ! /sbin/service %{name} start ; then
                logger -s -t "%name" -- "Installation failure. Not able to start the service." 
                exit 1
        fi
fi


exit 0

%clean
#this gets run only after a successful build and package, cleans up the assembled output
if [ "%{buildroot}" != "/" ] 
 then
	echo "cleaning %{buildroot}"
	%{__rm} -rf %{buildroot}*
else
	echo "ERROR:  buildroot is /, cannot clean"
	exit 1
fi

%files
%defattr(-,root,root,-)
%doc LICENSE README.md
%doc examples
%doc exampleConfig.js
/usr/share/%{name}/*
%{_initrddir}/%{name}
%config %{_sysconfdir}/%{name}
#own, but don't actually put in place
%ghost %{_localstatedir}/lock/subsys/%{name}


%changelog
* Fri Dec 7 2012 David Raistrick <keen@icantclick.org> - 0.5.0-3
- reorder configs and service start to get carbon configs updated -before- we start statsd, prevents things like 
  statsd.numStats from using the default schema
* Thu Nov 29 2012 David Raistrick <keen@icantclick.org> - 0.5.0-2
- add magic to update graphite configs to match up with statsd defaults
* Tue Nov 27 2012 David Raistrick <keen@icantclick.org> - 0.5.0-1
- nearly complete rewrite to use etsy statsd - based on oli99sc's is24-statsd rpm which uses a different statsd build
