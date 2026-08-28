# Android Concept Atlas virtual verification evidence

Captured: 2026-08-29 01:25:19 +09:00
Serial: emulator-5580
Scope: disposable Android Emulator only; no physical device.

## environment

### $ adb shell getprop ro.build.version.release
```text
13
```

### $ adb shell getprop ro.build.version.sdk
```text
33
```

### $ adb shell getprop ro.build.fingerprint
```text
google/sdk_gphone64_x86_64/emu64x:13/TE1A.240213.009/12342917:userdebug/dev-keys
```

### $ adb shell getprop ro.product.cpu.abi
```text
x86_64
```

### $ adb shell uname -a
```text
Linux localhost 5.15.119-android13-8-00034-gd34029c8258b-ab10871489 #1 SMP PREEMPT Wed Sep 27 18:42:24 UTC 2023 x86_64 Toybox
```

### $ adb shell id
```text
uid=2000(shell) gid=2000(shell) groups=2000(shell),1004(input),1007(log),1011(adb),1015(sdcard_rw),1028(sdcard_r),1078(ext_data_rw),1079(ext_obb_rw),3001(net_bt_admin),3002(net_bt),3003(inet),3006(net_bw_stats),3009(readproc),3011(uhid),3012(readtracefs) context=u:r:shell:s0
```

### $ adb shell getenforce
```text
Enforcing
```

## cpu-kernel

### $ adb shell cat /proc/cpuinfo
```text
processor	: 0
vendor_id	: AuthenticAMD
cpu family	: 26
model		: 96
model name	: AMD Ryzen AI 7 350 w/ Radeon 860M
stepping	: 0
microcode	: 0xffffffff
cpu MHz		: 4041.555
cache size	: 1024 KB
physical id	: 0
siblings	: 1
core id		: 0
cpu cores	: 1
apicid		: 0
initial apicid	: 0
fpu		: yes
fpu_exception	: yes
cpuid level	: 13
wp		: yes
flags		: fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush mmx fxsr sse sse2 syscall nx mmxext fxsr_opt pdpe1gb rdtscp lm constant_tsc rep_good nopl nonstop_tsc cpuid extd_apicid aperfmperf pni pclmulqdq ssse3 fma cx16 sse4_1 sse4_2 movbe popcnt aes xsave avx f16c rdrand hypervisor lahf_lm cmp_legacy cr8_legacy abm sse4a misalignsse 3dnowprefetch topoext vmmcall fsgsbase bmi1 avx2 smep bmi2 erms invpcid avx512f avx512dq rdseed adx avx512ifma clflushopt clwb avx512cd sha_ni avx512bw avx512vl xsaveopt xsavec xgetbv1 xsaves avx_vnni avx512_bf16 clzero xsaveerptr rdpru arat avx512vbmi umip avx512_vbmi2 gfni vaes vpclmulqdq avx512_vnni avx512_bitalg avx512_vpopcntdq rdpid fsrm avx512_vp2intersect
bugs		: sysret_ss_attrs null_seg spectre_v1 spectre_v2 spec_store_bypass
bogomips	: 3993.00
TLB size	: 192 4K pages
clflush size	: 64
cache_alignment	: 64
address sizes	: 48 bits physical, 48 bits virtual
power management:

processor	: 1
vendor_id	: AuthenticAMD
cpu family	: 26
model		: 96
model name	: AMD Ryzen AI 7 350 w/ Radeon 860M
stepping	: 0
microcode	: 0xffffffff
cpu MHz		: 4596.785
cache size	: 1024 KB
physical id	: 1
siblings	: 1
core id		: 0
cpu cores	: 1
apicid		: 1
initial apicid	: 1
fpu		: yes
fpu_exception	: yes
cpuid level	: 13
wp		: yes
flags		: fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush mmx fxsr sse sse2 syscall nx mmxext fxsr_opt pdpe1gb rdtscp lm constant_tsc rep_good nopl nonstop_tsc cpuid extd_apicid aperfmperf pni pclmulqdq ssse3 fma cx16 sse4_1 sse4_2 movbe popcnt aes xsave avx f16c rdrand hypervisor lahf_lm cmp_legacy cr8_legacy abm sse4a misalignsse 3dnowprefetch topoext vmmcall fsgsbase bmi1 avx2 smep bmi2 erms invpcid avx512f avx512dq rdseed adx avx512ifma clflushopt clwb avx512cd sha_ni avx512bw avx512vl xsaveopt xsavec xgetbv1 xsaves avx_vnni avx512_bf16 clzero xsaveerptr rdpru arat avx512vbmi umip avx512_vbmi2 gfni vaes vpclmulqdq avx512_vnni avx512_bitalg avx512_vpopcntdq rdpid fsrm avx512_vp2intersect
bugs		: sysret_ss_attrs null_seg spectre_v1 spectre_v2 spec_store_bypass
bogomips	: 4116.33
TLB size	: 192 4K pages
clflush size	: 64
cache_alignment	: 64
address sizes	: 48 bits physical, 48 bits virtual
power management:

processor	: 2
vendor_id	: AuthenticAMD
cpu family	: 26
model		: 96
model name	: AMD Ryzen AI 7 350 w/ Radeon 860M
stepping	: 0
microcode	: 0xffffffff
cpu MHz		: 4222.997
cache size	: 1024 KB
physical id	: 2
siblings	: 1
core id		: 0
cpu cores	: 1
apicid		: 2
initial apicid	: 2
fpu		: yes
fpu_exception	: yes
cpuid level	: 13
wp		: yes
flags		: fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush mmx fxsr sse sse2 syscall nx mmxext fxsr_opt pdpe1gb rdtscp lm constant_tsc rep_good nopl nonstop_tsc cpuid extd_apicid aperfmperf pni pclmulqdq ssse3 fma cx16 sse4_1 sse4_2 movbe popcnt aes xsave avx f16c rdrand hypervisor lahf_lm cmp_legacy cr8_legacy abm sse4a misalignsse 3dnowprefetch topoext vmmcall fsgsbase bmi1 avx2 smep bmi2 erms invpcid avx512f avx512dq rdseed adx avx512ifma clflushopt clwb avx512cd sha_ni avx512bw avx512vl xsaveopt xsavec xgetbv1 xsaves avx_vnni avx512_bf16 clzero xsaveerptr rdpru arat avx512vbmi umip avx512_vbmi2 gfni vaes vpclmulqdq avx512_vnni avx512_bitalg avx512_vpopcntdq rdpid fsrm avx512_vp2intersect
bugs		: sysret_ss_attrs null_seg spectre_v1 spectre_v2 spec_store_bypass
bogomips	: 3563.20
TLB size	: 192 4K pages
clflush size	: 64
cache_alignment	: 64
address sizes	: 48 bits physical, 48 bits virtual
power management:

processor	: 3
vendor_id	: AuthenticAMD
cpu family	: 26
model		: 96
model name	: AMD Ryzen AI 7 350 w/ Radeon 860M
stepping	: 0
microcode	: 0xffffffff
cpu MHz		: 4663.978
cache size	: 1024 KB
physical id	: 3
siblings	: 1
core id		: 0
cpu cores	: 1
apicid		: 3
initial apicid	: 3
fpu		: yes
fpu_exception	: yes
cpuid level	: 13
wp		: yes
flags		: fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush mmx fxsr sse sse2 syscall nx mmxext fxsr_opt pdpe1gb rdtscp lm constant_tsc rep_good nopl nonstop_tsc cpuid extd_apicid aperfmperf pni pclmulqdq ssse3 fma cx16 sse4_1 sse4_2 movbe popcnt aes xsave avx f16c rdrand hypervisor lahf_lm cmp_legacy cr8_legacy abm sse4a misalignsse 3dnowprefetch topoext vmmcall fsgsbase bmi1 avx2 smep bmi2 erms invpcid avx512f avx512dq rdseed adx avx512ifma clflushopt clwb avx512cd sha_ni avx512bw avx512vl xsaveopt xsavec xgetbv1 xsaves avx_vnni avx512_bf16 clzero xsaveerptr rdpru arat avx512vbmi umip avx512_vbmi2 gfni vaes vpclmulqdq avx512_vnni avx512_bitalg avx512_vpopcntdq rdpid fsrm avx512_vp2intersect
bugs		: sysret_ss_attrs null_seg spectre_v1 spectre_v2 spec_store_bypass
bogomips	: 3580.56
TLB size	: 192 4K pages
clflush size	: 64
cache_alignment	: 64
address sizes	: 48 bits physical, 48 bits virtual
power management:
```

### $ adb shell cat /proc/version
```text
Linux version 5.15.119-android13-8-00034-gd34029c8258b-ab10871489 (build-user@build-host) (Android (8508608, based on r450784e) clang version 14.0.7 (https://android.googlesource.com/toolchain/llvm-project 4c603efb0cca074e9238af8b4106c30add4418f6), LLD 14.0.7) #1 SMP PREEMPT Wed Sep 27 18:42:24 UTC 2023
```

### $ adb shell cat /proc/self/status
```text
Name:	cat
Umask:	0000
State:	R (running)
Tgid:	6938
Ngid:	0
Pid:	6938
PPid:	407
TracerPid:	0
Uid:	2000	2000	2000	2000
Gid:	2000	2000	2000	2000
FDSize:	128
Groups:	1004 1007 1011 1015 1028 1078 1079 3001 3002 3003 3006 3009 3011 3012
VmPeak:	10796952 kB
VmSize:	10796652 kB
VmLck:	       0 kB
VmPin:	       0 kB
VmHWM:	    3516 kB
VmRSS:	    3516 kB
RssAnon:	     652 kB
RssFile:	    2688 kB
RssShmem:	     176 kB
VmData:	    7808 kB
VmStk:	     132 kB
VmExe:	     284 kB
VmLib:	    4012 kB
VmPTE:	     120 kB
VmSwap:	       0 kB
CoreDumping:	0
THP_enabled:	1
Threads:	1
SigQ:	0/7842
SigPnd:	0000000000000000
ShdPnd:	0000000000000000
SigBlk:	0000000080000000
SigIgn:	0000002000000000
SigCgt:	0000004c400084f8
CapInh:	0000000000000000
CapPrm:	0000000000000000
CapEff:	0000000000000000
CapBnd:	000001ffffffffff
CapAmb:	0000000000000000
NoNewPrivs:	0
Seccomp:	0
Seccomp_filters:	0
Speculation_Store_Bypass:	vulnerable
SpeculationIndirectBranch:	always enabled
Cpus_allowed:	f
Cpus_allowed_list:	0-3
Mems_allowed:	1
Mems_allowed_list:	0
voluntary_ctxt_switches:	0
nonvoluntary_ctxt_switches:	8
```

### $ adb shell cat /proc/sys/kernel/randomize_va_space
```text
cat: /proc/sys/kernel/randomize_va_space: Permission denied
```

## boot-trust

### $ adb shell getprop ro.boot.verifiedbootstate
```text

```

### $ adb shell getprop ro.boot.flash.locked
```text

```

### $ adb shell getprop ro.boot.vbmeta.device_state
```text

```

### $ adb shell getprop ro.boot.slot_suffix
```text

```

### $ adb shell getprop ro.build.ab_update
```text
false
```

### $ adb shell getprop ro.treble.enabled
```text
true
```

### $ adb shell getprop ro.apex.updatable
```text
true
```

## process-isolation

### $ adb shell ps -A -o USER,PID,PPID,NAME,SECLABEL
```text
ps: bad -o 'USER,PID,PPID,NAME,SECLABEL'
Command line field types:

  ARGS    CMDLINE minus initial path     CMD     Thread name (/proc/TID/stat:2)
  CMDLINE Command line (argv[])          COMM    EXE filename (/proc/PID/exe)
  COMMAND EXE path (/proc/PID/exe)       NAME    Process name (PID's argv[0])

Process attribute field types:

  S       Process state:
	  R (running) S (sleeping) D (device I/O) T (stopped)  t (trace stop)
	  X (dead)    Z (zombie)   P (parked)     I (idle)
	  Also between Linux 2.6.33 and 3.13:
	  x (dead)    K (wakekill) W (waking)

  SCH     Scheduling policy (0=other, 1=fifo, 2=rr, 3=batch, 4=iso, 5=idle)
  STAT    Process state (S) plus:
	  < high priority          N low priority L locked memory
	  s session leader         + foreground   l multithreaded
                               ^
  %CPU    Percentage of CPU time used    %MEM    RSS as % of physical memory
  %VSZ    VSZ as % of physical memory    ADDR    Instruction pointer
  BIT     32 or 64                       C       Total %CPU used since start
  CPU     Which processor running on     DIO     Disk I/O
  DREAD   Data read from disk            DWRITE  Data written to disk
  ELAPSED Elapsed time since PID start   F       Flags 1=FORKNOEXEC 4=SUPERPRIV
  GID     Group ID                       GROUP   Group name
  IO      Data I/O                       LABEL   Security label
  MAJFL   Major page faults              MINFL   Minor page faults
  NI      Niceness (static 19 to -20)    PCY     Android scheduling policy
  PGID    Process Group ID               PID     Process ID
  PPID    Parent Process ID              PR      Prio Reversed (dyn 39-0, RT)
  PRI     Priority (dynamic 0 to 139)    PSR     Processor last executed on
  READ    Data read                      RES     Short RSS
  RGID    Real (before sgid) Group ID    RGROUP  Real (before sgid) group name
  RSS     Resident Set Size (DRAM pages) RTPRIO  Realtime priority
  RUID    Real (before suid) user ID     RUSER   Real (before suid) user name
  SHR     Shared memory                  STIME   Start time (ISO 8601)
  SWAP    Swap I/O                       SZ      4k pages to swap out
  TCNT    Thread count                   TID     Thread ID
  TIME    CPU time consumed              TIME+   CPU time (high precision)
  TTY     Controlling terminal           UID     User id
  USER    User name                      VIRT    Virtual memory size
  VSZ     Virtual memory size (1k units) WCHAN   Wait location in kernel
  WRITE   Data written
```

### $ adb shell cat /proc/1/status
```text
Name:	init
Umask:	0000
State:	S (sleeping)
Tgid:	1
Ngid:	0
Pid:	1
PPid:	0
TracerPid:	0
Uid:	0	0	0	0
Gid:	0	0	0	0
FDSize:	64
Groups:	3009
VmPeak:	10958016 kB
VmSize:	10956968 kB
VmLck:	       0 kB
VmPin:	       0 kB
VmHWM:	   11732 kB
VmRSS:	    2832 kB
RssAnon:	     628 kB
RssFile:	    1904 kB
RssShmem:	     300 kB
VmData:	   16180 kB
VmStk:	     132 kB
VmExe:	    1520 kB
VmLib:	    5700 kB
VmPTE:	     316 kB
VmSwap:	    2700 kB
CoreDumping:	0
THP_enabled:	1
Threads:	2
SigQ:	0/7842
SigPnd:	0000000000000000
ShdPnd:	0000000000000000
SigBlk:	0000000080010000
SigIgn:	0000002000000000
SigCgt:	0000004c400094f8
CapInh:	0000000000000000
CapPrm:	000001ffffffffff
CapEff:	000001ffffffffff
CapBnd:	000001ffffffffff
CapAmb:	0000000000000000
NoNewPrivs:	0
Seccomp:	0
Seccomp_filters:	0
Speculation_Store_Bypass:	vulnerable
SpeculationIndirectBranch:	always enabled
Cpus_allowed:	f
Cpus_allowed_list:	0-3
Mems_allowed:	1
Mems_allowed_list:	0
voluntary_ctxt_switches:	3116
nonvoluntary_ctxt_switches:	2032
```

### $ adb shell cat /proc/self/status
```text
Name:	cat
Umask:	0000
State:	R (running)
Tgid:	6976
Ngid:	0
Pid:	6976
PPid:	407
TracerPid:	0
Uid:	2000	2000	2000	2000
Gid:	2000	2000	2000	2000
FDSize:	128
Groups:	1004 1007 1011 1015 1028 1078 1079 3001 3002 3003 3006 3009 3011 3012
VmPeak:	10923928 kB
VmSize:	10923628 kB
VmLck:	       0 kB
VmPin:	       0 kB
VmHWM:	    3424 kB
VmRSS:	    3424 kB
RssAnon:	     664 kB
RssFile:	    2584 kB
RssShmem:	     176 kB
VmData:	    7808 kB
VmStk:	     132 kB
VmExe:	     284 kB
VmLib:	    4012 kB
VmPTE:	     124 kB
VmSwap:	       0 kB
CoreDumping:	0
THP_enabled:	1
Threads:	1
SigQ:	0/7842
SigPnd:	0000000000000000
ShdPnd:	0000000000000000
SigBlk:	0000000080000000
SigIgn:	0000002000000000
SigCgt:	0000004c400084f8
CapInh:	0000000000000000
CapPrm:	0000000000000000
CapEff:	0000000000000000
CapBnd:	000001ffffffffff
CapAmb:	0000000000000000
NoNewPrivs:	0
Seccomp:	0
Seccomp_filters:	0
Speculation_Store_Bypass:	vulnerable
SpeculationIndirectBranch:	always enabled
Cpus_allowed:	f
Cpus_allowed_list:	0-3
Mems_allowed:	1
Mems_allowed_list:	0
voluntary_ctxt_switches:	0
nonvoluntary_ctxt_switches:	10
```

## binder-hal

### $ adb shell ls -l /dev/binder /dev/hwbinder /dev/vndbinder
```text
lrwxrwxrwx 1 root root 20 2026-08-28 16:21 /dev/binder -> /dev/binderfs/binder
lrwxrwxrwx 1 root root 22 2026-08-28 16:21 /dev/hwbinder -> /dev/binderfs/hwbinder
lrwxrwxrwx 1 root root 23 2026-08-28 16:21 /dev/vndbinder -> /dev/binderfs/vndbinder
```

### $ adb shell service list
```text
Found 255 services:
0	DockObserver: []
1	SurfaceFlinger: [android.ui.ISurfaceComposer]
2	SurfaceFlingerAIDL: [android.gui.ISurfaceComposer]
3	accessibility: [android.view.accessibility.IAccessibilityManager]
4	account: [android.accounts.IAccountManager]
5	activity: [android.app.IActivityManager]
6	activity_task: [android.app.IActivityTaskManager]
7	adb: [android.debug.IAdbManager]
8	alarm: [android.app.IAlarmManager]
9	ambient_context: [android.app.ambientcontext.IAmbientContextManager]
10	android.frameworks.stats.IStats/default: [android.frameworks.stats.IStats]
11	android.hardware.camera.provider.ICameraProvider/internal/0: []
12	android.hardware.drm.IDrmFactory/clearkey: [android.hardware.drm.IDrmFactory]
13	android.hardware.drm.IDrmFactory/widevine: [android.hardware.drm.IDrmFactory]
14	android.hardware.identity.IIdentityCredentialStore/default: []
15	android.hardware.light.ILights/default: []
16	android.hardware.power.IPower/default: []
17	android.hardware.radio.config.IRadioConfig/default: []
18	android.hardware.radio.data.IRadioData/slot1: []
19	android.hardware.radio.messaging.IRadioMessaging/slot1: []
20	android.hardware.radio.modem.IRadioModem/slot1: []
21	android.hardware.radio.network.IRadioNetwork/slot1: []
22	android.hardware.radio.sim.IRadioSim/slot1: []
23	android.hardware.radio.voice.IRadioVoice/slot1: []
24	android.hardware.rebootescrow.IRebootEscrow/default: []
25	android.hardware.security.keymint.IKeyMintDevice/default: []
26	android.hardware.security.keymint.IRemotelyProvisionedComponent/default: []
27	android.hardware.security.secureclock.ISecureClock/default: []
28	android.hardware.security.sharedsecret.ISharedSecret/default: []
29	android.hardware.vibrator.IVibrator/default: []
30	android.hardware.vibrator.IVibratorManager/default: []
31	android.hardware.wifi.supplicant.ISupplicant/default: []
32	android.security.apc: [android.security.apc.IProtectedConfirmation]
33	android.security.authorization: [android.security.authorization.IKeystoreAuthorization]
34	android.security.compat: [android.security.compat.IKeystoreCompatService]
35	android.security.identity: [android.security.identity.ICredentialStoreFactory]
36	android.security.legacykeystore: [android.security.legacykeystore.ILegacyKeystore]
37	android.security.maintenance: [android.security.maintenance.IKeystoreMaintenance]
38	android.security.metrics: [android.security.metrics.IKeystoreMetrics]
39	android.security.remoteprovisioning: [android.security.remoteprovisioning.IRemoteProvisioning]
40	android.security.remoteprovisioning.IRemotelyProvisionedKeyPool: [android.security.remoteprovisioning.IRemotelyProvisionedKeyPool]
41	android.service.gatekeeper.IGateKeeperService: []
42	android.system.keystore2.IKeystoreService/default: [android.system.keystore2.IKeystoreService]
43	android.system.suspend.ISystemSuspend/default: []
44	app_binding: []
45	app_hibernation: [android.apphibernation.IAppHibernationService]
46	app_integrity: [android.content.integrity.IAppIntegrityManager]
47	app_prediction: [android.app.prediction.IPredictionManager]
48	app_search: [android.app.appsearch.aidl.IAppSearchManager]
49	appops: [com.android.internal.app.IAppOpsService]
50	appwidget: [com.android.internal.appwidget.IAppWidgetService]
51	attestation_verification: [android.security.attestationverification.IAttestationVerificationManagerService]
52	audio: [android.media.IAudioService]
53	auth: [android.hardware.biometrics.IAuthService]
54	autofill: [android.view.autofill.IAutoFillManager]
55	backup: [android.app.backup.IBackupManager]
56	battery: []
57	batteryproperties: [android.os.IBatteryPropertiesRegistrar]
58	batterystats: [com.android.internal.app.IBatteryStats]
59	binder_calls_stats: []
60	biometric: [android.hardware.biometrics.IBiometricService]
61	blob_store: [android.app.blob.IBlobStoreManager]
62	bluetooth_manager: [android.bluetooth.IBluetoothManager]
63	bugreport: [android.os.IDumpstate]
64	cacheinfo: []
65	carrier_config: [com.android.internal.telephony.ICarrierConfigLoader]
66	clipboard: [android.content.IClipboard]
67	color_display: [android.hardware.display.IColorDisplayManager]
68	companiondevice: [android.companion.ICompanionDeviceManager]
69	connectivity: [android.net.IConnectivityManager]
70	connectivity_native: [android.net.connectivity.aidl.ConnectivityNative]
71	connmetrics: [android.net.IIpConnectivityMetrics]
72	consumer_ir: [android.hardware.IConsumerIrService]
73	content: [android.content.IContentService]
74	content_capture: [android.view.contentcapture.IContentCaptureManager]
75	content_suggestions: [android.app.contentsuggestions.IContentSuggestionsManager]
76	country_detector: [android.location.ICountryDetector]
77	cpuinfo: []
78	crossprofileapps: [android.content.pm.ICrossProfileApps]
79	dataloader_manager: [android.content.pm.IDataLoaderManager]
80	dbinfo: []
81	device_config: []
82	device_identifiers: [android.os.IDeviceIdentifiersPolicyService]
83	device_policy: [android.app.admin.IDevicePolicyManager]
84	device_state: [android.hardware.devicestate.IDeviceStateManager]
85	deviceidle: [android.os.IDeviceIdleController]
86	devicestoragemonitor: []
87	diskstats: []
88	display: [android.hardware.display.IDisplayManager]
89	dnsresolver: []
90	domain_verification: [android.content.pm.verify.domain.IDomainVerificationManager]
91	dreams: [android.service.dreams.IDreamManager]
92	drm.drmManager: [drm.IDrmManagerService]
93	dropbox: [com.android.internal.os.IDropBoxManagerService]
94	dynamic_system: [android.os.image.IDynamicSystemService]
95	emergency_affordance: []
96	external_vibrator_service: [android.os.IExternalVibratorService]
97	file_integrity: [android.security.IFileIntegrityService]
98	fingerprint: [android.hardware.fingerprint.IFingerprintService]
99	font: [com.android.internal.graphics.fonts.IFontManager]
100	game: [android.app.IGameManagerService]
101	gfxinfo: []
102	gpu: [android.graphicsenv.IGpuService]
103	graphicsstats: [android.view.IGraphicsStats]
104	hardware_properties: [android.os.IHardwarePropertiesManager]
105	imms: [com.android.internal.telephony.IMms]
106	incident: []
107	incidentcompanion: [android.os.IIncidentCompanion]
108	incremental: [android.os.incremental.IIncrementalService]
109	input: [android.hardware.input.IInputManager]
110	input_method: [com.android.internal.view.IInputMethodManager]
111	inputflinger: [android.os.IInputFlinger]
112	installd: []
113	ions: [com.android.internal.telephony.IOns]
114	iphonesubinfo: [com.android.internal.telephony.IPhoneSubInfo]
115	ipsec: [android.net.IIpSecService]
116	isms: [com.android.internal.telephony.ISms]
117	isub: [com.android.internal.telephony.ISub]
118	jobscheduler: [android.app.job.IJobScheduler]
119	launcherapps: [android.content.pm.ILauncherApps]
120	legacy_permission: [android.permission.ILegacyPermissionManager]
121	lights: [android.hardware.lights.ILightsManager]
122	locale: [android.app.ILocaleManager]
123	location: [android.location.ILocationManager]
124	location_time_zone_manager: []
125	lock_settings: [com.android.internal.widget.ILockSettings]
126	logcat: [android.os.logcat.ILogcatManagerService]
127	looper_stats: []
128	manager: [android.os.IServiceManager]
129	mdns: []
130	media.audio_flinger: [android.media.IAudioFlingerService]
131	media.audio_policy: [android.media.IAudioPolicyService]
132	media.camera: [android.hardware.ICameraService]
133	media.camera.proxy: [android.hardware.ICameraServiceProxy]
134	media.extractor: [android.IMediaExtractorService]
135	media.metrics: [android.media.IMediaMetricsService]
136	media.player: [android.media.IMediaPlayerService]
137	media.resource_manager: [android.media.IResourceManagerService]
138	media.resource_observer: [android.media.IResourceObserverService]
139	media_communication: [android.media.IMediaCommunicationService]
140	media_metrics: [android.media.metrics.IMediaMetricsManager]
141	media_projection: [android.media.projection.IMediaProjectionManager]
142	media_resource_monitor: [android.media.IMediaResourceMonitor]
143	media_router: [android.media.IMediaRouterService]
144	media_session: [android.media.session.ISessionManager]
145	meminfo: []
146	memtrack.proxy: [android.hardware.memtrack.IMemtrack]
147	midi: [android.media.midi.IMidiManager]
148	mount: [android.os.storage.IStorageManager]
149	music_recognition: [android.media.musicrecognition.IMusicRecognitionManager]
150	nearby: [android.nearby.INearbyManager]
151	netd: []
152	netd_listener: [android.net.metrics.INetdEventListener]
153	netpolicy: [android.net.INetworkPolicyManager]
154	netstats: [android.net.INetworkStatsService]
155	network_management: [android.os.INetworkManagementService]
156	network_score: [android.net.INetworkScoreService]
157	network_stack: [android.net.INetworkStackConnector]
158	network_time_update_service: []
159	network_watchlist: [com.android.internal.net.INetworkWatchlistManager]
160	notification: [android.app.INotificationManager]
161	otadexopt: [android.content.pm.IOtaDexopt]
162	overlay: [android.content.om.IOverlayManager]
163	pac_proxy: [android.net.IPacProxyManager]
164	package: [android.content.pm.IPackageManager]
165	package_native: [android.content.pm.IPackageManagerNative]
166	people: [android.app.people.IPeopleManager]
167	performance_hint: [android.os.IHintManager]
168	permission: [android.os.IPermissionController]
169	permission_checker: [android.permission.IPermissionChecker]
170	permissionmgr: [android.permission.IPermissionManager]
171	phone: [com.android.internal.telephony.ITelephony]
172	pinner: []
173	platform_compat: [com.android.internal.compat.IPlatformCompat]
174	platform_compat_native: [com.android.internal.compat.IPlatformCompatNative]
175	power: [android.os.IPowerManager]
176	powerstats: []
177	print: [android.print.IPrintManager]
178	processinfo: [android.os.IProcessInfoService]
179	procstats: [com.android.internal.app.procstats.IProcessStats]
180	reboot_readiness: [android.scheduling.IRebootReadinessManager]
181	recovery: [android.os.IRecoverySystem]
182	resources: [android.content.res.IResourcesManager]
183	restrictions: [android.content.IRestrictionsManager]
184	role: [android.app.role.IRoleManager]
185	rollback: [android.content.rollback.IRollbackManager]
186	runtime: []
187	safety_center: [android.safetycenter.ISafetyCenterManager]
188	scheduling_policy: [android.os.ISchedulingPolicyService]
189	sdk_sandbox: [android.app.sdksandbox.ISdkSandboxManager]
190	search: [android.app.ISearchManager]
191	search_ui: [android.app.search.ISearchUiManager]
192	sec_key_att_app_id_provider: [android.security.keymaster.IKeyAttestationApplicationIdProvider]
193	secure_element: [android.se.omapi.ISecureElementService]
194	sensor_privacy: [android.hardware.ISensorPrivacyManager]
195	sensorservice: [android.gui.SensorServer]
196	serial: [android.hardware.ISerialManager]
197	servicediscovery: [android.net.nsd.INsdManager]
198	settings: []
199	shortcut: [android.content.pm.IShortcutService]
200	simphonebook: [com.android.internal.telephony.IIccPhoneBook]
201	slice: [android.app.slice.ISliceManager]
202	smartspace: [android.app.smartspace.ISmartspaceManager]
203	soundtrigger: [com.android.internal.app.ISoundTriggerService]
204	soundtrigger_middleware: [android.media.soundtrigger_middleware.ISoundTriggerMiddlewareService]
205	speech_recognition: [android.speech.IRecognitionServiceManager]
206	stats: [android.os.IStatsd]
207	statsbootstrap: [android.os.IStatsBootstrapAtomService]
208	statscompanion: [android.os.IStatsCompanionService]
209	statsmanager: [android.os.IStatsManagerService]
210	statusbar: [com.android.internal.statusbar.IStatusBarService]
211	storaged: [android.os.IStoraged]
212	storaged_pri: [android.os.storaged.IStoragedPrivate]
213	storagestats: [android.app.usage.IStorageStatsManager]
214	suspend_control: []
215	suspend_control_internal: []
216	system_config: [android.os.ISystemConfig]
217	system_server_dumper: []
218	system_update: [android.os.ISystemUpdateManager]
219	tare: [android.app.tare.IEconomyManager]
220	telecom: [com.android.internal.telecom.ITelecomService]
221	telephony.registry: [com.android.internal.telephony.ITelephonyRegistry]
222	telephony_ims: [android.telephony.ims.aidl.IImsRcsController]
223	testharness: []
224	tethering: [android.net.ITetheringConnector]
225	textclassification: [android.service.textclassifier.ITextClassifierService]
226	textservices: [com.android.internal.textservice.ITextServicesManager]
227	texttospeech: [android.speech.tts.ITextToSpeechManager]
228	thermalservice: [android.os.IThermalService]
229	time_detector: [android.app.timedetector.ITimeDetectorService]
230	time_zone_detector: [android.app.timezonedetector.ITimeZoneDetectorService]
231	tracing.proxy: [android.tracing.ITracingServiceProxy]
232	translation: [android.view.translation.ITranslationManager]
233	transparency: [com.android.internal.os.IBinaryTransparencyService]
234	trust: [android.app.trust.ITrustManager]
235	uimode: [android.app.IUiModeManager]
236	updatelock: [android.os.IUpdateLock]
237	uri_grants: [android.app.IUriGrantsManager]
238	usagestats: [android.app.usage.IUsageStatsManager]
239	usb: [android.hardware.usb.IUsbManager]
240	user: [android.os.IUserManager]
241	vcn_management: [android.net.vcn.IVcnManagementService]
242	vibrator_manager: [android.os.IVibratorManagerService]
243	virtualdevice: [android.companion.virtual.IVirtualDeviceManager]
244	voiceinteraction: [com.android.internal.app.IVoiceInteractionManagerService]
245	vold: []
246	vpn_management: [android.net.IVpnManager]
247	wallpaper: [android.app.IWallpaperManager]
248	wallpaper_effects_generation: [android.app.wallpapereffectsgeneration.IWallpaperEffectsGenerationManager]
249	webviewupdate: [android.webkit.IWebViewUpdateService]
250	wifi: [android.net.wifi.IWifiManager]
251	wifinl80211: []
252	wifip2p: [android.net.wifi.p2p.IWifiP2pManager]
253	wifiscanner: [android.net.wifi.IWifiScanner]
254	window: [android.view.IWindowManager]
```

### $ adb shell lshal
```text
Warning: Skipping "android.frameworks.cameraservice.service@2.0::ICameraService/default": cannot be fetched from service manager (null)
Warning: Skipping "android.frameworks.cameraservice.service@2.1::ICameraService/default": cannot be fetched from service manager (null)
Warning: Skipping "android.frameworks.cameraservice.service@2.2::ICameraService/default": cannot be fetched from service manager (null)
Warning: Skipping "android.frameworks.displayservice@1.0::IDisplayService/default": cannot be fetched from service manager (null)
Warning: Skipping "android.frameworks.schedulerservice@1.0::ISchedulingPolicyService/default": cannot be fetched from service manager (null)
Warning: Skipping "android.frameworks.sensorservice@1.0::ISensorManager/default": cannot be fetched from service manager (null)
Warning: Skipping "android.frameworks.stats@1.0::IStats/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.atrace@1.0::IAtraceDevice/default": no information for PID 174, are you root?
Warning: Skipping "android.hardware.audio.effect@7.0::IEffectsFactory/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.audio@7.0::IDevicesFactory/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.audio@7.1::IDevicesFactory/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.authsecret@1.0::IAuthSecret/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.biometrics.face@1.0::IBiometricsFace/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.biometrics.fingerprint@2.1::IBiometricsFingerprint/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.bluetooth.audio@2.0::IBluetoothAudioProvidersFactory/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.bluetooth.audio@2.1::IBluetoothAudioProvidersFactory/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.bluetooth@1.0::IBluetoothHci/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.bluetooth@1.1::IBluetoothHci/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.camera.provider@2.4::ICameraProvider/legacy/0": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.cas@1.0::IMediaCasService/default": no information for PID 322, are you root?
Warning: Skipping "android.hardware.contexthub@1.0::IContexthub/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.contexthub@1.1::IContexthub/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.drm@1.0::ICryptoFactory/clearkey": no information for PID 327, are you root?
Warning: Skipping "android.hardware.drm@1.0::ICryptoFactory/default": no information for PID 326, are you root?
Warning: Skipping "android.hardware.gatekeeper@1.0::IGatekeeper/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.gnss@1.0::IGnss/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.gnss@1.1::IGnss/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.gnss@2.0::IGnss/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.graphics.allocator@3.0::IAllocator/default": no information for PID 336, are you root?
Warning: Skipping "android.hardware.graphics.composer@2.1::IComposer/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.graphics.composer@2.2::IComposer/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.graphics.composer@2.3::IComposer/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.graphics.composer@2.4::IComposer/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.health@2.0::IHealth/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.health@2.1::IHealth/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.media.c2@1.0::IComponentStore/default": no information for PID 339, are you root?
Warning: Skipping "android.hardware.media.c2@1.0::IComponentStore/software": no information for PID 456, are you root?
Warning: Skipping "android.hardware.neuralnetworks@1.0::IDevice/nnapi-sample_all": no information for PID 340, are you root?
Warning: Skipping "android.hardware.neuralnetworks@1.0::IDevice/nnapi-sample_float_fast": no information for PID 341, are you root?
Warning: Skipping "android.hardware.power.stats@1.0::IPowerStats/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.sensors@2.0::ISensors/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.sensors@2.1::ISensors/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.soundtrigger@2.0::ISoundTriggerHw/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.soundtrigger@2.1::ISoundTriggerHw/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.soundtrigger@2.2::ISoundTriggerHw/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.thermal@1.0::IThermal/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.thermal@2.0::IThermal/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.usb@1.0::IUsb/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.wifi@1.0::IWifi/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.wifi@1.1::IWifi/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.wifi@1.2::IWifi/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.wifi@1.3::IWifi/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.wifi@1.4::IWifi/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.wifi@1.5::IWifi/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hardware.wifi@1.6::IWifi/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hidl.allocator@1.0::IAllocator/ashmem": no information for PID 316, are you root?
Warning: Skipping "android.hidl.base@1.0::IBase/ashmem": cannot be fetched from service manager (null)
Warning: Skipping "android.hidl.base@1.0::IBase/clearkey": cannot be fetched from service manager (null)
Warning: Skipping "android.hidl.base@1.0::IBase/default": cannot be fetched from service manager (null)
Warning: Skipping "android.hidl.base@1.0::IBase/legacy/0": cannot be fetched from service manager (null)
Warning: Skipping "android.hidl.base@1.0::IBase/nnapi-sample_all": cannot be fetched from service manager (null)
Warning: Skipping "android.hidl.base@1.0::IBase/nnapi-sample_float_fast": cannot be fetched from service manager (null)
Warning: Skipping "android.hidl.base@1.0::IBase/nnapi-sample_float_slow": cannot be fetched from service manager (null)
Warning: Skipping "android.hidl.base@1.0::IBase/nnapi-sample_minimal": cannot be fetched from service manager (null)
Warning: Skipping "android.hidl.base@1.0::IBase/nnapi-sample_quant": cannot be fetched from service manager (null)
Warning: Skipping "android.hidl.base@1.0::IBase/software": cannot be fetched from service manager (null)
Warning: Skipping "android.hidl.manager@1.0::IServiceManager/default": no information for PID 145, are you root?
Warning: Skipping "android.system.net.netd@1.0::INetd/default": cannot be fetched from service manager (null)
Warning: Skipping "android.system.net.netd@1.1::INetd/default": cannot be fetched from service manager (null)
Warning: Skipping "android.system.suspend@1.0::ISystemSuspend/default": cannot be fetched from service manager (null)
Warning: Skipping "android.system.wifi.keystore@1.0::IKeystore/default": cannot be fetched from service manager (null)
| All HIDL binderized services (registered with hwservicemanager)
VINTF R Interface                                                                     Thread Use Server Clients
FM    ? android.frameworks.cameraservice.service@2.0::ICameraService/default          N/A        N/A
FM    ? android.frameworks.cameraservice.service@2.1::ICameraService/default          N/A        N/A
FM    ? android.frameworks.cameraservice.service@2.2::ICameraService/default          N/A        N/A
FM    ? android.frameworks.displayservice@1.0::IDisplayService/default                N/A        N/A
DC,FM ? android.frameworks.schedulerservice@1.0::ISchedulingPolicyService/default     N/A        N/A
DC,FM ? android.frameworks.sensorservice@1.0::ISensorManager/default                  N/A        N/A
FM    ? android.frameworks.stats@1.0::IStats/default                                  N/A        N/A
DM,FC Y android.hardware.atrace@1.0::IAtraceDevice/default                            N/A        174
DM,FC ? android.hardware.audio.effect@7.0::IEffectsFactory/default                    N/A        N/A
DM,FC ? android.hardware.audio@7.0::IDevicesFactory/default                           N/A        N/A
DM,FC ? android.hardware.audio@7.1::IDevicesFactory/default                           N/A        N/A
DM,FC ? android.hardware.authsecret@1.0::IAuthSecret/default                          N/A        N/A
DM,FC ? android.hardware.biometrics.face@1.0::IBiometricsFace/default                 N/A        N/A
DM,FC ? android.hardware.biometrics.fingerprint@2.1::IBiometricsFingerprint/default   N/A        N/A
DM,FC ? android.hardware.bluetooth.audio@2.0::IBluetoothAudioProvidersFactory/default N/A        N/A
DM,FC ? android.hardware.bluetooth.audio@2.1::IBluetoothAudioProvidersFactory/default N/A        N/A
DM,FC ? android.hardware.bluetooth@1.0::IBluetoothHci/default                         N/A        N/A
DM,FC ? android.hardware.bluetooth@1.1::IBluetoothHci/default                         N/A        N/A
DM,FC ? android.hardware.camera.provider@2.4::ICameraProvider/legacy/0                N/A        N/A
DM    Y android.hardware.cas@1.0::IMediaCasService/default                            N/A        322
DM,FC Y android.hardware.cas@1.1::IMediaCasService/default                            N/A        322
DM,FC Y android.hardware.cas@1.2::IMediaCasService/default                            N/A        322
DM,FC ? android.hardware.contexthub@1.0::IContexthub/default                          N/A        N/A
DM,FC ? android.hardware.contexthub@1.1::IContexthub/default                          N/A        N/A
DM,FC Y android.hardware.drm@1.0::ICryptoFactory/clearkey                             N/A        327
DM,FC Y android.hardware.drm@1.0::ICryptoFactory/default                              N/A        326
DM,FC Y android.hardware.drm@1.0::IDrmFactory/clearkey                                N/A        327
DM,FC Y android.hardware.drm@1.0::IDrmFactory/default                                 N/A        326
DM,FC Y android.hardware.drm@1.1::ICryptoFactory/clearkey                             N/A        327
DM,FC Y android.hardware.drm@1.1::IDrmFactory/clearkey                                N/A        327
DM,FC Y android.hardware.drm@1.2::ICryptoFactory/clearkey                             N/A        327
DM,FC Y android.hardware.drm@1.2::IDrmFactory/clearkey                                N/A        327
DM,FC Y android.hardware.drm@1.3::ICryptoFactory/clearkey                             N/A        327
DM,FC Y android.hardware.drm@1.3::IDrmFactory/clearkey                                N/A        327
DM,FC Y android.hardware.drm@1.4::ICryptoFactory/clearkey                             N/A        327
DM,FC Y android.hardware.drm@1.4::IDrmFactory/clearkey                                N/A        327
DM,FC ? android.hardware.gatekeeper@1.0::IGatekeeper/default                          N/A        N/A
DM    ? android.hardware.gnss@1.0::IGnss/default                                      N/A        N/A
DM    ? android.hardware.gnss@1.1::IGnss/default                                      N/A        N/A
DM,FC ? android.hardware.gnss@2.0::IGnss/default                                      N/A        N/A
DM,FC Y android.hardware.graphics.allocator@3.0::IAllocator/default                   N/A        336
DM,FC ? android.hardware.graphics.composer@2.1::IComposer/default                     N/A        N/A
DM,FC ? android.hardware.graphics.composer@2.2::IComposer/default                     N/A        N/A
DM,FC ? android.hardware.graphics.composer@2.3::IComposer/default                     N/A        N/A
DM,FC ? android.hardware.graphics.composer@2.4::IComposer/default                     N/A        N/A
DM,FC ? android.hardware.health@2.0::IHealth/default                                  N/A        N/A
DM,FC ? android.hardware.health@2.1::IHealth/default                                  N/A        N/A
DM,FC Y android.hardware.media.c2@1.0::IComponentStore/default                        N/A        339
FM    Y android.hardware.media.c2@1.0::IComponentStore/software                       N/A        456
FM    Y android.hardware.media.c2@1.1::IComponentStore/software                       N/A        456
FM    Y android.hardware.media.c2@1.2::IComponentStore/software                       N/A        456
DM,FC Y android.hardware.neuralnetworks@1.0::IDevice/nnapi-sample_all                 N/A        340
DM,FC Y android.hardware.neuralnetworks@1.0::IDevice/nnapi-sample_float_fast          N/A        341
DM,FC Y android.hardware.neuralnetworks@1.0::IDevice/nnapi-sample_float_slow          N/A        341
DM,FC Y android.hardware.neuralnetworks@1.0::IDevice/nnapi-sample_minimal             N/A        341
DM,FC Y android.hardware.neuralnetworks@1.0::IDevice/nnapi-sample_quant               N/A        341
DM,FC Y android.hardware.neuralnetworks@1.1::IDevice/nnapi-sample_all                 N/A        340
DM,FC Y android.hardware.neuralnetworks@1.1::IDevice/nnapi-sample_float_fast          N/A        341
DM,FC Y android.hardware.neuralnetworks@1.1::IDevice/nnapi-sample_float_slow          N/A        341
DM,FC Y android.hardware.neuralnetworks@1.1::IDevice/nnapi-sample_minimal             N/A        341
DM,FC Y android.hardware.neuralnetworks@1.1::IDevice/nnapi-sample_quant               N/A        341
DM,FC Y android.hardware.neuralnetworks@1.2::IDevice/nnapi-sample_all                 N/A        340
DM,FC Y android.hardware.neuralnetworks@1.2::IDevice/nnapi-sample_float_fast          N/A        341
DM,FC Y android.hardware.neuralnetworks@1.2::IDevice/nnapi-sample_float_slow          N/A        341
DM,FC Y android.hardware.neuralnetworks@1.2::IDevice/nnapi-sample_minimal             N/A        341
DM,FC Y android.hardware.neuralnetworks@1.2::IDevice/nnapi-sample_quant               N/A        341
DM,FC Y android.hardware.neuralnetworks@1.3::IDevice/nnapi-sample_all                 N/A        340
DM,FC Y android.hardware.neuralnetworks@1.3::IDevice/nnapi-sample_float_fast          N/A        341
DM,FC Y android.hardware.neuralnetworks@1.3::IDevice/nnapi-sample_float_slow          N/A        341
DM,FC Y android.hardware.neuralnetworks@1.3::IDevice/nnapi-sample_minimal             N/A        341
DM,FC Y android.hardware.neuralnetworks@1.3::IDevice/nnapi-sample_quant               N/A        341
DM,FC ? android.hardware.power.stats@1.0::IPowerStats/default                         N/A        N/A
DM,FC ? android.hardware.sensors@2.0::ISensors/default                                N/A        N/A
DM,FC ? android.hardware.sensors@2.1::ISensors/default                                N/A        N/A
DM,FC ? android.hardware.soundtrigger@2.0::ISoundTriggerHw/default                    N/A        N/A
DM,FC ? android.hardware.soundtrigger@2.1::ISoundTriggerHw/default                    N/A        N/A
DM,FC ? android.hardware.soundtrigger@2.2::ISoundTriggerHw/default                    N/A        N/A
DM    ? android.hardware.thermal@1.0::IThermal/default                                N/A        N/A
DM,FC ? android.hardware.thermal@2.0::IThermal/default                                N/A        N/A
DM,FC ? android.hardware.usb@1.0::IUsb/default                                        N/A        N/A
DM,FC ? android.hardware.wifi@1.0::IWifi/default                                      N/A        N/A
DM,FC ? android.hardware.wifi@1.1::IWifi/default                                      N/A        N/A
DM,FC ? android.hardware.wifi@1.2::IWifi/default                                      N/A        N/A
DM,FC ? android.hardware.wifi@1.3::IWifi/default                                      N/A        N/A
DM,FC ? android.hardware.wifi@1.4::IWifi/default                                      N/A        N/A
DM,FC ? android.hardware.wifi@1.5::IWifi/default                                      N/A        N/A
DM,FC ? android.hardware.wifi@1.6::IWifi/default                                      N/A        N/A
DC,FM Y android.hidl.allocator@1.0::IAllocator/ashmem                                 N/A        316
X     ? android.hidl.base@1.0::IBase/ashmem                                           N/A        N/A
X     ? android.hidl.base@1.0::IBase/clearkey                                         N/A        N/A
X     ? android.hidl.base@1.0::IBase/default                                          N/A        N/A
X     ? android.hidl.base@1.0::IBase/legacy/0                                         N/A        N/A
X     ? android.hidl.base@1.0::IBase/nnapi-sample_all                                 N/A        N/A
X     ? android.hidl.base@1.0::IBase/nnapi-sample_float_fast                          N/A        N/A
X     ? android.hidl.base@1.0::IBase/nnapi-sample_float_slow                          N/A        N/A
X     ? android.hidl.base@1.0::IBase/nnapi-sample_minimal                             N/A        N/A
X     ? android.hidl.base@1.0::IBase/nnapi-sample_quant                               N/A        N/A
X     ? android.hidl.base@1.0::IBase/software                                         N/A        N/A
DC,FM Y android.hidl.manager@1.0::IServiceManager/default                             N/A        145
FM    Y android.hidl.manager@1.1::IServiceManager/default                             N/A        145
FM    Y android.hidl.manager@1.2::IServiceManager/default                             N/A        145
DC,FM Y android.hidl.token@1.0::ITokenManager/default                                 N/A        145
FM    ? android.system.net.netd@1.0::INetd/default                                    N/A        N/A
FM    ? android.system.net.netd@1.1::INetd/default                                    N/A        N/A
FM    ? android.system.suspend@1.0::ISystemSuspend/default                            N/A        N/A
DC,FM ? android.system.wifi.keystore@1.0::IKeystore/default                           N/A        N/A

| All HIDL interfaces getService() has ever returned as a passthrough interface;
| PIDs / processes shown below might be inaccurate because the process
| might have relinquished the interface or might have died.
| The Server / Server CMD column can be ignored.
| The Clients / Clients CMD column shows all process that have ever dlopen'ed
| the library and successfully fetched the passthrough implementation.
VINTF R Interface                                                                     Thread Use Server Clients
FC    ? android.hardware.audio.effect@7.0::IEffectsFactory/default                    N/A        317    317
FC    ? android.hardware.audio@7.1::IDevicesFactory/default                           N/A        317    317
FC    ? android.hardware.bluetooth.audio@2.1::IBluetoothAudioProvidersFactory/default N/A        317    317
FC    ? android.hardware.camera.provider@2.4::ICameraProvider/legacy/0                N/A        320    320
FC    ? android.hardware.drm@1.0::ICryptoFactory/default                              N/A        326    326
FC    ? android.hardware.drm@1.0::IDrmFactory/default                                 N/A        326    326
DM,FC ? android.hardware.graphics.mapper@3.0::IMapper/default                         N/A        N/A    320 337 395 456 513 815 1112 1216 1866
FC    ? android.hardware.health@2.1::IHealth/default                                  N/A        338    338
FC    ? android.hardware.soundtrigger@2.2::ISoundTriggerHw/default                    N/A        317    317

| All available HIDL passthrough implementations (all -impl.so files).
| These may return subclasses through their respective HIDL_FETCH_I* functions.
VINTF R Interface                                                                Thread Use Server Clients
X     ? android.hardware.audio.effect@7.0::I*/* (/vendor/lib64/hw/)              N/A        N/A
X     ? android.hardware.audio.legacy@7.1::I*/* (/vendor/lib64/hw/) (.ranchu)    N/A        N/A
X     ? android.hardware.audio@7.1::I*/* (/vendor/lib64/hw/) (.ranchu)           N/A        N/A
X     ? android.hardware.bluetooth.audio@2.1::I*/* (/vendor/lib64/hw/)           N/A        N/A
X     ? android.hardware.camera.provider@2.4::I*/* (/vendor/lib64/hw/)           N/A        N/A
X     ? android.hardware.drm@1.0::I*/* (/vendor/lib64/hw/)                       N/A        N/A
X     ? android.hardware.graphics.mapper@3.0::I*/* (/vendor/lib64/hw/) (-ranchu) N/A        N/A
X     ? android.hardware.health@2.0::I*/* (/vendor/lib64/hw/) (-2.1)             N/A        N/A
X     ? android.hardware.sensors@2.1::I*/* (/vendor/lib64/hw/) (.ranchu)         N/A        N/A
X     ? android.hardware.soundtrigger@2.2::I*/* (/vendor/lib64/hw/) (.ranchu)    N/A        N/A
X     ? android.hidl.memory@1.0::I*/* (/apex/com.android.vndk.v33/lib64/hw/)     N/A        N/A
X     ? android.hidl.memory@1.0::I*/* (/system/lib64/hw/)                        N/A        N/A
```

## partitions-fbe

### $ adb shell mount
```text
/dev/block/dm-5 on / type ext4 (ro,seclabel,relatime)
tmpfs on /dev type tmpfs (rw,seclabel,nosuid,relatime,mode=755)
devpts on /dev/pts type devpts (rw,seclabel,relatime,mode=600,ptmxmode=000)
proc on /proc type proc (rw,relatime,gid=3009,hidepid=invisible)
sysfs on /sys type sysfs (rw,seclabel,relatime)
selinuxfs on /sys/fs/selinux type selinuxfs (rw,relatime)
tmpfs on /mnt type tmpfs (rw,seclabel,nosuid,nodev,noexec,relatime,mode=755,gid=1000)
tmpfs on /mnt/installer type tmpfs (rw,seclabel,nosuid,nodev,noexec,relatime,mode=755,gid=1000)
tmpfs on /mnt/androidwritable type tmpfs (rw,seclabel,nosuid,nodev,noexec,relatime,mode=755,gid=1000)
/dev/block/vdd1 on /metadata type ext4 (rw,seclabel,nosuid,nodev,noatime)
/dev/block/dm-4 on /vendor type ext4 (ro,seclabel,relatime)
/dev/block/dm-3 on /product type ext4 (ro,seclabel,relatime)
/dev/block/dm-1 on /system_dlkm type erofs (ro,seclabel,relatime,user_xattr,acl,cache_strategy=readaround)
/dev/block/dm-2 on /system_ext type ext4 (ro,seclabel,relatime)
tmpfs on /apex type tmpfs (rw,seclabel,nosuid,nodev,noexec,relatime,mode=755)
tmpfs on /linkerconfig type tmpfs (rw,seclabel,nosuid,nodev,noexec,relatime,mode=755)
none on /dev/blkio type cgroup (rw,nosuid,nodev,noexec,relatime,blkio)
none on /sys/fs/cgroup type cgroup2 (rw,nosuid,nodev,noexec,relatime,memory_recursiveprot)
none on /dev/cpuctl type cgroup (rw,nosuid,nodev,noexec,relatime,cpu)
none on /dev/cpuset type cgroup (rw,nosuid,nodev,noexec,relatime,cpuset,noprefix,release_agent=/sbin/cpuset_release_agent)
none on /dev/memcg type cgroup (rw,nosuid,nodev,noexec,relatime,memory)
tracefs on /sys/kernel/tracing type tracefs (rw,seclabel,relatime,gid=3012)
none on /config type configfs (rw,nosuid,nodev,noexec,relatime)
binder on /dev/binderfs type binder (rw,relatime,max=1048576,stats=global)
none on /sys/fs/fuse/connections type fusectl (rw,relatime)
bpf on /sys/fs/bpf type bpf (rw,nosuid,nodev,noexec,relatime)
pstore on /sys/fs/pstore type pstore (rw,seclabel,nosuid,nodev,noexec,relatime)
tmpfs on /storage type tmpfs (rw,seclabel,nosuid,nodev,noexec,relatime,mode=755,gid=1000)
/dev/block/dm-34 on /data type ext4 (rw,seclabel,nosuid,nodev,noatime,resgid=1065,errors=panic)
tmpfs on /linkerconfig type tmpfs (rw,seclabel,nosuid,nodev,noexec,relatime,mode=755)
/dev/block/dm-34 on /data/user/0 type ext4 (rw,seclabel,nosuid,nodev,noatime,resgid=1065,errors=panic)
tmpfs on /data_mirror type tmpfs (rw,seclabel,nosuid,nodev,noexec,relatime,mode=700,gid=1000)
/dev/block/dm-34 on /data_mirror/data_ce/null type ext4 (rw,seclabel,nosuid,nodev,noatime,resgid=1065,errors=panic)
/dev/block/dm-34 on /data_mirror/data_ce/null/0 type ext4 (rw,seclabel,nosuid,nodev,noatime,resgid=1065,errors=panic)
/dev/block/dm-34 on /data_mirror/data_de/null type ext4 (rw,seclabel,nosuid,nodev,noatime,resgid=1065,errors=panic)
/dev/block/dm-34 on /data_mirror/misc_ce/null type ext4 (rw,seclabel,nosuid,nodev,noatime,resgid=1065,errors=panic)
/dev/block/dm-34 on /data_mirror/misc_de/null type ext4 (rw,seclabel,nosuid,nodev,noatime,resgid=1065,errors=panic)
/dev/block/dm-34 on /data_mirror/cur_profiles type ext4 (rw,seclabel,nosuid,nodev,noatime,resgid=1065,errors=panic)
/dev/block/dm-34 on /data_mirror/ref_profiles type ext4 (rw,seclabel,nosuid,nodev,noatime,resgid=1065,errors=panic)
/dev/block/loop5 on /apex/com.google.mainline.primary.libs@331731000 type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/loop4 on /apex/com.android.apex.cts.shim@1 type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/loop6 on /apex/com.android.runtime@1 type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/loop4 on /apex/com.android.apex.cts.shim type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/loop6 on /apex/com.android.runtime type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/loop7 on /apex/com.android.tzdata@331314030 type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/loop8 on /apex/com.android.vndk.v33@1 type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/loop7 on /apex/com.android.tzdata type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/loop8 on /apex/com.android.vndk.v33 type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/loop9 on /apex/com.android.btservices@331911000 type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/loop10 on /apex/com.android.i18n@1 type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/loop10 on /apex/com.android.i18n type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/loop9 on /apex/com.android.btservices type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-32 on /apex/com.android.appsearch@331311020 type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-32 on /apex/com.android.appsearch type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-33 on /apex/com.android.mediaprovider@331711020 type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-33 on /apex/com.android.mediaprovider type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-28 on /apex/com.android.ipsec@331312000 type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-28 on /apex/com.android.ipsec type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-22 on /apex/com.android.media.swcodec@331712000 type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-22 on /apex/com.android.media.swcodec type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-23 on /apex/com.android.adbd@331610002 type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-23 on /apex/com.android.adbd type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-24 on /apex/com.android.tethering@331711040 type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-24 on /apex/com.android.tethering type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-21 on /apex/com.android.sdkext@331412000 type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-21 on /apex/com.android.sdkext type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-20 on /apex/com.android.scheduling@331113000 type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-20 on /apex/com.android.scheduling type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-19 on /apex/com.android.conscrypt@331413000 type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-19 on /apex/com.android.conscrypt type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-15 on /apex/com.android.media@331712010 type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-15 on /apex/com.android.media type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-16 on /apex/com.android.os.statsd@331711010 type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-16 on /apex/com.android.os.statsd type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-11 on /apex/com.android.neuralnetworks@331310000 type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-11 on /apex/com.android.neuralnetworks type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-12 on /apex/com.android.cellbroadcast@331710020 type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-12 on /apex/com.android.cellbroadcast type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-27 on /apex/com.android.extservices@331412000 type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-27 on /apex/com.android.extservices type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-10 on /apex/com.android.adservices@331710270 type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-10 on /apex/com.android.adservices type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-26 on /apex/com.android.uwb@331613010 type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-26 on /apex/com.android.uwb type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-14 on /apex/com.android.wifi@331710030 type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-14 on /apex/com.android.wifi type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-8 on /apex/com.android.ondevicepersonalization@330442040 type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-8 on /apex/com.android.ondevicepersonalization type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-25 on /apex/com.android.art@331711080 type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-25 on /apex/com.android.art type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-7 on /apex/com.android.permission@331710050 type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-7 on /apex/com.android.permission type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-6 on /apex/com.android.resolv@331611010 type ext4 (ro,dirsync,seclabel,nodev,noatime)
/dev/block/dm-6 on /apex/com.android.resolv type ext4 (ro,dirsync,seclabel,nodev,noatime)
tmpfs on /apex/apex-info-list.xml type tmpfs (rw,seclabel,nosuid,nodev,noexec,relatime,mode=755)
/dev/fuse on /mnt/installer/0/emulated type fuse (rw,lazytime,nosuid,nodev,noexec,noatime,user_id=0,group_id=0,allow_other)
/dev/fuse on /mnt/androidwritable/0/emulated type fuse (rw,lazytime,nosuid,nodev,noexec,noatime,user_id=0,group_id=0,allow_other)
/dev/fuse on /mnt/user/0/emulated type fuse (rw,lazytime,nosuid,nodev,noexec,noatime,user_id=0,group_id=0,allow_other)
/dev/fuse on /storage/emulated type fuse (rw,lazytime,nosuid,nodev,noexec,noatime,user_id=0,group_id=0,allow_other)
/dev/block/dm-34 on /mnt/pass_through/0/emulated type ext4 (rw,seclabel,nosuid,nodev,noatime,resgid=1065,errors=panic)
/dev/block/dm-34 on /mnt/androidwritable/0/emulated/0/Android/data type ext4 (rw,seclabel,nosuid,nodev,noatime,resgid=1065,errors=panic)
/dev/block/dm-34 on /mnt/installer/0/emulated/0/Android/data type ext4 (rw,seclabel,nosuid,nodev,noatime,resgid=1065,errors=panic)
/dev/block/dm-34 on /mnt/user/0/emulated/0/Android/data type ext4 (rw,seclabel,nosuid,nodev,noatime,resgid=1065,errors=panic)
/dev/block/dm-34 on /storage/emulated/0/Android/data type ext4 (rw,seclabel,nosuid,nodev,noatime,resgid=1065,errors=panic)
/dev/block/dm-34 on /mnt/androidwritable/0/emulated/0/Android/obb type ext4 (rw,seclabel,nosuid,nodev,noatime,resgid=1065,errors=panic)
/dev/block/dm-34 on /mnt/installer/0/emulated/0/Android/obb type ext4 (rw,seclabel,nosuid,nodev,noatime,resgid=1065,errors=panic)
/dev/block/dm-34 on /mnt/user/0/emulated/0/Android/obb type ext4 (rw,seclabel,nosuid,nodev,noatime,resgid=1065,errors=panic)
/dev/block/dm-34 on /storage/emulated/0/Android/obb type ext4 (rw,seclabel,nosuid,nodev,noatime,resgid=1065,errors=panic)
```

### $ adb shell df -h
```text
Filesystem        Size Used Avail Use% Mounted on
/dev/block/dm-5   817M 753M   48M  95% /
tmpfs             983M 1.2M  982M   1% /dev
tmpfs             983M    0  983M   0% /mnt
/dev/block/dm-4   100M 100M     0 100% /vendor
/dev/block/dm-3   1.8G 1.8G     0 100% /product
/dev/block/dm-2   172M 171M     0 100% /system_ext
tmpfs             983M  24K  983M   1% /apex
/dev/block/dm-34  5.8G 769M  4.9G  14% /data
/dev/block/loop5  0.9M 972K  8.0K 100% /apex/com.google.mainline.primary.libs@331731000
/dev/block/loop4  232K  88K  140K  39% /apex/com.android.apex.cts.shim@1
/dev/block/loop6  5.1M 5.1M     0 100% /apex/com.android.runtime@1
/dev/block/loop7  784K 756K   12K  99% /apex/com.android.tzdata@331314030
/dev/block/loop8   29M  29M     0 100% /apex/com.android.vndk.v33@1
/dev/block/loop9   23M  23M     0 100% /apex/com.android.btservices@331911000
/dev/block/loop10  33M  33M     0 100% /apex/com.android.i18n@1
/dev/block/dm-32  3.4M 3.4M     0 100% /apex/com.android.appsearch@331311020
/dev/block/dm-33   10M  10M     0 100% /apex/com.android.mediaprovider@331711020
/dev/block/dm-28  756K 728K   16K  98% /apex/com.android.ipsec@331312000
/dev/block/dm-22   21M  21M     0 100% /apex/com.android.media.swcodec@331712000
/dev/block/dm-23  5.3M 5.2M     0 100% /apex/com.android.adbd@331610002
/dev/block/dm-24  8.2M 8.1M     0 100% /apex/com.android.tethering@331711040
/dev/block/dm-21  768K 740K   16K  98% /apex/com.android.sdkext@331412000
/dev/block/dm-20  232K 104K  124K  46% /apex/com.android.scheduling@331113000
/dev/block/dm-19  3.3M 3.3M     0 100% /apex/com.android.conscrypt@331413000
/dev/block/dm-15  5.0M 5.0M     0 100% /apex/com.android.media@331712010
/dev/block/dm-16  1.7M 1.6M     0 100% /apex/com.android.os.statsd@331711010
/dev/block/dm-11  5.0M 5.0M     0 100% /apex/com.android.neuralnetworks@331310000
/dev/block/dm-12   14M  14M     0 100% /apex/com.android.cellbroadcast@331710020
/dev/block/dm-27  6.3M 6.3M     0 100% /apex/com.android.extservices@331412000
/dev/block/dm-10   22M  22M     0 100% /apex/com.android.adservices@331710270
/dev/block/dm-26  3.3M 3.2M     0 100% /apex/com.android.uwb@331613010
/dev/block/dm-14  7.2M 7.2M     0 100% /apex/com.android.wifi@331710030
/dev/block/dm-8   232K  84K  144K  37% /apex/com.android.ondevicepersonalization@330442040
/dev/block/dm-25   31M  31M     0 100% /apex/com.android.art@331711080
/dev/block/dm-7    16M  16M     0 100% /apex/com.android.permission@331710050
/dev/block/dm-6   4.4M 4.4M     0 100% /apex/com.android.resolv@331611010
/dev/fuse         5.8G 769M  4.9G  14% /storage/emulated
```

### $ adb shell getprop ro.crypto.type
```text
file
```

### $ adb shell getprop ro.crypto.state
```text
encrypted
```

### $ adb shell getprop ro.crypto.volume.filenames_mode
```text
aes-256-cts
```

### $ adb shell ls -ldZ /data /data/user /data/user_de /metadata
```text
drwxrwx--x 50 system system u:object_r:system_data_root_file:s0  4096 2026-08-28 16:21 /data
ls: /metadata: Permission denied
drwx--x--x  3 system system u:object_r:system_data_file:s0       4096 2026-08-28 16:21 /data/user
drwx--x--x  3 system system u:object_r:system_data_file:s0       4096 2026-08-28 16:21 /data/user_de
```

## packages-permissions

### $ adb shell pm list features
```text
feature:reqGlEsVersion=0x30000
feature:android.hardware.audio.output
feature:android.hardware.bluetooth
feature:android.hardware.bluetooth_le
feature:android.hardware.camera
feature:android.hardware.camera.any
feature:android.hardware.camera.ar
feature:android.hardware.camera.autofocus
feature:android.hardware.camera.capability.manual_post_processing
feature:android.hardware.camera.capability.manual_sensor
feature:android.hardware.camera.capability.raw
feature:android.hardware.camera.concurrent
feature:android.hardware.camera.flash
feature:android.hardware.camera.front
feature:android.hardware.camera.level.full
feature:android.hardware.faketouch
feature:android.hardware.fingerprint
feature:android.hardware.hardware_keystore=200
feature:android.hardware.identity_credential=202201
feature:android.hardware.keystore.app_attest_key
feature:android.hardware.location
feature:android.hardware.location.gps
feature:android.hardware.location.network
feature:android.hardware.microphone
feature:android.hardware.ram.normal
feature:android.hardware.screen.landscape
feature:android.hardware.screen.portrait
feature:android.hardware.security.model.compatible
feature:android.hardware.sensor.accelerometer
feature:android.hardware.sensor.ambient_temperature
feature:android.hardware.sensor.barometer
feature:android.hardware.sensor.compass
feature:android.hardware.sensor.gyroscope
feature:android.hardware.sensor.hinge_angle
feature:android.hardware.sensor.light
feature:android.hardware.sensor.proximity
feature:android.hardware.sensor.relative_humidity
feature:android.hardware.telephony
feature:android.hardware.telephony.data
feature:android.hardware.telephony.gsm
feature:android.hardware.telephony.ims
feature:android.hardware.telephony.radio.access
feature:android.hardware.telephony.subscription
feature:android.hardware.touchscreen
feature:android.hardware.touchscreen.multitouch
feature:android.hardware.touchscreen.multitouch.distinct
feature:android.hardware.touchscreen.multitouch.jazzhand
feature:android.hardware.vulkan.compute
feature:android.hardware.vulkan.level=1
feature:android.hardware.vulkan.version=4198400
feature:android.hardware.wifi
feature:android.hardware.wifi.direct
feature:android.hardware.wifi.passpoint
feature:android.software.activities_on_secondary_displays
feature:android.software.adoptable_storage
feature:android.software.app_enumeration
feature:android.software.app_widgets
feature:android.software.autofill
feature:android.software.backup
feature:android.software.cant_save_state
feature:android.software.companion_device_setup
feature:android.software.controls
feature:android.software.cts
feature:android.software.device_admin
feature:android.software.erofs
feature:android.software.file_based_encryption
feature:android.software.home_screen
feature:android.software.incremental_delivery=2
feature:android.software.input_methods
feature:android.software.ipsec_tunnels
feature:android.software.live_wallpaper
feature:android.software.managed_users
feature:android.software.midi
feature:android.software.opengles.deqp.level=132514561
feature:android.software.picture_in_picture
feature:android.software.print
feature:android.software.secure_lock_screen
feature:android.software.securely_removes_users
feature:android.software.telecom
feature:android.software.verified_boot
feature:android.software.voice_recognizers
feature:android.software.vulkan.deqp.level=132514561
feature:android.software.webview
feature:com.google.android.apps.dialer.SUPPORTED
feature:com.google.android.feature.EXCHANGE_6_2
feature:com.google.android.feature.GOOGLE_BUILD
feature:com.google.android.feature.GOOGLE_EXPERIENCE
feature:com.google.android.feature.WELLBEING
```

### $ adb shell pm list packages -3
```text

```

### $ adb shell cmd appops get com.android.settings
```text
GET_USAGE_STATS: default; rejectTime=+2m4s870ms ago
USE_ICC_AUTH_WITH_DEVICE_IDENTIFIER: default; rejectTime=+5s73ms ago
BLUETOOTH_CONNECT: allow; time=+5s131ms ago
```

### $ adb shell dumpsys package com.android.settings
```text
Activity Resolver Table:
  Full MIME Types:
      vnd.android.cursor.item/telephony-carrier:
        5d183d9 com.android.settings/.Settings$ApnEditorActivity filter 337719e
          Action: "android.intent.action.VIEW"
          Action: "android.intent.action.EDIT"
          Category: "android.intent.category.DEFAULT"
          StaticType: "vnd.android.cursor.item/telephony-carrier"
      vnd.android.document/root:
        813a923 com.android.settings/.Settings$PublicVolumeSettingsActivity filter 1f9de20
          Action: "android.provider.action.DOCUMENT_ROOT_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          Scheme: "content"
          Authority: "com.android.externalstorage.documents": -1
          StaticType: "vnd.android.document/root"
      vnd.android.cursor.dir/telephony-carrier:
        5d183d9 com.android.settings/.Settings$ApnEditorActivity filter 16db47f
          Action: "android.intent.action.INSERT"
          Category: "android.intent.category.DEFAULT"
          StaticType: "vnd.android.cursor.dir/telephony-carrier"

  Base MIME Types:
      vnd.android.document:
        813a923 com.android.settings/.Settings$PublicVolumeSettingsActivity filter 1f9de20
          Action: "android.provider.action.DOCUMENT_ROOT_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          Scheme: "content"
          Authority: "com.android.externalstorage.documents": -1
          StaticType: "vnd.android.document/root"
      vnd.android.cursor.dir:
        5d183d9 com.android.settings/.Settings$ApnEditorActivity filter 16db47f
          Action: "android.intent.action.INSERT"
          Category: "android.intent.category.DEFAULT"
          StaticType: "vnd.android.cursor.dir/telephony-carrier"
      vnd.android.cursor.item:
        5d183d9 com.android.settings/.Settings$ApnEditorActivity filter 337719e
          Action: "android.intent.action.VIEW"
          Action: "android.intent.action.EDIT"
          Category: "android.intent.category.DEFAULT"
          StaticType: "vnd.android.cursor.item/telephony-carrier"

  Schemes:
      printjob:
        48648e4 com.android.settings/.Settings$PrintJobSettingsActivity filter bbab14d
          Action: "android.settings.ACTION_PRINT_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          Scheme: "printjob"
          Path: "PatternMatcher{GLOB: *}"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      package:
        c181612 com.android.settings/.localepicker.AppLocalePickerActivity filter e711e3
          Action: "android.settings.APP_LOCALE_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          Scheme: "package"
        9dc30f6 com.android.settings/.datausage.AppDataUsageActivity filter deffcf7
          Action: "android.settings.IGNORE_BACKGROUND_DATA_RESTRICTIONS_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          Scheme: "package"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        c4c2764 com.android.settings/.fuelgauge.RequestIgnoreBatteryOptimizations filter bc56dcd
          Action: "android.settings.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS"
          Category: "android.intent.category.DEFAULT"
          Scheme: "package"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        35655d0 com.android.settings/.applications.InstalledAppDetails filter 8c819c9
          Action: "android.settings.APPLICATION_DETAILS_SETTINGS"
          Action: "android.intent.action.AUTO_REVOKE_PERMISSIONS"
          Category: "android.intent.category.DEFAULT"
          Scheme: "package"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        f8468ce com.android.settings/.applications.InstalledAppOpenByDefaultActivity filter a393ef
          Action: "android.settings.APP_OPEN_BY_DEFAULT_SETTINGS"
          Action: "com.android.settings.APP_OPEN_BY_DEFAULT_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          Scheme: "package"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        9a4a38c com.android.settings/.Settings$AppUsageAccessSettingsActivity filter f367ad5
          Action: "android.settings.USAGE_ACCESS_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          Scheme: "package"
        f7eb309 com.android.settings/.Settings$AppPictureInPictureSettingsActivity filter 575290e
          Action: "android.settings.PICTURE_IN_PICTURE_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          Scheme: "package"
        40fcd28 com.android.settings/.Settings$AppInteractAcrossProfilesSettingsActivity filter 2cba41
          Action: "android.settings.MANAGE_CROSS_PROFILE_ACCESS"
          Category: "android.intent.category.DEFAULT"
          Scheme: "package"
        3114be6 com.android.settings/.Settings$ZenAccessDetailSettingsActivity filter d619527
          Action: "android.settings.NOTIFICATION_POLICY_ACCESS_DETAIL_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          Scheme: "package"
        81b9b35 com.android.settings/.Settings$PremiumSmsAccessActivity filter d096bca
          Action: "android.settings.PREMIUM_SMS_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          Scheme: "package"
        22f271e com.android.settings/.Settings$OverlaySettingsActivity filter 3b72dcc
          Action: "android.settings.action.MANAGE_OVERLAY_PERMISSION"
          Category: "android.intent.category.DEFAULT"
          Scheme: "package"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        cbad815 com.android.settings/.Settings$AppDrawOverlaySettingsActivity filter ea2972a
          Action: "android.settings.MANAGE_APP_OVERLAY_PERMISSION"
          Category: "android.intent.category.DEFAULT"
          Scheme: "package"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        67de091 com.android.settings/.Settings$AppWriteSettingsActivity filter f2afbf6
          Action: "android.settings.action.MANAGE_WRITE_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          Scheme: "package"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        88ef4cd com.android.settings/.Settings$AlarmsAndRemindersAppActivity filter 702e182
          Action: "android.settings.REQUEST_SCHEDULE_EXACT_ALARM"
          Category: "android.intent.category.DEFAULT"
          Scheme: "package"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        62310c9 com.android.settings/.Settings$ManageAppExternalSourcesActivity filter 8193ce
          Action: "android.settings.MANAGE_UNKNOWN_APP_SOURCES"
          Category: "android.intent.category.DEFAULT"
          Scheme: "package"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        7c71001 com.android.settings/.Settings$AppManageExternalStorageActivity filter 8684ea6
          Action: "android.settings.MANAGE_APP_ALL_FILES_ACCESS_PERMISSION"
          Category: "android.intent.category.DEFAULT"
          Scheme: "package"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        993ab3d com.android.settings/.Settings$AppMediaManagementAppsActivity filter 3aaf32
          Action: "android.settings.REQUEST_MANAGE_MEDIA"
          Category: "android.intent.category.DEFAULT"
          Scheme: "package"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        1b5822c com.android.settings/.fuelgauge.AdvancedPowerUsageDetailActivity filter 1fa04f5
          Action: "android.settings.VIEW_ADVANCED_POWER_USAGE_DETAIL"
          Category: "android.intent.category.DEFAULT"
          Scheme: "package"
        b2addad com.android.settings/.applications.autofill.AutofillPickerTrampolineActivity filter 19948e2
          Action: "android.settings.REQUEST_SET_AUTOFILL_SERVICE"
          Category: "android.intent.category.DEFAULT"
          Scheme: "package"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      DPP:
        f1c0063 com.android.settings/.wifi.dpp.WifiDppConfiguratorActivity filter 339cd19
          Action: "android.settings.PROCESS_WIFI_EASY_CONNECT_URI"
          Category: "android.intent.category.DEFAULT"
          Scheme: "DPP"
      content:
        813a923 com.android.settings/.Settings$PublicVolumeSettingsActivity filter 1f9de20
          Action: "android.provider.action.DOCUMENT_ROOT_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          Scheme: "content"
          Authority: "com.android.externalstorage.documents": -1
          StaticType: "vnd.android.document/root"
      settings:
        4126682 com.android.settings/.slices.SliceDeepLinkSpringBoard filter 19d7193
          Action: "android.intent.action.VIEW"
          Category: "android.intent.category.DEFAULT"
          Category: "android.intent.category.BROWSABLE"
          Scheme: "settings"
          Authority: "com.android.settings.slices": -1

  Non-Data Actions:
      android.settings.FINGERPRINT_SETUP:
        d6658f0 com.android.settings/.biometrics.fingerprint.SetupFingerprintEnrollIntroduction filter d4d2e69
          Action: "android.settings.FINGERPRINT_SETUP"
          Category: "android.intent.category.DEFAULT"
      android.net.wifi.PICK_WIFI_NETWORK:
        4bdbe11 com.android.settings/.wifi.WifiPickerActivity filter 6d94b76
          Action: "android.net.wifi.PICK_WIFI_NETWORK"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.SHOW_REGULATORY_INFO:
        691259c com.android.settings/.RegulatoryInfoDisplayActivity filter 7eabba5
          Action: "android.settings.SHOW_REGULATORY_INFO"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
      android.settings.MANAGE_ALL_FILES_ACCESS_PERMISSION:
        caabf0b com.android.settings/.Settings$ManageExternalStorageActivity filter 86ae1e8
          Action: "android.settings.MANAGE_ALL_FILES_ACCESS_PERMISSION"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      com.android.settings.action.SUPPORT_SETTINGS:
        78931d7 com.android.settings/.support.SupportDashboardActivity filter 5e3eac4
          Action: "com.android.settings.action.SUPPORT_SETTINGS"
          Category: "android.intent.category.DEFAULT"
      android.settings.SHOW_MANUAL:
        5ee466e com.android.settings/.ManualDisplayActivity filter 6fdb10f
          Action: "android.settings.SHOW_MANUAL"
          Category: "android.intent.category.DEFAULT"
      android.settings.NETWORK_OPERATOR_SETTINGS:
        6fd2fa com.android.settings/.Settings$MobileNetworkActivity filter 94130ab
          Action: "android.intent.action.MAIN"
          Action: "android.telephony.ims.action.SHOW_CAPABILITY_DISCOVERY_OPT_IN"
          Action: "android.settings.NETWORK_OPERATOR_SETTINGS"
          Action: "android.settings.DATA_ROAMING_SETTINGS"
          Action: "android.settings.MMS_MESSAGE_SETTING"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      com.android.settings.action.SETTINGS:
        1eebc4c com.android.settings/.Settings$DevelopmentSettingsDashboardActivity filter c2509aa
          Action: "com.android.settings.action.SETTINGS"
        670d112 com.android.settings/.Settings$UserSettingsActivity filter 74aaae0
          Action: "com.android.settings.action.SETTINGS"
      android.net.wifi.action.REQUEST_ENABLE:
        abc5b7a com.android.settings/.wifi.RequestToggleWiFiActivity filter 6e4f2b
          Action: "android.net.wifi.action.REQUEST_ENABLE"
          Action: "android.net.wifi.action.REQUEST_DISABLE"
          Category: "android.intent.category.DEFAULT"
      android.settings.ACTION_NOTIFICATION_LISTENER_SETTINGS:
        251706a com.android.settings/.Settings$NotificationAccessSettingsActivity filter 8e9595b
          Action: "android.settings.ACTION_NOTIFICATION_LISTENER_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.USER_SETTINGS:
        670d112 com.android.settings/.Settings$UserSettingsActivity filter 3a8b0e3
          Action: "android.settings.USER_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      com.android.settings.USER_DICTIONARY_INSERT:
        ed91910 com.android.settings/.inputmethod.UserDictionaryAddWordActivity filter a72bc09
          Action: "com.android.settings.USER_DICTIONARY_INSERT"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.SHOW_RESTRICTED_SETTING_DIALOG:
        6c2f085 com.android.settings/.ActionDisabledByAppOpsDialog filter 2271eda
          Action: "android.settings.SHOW_RESTRICTED_SETTING_DIALOG"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.DISPLAY_SETTINGS:
        8b93d58 com.android.settings/.Settings$DisplaySettingsActivity filter 1a01eb1
          Action: "com.android.settings.DISPLAY_SETTINGS"
          Action: "android.settings.DISPLAY_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.DATA_SAVER_SETTINGS:
        32e09ba com.android.settings/.Settings$DataSaverSummaryActivity filter 16d006b
          Action: "android.settings.DATA_SAVER_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      com.google.android.settings.security.SECURITY_ADVANCED_SETTINGS:
        1489bee com.android.settings/com.google.android.settings.security.SecurityAdvancedSettingsActivity filter 381188f
          Action: "com.google.android.settings.security.SECURITY_ADVANCED_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      com.android.settings.BLUETOOTH_DEVICE_DETAIL_SETTINGS:
        e07112e com.android.settings/.Settings$BluetoothDeviceDetailActivity filter 7d284cf
          Action: "com.android.settings.BLUETOOTH_DEVICE_DETAIL_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      com.google.android.settings.future.AWARE_ASSIST_SETTINGS:
        5a016 com.android.settings/com.google.android.settings.aware.AwareAssistSettingsActivity filter 300d97
          Action: "com.google.android.settings.future.AWARE_ASSIST_SETTINGS"
          Category: "android.intent.category.DEFAULT"
      com.google.android.settings.warranty.SUW_DIGITAL_WARRANTY:
        5c43ac6 com.android.settings/com.google.android.settings.warranty.SuwWarrantyActivity filter 9998a87
          Action: "com.google.android.settings.warranty.SUW_DIGITAL_WARRANTY"
          Category: "android.intent.category.DEFAULT"
      android.settings.LOCATION_SOURCE_SETTINGS:
        7d2d300 com.android.settings/.Settings$LocationSettingsActivity filter 30e0739
          Action: "android.settings.LOCATION_SOURCE_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.BLUETOOTH_SETTINGS:
        55824c6 com.android.settings/.Settings$ConnectedDeviceDashboardActivity filter 8e02c87
          Action: "android.settings.BLUETOOTH_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.telephony.ims.action.SHOW_CAPABILITY_DISCOVERY_OPT_IN:
        6fd2fa com.android.settings/.Settings$MobileNetworkActivity filter 94130ab
          Action: "android.intent.action.MAIN"
          Action: "android.telephony.ims.action.SHOW_CAPABILITY_DISCOVERY_OPT_IN"
          Action: "android.settings.NETWORK_OPERATOR_SETTINGS"
          Action: "android.settings.DATA_ROAMING_SETTINGS"
          Action: "android.settings.MMS_MESSAGE_SETTING"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      com.android.credentials.INSTALL:
        31c2148 com.android.settings/.security.CredentialStorage filter ace4be1
          Action: "com.android.credentials.INSTALL"
          Action: "com.android.credentials.RESET"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.APPLICATION_DEVELOPMENT_SETTINGS:
        1eebc4c com.android.settings/.Settings$DevelopmentSettingsDashboardActivity filter ecd8495
          Action: "android.settings.APPLICATION_DEVELOPMENT_SETTINGS"
          Action: "com.android.settings.APPLICATION_DEVELOPMENT_SETTINGS"
          Action: "android.service.quicksettings.action.QS_TILE_PREFERENCES"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        833199b com.android.settings/.development.DevelopmentSettingsDisabledActivity filter 8715138
          Action: "android.settings.APPLICATION_DEVELOPMENT_SETTINGS"
          Action: "com.android.settings.APPLICATION_DEVELOPMENT_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=-1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.MEDIA_BROADCAST_DIALOG:
        33ce5c com.android.settings/.Settings$BluetoothBroadcastActivity filter 6171565
          Action: "android.settings.MEDIA_BROADCAST_DIALOG"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.SETTINGS:
        3aa2f97 com.android.settings/.homepage.SettingsHomepageActivity filter fc07584
          Action: "android.settings.SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      com.android.settings.SETUP_LOCK_SCREEN:
        5f0141c com.android.settings/.password.SetupChooseLockGeneric filter 7014825
          Action: "com.android.settings.SETUP_LOCK_SCREEN"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.HARD_KEYBOARD_SETTINGS:
        2fc556a com.android.settings/.Settings$PhysicalKeyboardActivity filter 172da5b
          Action: "android.settings.HARD_KEYBOARD_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.VR_LISTENER_SETTINGS:
        9a179a4 com.android.settings/.Settings$VrListenersSettingsActivity filter 5a8f30d
          Action: "android.settings.VR_LISTENER_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      com.android.settings.sim.SIM_SUB_INFO_SETTINGS:
        3dd7a8f com.android.settings/.Settings$NetworkDashboardActivity filter a3ef11c
          Action: "android.settings.WIRELESS_SETTINGS"
          Action: "android.settings.AIRPLANE_MODE_SETTINGS"
          Action: "com.android.settings.sim.SIM_SUB_INFO_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.ADD_ACCOUNT_SETTINGS:
        1429d4f com.android.settings/.accounts.AddAccountSettings filter f653cdc
          Action: "android.settings.ADD_ACCOUNT_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      com.google.android.settings.action.CONFIRM_FACE_ENROLLMENT:
        c5c899f com.android.settings/com.google.android.settings.biometrics.face.FaceEnrollConfirmation filter 54f3aec
          Action: "com.google.android.settings.action.CONFIRM_FACE_ENROLLMENT"
          Category: "android.intent.category.DEFAULT"
      android.settings.COLOR_INVERSION_SETTINGS:
        17b4ec1 com.android.settings/.Settings$AccessibilityInversionSettingsActivity filter dc58666
          Action: "android.settings.COLOR_INVERSION_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.MANAGED_PROFILE_SETTINGS:
        48bec29 com.android.settings/.Settings$ManagedProfileSettingsActivity filter 23e3bae
          Action: "android.settings.MANAGED_PROFILE_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.USAGE_ACCESS_SETTINGS:
        b00b6de com.android.settings/.Settings$UsageAccessSettingsActivity filter 4b9b0bf
          Action: "android.settings.USAGE_ACCESS_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.bluetooth.device.action.CONNECTION_ACCESS_CANCEL:
        f1b0926 com.android.settings/.bluetooth.BluetoothPermissionActivity filter 4b0a967
          Action: "android.bluetooth.device.action.CONNECTION_ACCESS_REQUEST"
          Action: "android.bluetooth.device.action.CONNECTION_ACCESS_CANCEL"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      com.android.settings.TRUSTED_CREDENTIALS_USER:
        2cf4de2 com.android.settings/.Settings$TrustedCredentialsSettingsActivity filter acb3573
          Action: "com.android.settings.TRUSTED_CREDENTIALS"
          Action: "com.android.settings.TRUSTED_CREDENTIALS_USER"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.BIOMETRIC_ENROLL:
        a1c3884 com.android.settings/.biometrics.BiometricEnrollActivity filter 154786d
          Action: "android.settings.BIOMETRIC_ENROLL"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
      android.app.action.CONFIRM_FRP_CREDENTIAL:
        3b4fc3e com.android.settings/.password.ConfirmDeviceCredentialActivity filter ede7a9f
          Action: "android.app.action.CONFIRM_DEVICE_CREDENTIAL"
          Action: "android.app.action.CONFIRM_FRP_CREDENTIAL"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.app.action.ADD_DEVICE_ADMIN:
        9aaf392 com.android.settings/.applications.specialaccess.deviceadmin.DeviceAdminAdd filter 8ec6163
          Action: "android.app.action.ADD_DEVICE_ADMIN"
          Category: "android.intent.category.DEFAULT"
          mPriority=1000, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.bluetooth.device.action.CONNECTION_ACCESS_REQUEST:
        f1b0926 com.android.settings/.bluetooth.BluetoothPermissionActivity filter 4b0a967
          Action: "android.bluetooth.device.action.CONNECTION_ACCESS_REQUEST"
          Action: "android.bluetooth.device.action.CONNECTION_ACCESS_CANCEL"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      com.android.settings.WIFI_TETHER_SETTINGS:
        116d062 com.android.settings/.Settings$WifiTetherSettingsActivity filter 800c5f3
          Action: "com.android.settings.WIFI_TETHER_SETTINGS"
          Category: "android.intent.category.DEFAULT"
      android.settings.LICENSE:
        cfbf35d com.android.settings/.SettingsLicenseActivity filter 25b24d2
          Action: "android.settings.LICENSE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.nfc.cardemulation.action.ACTION_CHANGE_DEFAULT:
        e5f950c com.android.settings/.nfc.PaymentDefaultDialog filter 1644e55
          Action: "android.nfc.cardemulation.action.ACTION_CHANGE_DEFAULT"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.NOTIFICATION_ASSISTANT_SETTINGS:
        30e2936 com.android.settings/.Settings$NotificationAssistantSettingsActivity filter 35a3037
          Action: "android.settings.NOTIFICATION_ASSISTANT_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.ACTION_OTHER_SOUND_SETTINGS:
        416a13b com.android.settings/.Settings$SoundSettingsActivity filter 164d058
          Action: "com.android.settings.SOUND_SETTINGS"
          Action: "android.settings.SOUND_SETTINGS"
          Action: "android.settings.ACTION_OTHER_SOUND_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.ACCOUNT_SYNC_SETTINGS:
        48ca4f3 com.android.settings/.Settings$AccountSyncSettingsActivity filter 11675b0
          Action: "android.settings.ACCOUNT_SYNC_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.net.action.PROMPT_UNVALIDATED:
        6097e26 com.android.settings/.wifi.WifiNoInternetDialog filter dde7a67
          Action: "android.net.action.PROMPT_UNVALIDATED"
          Category: "android.intent.category.DEFAULT"
      android.settings.LOCATION_SCANNING_SETTINGS:
        90756df com.android.settings/.Settings$ScanningSettingsActivity filter 4121f2c
          Action: "android.settings.LOCATION_SCANNING_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.intent.action.MAIN:
        d8716d com.android.settings/.Settings filter 605b1a2
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.DEFAULT"
          Category: "android.intent.category.LAUNCHER"
        3dd7a8f com.android.settings/.Settings$NetworkDashboardActivity filter 1eb6125
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.DEFAULT"
          Category: "android.intent.category.VOICE_LAUNCH"
        6fd2fa com.android.settings/.Settings$MobileNetworkActivity filter 94130ab
          Action: "android.intent.action.MAIN"
          Action: "android.telephony.ims.action.SHOW_CAPABILITY_DISCOVERY_OPT_IN"
          Action: "android.settings.NETWORK_OPERATOR_SETTINGS"
          Action: "android.settings.DATA_ROAMING_SETTINGS"
          Action: "android.settings.MMS_MESSAGE_SETTING"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        c6e47b4 com.android.settings/.Settings$BluetoothSettingsActivity filter e058fdd
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.SHORTCUT"
          mPriority=10, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        a2ed94c com.android.settings/.Settings$NetworkProviderSettingsActivity filter 9e2eeaa
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.SHORTCUT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        aaf2a4d com.android.settings/.Settings$ConfigureWifiSettingsActivity filter 3e0c213
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.VOICE_LAUNCH"
          Category: "android.intent.category.DEFAULT"
        6ba534e com.android.settings/.Settings$WifiInfoActivity filter f0b6c6f
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.DEVELOPMENT_PREFERENCE"
          Category: "android.intent.category.DEFAULT"
        fc12d7c com.android.settings/.wifi.WifiConfigInfo filter b045605
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.DEVELOPMENT_PREFERENCE"
          Category: "android.intent.category.DEFAULT"
        fec565a com.android.settings/.Settings$WifiAPITestActivity filter d8c608b
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.DEVELOPMENT_PREFERENCE"
          Category: "android.intent.category.DEFAULT"
        b1a568 com.android.settings/.wifi.WifiStatusTest filter 2794d81
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.DEVELOPMENT_PREFERENCE"
          Category: "android.intent.category.DEFAULT"
        cec40bd com.android.settings/.Settings$ApnSettingsActivity filter 14e5603
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.DEFAULT"
          Category: "android.intent.category.VOICE_LAUNCH"
        1294644 com.android.settings/.Settings$TetherSettingsActivity filter e93d32d
          Action: "android.intent.action.MAIN"
          Action: "android.settings.TETHER_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          Category: "android.intent.category.VOICE_LAUNCH"
        116d062 com.android.settings/.Settings$WifiTetherSettingsActivity filter 19682b0
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.SHORTCUT"
          mPriority=4, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        d077529 com.android.settings/.Settings$WifiP2pSettingsActivity filter 89590ae
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.DEFAULT"
          Category: "android.intent.category.VOICE_LAUNCH"
        e57ce4f com.android.settings/.Settings$VpnSettingsActivity filter 3f93ae5
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.SHORTCUT"
          mPriority=5, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        f4bf7c8 com.android.settings/.Settings$DateTimeSettingsActivity filter 9a30786
          Action: "android.intent.action.MAIN"
          Action: "android.intent.action.QUICK_CLOCK"
          Category: "android.intent.category.VOICE_LAUNCH"
          Category: "android.intent.category.DEFAULT"
        e593847 com.android.settings/.Settings$LocalePickerActivity filter d3ce19d
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.DEFAULT"
          Category: "android.intent.category.VOICE_LAUNCH"
        267f7e0 com.android.settings/.Settings$LanguageAndInputSettingsActivity filter b0afa99
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.VOICE_LAUNCH"
          Category: "android.intent.category.DEFAULT"
        9d0e2f8 com.android.settings/.Settings$SpellCheckersSettingsActivity filter 6e863d1
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.VOICE_LAUNCH"
          Category: "android.intent.category.DEFAULT"
        4025e36 com.android.settings/.inputmethod.InputMethodAndSubtypeEnablerActivity filter fad36a4
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.VOICE_LAUNCH"
          Category: "android.intent.category.DEFAULT"
        a3e6c0d com.android.settings/.Settings$UserDictionarySettingsActivity filter eb039d3
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.DEFAULT"
          Category: "android.intent.category.VOICE_LAUNCH"
        1afe0e com.android.settings/.Settings$ZenModeSettingsActivity filter 9820fc5
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.SHORTCUT"
          mPriority=41, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        48ced1a com.android.settings/.notification.zen.ZenSuggestionActivity filter c5b104b
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.suggested.category.ZEN"
        48ced1a com.android.settings/.notification.zen.ZenSuggestionActivity filter 6befa28
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.suggested.category.FIRST_IMPRESSION"
        b440572 com.android.settings/.wallpaper.WallpaperSuggestionActivity filter dcb3dc3
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.suggested.category.FIRST_IMPRESSION"
        b440572 com.android.settings/.wallpaper.WallpaperSuggestionActivity filter 42ce640
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.suggested.category.PERSONALIZE"
        ac5b979 com.android.settings/.wallpaper.StyleSuggestionActivity filter 14906be
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.suggested.category.FIRST_IMPRESSION"
        119f31f com.android.settings/.Settings$ZenModeScheduleRuleSettingsActivity filter b5f7435
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.DEFAULT"
        8b93d58 com.android.settings/.Settings$DisplaySettingsActivity filter 86d2f96
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.SHORTCUT"
          mPriority=30, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        f012717 com.android.settings/.Settings$SmartAutoRotateSettingsActivity filter 766f4ed
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.SHORTCUT"
          mPriority=32, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        1c4af22 com.android.settings/.Settings$NightDisplaySettingsActivity filter 4671db3
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.SHORTCUT"
          mPriority=32, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        b4af2e9 com.android.settings/.Settings$DarkThemeSettingsActivity filter e229b6e
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.SHORTCUT"
          mPriority=32, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        92a029c com.android.settings/.Settings$NightDisplaySuggestionActivity filter 456d4a5
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.suggested.category.FIRST_IMPRESSION"
        a61007a com.android.settings/.Settings$MyDeviceInfoActivity filter 122ac88
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.SHORTCUT"
          mPriority=71, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        b096859 com.android.settings/.Settings$ManageApplicationsActivity filter dcf6cff
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.SHORTCUT"
          mPriority=20, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        692fefc com.android.settings/.Settings$RunningServicesActivity filter 92f8985
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.DEFAULT"
          Category: "android.intent.category.MONKEY"
          Category: "android.intent.category.VOICE_LAUNCH"
        70243da com.android.settings/.Settings$StorageUseActivity filter 48f0ee8
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.DEFAULT"
          Category: "android.intent.category.MONKEY"
          Category: "android.intent.category.VOICE_LAUNCH"
        6e43901 com.android.settings/.Settings$NotificationStationActivity filter 50c3a6
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.SHORTCUT"
          mPriority=22, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        66411e7 com.android.settings/.notification.history.NotificationHistoryActivity filter 7da643d
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.DEFAULT"
        7d2d300 com.android.settings/.Settings$LocationSettingsActivity filter 242a17e
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.SHORTCUT"
          mPriority=52, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        f3481fb com.android.settings/.Settings$SecurityDashboardActivity filter d6c6471
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.DEFAULT"
          Category: "android.intent.category.VOICE_LAUNCH"
        cc0fc30 com.android.settings/.Settings$PrivacySettingsActivity filter 82230a9
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.DEFAULT"
          Category: "android.intent.category.VOICE_LAUNCH"
        77609f4 com.android.settings/.Settings$DeviceAdminSettingsActivity filter b02c51d
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.DEFAULT"
          Category: "android.intent.category.VOICE_LAUNCH"
        95d62ea com.android.settings/.Settings$IccLockSettingsActivity filter be299db
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.DEFAULT"
          Category: "android.intent.category.VOICE_LAUNCH"
        4be6c78 com.android.settings/.Settings$AccessibilitySettingsActivity filter 726c3b6
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.SHORTCUT"
          mPriority=60, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        686953 com.android.settings/.TextReadingForSetupWizardActivity filter 5be5290
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.suggested.category.DISPLAY_SETTINGS"
        a913789 com.android.settings/.FontSizeSettingsForSetupWizardActivity filter bb6938e
          Action: "android.intent.action.MAIN"
        b8647af com.android.settings/.Settings$AccessibilityDaltonizerSettingsActivity filter fccc345
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.DEFAULT"
        a0c5a9a com.android.settings/.Settings$ReduceBrightColorsSettingsActivity filter ae1e3a8
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.DEFAULT"
        17b4ec1 com.android.settings/.Settings$AccessibilityInversionSettingsActivity filter 4f17da7
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.DEFAULT"
        c009e4a com.android.settings/.SetupRedactionInterstitial filter 3ba21bb
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.suggested.category.LOCK_SCREEN_REDACTION"
        c36f0ee com.android.settings/.SetupFingerprintSuggestionActivity filter 6e1498f
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.suggested.category.FINGERPRINT_ENROLL"
        5f85608 com.android.settings/.password.ScreenLockSuggestionActivity filter 72341a1
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.suggested.category.FIRST_IMPRESSION"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        b882fc6 com.android.settings/.biometrics.fingerprint.FingerprintEnrollSuggestionActivity filter aedb87
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.suggested.category.FIRST_IMPRESSION"
          mPriority=2, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        2c0cab4 com.android.settings/.Settings$StorageDashboardActivity filter cc78252
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.SHORTCUT"
          mPriority=50, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        84ed511 com.android.settings/.Settings$PrintSettingsActivity filter f1fb477
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.DEFAULT"
          Category: "android.intent.category.VOICE_LAUNCH"
        222a50a com.android.settings/.UsageStatsActivity filter 6c5817b
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.DEVELOPMENT_PREFERENCE"
        fadcb98 com.android.settings/.Settings$PowerUsageSummaryActivity filter 4ce07d6
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.SHORTCUT"
          mPriority=51, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        4ce21e5 com.android.settings/.FallbackHome filter 63664ba
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.HOME"
          Category: "android.intent.category.DEFAULT"
          mPriority=-1000, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        9b5bf6b com.android.settings/.Settings$DataUsageSummaryActivity filter c43f761
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.SHORTCUT"
          mPriority=3, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        41b3199 com.android.settings/.Settings$PaymentSettingsActivity filter 3ab783f
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.DEFAULT"
        c0ba2c2 com.android.settings/.Settings$PictureInPictureSettingsActivity filter 74e8c10
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.DEFAULT"
        438ef2f com.android.settings/.Settings$TurnScreenOnSettingsActivity filter 8d676c5
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.DEFAULT"
        a964072 com.android.settings/.Settings$ConfigureNotificationSettingsActivity filter a651940
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.SHORTCUT"
          mPriority=21, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        416a13b com.android.settings/.Settings$SoundSettingsActivity filter b77b5b1
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.SHORTCUT"
          mPriority=40, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        1428c34 com.android.settings/.sim.SimDialogActivity filter 445ba5d
          Action: "android.intent.action.MAIN"
        166dfd2 com.android.settings/.Settings$WifiCallingSettingsActivity filter f6b78a3
          Action: "android.intent.action.MAIN"
          Action: "android.settings.WIFI_CALLING_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          Category: "android.intent.category.VOICE_LAUNCH"
        9637a0 com.android.settings/.wifi.calling.WifiCallingSuggestionActivity filter aa89f59
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.suggested.category.FIRST_IMPRESSION"
        d0a0483 com.android.settings/.backup.UserBackupSettingsActivity filter af60600
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.DEFAULT"
          Category: "android.intent.category.VOICE_LAUNCH"
        f74f28a com.android.settings/.Settings$AccountDashboardActivity filter 40e9518
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.SHORTCUT"
          mPriority=53, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        432fb71 com.android.settings/.Settings$SystemDashboardActivity filter cb7ad56
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.SHORTCUT"
          mPriority=70, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        6b5868c com.android.settings/.Settings$WifiCallingDisclaimerActivity filter 69121d5
          Action: "android.intent.action.MAIN"
          Category: "android.intent.category.DEFAULT"
        db88eb6 com.android.settings/.Settings$GestureNavigationSettingsActivity filter 9d467b7
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.SHORTCUT"
          mPriority=32, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        22cb68d com.android.settings/.Settings$ButtonNavigationSettingsActivity filter ab6e042
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.SHORTCUT"
          mPriority=32, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        2edaabc com.android.settings/.Settings$OneHandedSettingsActivity filter 304359a
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.SHORTCUT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        c8d25c1 com.android.settings/com.google.android.settings.gestures.assist.AssistGestureTrainingIntroActivity filter 898aca7
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.suggested.category.ASSIST_GESTURE"
        dc69554 com.android.settings/com.google.android.settings.gestures.AssistGestureSuggestion filter 2055cfd
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.suggested.category.FIRST_IMPRESSION"
          mPriority=30, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        74bddf2 com.android.settings/com.google.android.settings.gestures.columbus.ColumbusGestureTrainingIntroActivity filter ca1b2c0
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.suggested.category.COLUMBUS_GESTURE"
        5382eb5 com.android.settings/com.google.android.settings.aware.AwareSettingsActivity filter c8a20bb
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.suggested.category.FIRST_IMPRESSION"
        86b19d8 com.android.settings/com.google.android.settings.aware.WakeScreenSuggestionActivity filter c8a0131
          Action: "android.intent.action.MAIN"
          Category: "com.android.settings.suggested.category.FIRST_IMPRESSION"
      android.settings.TETHER_SETTINGS:
        1294644 com.android.settings/.Settings$TetherSettingsActivity filter e93d32d
          Action: "android.intent.action.MAIN"
          Action: "android.settings.TETHER_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          Category: "android.intent.category.VOICE_LAUNCH"
      android.settings.NOTIFICATION_POLICY_ACCESS_SETTINGS:
        12893d4 com.android.settings/.Settings$ZenAccessSettingsActivity filter 549b97d
          Action: "android.settings.NOTIFICATION_POLICY_ACCESS_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.intent.action.MANAGE_PACKAGE_STORAGE:
        70243da com.android.settings/.Settings$StorageUseActivity filter 13f800b
          Action: "android.intent.action.MANAGE_PACKAGE_STORAGE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.ZEN_MODE_ONBOARDING:
        278e341 com.android.settings/.notification.zen.ZenOnboardingActivity filter 7fcc0e6
          Action: "android.settings.ZEN_MODE_ONBOARDING"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.INTERNAL_STORAGE_SETTINGS:
        2c0cab4 com.android.settings/.Settings$StorageDashboardActivity filter 51156dd
          Action: "android.settings.INTERNAL_STORAGE_SETTINGS"
          Action: "android.settings.MEMORY_CARD_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.WIFI_ADD_NETWORKS:
        4eb8c1d com.android.settings/.wifi.addappnetworks.AddAppNetworksActivity filter 869ae92
          Action: "android.settings.WIFI_ADD_NETWORKS"
          Category: "android.intent.category.DEFAULT"
      android.settings.MANAGE_APPLICATIONS_SETTINGS:
        b096859 com.android.settings/.Settings$ManageApplicationsActivity filter ea2bc1e
          Action: "android.settings.APPLICATION_SETTINGS"
          Action: "android.settings.MANAGE_APPLICATIONS_SETTINGS"
          Action: "android.settings.MANAGE_ALL_APPLICATIONS_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.LOCK_SCREEN_SETTINGS:
        5851621 com.android.settings/.Settings$LockScreenSettingsActivity filter 4eeaa46
          Action: "android.settings.LOCK_SCREEN_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.SHOW_REMOTE_BUGREPORT_DIALOG:
        a777868 com.android.settings/.RemoteBugreportActivity filter 3fe2481
          Action: "android.settings.SHOW_REMOTE_BUGREPORT_DIALOG"
          Category: "android.intent.category.DEFAULT"
      android.settings.TETHER_UNSUPPORTED_CARRIER_UI:
        2c3bcd6 com.android.settings/.network.TetherProvisioningCarrierDialogActivity filter 464cb57
          Action: "android.settings.TETHER_UNSUPPORTED_CARRIER_UI"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.SYNC_SETTINGS:
        f74f28a com.android.settings/.Settings$AccountDashboardActivity filter 76d80fb
          Action: "android.settings.SYNC_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      com.android.settings.security.SECURITY_ADVANCED_SETTINGS:
        e276256 com.android.settings/.Settings$SecurityAdvancedSettings filter b3f42d7
          Action: "com.android.settings.security.SECURITY_ADVANCED_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      com.android.settings.action.SCREEN_SAVER:
        10d371c com.android.settings/com.google.android.settings.dream.DreamSetupActivity filter 5132f25
          Action: "com.android.settings.action.SCREEN_SAVER"
          Category: "android.intent.category.DEFAULT"
      android.settings.NETWORK_PROVIDER_SETTINGS:
        a2ed94c com.android.settings/.Settings$NetworkProviderSettingsActivity filter 8efdd95
          Action: "android.settings.NETWORK_PROVIDER_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      com.android.settings.GESTURE_NAVIGATION_SETTINGS:
        db88eb6 com.android.settings/.Settings$GestureNavigationSettingsActivity filter 5941b24
          Action: "com.android.settings.GESTURE_NAVIGATION_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.app.action.SET_PROFILE_OWNER:
        7e3d160 com.android.settings/.applications.specialaccess.deviceadmin.ProfileOwnerAdd filter 60b9619
          Action: "android.app.action.SET_PROFILE_OWNER"
          Category: "android.intent.category.DEFAULT"
          mPriority=1000, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.WEBVIEW_SETTINGS:
        f112402 com.android.settings/.WebViewImplementation filter ed12113
          Action: "android.settings.WEBVIEW_SETTINGS"
          Category: "android.intent.category.DEFAULT"
      android.settings.NFC_PAYMENT_SETTINGS:
        41b3199 com.android.settings/.Settings$PaymentSettingsActivity filter e06ec5e
          Action: "android.settings.NFC_PAYMENT_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.WIFI_SCANNING_SETTINGS:
        93eddf5 com.android.settings/.Settings$WifiScanningSettingsActivity filter 7e3578a
          Action: "android.settings.WIFI_SCANNING_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      com.android.settings.TTS_SETTINGS:
        893a2f2 com.android.settings/.Settings$TextToSpeechSettingsActivity filter bae4d43
          Action: "com.android.settings.TTS_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.ACTION_APP_NOTIFICATION_REDACTION:
        e2986d8 com.android.settings/.notification.RedactionSettingsStandalone filter 1d46a31
          Action: "android.settings.ACTION_APP_NOTIFICATION_REDACTION"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.MEMORY_CARD_SETTINGS:
        2c0cab4 com.android.settings/.Settings$StorageDashboardActivity filter 51156dd
          Action: "android.settings.INTERNAL_STORAGE_SETTINGS"
          Action: "android.settings.MEMORY_CARD_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.ACCESSIBILITY_SETTINGS:
        4be6c78 com.android.settings/.Settings$AccessibilitySettingsActivity filter 6f0ef51
          Action: "android.settings.ACCESSIBILITY_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.REQUEST_SCHEDULE_EXACT_ALARM:
        4566bf7 com.android.settings/.Settings$AlarmsAndRemindersActivity filter 5bb6a64
          Action: "android.settings.REQUEST_SCHEDULE_EXACT_ALARM"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.WIFI_CALLING_SETTINGS:
        166dfd2 com.android.settings/.Settings$WifiCallingSettingsActivity filter f6b78a3
          Action: "android.intent.action.MAIN"
          Action: "android.settings.WIFI_CALLING_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          Category: "android.intent.category.VOICE_LAUNCH"
      android.settings.REVERSE_CHARGING_SETTINGS:
        263fb84 com.android.settings/com.google.android.settings.fuelgauge.reversecharging.ReverseChargingTrampoline filter 74c7f6d
          Action: "android.settings.REVERSE_CHARGING_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.DARK_THEME_SETTINGS:
        b4af2e9 com.android.settings/.Settings$DarkThemeSettingsActivity filter 52be20f
          Action: "android.settings.DARK_THEME_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.bluetooth.adapter.action.REQUEST_ENABLE:
        4bfd07c com.android.settings/.bluetooth.RequestPermissionActivity filter 319bd05
          Action: "android.bluetooth.adapter.action.REQUEST_DISCOVERABLE"
          Action: "android.bluetooth.adapter.action.REQUEST_ENABLE"
          Action: "android.bluetooth.adapter.action.REQUEST_DISABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.MOBILE_NETWORK_LIST:
        cd80308 com.android.settings/.Settings$MobileNetworkListActivity filter 915eaa1
          Action: "android.settings.MOBILE_NETWORK_LIST"
          Action: "android.settings.MANAGE_ALL_SIM_PROFILES_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.PRIVACY_SETTINGS:
        d18662e com.android.settings/.Settings$PrivacyDashboardActivity filter 819b5cf
          Action: "android.settings.PRIVACY_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
      com.android.settings.ADVANCED_CONNECTED_DEVICE_SETTINGS:
        3451473 com.android.settings/.Settings$AdvancedConnectedDeviceActivity filter 44a7a9
          Action: "com.android.settings.ADVANCED_CONNECTED_DEVICE_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.ALL_APPS_NOTIFICATION_SETTINGS:
        33a7a96 com.android.settings/.Settings$NotificationAppListActivity filter 7441617
          Action: "android.settings.ALL_APPS_NOTIFICATION_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      com.android.settings.MONITORING_CERT_INFO:
        99727c4 com.android.settings/.MonitoringCertInfoActivity filter 911d6ad
          Action: "com.android.settings.MONITORING_CERT_INFO"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.MMS_MESSAGE_SETTING:
        6fd2fa com.android.settings/.Settings$MobileNetworkActivity filter 94130ab
          Action: "android.intent.action.MAIN"
          Action: "android.telephony.ims.action.SHOW_CAPABILITY_DISCOVERY_OPT_IN"
          Action: "android.settings.NETWORK_OPERATOR_SETTINGS"
          Action: "android.settings.DATA_ROAMING_SETTINGS"
          Action: "android.settings.MMS_MESSAGE_SETTING"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.MOBILE_DATA_USAGE:
        4561286 com.android.settings/.Settings$MobileDataUsageListActivity filter beee747
          Action: "android.settings.MOBILE_DATA_USAGE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.NOTIFICATION_HISTORY:
        66411e7 com.android.settings/.notification.history.NotificationHistoryActivity filter 5ba3194
          Action: "android.settings.NOTIFICATION_HISTORY"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.WIRELESS_SETTINGS:
        3dd7a8f com.android.settings/.Settings$NetworkDashboardActivity filter a3ef11c
          Action: "android.settings.WIRELESS_SETTINGS"
          Action: "android.settings.AIRPLANE_MODE_SETTINGS"
          Action: "com.android.settings.sim.SIM_SUB_INFO_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.action.ONE_HANDED_SETTINGS:
        2edaabc com.android.settings/.Settings$OneHandedSettingsActivity filter 29f2a45
          Action: "android.settings.action.ONE_HANDED_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.USER_DICTIONARY_SETTINGS:
        a3e6c0d com.android.settings/.Settings$UserDictionarySettingsActivity filter 8e27c2
          Action: "android.settings.USER_DICTIONARY_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.NOTIFICATION_LISTENER_DETAIL_SETTINGS:
        bf6f5f8 com.android.settings/.Settings$NotificationAccessDetailsActivity filter ce87ad1
          Action: "android.settings.NOTIFICATION_LISTENER_DETAIL_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.ALL_APPS_NOTIFICATION_SETTINGS_FOR_REVIEW:
        3829a04 com.android.settings/.Settings$NotificationReviewPermissionsActivity filter ca0fbed
          Action: "android.settings.ALL_APPS_NOTIFICATION_SETTINGS_FOR_REVIEW"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.WIFI_IP_SETTINGS:
        aaf2a4d com.android.settings/.Settings$ConfigureWifiSettingsActivity filter 6a902
          Action: "android.settings.WIFI_IP_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.APPLICATION_SETTINGS:
        b096859 com.android.settings/.Settings$ManageApplicationsActivity filter ea2bc1e
          Action: "android.settings.APPLICATION_SETTINGS"
          Action: "android.settings.MANAGE_APPLICATIONS_SETTINGS"
          Action: "android.settings.MANAGE_ALL_APPLICATIONS_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.bluetooth.device.action.PAIRING_REQUEST:
        b717e4e com.android.settings/.bluetooth.BluetoothPairingDialog filter 222bb6f
          Action: "android.bluetooth.device.action.PAIRING_REQUEST"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.service.quicksettings.action.QS_TILE_PREFERENCES:
        1eebc4c com.android.settings/.Settings$DevelopmentSettingsDashboardActivity filter ecd8495
          Action: "android.settings.APPLICATION_DEVELOPMENT_SETTINGS"
          Action: "com.android.settings.APPLICATION_DEVELOPMENT_SETTINGS"
          Action: "android.service.quicksettings.action.QS_TILE_PREFERENCES"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      com.android.settings.TRUSTED_CREDENTIALS:
        2cf4de2 com.android.settings/.Settings$TrustedCredentialsSettingsActivity filter acb3573
          Action: "com.android.settings.TRUSTED_CREDENTIALS"
          Action: "com.android.settings.TRUSTED_CREDENTIALS_USER"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.credentials.UNLOCK:
        f3481fb com.android.settings/.Settings$SecurityDashboardActivity filter c180218
          Action: "android.settings.SECURITY_SETTINGS"
          Action: "android.credentials.UNLOCK"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.ZEN_MODE_PRIORITY_SETTINGS:
        1afe0e com.android.settings/.Settings$ZenModeSettingsActivity filter c9eb63c
          Action: "android.settings.ZEN_MODE_PRIORITY_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.FACE_ENROLL:
        2b25516 com.android.settings/.biometrics.face.FaceEnrollIntroduction filter df1e97
          Action: "android.settings.FACE_ENROLL"
          Category: "android.intent.category.DEFAULT"
      android.settings.SETTINGS_EMBED_DEEP_LINK_ACTIVITY:
        1d82e33 com.android.settings/.homepage.DeepLinkHomepageActivity filter 59165f0
          Action: "android.settings.SETTINGS_EMBED_DEEP_LINK_ACTIVITY"
          Category: "android.intent.category.DEFAULT"
      android.intent.action.QUICK_CLOCK:
        f4bf7c8 com.android.settings/.Settings$DateTimeSettingsActivity filter 9a30786
          Action: "android.intent.action.MAIN"
          Action: "android.intent.action.QUICK_CLOCK"
          Category: "android.intent.category.VOICE_LAUNCH"
          Category: "android.intent.category.DEFAULT"
      com.android.settings.action.FACTORY_RESET:
        356be8e com.android.settings/.Settings$FactoryResetActivity filter 9d296af
          Action: "com.android.settings.action.FACTORY_RESET"
          Category: "android.intent.category.DEFAULT"
      com.android.settings.action.AWARE_SETTING:
        5382eb5 com.android.settings/com.google.android.settings.aware.AwareSettingsActivity filter c25394a
          Action: "com.android.settings.action.AWARE_SETTING"
          Category: "android.intent.category.DEFAULT"
      android.net.vpn.SETTINGS:
        e57ce4f com.android.settings/.Settings$VpnSettingsActivity filter c5919dc
          Action: "android.settings.VPN_SETTINGS"
          Action: "android.net.vpn.SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.BLUETOOTH_PAIRING_SETTINGS:
        9a40407 com.android.settings/.Settings$BlueToothPairingActivity filter 87a0934
          Action: "android.settings.BLUETOOTH_PAIRING_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.ZEN_MODE_AUTOMATION_SETTINGS:
        1486627 com.android.settings/.Settings$ZenModeAutomationSettingsActivity filter 41d90d4
          Action: "android.settings.ZEN_MODE_AUTOMATION_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.DEVICE_INFO_SETTINGS:
        a61007a com.android.settings/.Settings$MyDeviceInfoActivity filter 1ce902b
          Action: "android.settings.DEVICE_INFO_SETTINGS"
          Action: "android.settings.DEVICE_NAME"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.FINGERPRINT_SETTINGS:
        e68edac com.android.settings/.Settings$FingerprintSettingsActivity filter a1fca75
          Action: "android.settings.FINGERPRINT_SETTINGS"
          Category: "android.intent.category.DEFAULT"
      com.android.credentials.RESET:
        31c2148 com.android.settings/.security.CredentialStorage filter ace4be1
          Action: "com.android.credentials.INSTALL"
          Action: "com.android.credentials.RESET"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.net.wifi.action.REQUEST_SCAN_ALWAYS_AVAILABLE:
        6b315a com.android.settings/.wifi.WifiScanModeActivity filter c499f8b
          Action: "android.net.wifi.action.REQUEST_SCAN_ALWAYS_AVAILABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.REQUEST_MANAGE_MEDIA:
        6c440e7 com.android.settings/.Settings$MediaManagementAppsActivity filter 7003494
          Action: "android.settings.REQUEST_MANAGE_MEDIA"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.SECURITY_SETTINGS:
        f3481fb com.android.settings/.Settings$SecurityDashboardActivity filter c180218
          Action: "android.settings.SECURITY_SETTINGS"
          Action: "android.credentials.UNLOCK"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.BLUTOOTH_FIND_BROADCASTS_ACTIVITY:
        177123a com.android.settings/.Settings$BluetoothFindBroadcastsActivity filter a1c9eeb
          Action: "android.settings.BLUTOOTH_FIND_BROADCASTS_ACTIVITY"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.intent.action.POWER_USAGE_SUMMARY:
        fadcb98 com.android.settings/.Settings$PowerUsageSummaryActivity filter 982ff1
          Action: "android.intent.action.POWER_USAGE_SUMMARY"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.panel.action.NFC:
        b5d7448 com.android.settings/.panel.SettingsPanelActivity filter ab41806
          Action: "android.settings.panel.action.NFC"
          Category: "android.intent.category.DEFAULT"
      android.settings.SHOW_ADMIN_SUPPORT_DETAILS:
        188e2ef com.android.settings/.enterprise.ActionDisabledByAdminDialog filter 47a1fc
          Action: "android.settings.SHOW_ADMIN_SUPPORT_DETAILS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.WARRANTY_DETAILS:
        944a908 com.android.settings/com.google.android.settings.warranty.WarrantyDetailsActivity filter 1ec98a1
          Action: "android.settings.WARRANTY_DETAILS"
          Category: "android.intent.category.DEFAULT"
      com.google.android.settings.COLUMBUS_GESTURE_TRAINING:
        74bddf2 com.android.settings/com.google.android.settings.gestures.columbus.ColumbusGestureTrainingIntroActivity filter 4196c43
          Action: "com.google.android.settings.COLUMBUS_GESTURE_TRAINING"
          Category: "android.intent.category.DEFAULT"
      android.settings.PRIVACY_ADVANCED_SETTINGS:
        d18662e com.android.settings/.Settings$PrivacyDashboardActivity filter 571ab5c
          Action: "android.settings.PRIVACY_ADVANCED_SETTINGS"
          Category: "android.intent.category.DEFAULT"
      android.settings.ZEN_MODE_SETTINGS:
        1afe0e com.android.settings/.Settings$ZenModeSettingsActivity filter 1baa02f
          Action: "android.settings.ZEN_MODE_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.VPN_SETTINGS:
        e57ce4f com.android.settings/.Settings$VpnSettingsActivity filter c5919dc
          Action: "android.settings.VPN_SETTINGS"
          Action: "android.net.vpn.SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.intent.action.PICK_ACTIVITY:
        f7fb314 com.android.settings/.ActivityPicker filter 76787bd
          Action: "android.intent.action.PICK_ACTIVITY"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.AUTO_ROTATE_SETTINGS:
        f012717 com.android.settings/.Settings$SmartAutoRotateSettingsActivity filter 30d704
          Action: "android.settings.AUTO_ROTATE_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.TURN_SCREEN_ON_SETTINGS:
        438ef2f com.android.settings/.Settings$TurnScreenOnSettingsActivity filter 278593c
          Action: "android.settings.TURN_SCREEN_ON_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.BUGREPORT_HANDLER_SETTINGS:
        ed10f50 com.android.settings/.Settings$BugReportHandlerPickerActivity filter 98e1549
          Action: "android.settings.BUGREPORT_HANDLER_SETTINGS"
          Category: "android.intent.category.DEFAULT"
      android.net.wifi.action.REQUEST_DISABLE:
        abc5b7a com.android.settings/.wifi.RequestToggleWiFiActivity filter 6e4f2b
          Action: "android.net.wifi.action.REQUEST_ENABLE"
          Action: "android.net.wifi.action.REQUEST_DISABLE"
          Category: "android.intent.category.DEFAULT"
      android.settings.CONVERSATION_SETTINGS:
        23d7079 com.android.settings/.Settings$ConversationListSettingsActivity filter 303f1be
          Action: "android.settings.CONVERSATION_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.MANAGE_ALL_APPLICATIONS_SETTINGS:
        b096859 com.android.settings/.Settings$ManageApplicationsActivity filter ea2bc1e
          Action: "android.settings.APPLICATION_SETTINGS"
          Action: "android.settings.MANAGE_APPLICATIONS_SETTINGS"
          Action: "android.settings.MANAGE_ALL_APPLICATIONS_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.WIFI_DPP_CONFIGURATOR_QR_CODE_GENERATOR:
        f1c0063 com.android.settings/.wifi.dpp.WifiDppConfiguratorActivity filter 69c8460
          Action: "android.settings.WIFI_DPP_CONFIGURATOR_QR_CODE_SCANNER"
          Action: "android.settings.WIFI_DPP_CONFIGURATOR_QR_CODE_GENERATOR"
          Category: "android.intent.category.DEFAULT"
      android.settings.REQUEST_ENABLE_CONTENT_CAPTURE:
        d18662e com.android.settings/.Settings$PrivacyDashboardActivity filter 8c42e65
          Action: "android.settings.REQUEST_ENABLE_CONTENT_CAPTURE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.ASSIST_GESTURE_SETTINGS:
        5e1b980 com.android.settings/.Settings$AssistGestureSettingsActivity filter a12bb9
          Action: "android.settings.ASSIST_GESTURE_SETTINGS"
          Category: "android.intent.category.DEFAULT"
      android.settings.ENTERPRISE_PRIVACY_SETTINGS:
        9937fc0 com.android.settings/.Settings$EnterprisePrivacySettingsActivity filter 33a14f9
          Action: "android.settings.ENTERPRISE_PRIVACY_SETTINGS"
          Category: "android.intent.category.DEFAULT"
      android.settings.WIFI_SETTINGS:
        e71069e com.android.settings/.Settings$WifiSettingsActivity filter 258257f
          Action: "android.settings.WIFI_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.bluetooth.adapter.action.REQUEST_DISCOVERABLE:
        4bfd07c com.android.settings/.bluetooth.RequestPermissionActivity filter 319bd05
          Action: "android.bluetooth.adapter.action.REQUEST_DISCOVERABLE"
          Action: "android.bluetooth.adapter.action.REQUEST_ENABLE"
          Action: "android.bluetooth.adapter.action.REQUEST_DISABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.APP_NOTIFICATION_SETTINGS:
        39baa22 com.android.settings/.Settings$AppNotificationSettingsActivity filter f69fcb3
          Action: "android.settings.APP_NOTIFICATION_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.AIRPLANE_MODE_SETTINGS:
        3dd7a8f com.android.settings/.Settings$NetworkDashboardActivity filter a3ef11c
          Action: "android.settings.WIRELESS_SETTINGS"
          Action: "android.settings.AIRPLANE_MODE_SETTINGS"
          Action: "com.android.settings.sim.SIM_SUB_INFO_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.MANAGE_UNKNOWN_APP_SOURCES:
        97bd093 com.android.settings/.Settings$ManageExternalSourcesActivity filter 7f6c8d0
          Action: "android.settings.MANAGE_UNKNOWN_APP_SOURCES"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.panel.action.INTERNET_CONNECTIVITY:
        b5d7448 com.android.settings/.panel.SettingsPanelActivity filter 7e8a2e1
          Action: "android.settings.panel.action.INTERNET_CONNECTIVITY"
          Category: "android.intent.category.DEFAULT"
      android.settings.MODULE_LICENSES:
        272d9a3 com.android.settings/.Settings$ModuleLicensesActivity filter 4884a0
          Action: "android.settings.MODULE_LICENSES"
          Category: "android.intent.category.DEFAULT"
      android.settings.SOUND_SETTINGS:
        416a13b com.android.settings/.Settings$SoundSettingsActivity filter 164d058
          Action: "com.android.settings.SOUND_SETTINGS"
          Action: "android.settings.SOUND_SETTINGS"
          Action: "android.settings.ACTION_OTHER_SOUND_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.VOICE_CONTROL_DO_NOT_DISTURB_MODE:
        6b57432 com.android.settings/.notification.zen.ZenModeVoiceActivity filter 555e583
          Action: "android.settings.VOICE_CONTROL_DO_NOT_DISTURB_MODE"
          Category: "android.intent.category.DEFAULT"
          Category: "android.intent.category.VOICE"
      android.settings.VOICE_INPUT_SETTINGS:
        284b20c com.android.settings/.Settings$ManageAssistActivity filter 207a755
          Action: "android.settings.VOICE_INPUT_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.MANAGE_DOMAIN_URLS:
        c14acc com.android.settings/.Settings$ManageDomainUrlsActivity filter cdf3115
          Action: "android.settings.MANAGE_DOMAIN_URLS"
          Category: "android.intent.category.DEFAULT"
      android.settings.APP_MEMORY_USAGE:
        73a7c2a com.android.settings/.Settings$AppMemoryUsageActivity filter 837da1b
          Action: "android.settings.APP_MEMORY_USAGE"
          Category: "android.intent.category.DEFAULT"
      android.settings.action.MANAGE_OVERLAY_PERMISSION:
        22f271e com.android.settings/.Settings$OverlaySettingsActivity filter b32fbff
          Action: "android.settings.action.MANAGE_OVERLAY_PERMISSION"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.WIFI_SAVED_NETWORK_SETTINGS:
        f869c50 com.android.settings/.Settings$SavedAccessPointsSettingsActivity filter 5d11e49
          Action: "android.settings.WIFI_SAVED_NETWORK_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.VOICE_CONTROL_AIRPLANE_MODE:
        c21c752 com.android.settings/.AirplaneModeVoiceActivity filter 890a23
          Action: "android.settings.VOICE_CONTROL_AIRPLANE_MODE"
          Category: "android.intent.category.DEFAULT"
          Category: "android.intent.category.VOICE"
      com.google.android.settings.fuelgauge.REVERSE_CHARGING_TOOL_SETTINGS:
        5e74bf0 com.android.settings/com.google.android.settings.fuelgauge.reversecharging.ReverseChargingToolTrampoline filter 83ea569
          Action: "com.google.android.settings.fuelgauge.REVERSE_CHARGING_TOOL_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.DATA_ROAMING_SETTINGS:
        6fd2fa com.android.settings/.Settings$MobileNetworkActivity filter 94130ab
          Action: "android.intent.action.MAIN"
          Action: "android.telephony.ims.action.SHOW_CAPABILITY_DISCOVERY_OPT_IN"
          Action: "android.settings.NETWORK_OPERATOR_SETTINGS"
          Action: "android.settings.DATA_ROAMING_SETTINGS"
          Action: "android.settings.MMS_MESSAGE_SETTING"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      com.google.android.settings.gestures.QUICK_TAP_SETTINGS:
        5cfcbf9 com.android.settings/com.google.android.settings.gestures.columbus.ColumbusSettingsActivity filter 535e73e
          Action: "com.google.android.settings.gestures.QUICK_TAP_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.NFCSHARING_SETTINGS:
        b9e91b2 com.android.settings/.Settings$AndroidBeamSettingsActivity filter 4947503
          Action: "android.settings.NFCSHARING_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.ZEN_MODE_SCHEDULE_RULE_SETTINGS:
        119f31f com.android.settings/.Settings$ZenModeScheduleRuleSettingsActivity filter 91a266c
          Action: "android.settings.ZEN_MODE_SCHEDULE_RULE_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.MANAGE_CROSS_PROFILE_ACCESS:
        cdec81a com.android.settings/.Settings$InteractAcrossProfilesSettingsActivity filter 9ef4f4b
          Action: "android.settings.MANAGE_CROSS_PROFILE_ACCESS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.NIGHT_DISPLAY_SETTINGS:
        1c4af22 com.android.settings/.Settings$NightDisplaySettingsActivity filter 6665f70
          Action: "android.settings.NIGHT_DISPLAY_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      com.google.android.settings.ASSIST_GESTURE_TRAINING:
        c8d25c1 com.android.settings/com.google.android.settings.gestures.assist.AssistGestureTrainingIntroActivity filter de01166
          Action: "com.google.android.settings.ASSIST_GESTURE_TRAINING"
          Category: "android.intent.category.DEFAULT"
      android.settings.ACCESSIBILITY_SETTINGS_FOR_SUW:
        d042f8d com.android.settings/.accessibility.AccessibilitySettingsForSetupWizardActivity filter 5536542
          Action: "android.settings.ACCESSIBILITY_SETTINGS_FOR_SUW"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.ACTION_POWER_MENU_SETTINGS:
        57a7f78 com.android.settings/.Settings$PowerMenuSettingsActivity filter 6cf0651
          Action: "android.settings.ACTION_POWER_MENU_SETTINGS"
          Category: "android.intent.category.DEFAULT"
      android.app.action.CONFIRM_DEVICE_CREDENTIAL:
        3b4fc3e com.android.settings/.password.ConfirmDeviceCredentialActivity filter ede7a9f
          Action: "android.app.action.CONFIRM_DEVICE_CREDENTIAL"
          Action: "android.app.action.CONFIRM_FRP_CREDENTIAL"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.NOTIFICATION_SETTINGS:
        a964072 com.android.settings/.Settings$ConfigureNotificationSettingsActivity filter 3c85cc3
          Action: "android.settings.NOTIFICATION_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.DATA_USAGE_SETTINGS:
        9b5bf6b com.android.settings/.Settings$DataUsageSummaryActivity filter a774ac8
          Action: "android.settings.DATA_USAGE_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.DREAM_SETTINGS:
        71a4b74 com.android.settings/.Settings$DreamSettingsActivity filter 8e7a89d
          Action: "android.settings.DREAM_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      com.android.settings.wifi.action.NETWORK_REQUEST:
        f24b546 com.android.settings/.wifi.NetworkRequestDialogActivity filter c00b307
          Action: "com.android.settings.wifi.action.NETWORK_REQUEST"
          Category: "android.intent.category.DEFAULT"
      android.settings.action.MANAGE_WRITE_SETTINGS:
        9c5591b com.android.settings/.Settings$WriteSettingsActivity filter f5ab8
          Action: "android.settings.action.MANAGE_WRITE_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.WIFI_DETAILS_SETTINGS:
        bd39a9b com.android.settings/.Settings$WifiDetailsSettingsActivity filter 1163e38
          Action: "android.settings.WIFI_DETAILS_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.REVERSE_CHARGING_BOTTOM_SHEET:
        5b3a7a2 com.android.settings/com.google.android.settings.fuelgauge.reversecharging.BottomSheetActivity filter 3ddec33
          Action: "android.settings.REVERSE_CHARGING_BOTTOM_SHEET"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.bluetooth.adapter.action.REQUEST_DISABLE:
        4bfd07c com.android.settings/.bluetooth.RequestPermissionActivity filter 319bd05
          Action: "android.bluetooth.adapter.action.REQUEST_DISCOVERABLE"
          Action: "android.bluetooth.adapter.action.REQUEST_ENABLE"
          Action: "android.bluetooth.adapter.action.REQUEST_DISABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.INPUT_METHOD_SUBTYPE_SETTINGS:
        4025e36 com.android.settings/.inputmethod.InputMethodAndSubtypeEnablerActivity filter 17ac137
          Action: "android.settings.INPUT_METHOD_SUBTYPE_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.CAST_SETTINGS:
        22eec80 com.android.settings/.Settings$WifiDisplaySettingsActivity filter 509e2b9
          Action: "android.settings.CAST_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      com.android.settings.ACCESSIBILITY_COLOR_SPACE_SETTINGS:
        b8647af com.android.settings/.Settings$AccessibilityDaltonizerSettingsActivity filter 25e07bc
          Action: "com.android.settings.ACCESSIBILITY_COLOR_SPACE_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.panel.action.VOLUME:
        b5d7448 com.android.settings/.panel.SettingsPanelActivity filter df98cf4
          Action: "android.settings.panel.action.VOLUME"
          Category: "android.intent.category.DEFAULT"
      com.android.settings.APPLICATION_DEVELOPMENT_SETTINGS:
        1eebc4c com.android.settings/.Settings$DevelopmentSettingsDashboardActivity filter ecd8495
          Action: "android.settings.APPLICATION_DEVELOPMENT_SETTINGS"
          Action: "com.android.settings.APPLICATION_DEVELOPMENT_SETTINGS"
          Action: "android.service.quicksettings.action.QS_TILE_PREFERENCES"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
        833199b com.android.settings/.development.DevelopmentSettingsDisabledActivity filter 8715138
          Action: "android.settings.APPLICATION_DEVELOPMENT_SETTINGS"
          Action: "com.android.settings.APPLICATION_DEVELOPMENT_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=-1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      com.android.settings.WIFI_DIALOG:
        158ff88 com.android.settings/.wifi.WifiDialogActivity filter bf06d21
          Action: "com.android.settings.WIFI_DIALOG"
          Category: "android.intent.category.DEFAULT"
      com.android.settings.BATTERY_SAVER_SCHEDULE_SETTINGS:
        3d87dea com.android.settings/.Settings$BatterySaverScheduleSettingsActivity filter 68718db
          Action: "com.android.settings.BATTERY_SAVER_SCHEDULE_SETTINGS"
          Category: "android.intent.category.DEFAULT"
      android.settings.ACTION_PRINT_SETTINGS:
        84ed511 com.android.settings/.Settings$PrintSettingsActivity filter aa21676
          Action: "android.settings.ACTION_PRINT_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.WIFI_DPP_CONFIGURATOR_QR_CODE_SCANNER:
        f1c0063 com.android.settings/.wifi.dpp.WifiDppConfiguratorActivity filter 69c8460
          Action: "android.settings.WIFI_DPP_CONFIGURATOR_QR_CODE_SCANNER"
          Action: "android.settings.WIFI_DPP_CONFIGURATOR_QR_CODE_GENERATOR"
          Category: "android.intent.category.DEFAULT"
      android.settings.REDUCE_BRIGHT_COLORS_SETTINGS:
        a0c5a9a com.android.settings/.Settings$ReduceBrightColorsSettingsActivity filter 7f9afcb
          Action: "android.settings.REDUCE_BRIGHT_COLORS_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.INPUT_METHOD_SETTINGS:
        75d815e com.android.settings/.Settings$AvailableVirtualKeyboardActivity filter ceee93f
          Action: "android.settings.INPUT_METHOD_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      com.android.settings.DISPLAY_SETTINGS:
        8b93d58 com.android.settings/.Settings$DisplaySettingsActivity filter 1a01eb1
          Action: "com.android.settings.DISPLAY_SETTINGS"
          Action: "android.settings.DISPLAY_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.LOCALE_SETTINGS:
        e593847 com.android.settings/.Settings$LocalePickerActivity filter 90cc874
          Action: "android.settings.LOCALE_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.app.action.SET_NEW_PASSWORD:
        1252dfa com.android.settings/.password.SetNewPasswordActivity filter a32efab
          Action: "android.app.action.SET_NEW_PASSWORD"
          Action: "android.app.action.SET_NEW_PARENT_PROFILE_PASSWORD"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.appwidget.action.APPWIDGET_BIND:
        dd650ac com.android.settings/.AllowBindAppWidgetActivity filter 1dcf175
          Action: "android.appwidget.action.APPWIDGET_BIND"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.appwidget.action.APPWIDGET_PICK:
        c6016fe com.android.settings/.AppWidgetPickActivity filter 25f5e5f
          Action: "android.appwidget.action.APPWIDGET_PICK"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.net.action.PROMPT_LOST_VALIDATION:
        6097e26 com.android.settings/.wifi.WifiNoInternetDialog filter 3afb014
          Action: "android.net.action.PROMPT_LOST_VALIDATION"
          Category: "android.intent.category.DEFAULT"
      android.settings.IGNORE_BATTERY_OPTIMIZATION_SETTINGS:
        1e47b8 com.android.settings/.Settings$HighPowerApplicationsActivity filter 70ec991
          Action: "android.settings.IGNORE_BATTERY_OPTIMIZATION_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.TETHER_PROVISIONING_UI:
        34d3898 com.android.settings/.network.TetherProvisioningActivity filter caf98f1
          Action: "android.settings.TETHER_PROVISIONING_UI"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.WARRANTY:
        d2688fa com.android.settings/com.google.android.settings.warranty.WarrantyActivity filter 280aeab
          Action: "android.settings.WARRANTY"
          Category: "android.intent.category.DEFAULT"
      android.settings.ADAPTIVE_BRIGHTNESS_SETTINGS:
        2c74577 com.android.settings/.Settings$AdaptiveBrightnessActivity filter 70d05e4
          Action: "android.settings.ADAPTIVE_BRIGHTNESS_SETTINGS"
          Category: "android.intent.category.DEFAULT"
      com.google.android.settings.notification.CLEAR_CALLING:
        9ff4db4 com.android.settings/com.google.android.settings.notification.ClearCallingSettingsActivity filter 8991ddd
          Action: "com.google.android.settings.notification.CLEAR_CALLING"
          Category: "android.intent.category.DEFAULT"
      android.settings.BLUETOOTH_LE_AUDIO_QR_CODE_SCANNER:
        3beecb com.android.settings/.bluetooth.QrCodeScanModeActivity filter 848b6a8
          Action: "android.settings.BLUETOOTH_LE_AUDIO_QR_CODE_SCANNER"
          Category: "android.intent.category.DEFAULT"
      android.settings.APN_SETTINGS:
        cec40bd com.android.settings/.Settings$ApnSettingsActivity filter b7f56b2
          Action: "android.settings.APN_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      com.android.settings.action.IA_SETTINGS:
        d0a0483 com.android.settings/.backup.UserBackupSettingsActivity filter 494be39
          Action: "com.android.settings.action.IA_SETTINGS"
      android.security.MANAGE_CREDENTIALS:
        5fb0d06 com.android.settings/.security.RequestManageCredentials filter 2808fc7
          Action: "android.security.MANAGE_CREDENTIALS"
          Category: "android.intent.category.DEFAULT"
      android.settings.PRIVACY_CONTROLS:
        8c8b73a com.android.settings/.Settings$PrivacyControlsActivity filter 625dfeb
          Action: "android.settings.PRIVACY_CONTROLS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.app.action.CONFIRM_DEVICE_CREDENTIAL_WITH_USER:
        410d7ec com.android.settings/.password.ConfirmDeviceCredentialActivity$InternalActivity filter 97e07b5
          Action: "android.app.action.CONFIRM_DEVICE_CREDENTIAL_WITH_USER"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      com.android.settings.SEARCH_RESULT_TRAMPOLINE:
        5822b20 com.android.settings/.search.SearchResultTrampoline filter c504cd9
          Action: "com.android.settings.SEARCH_RESULT_TRAMPOLINE"
          Category: "android.intent.category.DEFAULT"
      com.android.settings.SOUND_SETTINGS:
        416a13b com.android.settings/.Settings$SoundSettingsActivity filter 164d058
          Action: "com.android.settings.SOUND_SETTINGS"
          Action: "android.settings.SOUND_SETTINGS"
          Action: "android.settings.ACTION_OTHER_SOUND_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.CAPTIONING_SETTINGS:
        5459254 com.android.settings/.Settings$CaptioningSettingsActivity filter 22d15fd
          Action: "android.settings.CAPTIONING_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.ZEN_MODE_EVENT_RULE_SETTINGS:
        30ad0ca com.android.settings/.Settings$ZenModeEventRuleSettingsActivity filter d74a23b
          Action: "android.settings.ZEN_MODE_EVENT_RULE_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.FACE_SETTINGS:
        a082bfe com.android.settings/.Settings$FaceSettingsActivity filter 7564f5f
          Action: "android.settings.FACE_SETTINGS"
          Category: "android.intent.category.DEFAULT"
      android.intent.action.CREATE_SHORTCUT:
        397b769 com.android.settings/.Settings$CreateShortcutActivity filter 5b145ee
          Action: "android.intent.action.CREATE_SHORTCUT"
          Category: "android.intent.category.DEFAULT"
      android.settings.CHANNEL_NOTIFICATION_SETTINGS:
        915270 com.android.settings/.notification.app.ChannelPanelActivity filter 79e69e9
          Action: "android.settings.CHANNEL_NOTIFICATION_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.ACTION_CONDITION_PROVIDER_SETTINGS:
        1486627 com.android.settings/.Settings$ZenModeAutomationSettingsActivity filter aaf727d
          Action: "android.settings.ACTION_CONDITION_PROVIDER_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.FINGERPRINT_ENROLL:
        ef6aca2 com.android.settings/.biometrics.fingerprint.FingerprintEnrollIntroduction filter eed0d33
          Action: "android.settings.FINGERPRINT_ENROLL"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
      android.settings.DEVICE_NAME:
        a61007a com.android.settings/.Settings$MyDeviceInfoActivity filter 1ce902b
          Action: "android.settings.DEVICE_INFO_SETTINGS"
          Action: "android.settings.DEVICE_NAME"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.MANAGE_ALL_SIM_PROFILES_SETTINGS:
        cd80308 com.android.settings/.Settings$MobileNetworkListActivity filter 915eaa1
          Action: "android.settings.MOBILE_NETWORK_LIST"
          Action: "android.settings.MANAGE_ALL_SIM_PROFILES_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.bluetooth.devicepicker.action.LAUNCH:
        ab70a0a com.android.settings/.bluetooth.DevicePickerActivity filter 2ba827b
          Action: "android.bluetooth.devicepicker.action.LAUNCH"
          Category: "android.intent.category.DEFAULT"
      android.settings.ACCESSIBILITY_DETAILS_SETTINGS:
        fe6f8b7 com.android.settings/.Settings$AccessibilityDetailsSettingsActivity filter 9a9d824
          Action: "android.settings.ACCESSIBILITY_DETAILS_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.DATE_SETTINGS:
        f4bf7c8 com.android.settings/.Settings$DateTimeSettingsActivity filter 587a061
          Action: "android.settings.DATE_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.panel.action.WIFI:
        b5d7448 com.android.settings/.panel.SettingsPanelActivity filter 8a43ec7
          Action: "android.settings.panel.action.WIFI"
          Category: "android.intent.category.DEFAULT"
      com.android.settings.BUTTON_NAVIGATION_SETTINGS:
        22cb68d com.android.settings/.Settings$ButtonNavigationSettingsActivity filter d3dc853
          Action: "com.android.settings.BUTTON_NAVIGATION_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.app.action.SET_NEW_PARENT_PROFILE_PASSWORD:
        1252dfa com.android.settings/.password.SetNewPasswordActivity filter a32efab
          Action: "android.app.action.SET_NEW_PASSWORD"
          Action: "android.app.action.SET_NEW_PARENT_PROFILE_PASSWORD"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.VOICE_CONTROL_BATTERY_SAVER_MODE:
        deeda2d com.android.settings/.fuelgauge.BatterySaverModeVoiceActivity filter facb62
          Action: "android.settings.VOICE_CONTROL_BATTERY_SAVER_MODE"
          Category: "android.intent.category.DEFAULT"
          Category: "android.intent.category.VOICE"
      android.settings.WIFI_DPP_ENROLLEE_QR_CODE_SCANNER:
        67021de com.android.settings/.wifi.dpp.WifiDppEnrolleeActivity filter 7c43fbf
          Action: "android.settings.WIFI_DPP_ENROLLEE_QR_CODE_SCANNER"
          Category: "android.intent.category.DEFAULT"
      android.settings.BATTERY_SAVER_SETTINGS:
        7a0ba57 com.android.settings/.Settings$BatterySaverSettingsActivity filter e800944
          Action: "android.settings.BATTERY_SAVER_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.PICTURE_IN_PICTURE_SETTINGS:
        c0ba2c2 com.android.settings/.Settings$PictureInPictureSettingsActivity filter 9798d3
          Action: "android.settings.PICTURE_IN_PICTURE_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.ACTION_MEDIA_CONTROLS_SETTINGS:
        989c590 com.android.settings/.Settings$MediaControlsSettingsActivity filter 73b2e89
          Action: "android.settings.ACTION_MEDIA_CONTROLS_SETTINGS"
          Category: "android.intent.category.DEFAULT"
      android.settings.NFC_SETTINGS:
        3451473 com.android.settings/.Settings$AdvancedConnectedDeviceActivity filter 496ef30
          Action: "android.settings.NFC_SETTINGS"
          Category: "android.intent.category.BROWSABLE"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.STORAGE_MANAGER_SETTINGS:
        e608c7e com.android.settings/.Settings$AutomaticStorageManagerSettingsActivity filter 15e65df
          Action: "android.settings.STORAGE_MANAGER_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false
      android.settings.APP_NOTIFICATION_BUBBLE_SETTINGS:
        34a021f com.android.settings/.Settings$AppBubbleNotificationSettingsActivity filter 622896c
          Action: "android.settings.APP_NOTIFICATION_BUBBLE_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          mPriority=1, mOrder=0, mHasStaticPartialTypes=false, mHasDynamicPartialTypes=false

  MIME Typed Actions:
      android.intent.action.EDIT:
        5d183d9 com.android.settings/.Settings$ApnEditorActivity filter 337719e
          Action: "android.intent.action.VIEW"
          Action: "android.intent.action.EDIT"
          Category: "android.intent.category.DEFAULT"
          StaticType: "vnd.android.cursor.item/telephony-carrier"
      android.intent.action.VIEW:
        5d183d9 com.android.settings/.Settings$ApnEditorActivity filter 337719e
          Action: "android.intent.action.VIEW"
          Action: "android.intent.action.EDIT"
          Category: "android.intent.category.DEFAULT"
          StaticType: "vnd.android.cursor.item/telephony-carrier"
      android.provider.action.DOCUMENT_ROOT_SETTINGS:
        813a923 com.android.settings/.Settings$PublicVolumeSettingsActivity filter 1f9de20
          Action: "android.provider.action.DOCUMENT_ROOT_SETTINGS"
          Category: "android.intent.category.DEFAULT"
          Scheme: "content"
          Authority: "com.android.externalstorage.documents": -1
          StaticType: "vnd.android.document/root"
      android.intent.action.INSERT:
        5d183d9 com.android.settings/.Settings$ApnEditorActivity filter 16db47f
          Action: "android.intent.action.INSERT"
          Category: "android.intent.category.DEFAULT"
          StaticType: "vnd.android.cursor.dir/telephony-carrier"

Receiver Resolver Table:
  Schemes:
      android_secret_code:
        4b324aa com.android.settings/.TestingSettingsBroadcastReceiver filter aee989b
          Action: "android.telephony.action.SECRET_CODE"
          Scheme: "android_secret_code"
          Authority: "4636": -1

  Non-Data Actions:
      android.telephony.action.PRIMARY_SUBSCRIPTION_LIST_CHANGED:
        5eb8be4 com.android.settings/.sim.SimSelectNotification filter 42384d
          Action: "android.telephony.action.PRIMARY_SUBSCRIPTION_LIST_CHANGED"
          Action: "android.settings.ENABLE_MMS_DATA_REQUEST"
      com.android.settings.SEARCH_START:
        21d9120 com.android.settings/.search.SearchStateReceiver filter 78ebad9
          Action: "com.android.settings.SEARCH_START"
          Action: "com.android.settings.SEARCH_EXIT"
      android.settings.ENABLE_MMS_DATA_REQUEST:
        5eb8be4 com.android.settings/.sim.SimSelectNotification filter 42384d
          Action: "android.telephony.action.PRIMARY_SUBSCRIPTION_LIST_CHANGED"
          Action: "android.settings.ENABLE_MMS_DATA_REQUEST"
      settings.intelligence.battery.action.FETCH_BATTERY_USAGE_DATA:
        23bb614 com.android.settings/com.google.android.settings.fuelgauge.BatteryBroadcastReceiver filter c5ecebd
          Action: "settings.intelligence.battery.action.FETCH_BATTERY_USAGE_DATA"
          Action: "settings.intelligence.battery.action.FETCH_BLUETOOTH_BATTERY_DATA"
          Action: "settings.intelligence.battery.action.CLEAR_BATTERY_CACHE_DATA"
      android.bluetooth.device.action.CONNECTION_ACCESS_CANCEL:
        c1a9f4c com.android.settings/.bluetooth.BluetoothPermissionRequest filter 4a72b95
          Action: "android.bluetooth.device.action.CONNECTION_ACCESS_REQUEST"
          Action: "android.bluetooth.device.action.CONNECTION_ACCESS_CANCEL"
      android.bluetooth.device.action.CONNECTION_ACCESS_REQUEST:
        c1a9f4c com.android.settings/.bluetooth.BluetoothPermissionRequest filter 4a72b95
          Action: "android.bluetooth.device.action.CONNECTION_ACCESS_REQUEST"
          Action: "android.bluetooth.device.action.CONNECTION_ACCESS_CANCEL"
      android.net.wifi.wsu.action.WSU_POST_PROVISIONING:
        a89ccb2 com.android.settings/com.google.android.wifitrackerlib.WsuPostProvisioningReceiver filter cb69403
          Action: "android.net.wifi.wsu.action.WSU_POST_PROVISIONING"
      android.telephony.action.SIM_SLOT_STATUS_CHANGED:
        4b4a94e com.android.settings/.sim.receivers.SimSlotChangeReceiver filter cd60a6f
          Action: "android.telephony.action.SIM_SLOT_STATUS_CHANGED"
      com.google.android.settings.routines.RoutinesActionBroadcastReceiver.RINGER_MODE_SILENCE_ACTION:
        2389426 com.android.settings/com.google.android.settings.routines.RoutinesActionBroadcastReceiver filter a9ed867
          Action: "com.google.android.settings.routines.RoutinesActionBroadcastReceiver.RINGER_MODE_SILENCE_ACTION"
      android.intent.action.USER_INITIALIZE:
        6393d52 com.android.settings/.SettingsInitialize filter 67a4823
          Action: "android.intent.action.USER_INITIALIZE"
          Action: "android.intent.action.PRE_BOOT_COMPLETED"
      android.bluetooth.device.action.PAIRING_REQUEST:
        189dc9e com.android.settings/.bluetooth.BluetoothPairingRequest filter 91f437f
          Action: "android.bluetooth.device.action.PAIRING_REQUEST"
          Action: "android.bluetooth.action.CSIS_SET_MEMBER_AVAILABLE"
      android.provider.Contacts.PROFILE_CHANGED:
        d76e176 com.android.settings/.users.ProfileUpdateReceiver filter b942377
          Action: "android.provider.Contacts.PROFILE_CHANGED"
      settings.intelligence.battery.action.FETCH_BLUETOOTH_BATTERY_DATA:
        23bb614 com.android.settings/com.google.android.settings.fuelgauge.BatteryBroadcastReceiver filter c5ecebd
          Action: "settings.intelligence.battery.action.FETCH_BATTERY_USAGE_DATA"
          Action: "settings.intelligence.battery.action.FETCH_BLUETOOTH_BATTERY_DATA"
          Action: "settings.intelligence.battery.action.CLEAR_BATTERY_CACHE_DATA"
      com.google.android.setupwizard.SETUP_WIZARD_FINISHED:
        f2a737c com.android.settings/.sim.receivers.SuwFinishReceiver filter 22b2405
          Action: "com.google.android.setupwizard.SETUP_WIZARD_FINISHED"
      android.bluetooth.intent.DISCOVERABLE_TIMEOUT:
        cf86438 com.android.settings/com.android.settingslib.bluetooth.BluetoothDiscoverableTimeoutReceiver filter f9bec11
          Action: "android.bluetooth.intent.DISCOVERABLE_TIMEOUT"
      com.android.settings.SEARCH_EXIT:
        21d9120 com.android.settings/.search.SearchStateReceiver filter 78ebad9
          Action: "com.android.settings.SEARCH_START"
          Action: "com.android.settings.SEARCH_EXIT"
      settings.intelligence.battery.action.CLEAR_BATTERY_CACHE_DATA:
        23bb614 com.android.settings/com.google.android.settings.fuelgauge.BatteryBroadcastReceiver filter c5ecebd
          Action: "settings.intelligence.battery.action.FETCH_BATTERY_USAGE_DATA"
          Action: "settings.intelligence.battery.action.FETCH_BLUETOOTH_BATTERY_DATA"
          Action: "settings.intelligence.battery.action.CLEAR_BATTERY_CACHE_DATA"
      android.intent.action.PRE_BOOT_COMPLETED:
        6393d52 com.android.settings/.SettingsInitialize filter 67a4823
          Action: "android.intent.action.USER_INITIALIZE"
          Action: "android.intent.action.PRE_BOOT_COMPLETED"
      android.intent.action.BOOT_COMPLETED:
        1e79f02 com.android.settings/.fuelgauge.batterytip.AnomalyConfigReceiver filter f9d8013
          Action: "android.app.action.STATSD_STARTED"
          Action: "android.intent.action.BOOT_COMPLETED"
        2360c5a com.android.settings/.sim.receivers.SimCompleteBootReceiver filter 62de8b
          Action: "android.intent.action.BOOT_COMPLETED"
        4694b68 com.android.settings/.safetycenter.SafetySourceBroadcastReceiver filter 3efb81
          Action: "android.safetycenter.action.REFRESH_SAFETY_SOURCES"
          Action: "android.intent.action.BOOT_COMPLETED"
      android.bluetooth.action.CSIS_SET_MEMBER_AVAILABLE:
        189dc9e com.android.settings/.bluetooth.BluetoothPairingRequest filter 91f437f
          Action: "android.bluetooth.device.action.PAIRING_REQUEST"
          Action: "android.bluetooth.action.CSIS_SET_MEMBER_AVAILABLE"
      com.android.settings.action.LAUNCH_BLUETOOTH_PAIRING:
        4c78250 com.android.settings/.media.BluetoothPairingReceiver filter c870c49
          Action: "com.android.settings.action.LAUNCH_BLUETOOTH_PAIRING"
      android.app.action.STATSD_STARTED:
        1e79f02 com.android.settings/.fuelgauge.batterytip.AnomalyConfigReceiver filter f9d8013
          Action: "android.app.action.STATSD_STARTED"
          Action: "android.intent.action.BOOT_COMPLETED"
      android.safetycenter.action.REFRESH_SAFETY_SOURCES:
        4694b68 com.android.settings/.safetycenter.SafetySourceBroadcastReceiver filter 3efb81
          Action: "android.safetycenter.action.REFRESH_SAFETY_SOURCES"
          Action: "android.intent.action.BOOT_COMPLETED"

Service Resolver Table:
  Non-Data Actions:
      android.service.quicksettings.action.QS_TILE:
        5da400a com.android.settings/.development.qstile.DevelopmentTiles$ShowLayout filter f2c807b permission android.permission.BIND_QUICK_SETTINGS_TILE
          Action: "android.service.quicksettings.action.QS_TILE"
        f3a5e98 com.android.settings/.development.qstile.DevelopmentTiles$GPUProfiling filter 63cc6f1 permission android.permission.BIND_QUICK_SETTINGS_TILE
          Action: "android.service.quicksettings.action.QS_TILE"
        be452d6 com.android.settings/.development.qstile.DevelopmentTiles$ForceRTL filter 8f8a957 permission android.permission.BIND_QUICK_SETTINGS_TILE
          Action: "android.service.quicksettings.action.QS_TILE"
        5c2cc44 com.android.settings/.development.qstile.DevelopmentTiles$AnimationSpeed filter ec5e12d permission android.permission.BIND_QUICK_SETTINGS_TILE
          Action: "android.service.quicksettings.action.QS_TILE"
        aaac662 com.android.settings/.development.qstile.DevelopmentTiles$WinscopeTrace filter 4f483f3 permission android.permission.BIND_QUICK_SETTINGS_TILE
          Action: "android.service.quicksettings.action.QS_TILE"
        d4268b0 com.android.settings/.development.qstile.DevelopmentTiles$SensorsOff filter 94c6329 permission android.permission.BIND_QUICK_SETTINGS_TILE
          Action: "android.service.quicksettings.action.QS_TILE"
        672e6ae com.android.settings/.development.qstile.DevelopmentTiles$WirelessDebugging filter 9c96c4f permission android.permission.BIND_QUICK_SETTINGS_TILE
          Action: "android.service.quicksettings.action.QS_TILE"
        ddd5fdc com.android.settings/.development.qstile.DevelopmentTiles$ShowTaps filter a9f08e5 permission android.permission.BIND_QUICK_SETTINGS_TILE
          Action: "android.service.quicksettings.action.QS_TILE"
        8abfba com.android.settings/.development.qstile.DevelopmentTiles$DesktopMode filter 55a7e6b permission android.permission.BIND_QUICK_SETTINGS_TILE
          Action: "android.service.quicksettings.action.QS_TILE"

Provider Resolver Table:
  Non-Data Actions:
      android.content.action.SETTINGS_HOMEPAGE_DATA:
        5afb3ac com.android.settings/.homepage.contextualcards.SettingsContextualCardProvider filter 7961875
          Action: "android.content.action.SETTINGS_HOMEPAGE_DATA"
      com.android.settings.action.SUGGESTION_STATE_PROVIDER:
        e4401fe com.android.settings/.dashboard.suggestions.SuggestionStateProvider filter 4046d5f
          Action: "com.android.settings.action.SUGGESTION_STATE_PROVIDER"
      android.content.action.SEARCH_INDEXABLES_PROVIDER:
        8281f80 com.android.settings/.search.SettingsSearchIndexablesProvider filter fae99b9
          Action: "android.content.action.SEARCH_INDEXABLES_PROVIDER"

Domain verification status:

Permissions:
  Permission [com.google.android.settings.future.logging.RESTRICTED_SEND_FUTURE_LOGS] (4abed72):
    sourcePackage=com.android.settings
    uid=1000 gids=[] type=0 prot=signature|privileged
    perm=PermissionInfo{7b905c3 com.google.android.settings.future.logging.RESTRICTED_SEND_FUTURE_LOGS}

Permissions:
  Permission [com.google.android.settings.setup.dock.RUN_DOCK_SETUP] (15b0e40):
    sourcePackage=com.android.settings
    uid=1000 gids=[] type=0 prot=signature|privileged
    perm=PermissionInfo{79cc179 com.google.android.settings.setup.dock.RUN_DOCK_SETUP}

Permissions:
  Permission [com.android.settings.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION] (d476ebe):
    sourcePackage=com.android.settings
    uid=1000 gids=[] type=0 prot=signature
    perm=PermissionInfo{1c3b1f com.android.settings.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION}

Permissions:
  Permission [com.google.android.settings.routines.ROUTINES_ACTIONS] (f02ce6c):
    sourcePackage=com.android.settings
    uid=1000 gids=[] type=0 prot=signature|privileged
    perm=PermissionInfo{29efc35 com.google.android.settings.routines.ROUTINES_ACTIONS}

Registered ContentProviders:
  com.android.settings/.homepage.contextualcards.SettingsContextualCardProvider:
    Provider{5afb3ac com.android.settings/.homepage.contextualcards.SettingsContextualCardProvider}
  com.android.settings/.emergency.EmergencyActionContentProvider:
    Provider{487b8ca com.android.settings/.emergency.EmergencyActionContentProvider}
  com.android.settings/.dashboard.SummaryProvider:
    Provider{e536a3b com.android.settings/.dashboard.SummaryProvider}
  com.android.settings/.slices.SettingsSliceProvider:
    Provider{8846558 com.android.settings/.slices.SettingsSliceProvider}
  com.android.settings/.dashboard.suggestions.SuggestionStateProvider:
    Provider{e4401fe com.android.settings/.dashboard.suggestions.SuggestionStateProvider}
  com.android.settings/.deviceinfo.legal.ModuleLicenseProvider:
    Provider{15026b1 com.android.settings/.deviceinfo.legal.ModuleLicenseProvider}
  com.android.settings/androidx.startup.InitializationProvider:
    Provider{8d09796 com.android.settings/androidx.startup.InitializationProvider}
  com.android.settings/com.google.android.settings.external.ExternalSettingsProvider:
    Provider{3046f17 com.android.settings/com.google.android.settings.external.ExternalSettingsProvider}
  com.android.settings/.search.SettingsSearchIndexablesProvider:
    Provider{8281f80 com.android.settings/.search.SettingsSearchIndexablesProvider}
  com.android.settings/androidx.core.content.FileProvider:
    Provider{5867f04 com.android.settings/androidx.core.content.FileProvider}
  com.android.settings/.homepage.contextualcards.CardContentProvider:
    Provider{60f7ced com.android.settings/.homepage.contextualcards.CardContentProvider}
  com.android.settings/com.google.android.settings.fuelgauge.BatteryUsageContentProvider:
    Provider{8f69722 com.android.settings/com.google.android.settings.fuelgauge.BatteryUsageContentProvider}

ContentProvider Authorities:
  [com.android.settings.module_licenses]:
    Provider{15026b1 com.android.settings/.deviceinfo.legal.ModuleLicenseProvider}
      applicationInfo=ApplicationInfo{956e5b3 com.android.settings}
  [android.settings.slices]:
    Provider{8846558 com.android.settings/.slices.SettingsSliceProvider}
      applicationInfo=ApplicationInfo{f6e8770 com.android.settings}
  [com.android.settings.homepage.CardContentProvider]:
    Provider{60f7ced com.android.settings/.homepage.contextualcards.CardContentProvider}
      applicationInfo=ApplicationInfo{ff3fae9 com.android.settings}
  [com.android.settings.files]:
    Provider{5867f04 com.android.settings/androidx.core.content.FileProvider}
      applicationInfo=ApplicationInfo{a8b036e com.android.settings}
  [com.android.settings.slices]:
    Provider{8846558 com.android.settings/.slices.SettingsSliceProvider}
      applicationInfo=ApplicationInfo{d502a0f com.android.settings}
  [com.android.settings.androidx-startup]:
    Provider{8d09796 com.android.settings/androidx.startup.InitializationProvider}
      applicationInfo=ApplicationInfo{e8caa9c com.android.settings}
  [com.android.settings.homepage.contextualcards]:
    Provider{5afb3ac com.android.settings/.homepage.contextualcards.SettingsContextualCardProvider}
      applicationInfo=ApplicationInfo{e885ca5 com.android.settings}
  [com.google.android.settings.external]:
    Provider{3046f17 com.android.settings/com.google.android.settings.external.ExternalSettingsProvider}
      applicationInfo=ApplicationInfo{8e7e87a com.android.settings}
  [com.android.settings]:
    Provider{8281f80 com.android.settings/.search.SettingsSearchIndexablesProvider}
      applicationInfo=ApplicationInfo{bef582b com.android.settings}
  [com.android.settings.dashboard.SummaryProvider]:
    Provider{e536a3b com.android.settings/.dashboard.SummaryProvider}
      applicationInfo=ApplicationInfo{e07d488 com.android.settings}
  [com.android.settings.suggestions.status]:
    Provider{e4401fe com.android.settings/.dashboard.suggestions.SuggestionStateProvider}
      applicationInfo=ApplicationInfo{5471e21 com.android.settings}
  [com.android.settings.emergency]:
    Provider{487b8ca com.android.settings/.emergency.EmergencyActionContentProvider}
      applicationInfo=ApplicationInfo{8fc1246 com.android.settings}
  [com.google.android.settings.fuelgauge.provider]:
    Provider{8f69722 com.android.settings/com.google.android.settings.fuelgauge.BatteryUsageContentProvider}
      applicationInfo=ApplicationInfo{9094c07 com.android.settings}

Key Set Manager:
  [com.android.settings]
      Signing KeySets: 2

Packages:
  Package [com.android.settings] (e1a75c5):
    userId=1000
    sharedUser=SharedUserSetting{289b134 android.uid.system/1000}
    pkg=Package{ad67b5d com.android.settings}
    codePath=/system_ext/priv-app/SettingsGoogle
    resourcePath=/system_ext/priv-app/SettingsGoogle
    legacyNativeLibraryDir=/system_ext/priv-app/SettingsGoogle/lib
    extractNativeLibs=true
    primaryCpuAbi=x86_64
    secondaryCpuAbi=null
    cpuAbiOverride=null
    versionCode=33 minSdk=33 targetSdk=33
    minExtensionVersions=[]
    versionName=13
    usesNonSdkApi=true
    splits=[base]
    apkSigningVersion=3
    flags=[ SYSTEM HAS_CODE ALLOW_CLEAR_USER_DATA ALLOW_BACKUP KILL_AFTER_RESTORE ]
    privateFlags=[ PRIVATE_FLAG_ACTIVITIES_RESIZE_MODE_RESIZEABLE_VIA_SDK_VERSION ALLOW_AUDIO_PLAYBACK_CAPTURE DEFAULT_TO_DEVICE_PROTECTED_STORAGE DIRECT_BOOT_AWARE PRIVILEGED SYSTEM_EXT PRIVATE_FLAG_ALLOW_NATIVE_HEAP_POINTER_TAGGING ]
    forceQueryable=false
    queriesIntents=[Intent { act=com.android.setupwizard.action.PARTNER_CUSTOMIZATION }]
    dataDir=/data/user_de/0/com.android.settings
    supportsScreens=[small, medium, large, xlarge, resizeable, anyDensity]
    usesLibraries:
      org.apache.http.legacy
    usesOptionalLibraries:
      androidx.window.extensions
      androidx.window.sidecar
    usesLibraryFiles:
      /system/framework/org.apache.http.legacy.jar
      /system_ext/framework/androidx.window.extensions.jar
      /system_ext/framework/androidx.window.sidecar.jar
    timeStamp=2024-09-09 23:06:33
    lastUpdateTime=2024-09-09 23:06:33
    packageSource=0
    signatures=PackageSignatures{dd70cd2 version:3, signatures:[b2d95fc0], past signatures:[]}
    installPermissionsFixed=false
    pkgFlags=[ SYSTEM HAS_CODE ALLOW_CLEAR_USER_DATA ALLOW_BACKUP KILL_AFTER_RESTORE ]
    declared permissions:
      com.google.android.settings.routines.ROUTINES_ACTIONS: prot=signature|privileged, INSTALLED
      com.google.android.settings.future.logging.RESTRICTED_SEND_FUTURE_LOGS: prot=signature|privileged, INSTALLED
      com.google.android.settings.setup.dock.RUN_DOCK_SETUP: prot=signature|privileged, INSTALLED
      com.android.settings.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION: prot=signature, INSTALLED
    requested permissions:
      android.permission.REQUEST_NETWORK_SCORES
      android.permission.WRITE_MEDIA_STORAGE
      android.permission.MANAGE_EXTERNAL_STORAGE
      android.permission.WRITE_EXTERNAL_STORAGE
      android.permission.READ_MEDIA_IMAGES
      android.permission.READ_MEDIA_VIDEO
      android.permission.READ_MEDIA_AUDIO
      android.permission.WRITE_SETTINGS
      android.permission.WRITE_SECURE_SETTINGS
      android.permission.DEVICE_POWER
      android.permission.CHANGE_CONFIGURATION
      android.permission.MOUNT_UNMOUNT_FILESYSTEMS
      android.permission.VIBRATE
      android.permission.BLUETOOTH_ADVERTISE
      android.permission.BLUETOOTH_CONNECT
      android.permission.BLUETOOTH_SCAN
      android.permission.BLUETOOTH_PRIVILEGED
      android.permission.NFC
      android.permission.HARDWARE_TEST
      android.permission.CALL_PHONE
      android.permission.MODIFY_AUDIO_SETTINGS
      android.permission.QUERY_AUDIO_STATE
      android.permission.MASTER_CLEAR
      com.google.android.googleapps.permission.GOOGLE_AUTH
      android.permission.ACCESS_DOWNLOAD_MANAGER
      android.permission.READ_CONTACTS
      android.permission.WRITE_CONTACTS
      android.permission.ACCESS_NETWORK_STATE
      android.permission.LOCAL_MAC_ADDRESS
      android.permission.ACCESS_WIFI_STATE
      com.android.certinstaller.INSTALL_AS_USER
      android.permission.CHANGE_WIFI_STATE
      android.permission.TETHER_PRIVILEGED
      android.permission.FOREGROUND_SERVICE
      android.permission.INTERNET
      android.permission.CLEAR_APP_USER_DATA
      android.permission.READ_PHONE_STATE
      android.permission.READ_PRIVILEGED_PHONE_STATE
      android.permission.MODIFY_PHONE_STATE
      android.permission.ACCESS_FINE_LOCATION
      android.permission.WRITE_APN_SETTINGS
      android.permission.ACCESS_CHECKIN_PROPERTIES
      android.permission.READ_USER_DICTIONARY
      android.permission.WRITE_USER_DICTIONARY
      android.permission.FORCE_STOP_PACKAGES
      android.permission.PACKAGE_USAGE_STATS
      android.permission.BATTERY_STATS
      com.android.launcher.permission.READ_SETTINGS
      com.android.launcher.permission.WRITE_SETTINGS
      android.permission.MOVE_PACKAGE
      android.permission.USE_CREDENTIALS
      android.permission.BACKUP
      android.permission.READ_SYNC_STATS
      android.permission.READ_SYNC_SETTINGS
      android.permission.WRITE_SYNC_SETTINGS
      android.permission.READ_DEVICE_CONFIG
      android.permission.STATUS_BAR
      android.permission.MANAGE_USB
      android.permission.MANAGE_DEBUGGING
      android.permission.SET_POINTER_SPEED
      android.permission.SET_KEYBOARD_LAYOUT
      android.permission.INTERACT_ACROSS_USERS_FULL
      android.permission.COPY_PROTECTED_DATA
      android.permission.MANAGE_USERS
      android.permission.MANAGE_PROFILE_AND_DEVICE_OWNERS
      android.permission.READ_PROFILE
      android.permission.CONFIGURE_WIFI_DISPLAY
      android.permission.CONFIGURE_DISPLAY_COLOR_MODE
      android.permission.CONTROL_DISPLAY_COLOR_TRANSFORMS
      android.permission.SUGGEST_MANUAL_TIME_AND_ZONE
      android.permission.ACCESS_NOTIFICATIONS
      android.permission.REBOOT
      android.permission.RECEIVE_BOOT_COMPLETED
      android.permission.MANAGE_DEVICE_ADMINS
      android.permission.READ_SEARCH_INDEXABLES
      android.permission.BIND_SETTINGS_SUGGESTIONS_SERVICE
      android.permission.OEM_UNLOCK_STATE
      android.permission.MANAGE_USER_OEM_UNLOCK_STATE
      android.permission.OVERRIDE_WIFI_CONFIG
      android.permission.RESTART_WIFI_SUBSYSTEM
      android.permission.MANAGE_FINGERPRINT
      android.permission.USE_BIOMETRIC
      android.permission.USE_BIOMETRIC_INTERNAL
      android.permission.USER_ACTIVITY
      android.permission.CHANGE_APP_IDLE_STATE
      android.permission.PEERS_MAC_ADDRESS
      android.permission.MANAGE_NOTIFICATIONS
      android.permission.DELETE_PACKAGES
      android.permission.REQUEST_DELETE_PACKAGES
      android.permission.MANAGE_APP_OPS_RESTRICTIONS
      android.permission.MANAGE_APP_OPS_MODES
      android.permission.HIDE_NON_SYSTEM_OVERLAY_WINDOWS
      android.permission.READ_PRINT_SERVICES
      android.permission.NETWORK_SETTINGS
      android.permission.TEST_BLACKLISTED_PASSWORD
      android.permission.USE_RESERVED_DISK
      android.permission.MANAGE_SCOPED_ACCESS_DIRECTORY_PERMISSIONS
      android.permission.CAMERA
      android.permission.MEDIA_CONTENT_CONTROL
      android.permission.INSTALL_DYNAMIC_SYSTEM
      android.permission.BIND_CELL_BROADCAST_SERVICE
      android.permission.SYSTEM_ALERT_WINDOW
      android.permission.READ_DREAM_STATE
      android.permission.READ_DREAM_SUPPRESSION
      android.permission.MANAGE_APP_HIBERNATION
      android.permission.LAUNCH_MULTI_PANE_SETTINGS_DEEP_LINK
      android.permission.ALLOW_PLACE_IN_MULTI_PANE_SETTINGS
      android.permission.POST_NOTIFICATIONS
      android.permission.READ_APP_SPECIFIC_LOCALES
      android.permission.QUERY_ADMIN_POLICY
      android.permission.READ_SAFETY_CENTER_STATUS
      android.permission.SEND_SAFETY_CENTER_UPDATE
      android.permission.START_VIEW_APP_FEATURES
      android.permission.CUSTOMIZE_SYSTEM_UI
      android.permission.MANAGE_GAME_MODE
      android.permission.WAKE_LOCK
      com.google.android.settings.routines.ROUTINES_ACTIONS
      com.google.android.settings.intelligence.BATTERY_DATA
      com.google.android.settings.setup.dock.RUN_DOCK_SETUP
      android.permission.MANAGE_ACTIVITY_TASKS
      android.permission.USE_FULL_SCREEN_INTENT
      android.permission.READ_EXTERNAL_STORAGE
      com.android.settings.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION
      android.permission.ACCESS_COARSE_LOCATION
    install permissions:
      android.permission.BIND_INCALL_SERVICE: granted=true
      android.permission.WRITE_SETTINGS: granted=true
      android.permission.CONFIGURE_WIFI_DISPLAY: granted=true
      android.permission.CONFIGURE_DISPLAY_COLOR_MODE: granted=true
      android.permission.CONTROL_DISPLAY_COLOR_TRANSFORMS: granted=true
      com.android.keychain.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION: granted=true
      android.permission.BIND_ATTENTION_SERVICE: granted=true
      android.permission.USE_CREDENTIALS: granted=true
      android.permission.MODIFY_AUDIO_SETTINGS: granted=true
      android.permission.MANAGE_EXTERNAL_STORAGE: granted=true
      android.permission.ACCESS_CHECKIN_PROPERTIES: granted=true
      android.permission.MODIFY_AUDIO_ROUTING: granted=true
      android.permission.READ_SAFETY_CENTER_STATUS: granted=true
      android.permission.QUERY_AUDIO_STATE: granted=true
      android.permission.INSTALL_LOCATION_PROVIDER: granted=true
      android.permission.USE_RESERVED_DISK: granted=true
      android.permission.SYSTEM_ALERT_WINDOW: granted=true
      android.permission.BROADCAST_PHONE_ACCOUNT_REGISTRATION: granted=true
      android.permission.CLEAR_APP_USER_DATA: granted=true
      android.permission.BROADCAST_CALLLOG_INFO: granted=true
      android.permission.NFC: granted=true
      android.permission.BIND_ROTATION_RESOLVER_SERVICE: granted=true
      android.permission.NETWORK_SETTINGS: granted=true
      android.permission.CALL_PRIVILEGED: granted=true
      android.permission.MASTER_CLEAR: granted=true
      android.permission.FOREGROUND_SERVICE: granted=true
      android.permission.WRITE_SYNC_SETTINGS: granted=true
      android.permission.ALLOW_PLACE_IN_MULTI_PANE_SETTINGS: granted=true
      android.permission.MANAGE_DYNAMIC_SYSTEM: granted=true
      android.permission.LAUNCH_MULTI_PANE_SETTINGS_DEEP_LINK: granted=true
      android.permission.MANAGE_ACTIVITY_TASKS: granted=true
      android.permission.RECEIVE_BOOT_COMPLETED: granted=true
      com.google.android.googleapps.permission.GOOGLE_AUTH: granted=true
      android.permission.MANAGE_ROLE_HOLDERS: granted=true
      android.permission.PEERS_MAC_ADDRESS: granted=true
      android.permission.DEVICE_POWER: granted=true
      android.permission.READ_PRINT_SERVICES: granted=true
      android.permission.MANAGE_PROFILE_AND_DEVICE_OWNERS: granted=true
      android.permission.RESTART_WIFI_SUBSYSTEM: granted=true
      android.permission.READ_PROFILE: granted=true
      android.permission.BLUETOOTH: granted=true
      android.permission.WRITE_MEDIA_STORAGE: granted=true
      android.permission.WRITE_BLOCKED_NUMBERS: granted=true
      android.permission.INTERNET: granted=true
      android.permission.UPDATE_PACKAGES_WITHOUT_USER_ACTION: granted=true
      android.permission.BLUETOOTH_ADMIN: granted=true
      android.permission.CONTROL_VPN: granted=true
      android.permission.UPDATE_DEVICE_STATS: granted=true
      android.permission.MANAGE_FINGERPRINT: granted=true
      android.permission.READ_PROJECTION_STATE: granted=true
      android.permission.SEND_SAFETY_CENTER_UPDATE: granted=true
      android.permission.BIND_CONNECTION_SERVICE: granted=true
      android.permission.ACCESS_INSTANT_APPS: granted=true
      com.google.android.settings.intelligence.BATTERY_DATA: granted=true
      android.permission.ACCESS_CONTEXT_HUB: granted=true
      android.permission.MANAGE_USB: granted=true
      android.permission.INTERACT_ACROSS_USERS_FULL: granted=true
      android.permission.STOP_APP_SWITCHES: granted=true
      android.permission.BATTERY_STATS: granted=true
      android.permission.PACKAGE_USAGE_STATS: granted=true
      android.permission.MOUNT_UNMOUNT_FILESYSTEMS: granted=true
      android.permission.TETHER_PRIVILEGED: granted=true
      android.permission.WRITE_SECURE_SETTINGS: granted=true
      android.permission.MANAGE_DEBUGGING: granted=true
      android.permission.MOVE_PACKAGE: granted=true
      android.permission.READ_BLOCKED_NUMBERS: granted=true
      android.permission.READ_SEARCH_INDEXABLES: granted=true
      com.google.android.settings.setup.dock.RUN_DOCK_SETUP: granted=true
      android.permission.USE_FULL_SCREEN_INTENT: granted=true
      android.permission.READ_PRIVILEGED_PHONE_STATE: granted=true
      android.permission.TRIGGER_TIME_ZONE_RULES_CHECK: granted=true
      android.permission.ACCESS_DOWNLOAD_MANAGER: granted=true
      android.permission.BLUETOOTH_PRIVILEGED: granted=true
      android.permission.HARDWARE_TEST: granted=true
      android.permission.USE_BIOMETRIC_INTERNAL: granted=true
      android.permission.INSTALL_DYNAMIC_SYSTEM: granted=true
      android.permission.SUBSTITUTE_NOTIFICATION_APP_NAME: granted=true
      android.intent.category.MASTER_CLEAR.permission.C2D_MESSAGE: granted=true
      android.permission.BIND_JOB_SERVICE: granted=true
      android.permission.CONFIRM_FULL_BACKUP: granted=true
      android.permission.WRITE_APN_SETTINGS: granted=true
      android.permission.CHANGE_WIFI_STATE: granted=true
      android.permission.MANAGE_USERS: granted=true
      android.permission.ACCESS_NETWORK_STATE: granted=true
      android.permission.BACKUP: granted=true
      android.permission.CHANGE_CONFIGURATION: granted=true
      android.permission.USER_ACTIVITY: granted=true
      android.permission.LOCAL_MAC_ADDRESS: granted=true
      android.permission.READ_LOGS: granted=true
      android.permission.COPY_PROTECTED_DATA: granted=true
      android.permission.INTERACT_ACROSS_USERS: granted=true
      android.permission.SET_KEYBOARD_LAYOUT: granted=true
      android.permission.BROADCAST_CLOSE_SYSTEM_DIALOGS: granted=true
      android.permission.READ_DREAM_STATE: granted=true
      android.permission.START_VIEW_APP_FEATURES: granted=true
      android.permission.MANAGE_APP_OPS_RESTRICTIONS: granted=true
      android.permission.MANAGE_USER_OEM_UNLOCK_STATE: granted=true
      com.android.phone.permission.ACCESS_LAST_KNOWN_CELL_ID: granted=true
      android.permission.REQUEST_NETWORK_SCORES: granted=true
      android.permission.CONNECTIVITY_USE_RESTRICTED_NETWORKS: granted=true
      android.permission.WRITE_USER_DICTIONARY: granted=true
      android.permission.READ_DREAM_SUPPRESSION: granted=true
      android.permission.READ_SYNC_STATS: granted=true
      android.permission.REBOOT: granted=true
      android.permission.REQUEST_DELETE_PACKAGES: granted=true
      android.permission.OEM_UNLOCK_STATE: granted=true
      android.permission.MANAGE_DEVICE_ADMINS: granted=true
      android.permission.CHANGE_APP_IDLE_STATE: granted=true
      android.permission.BIND_SETTINGS_SUGGESTIONS_SERVICE: granted=true
      android.permission.TEST_BLACKLISTED_PASSWORD: granted=true
      android.permission.MANAGE_NOTIFICATION_LISTENERS: granted=true
      android.permission.SET_POINTER_SPEED: granted=true
      android.permission.MANAGE_NOTIFICATIONS: granted=true
      android.permission.MANAGE_GAME_MODE: granted=true
      android.permission.SEND_SHOW_SUSPENDED_APP_DETAILS: granted=true
      android.permission.READ_SYNC_SETTINGS: granted=true
      android.permission.BIND_CELL_BROADCAST_SERVICE: granted=true
      android.permission.LOADER_USAGE_STATS: granted=true
      android.permission.OVERRIDE_WIFI_CONFIG: granted=true
      android.permission.FORCE_STOP_PACKAGES: granted=true
      android.permission.SUGGEST_MANUAL_TIME_AND_ZONE: granted=true
      android.permission.HIDE_NON_SYSTEM_OVERLAY_WINDOWS: granted=true
      android.permission.ACCESS_NOTIFICATIONS: granted=true
      android.permission.HANDLE_CALL_INTENT: granted=true
      android.permission.MEDIA_RESOURCE_OVERRIDE_PID: granted=true
      android.permission.CUSTOMIZE_SYSTEM_UI: granted=true
      android.permission.VIBRATE: granted=true
      com.android.certinstaller.INSTALL_AS_USER: granted=true
      android.permission.MANAGE_APP_HIBERNATION: granted=true
      android.permission.HANDLE_CAR_MODE_CHANGES: granted=true
      android.permission.READ_USER_DICTIONARY: granted=true
      android.permission.MANAGE_SCOPED_ACCESS_DIRECTORY_PERMISSIONS: granted=true
      android.permission.ACCESS_WIFI_STATE: granted=true
      android.permission.READ_APP_SPECIFIC_LOCALES: granted=true
      android.permission.USE_BIOMETRIC: granted=true
      android.permission.MANAGE_APP_OPS_MODES: granted=true
      com.android.settings.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION: granted=true
      android.permission.MODIFY_PHONE_STATE: granted=true
      android.permission.STATUS_BAR: granted=true
      android.permission.QUERY_ALL_PACKAGES: granted=true
      com.google.android.settings.routines.ROUTINES_ACTIONS: granted=true
      android.permission.READ_DEVICE_CONFIG: granted=true
      android.permission.LOCATION_HARDWARE: granted=true
      android.permission.UNLIMITED_TOASTS: granted=true
      android.permission.QUERY_ADMIN_POLICY: granted=true
      android.permission.WAKE_LOCK: granted=true
      android.permission.BIND_NETWORK_RECOMMENDATION_SERVICE: granted=true
      android.permission.UPDATE_APP_OPS_STATS: granted=true
      android.permission.READ_OEM_UNLOCK_STATE: granted=true
      android.permission.MEDIA_CONTENT_CONTROL: granted=true
      android.permission.DELETE_PACKAGES: granted=true
    User 0: ceDataInode=123383 installed=true hidden=false suspended=false distractionFlags=0 stopped=false notLaunched=false enabled=0 instant=false virtual=false
      installReason=0
      firstInstallTime=2024-09-09 23:06:33
      uninstallReason=0
      overlay paths:
        /product/overlay/EmulationPixel6/EmulationPixel6Overlay.apk
        /product/overlay/NavigationBarModeGestural/NavigationBarModeGesturalOverlay.apk
        /product/overlay/SettingsGoogle__auto_generated_rro_product.apk
      legacy overlay paths:
        /product/overlay/EmulationPixel6/EmulationPixel6Overlay.apk
        /product/overlay/NavigationBarModeGestural/NavigationBarModeGesturalOverlay.apk
        /product/overlay/SettingsGoogle__auto_generated_rro_product.apk
      enabledComponents:
        com.android.settings.WebViewImplementation
        com.android.settings.homepage.DeepLinkHomepageActivity
        com.android.settings.search.SearchStateReceiver

Queries:
  system apps queryable: false
  queries via forceQueryable:
  forceQueryable:
    [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
  queries via package name:
  queries via component:
  queryable via interaction:
    User 0:
      [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]:
        [com.android.providers.telephony,com.android.ons,com.android.stk,com.android.phone,com.android.mms.service]
        [com.android.bluetooth,com.google.android.bluetooth]
        [com.google.android.cellbroadcastservice,com.google.android.networkstack,com.google.android.networkstack.tethering]
        com.android.shell
        [com.android.providers.userdictionary,com.android.calllogbackup,com.android.providers.contacts,com.android.providers.blockednumber]
        com.android.cellbroadcastreceiver
        com.android.externalstorage
        com.android.managedprovisioning
        [com.android.soundpicker,com.android.mtp,com.android.providers.downloads.ui,com.android.providers.media,com.android.providers.downloads]
        com.android.providers.calendar
        com.google.android.documentsui
        com.android.carrierdefaultapp
        com.android.traceur
        com.google.android.partnersetup
        com.google.android.settings.intelligence
        com.google.android.dialer
        com.google.android.apps.messaging
        com.google.android.ims
        com.google.android.apps.wellbeing
        com.google.android.as.oss
        com.google.android.setupwizard
        com.google.android.as
        [com.google.android.gms,com.google.android.gsf]
        com.google.android.googlequicksearchbox
        com.google.android.contacts
        com.google.android.apps.youtube.music
        com.google.android.calendar
        com.google.android.apps.docs
        com.google.android.inputmethod.latin
        com.google.android.deskclock
        com.google.android.apps.maps
        com.google.android.youtube
        com.google.android.apps.photos
        com.google.android.gm
        com.google.android.sdksetup
        com.android.remoteprovisioner
        com.google.android.apps.nexuslauncher
        com.google.android.apps.wallpaper
        com.android.systemui
        com.google.android.providers.media.module
        com.google.android.ext.services
        com.google.android.cellbroadcastreceiver
        com.google.android.permissioncontroller
      [com.android.providers.telephony,com.android.ons,com.android.stk,com.android.phone,com.android.mms.service]:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      [com.android.bluetooth,com.google.android.bluetooth]:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      [com.google.android.cellbroadcastservice,com.google.android.networkstack,com.google.android.networkstack.tethering]:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      [com.android.providers.userdictionary,com.android.calllogbackup,com.android.providers.contacts,com.android.providers.blockednumber]:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      [com.android.soundpicker,com.android.mtp,com.android.providers.downloads.ui,com.android.providers.media,com.android.providers.downloads]:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      com.android.providers.calendar:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      com.android.printspooler:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      com.google.android.partnersetup:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      com.google.android.configupdater:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      com.android.imsserviceentitlement:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      com.google.android.settings.intelligence:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      com.google.android.dialer:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      com.google.android.apps.messaging:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      com.google.android.ims:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      com.google.android.apps.wellbeing:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      com.google.android.setupwizard:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      com.google.android.as:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      [com.google.android.gms,com.google.android.gsf]:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      com.google.android.googlequicksearchbox:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      com.google.android.contacts:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      com.google.android.apps.youtube.music:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      com.google.android.webview:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      com.google.android.calendar:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      com.google.android.apps.docs:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      com.google.android.inputmethod.latin:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      com.google.android.deskclock:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      com.google.android.apps.maps:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      com.google.android.youtube:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      com.google.android.apps.photos:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      com.google.android.gm:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      com.google.android.apps.nexuslauncher:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      com.android.systemui:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      com.google.android.providers.media.module:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      com.google.android.ext.services:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
      com.google.android.permissioncontroller:
        [com.android.localtransport,com.android.dynsystem,com.android.inputdevices,com.android.location.fused,com.android.keychain,android,com.android.wallpaperbackup,com.android.emulator.multidisplay,com.android.server.telecom,com.android.settings,com.android.providers.settings]
  queryable via uses-library:

Shared users:
  SharedUser [android.uid.system] (289b134):
    userId=1000
    Packages
      PackageSetting{13517af com.android.localtransport/1000}
      PackageSetting{1c9afeb com.android.dynsystem/1000}
      PackageSetting{4f53f51 com.android.inputdevices/1000}
      PackageSetting{626bfab com.android.location.fused/1000}
      PackageSetting{9ca3953 com.android.keychain/1000}
      PackageSetting{b3a3163 android/1000}
      PackageSetting{c38198f com.android.wallpaperbackup/1000}
      PackageSetting{d562254 com.android.emulator.multidisplay/1000}
      PackageSetting{d766824 com.android.server.telecom/1000}
      PackageSetting{e1a75c5 com.android.settings/1000}
      PackageSetting{f5272ea com.android.providers.settings/1000}
    install permissions:
      android.permission.BIND_INCALL_SERVICE: granted=true
      android.permission.WRITE_SETTINGS: granted=true
      android.permission.CONFIGURE_WIFI_DISPLAY: granted=true
      android.permission.CONFIGURE_DISPLAY_COLOR_MODE: granted=true
      android.permission.CONTROL_DISPLAY_COLOR_TRANSFORMS: granted=true
      com.android.keychain.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION: granted=true
      android.permission.BIND_ATTENTION_SERVICE: granted=true
      android.permission.USE_CREDENTIALS: granted=true
      android.permission.MODIFY_AUDIO_SETTINGS: granted=true
      android.permission.MANAGE_EXTERNAL_STORAGE: granted=true
      android.permission.ACCESS_CHECKIN_PROPERTIES: granted=true
      android.permission.MODIFY_AUDIO_ROUTING: granted=true
      android.permission.READ_SAFETY_CENTER_STATUS: granted=true
      android.permission.QUERY_AUDIO_STATE: granted=true
      android.permission.INSTALL_LOCATION_PROVIDER: granted=true
      android.permission.USE_RESERVED_DISK: granted=true
      android.permission.SYSTEM_ALERT_WINDOW: granted=true
      android.permission.BROADCAST_PHONE_ACCOUNT_REGISTRATION: granted=true
      android.permission.CLEAR_APP_USER_DATA: granted=true
      android.permission.BROADCAST_CALLLOG_INFO: granted=true
      android.permission.NFC: granted=true
      android.permission.BIND_ROTATION_RESOLVER_SERVICE: granted=true
      android.permission.NETWORK_SETTINGS: granted=true
      android.permission.CALL_PRIVILEGED: granted=true
      android.permission.MASTER_CLEAR: granted=true
      android.permission.FOREGROUND_SERVICE: granted=true
      android.permission.WRITE_SYNC_SETTINGS: granted=true
      android.permission.ALLOW_PLACE_IN_MULTI_PANE_SETTINGS: granted=true
      android.permission.MANAGE_DYNAMIC_SYSTEM: granted=true
      android.permission.LAUNCH_MULTI_PANE_SETTINGS_DEEP_LINK: granted=true
      android.permission.MANAGE_ACTIVITY_TASKS: granted=true
      android.permission.RECEIVE_BOOT_COMPLETED: granted=true
      com.google.android.googleapps.permission.GOOGLE_AUTH: granted=true
      android.permission.MANAGE_ROLE_HOLDERS: granted=true
      android.permission.PEERS_MAC_ADDRESS: granted=true
      android.permission.DEVICE_POWER: granted=true
      android.permission.READ_PRINT_SERVICES: granted=true
      android.permission.MANAGE_PROFILE_AND_DEVICE_OWNERS: granted=true
      android.permission.RESTART_WIFI_SUBSYSTEM: granted=true
      android.permission.READ_PROFILE: granted=true
      android.permission.BLUETOOTH: granted=true
      android.permission.WRITE_MEDIA_STORAGE: granted=true
      android.permission.WRITE_BLOCKED_NUMBERS: granted=true
      android.permission.INTERNET: granted=true
      android.permission.UPDATE_PACKAGES_WITHOUT_USER_ACTION: granted=true
      android.permission.BLUETOOTH_ADMIN: granted=true
      android.permission.CONTROL_VPN: granted=true
      android.permission.UPDATE_DEVICE_STATS: granted=true
      android.permission.MANAGE_FINGERPRINT: granted=true
      android.permission.READ_PROJECTION_STATE: granted=true
      android.permission.SEND_SAFETY_CENTER_UPDATE: granted=true
      android.permission.BIND_CONNECTION_SERVICE: granted=true
      android.permission.ACCESS_INSTANT_APPS: granted=true
      com.google.android.settings.intelligence.BATTERY_DATA: granted=true
      android.permission.ACCESS_CONTEXT_HUB: granted=true
      android.permission.MANAGE_USB: granted=true
      android.permission.INTERACT_ACROSS_USERS_FULL: granted=true
      android.permission.STOP_APP_SWITCHES: granted=true
      android.permission.BATTERY_STATS: granted=true
      android.permission.PACKAGE_USAGE_STATS: granted=true
      android.permission.MOUNT_UNMOUNT_FILESYSTEMS: granted=true
      android.permission.TETHER_PRIVILEGED: granted=true
      android.permission.WRITE_SECURE_SETTINGS: granted=true
      android.permission.MANAGE_DEBUGGING: granted=true
      android.permission.MOVE_PACKAGE: granted=true
      android.permission.READ_BLOCKED_NUMBERS: granted=true
      android.permission.READ_SEARCH_INDEXABLES: granted=true
      com.google.android.settings.setup.dock.RUN_DOCK_SETUP: granted=true
      android.permission.USE_FULL_SCREEN_INTENT: granted=true
      android.permission.READ_PRIVILEGED_PHONE_STATE: granted=true
      android.permission.TRIGGER_TIME_ZONE_RULES_CHECK: granted=true
      android.permission.ACCESS_DOWNLOAD_MANAGER: granted=true
      android.permission.BLUETOOTH_PRIVILEGED: granted=true
      android.permission.HARDWARE_TEST: granted=true
      android.permission.USE_BIOMETRIC_INTERNAL: granted=true
      android.permission.INSTALL_DYNAMIC_SYSTEM: granted=true
      android.permission.SUBSTITUTE_NOTIFICATION_APP_NAME: granted=true
      android.intent.category.MASTER_CLEAR.permission.C2D_MESSAGE: granted=true
      android.permission.BIND_JOB_SERVICE: granted=true
      android.permission.CONFIRM_FULL_BACKUP: granted=true
      android.permission.WRITE_APN_SETTINGS: granted=true
      android.permission.CHANGE_WIFI_STATE: granted=true
      android.permission.MANAGE_USERS: granted=true
      android.permission.ACCESS_NETWORK_STATE: granted=true
      android.permission.BACKUP: granted=true
      android.permission.CHANGE_CONFIGURATION: granted=true
      android.permission.USER_ACTIVITY: granted=true
      android.permission.LOCAL_MAC_ADDRESS: granted=true
      android.permission.READ_LOGS: granted=true
      android.permission.COPY_PROTECTED_DATA: granted=true
      android.permission.INTERACT_ACROSS_USERS: granted=true
      android.permission.SET_KEYBOARD_LAYOUT: granted=true
      android.permission.BROADCAST_CLOSE_SYSTEM_DIALOGS: granted=true
      android.permission.READ_DREAM_STATE: granted=true
      android.permission.START_VIEW_APP_FEATURES: granted=true
      android.permission.MANAGE_APP_OPS_RESTRICTIONS: granted=true
      android.permission.MANAGE_USER_OEM_UNLOCK_STATE: granted=true
      com.android.phone.permission.ACCESS_LAST_KNOWN_CELL_ID: granted=true
      android.permission.REQUEST_NETWORK_SCORES: granted=true
      android.permission.CONNECTIVITY_USE_RESTRICTED_NETWORKS: granted=true
      android.permission.WRITE_USER_DICTIONARY: granted=true
      android.permission.READ_DREAM_SUPPRESSION: granted=true
      android.permission.READ_SYNC_STATS: granted=true
      android.permission.REBOOT: granted=true
      android.permission.REQUEST_DELETE_PACKAGES: granted=true
      android.permission.OEM_UNLOCK_STATE: granted=true
      android.permission.MANAGE_DEVICE_ADMINS: granted=true
      android.permission.CHANGE_APP_IDLE_STATE: granted=true
      android.permission.BIND_SETTINGS_SUGGESTIONS_SERVICE: granted=true
      android.permission.TEST_BLACKLISTED_PASSWORD: granted=true
      android.permission.MANAGE_NOTIFICATION_LISTENERS: granted=true
      android.permission.SET_POINTER_SPEED: granted=true
      android.permission.MANAGE_NOTIFICATIONS: granted=true
      android.permission.MANAGE_GAME_MODE: granted=true
      android.permission.SEND_SHOW_SUSPENDED_APP_DETAILS: granted=true
      android.permission.READ_SYNC_SETTINGS: granted=true
      android.permission.BIND_CELL_BROADCAST_SERVICE: granted=true
      android.permission.LOADER_USAGE_STATS: granted=true
      android.permission.OVERRIDE_WIFI_CONFIG: granted=true
      android.permission.FORCE_STOP_PACKAGES: granted=true
      android.permission.SUGGEST_MANUAL_TIME_AND_ZONE: granted=true
      android.permission.HIDE_NON_SYSTEM_OVERLAY_WINDOWS: granted=true
      android.permission.ACCESS_NOTIFICATIONS: granted=true
      android.permission.HANDLE_CALL_INTENT: granted=true
      android.permission.MEDIA_RESOURCE_OVERRIDE_PID: granted=true
      android.permission.CUSTOMIZE_SYSTEM_UI: granted=true
      android.permission.VIBRATE: granted=true
      com.android.certinstaller.INSTALL_AS_USER: granted=true
      android.permission.MANAGE_APP_HIBERNATION: granted=true
      android.permission.HANDLE_CAR_MODE_CHANGES: granted=true
      android.permission.READ_USER_DICTIONARY: granted=true
      android.permission.MANAGE_SCOPED_ACCESS_DIRECTORY_PERMISSIONS: granted=true
      android.permission.ACCESS_WIFI_STATE: granted=true
      android.permission.READ_APP_SPECIFIC_LOCALES: granted=true
      android.permission.USE_BIOMETRIC: granted=true
      android.permission.MANAGE_APP_OPS_MODES: granted=true
      com.android.settings.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION: granted=true
      android.permission.MODIFY_PHONE_STATE: granted=true
      android.permission.STATUS_BAR: granted=true
      android.permission.QUERY_ALL_PACKAGES: granted=true
      com.google.android.settings.routines.ROUTINES_ACTIONS: granted=true
      android.permission.READ_DEVICE_CONFIG: granted=true
      android.permission.LOCATION_HARDWARE: granted=true
      android.permission.UNLIMITED_TOASTS: granted=true
      android.permission.QUERY_ADMIN_POLICY: granted=true
      android.permission.WAKE_LOCK: granted=true
      android.permission.BIND_NETWORK_RECOMMENDATION_SERVICE: granted=true
      android.permission.UPDATE_APP_OPS_STATS: granted=true
      android.permission.READ_OEM_UNLOCK_STATE: granted=true
      android.permission.MEDIA_CONTENT_CONTROL: granted=true
      android.permission.DELETE_PACKAGES: granted=true
    User 0:
      gids=[1065, 3002, 3003, 3001, 3007, 1007]
      runtime permissions:
        android.permission.POST_NOTIFICATIONS: granted=true, flags=[ SYSTEM_FIXED|GRANTED_BY_DEFAULT]
        android.permission.READ_CALL_LOG: granted=true, flags=[ SYSTEM_FIXED|GRANTED_BY_DEFAULT|RESTRICTION_SYSTEM_EXEMPT|RESTRICTION_UPGRADE_EXEMPT]
        android.permission.ACCESS_FINE_LOCATION: granted=true, flags=[ SYSTEM_FIXED|GRANTED_BY_DEFAULT|RESTRICTION_SYSTEM_EXEMPT]
        android.permission.BLUETOOTH_CONNECT: granted=true, flags=[ SYSTEM_FIXED|GRANTED_BY_DEFAULT|USER_SENSITIVE_WHEN_GRANTED|USER_SENSITIVE_WHEN_DENIED]
        android.permission.READ_EXTERNAL_STORAGE: granted=true, flags=[ SYSTEM_FIXED|GRANTED_BY_DEFAULT|RESTRICTION_SYSTEM_EXEMPT|RESTRICTION_UPGRADE_EXEMPT]
        android.permission.ACCESS_COARSE_LOCATION: granted=true, flags=[ SYSTEM_FIXED|GRANTED_BY_DEFAULT|REVOKE_WHEN_REQUESTED|RESTRICTION_SYSTEM_EXEMPT]
        android.permission.READ_PHONE_STATE: granted=true, flags=[ SYSTEM_FIXED|GRANTED_BY_DEFAULT|USER_SENSITIVE_WHEN_GRANTED|USER_SENSITIVE_WHEN_DENIED]
        android.permission.SEND_SMS: granted=true, flags=[ SYSTEM_FIXED|GRANTED_BY_DEFAULT|RESTRICTION_SYSTEM_EXEMPT|RESTRICTION_UPGRADE_EXEMPT]
        android.permission.CALL_PHONE: granted=true, flags=[ SYSTEM_FIXED|GRANTED_BY_DEFAULT|USER_SENSITIVE_WHEN_GRANTED|USER_SENSITIVE_WHEN_DENIED]
        android.permission.READ_MEDIA_IMAGES: granted=true, flags=[ SYSTEM_FIXED|GRANTED_BY_DEFAULT|USER_SENSITIVE_WHEN_GRANTED|USER_SENSITIVE_WHEN_DENIED]
        android.permission.WRITE_CONTACTS: granted=true, flags=[ SYSTEM_FIXED|GRANTED_BY_DEFAULT|USER_SENSITIVE_WHEN_GRANTED|USER_SENSITIVE_WHEN_DENIED]
        android.permission.CAMERA: granted=true, flags=[ SYSTEM_FIXED|GRANTED_BY_DEFAULT|USER_SENSITIVE_WHEN_GRANTED|USER_SENSITIVE_WHEN_DENIED]
        android.permission.WRITE_CALL_LOG: granted=true, flags=[ SYSTEM_FIXED|GRANTED_BY_DEFAULT|RESTRICTION_SYSTEM_EXEMPT|RESTRICTION_UPGRADE_EXEMPT]
        android.permission.READ_MEDIA_AUDIO: granted=true, flags=[ SYSTEM_FIXED|GRANTED_BY_DEFAULT|USER_SENSITIVE_WHEN_GRANTED|USER_SENSITIVE_WHEN_DENIED]
        android.permission.READ_MEDIA_VIDEO: granted=true, flags=[ SYSTEM_FIXED|GRANTED_BY_DEFAULT|USER_SENSITIVE_WHEN_GRANTED|USER_SENSITIVE_WHEN_DENIED]
        android.permission.BLUETOOTH_ADVERTISE: granted=true, flags=[ SYSTEM_FIXED|GRANTED_BY_DEFAULT|USER_SENSITIVE_WHEN_GRANTED|USER_SENSITIVE_WHEN_DENIED]
        android.permission.GET_ACCOUNTS: granted=true, flags=[ SYSTEM_FIXED|GRANTED_BY_DEFAULT]
        android.permission.WRITE_EXTERNAL_STORAGE: granted=true, flags=[ SYSTEM_FIXED|GRANTED_BY_DEFAULT|USER_SENSITIVE_WHEN_GRANTED|USER_SENSITIVE_WHEN_DENIED|RESTRICTION_SYSTEM_EXEMPT|RESTRICTION_UPGRADE_EXEMPT]
        android.permission.READ_CONTACTS: granted=true, flags=[ SYSTEM_FIXED|GRANTED_BY_DEFAULT]
        android.permission.ACCESS_BACKGROUND_LOCATION: granted=true, flags=[ SYSTEM_FIXED|GRANTED_BY_DEFAULT|RESTRICTION_SYSTEM_EXEMPT|RESTRICTION_UPGRADE_EXEMPT]
        android.permission.BLUETOOTH_SCAN: granted=true, flags=[ SYSTEM_FIXED|GRANTED_BY_DEFAULT|USER_SENSITIVE_WHEN_GRANTED|USER_SENSITIVE_WHEN_DENIED]

Dexopt state:
  [com.android.settings]
    path: /system_ext/priv-app/SettingsGoogle/SettingsGoogle.apk
      x86_64: [status=verify] [reason=prebuilt]
  BgDexopt state:
    enabled:true
    mDexOptThread:null
    mDexOptCancellingThread:null
    mFinishedPostBootUpdate:false
    mLastExecutionStatus:0
    mLastExecutionStartTimeMs:0
    mLastExecutionDurationIncludingSleepMs:0
    mLastExecutionStartUptimeMs:0
    mLastExecutionDurationMs:0
    now:266015
    mLastCancelledPackages:
    mFailedPackageNamesPrimary:
    mFailedPackageNamesSecondary:

Compiler stats:
  [com.android.settings]
    (No recorded stats)
```

## art-apex

### $ adb shell getprop | grep -E "dalvik|zygote"
```text
[dalvik.vm.appimageformat]: [lz4]
[dalvik.vm.dex2oat-Xms]: [64m]
[dalvik.vm.dex2oat-Xmx]: [512m]
[dalvik.vm.dex2oat-max-image-block-size]: [524288]
[dalvik.vm.dex2oat-minidebuginfo]: [true]
[dalvik.vm.dex2oat-resolve-startup-strings]: [true]
[dalvik.vm.dex2oat64.enabled]: [1]
[dalvik.vm.dexopt.secondary]: [true]
[dalvik.vm.dexopt.thermal-cutoff]: [2]
[dalvik.vm.heapgrowthlimit]: [192m]
[dalvik.vm.heapmaxfree]: [8m]
[dalvik.vm.heapminfree]: [512k]
[dalvik.vm.heapsize]: [512m]
[dalvik.vm.heapstartsize]: [8m]
[dalvik.vm.heaptargetutilization]: [0.75]
[dalvik.vm.image-dex2oat-Xms]: [64m]
[dalvik.vm.image-dex2oat-Xmx]: [64m]
[dalvik.vm.isa.x86_64.features]: [default]
[dalvik.vm.isa.x86_64.variant]: [x86_64]
[dalvik.vm.lockprof.threshold]: [500]
[dalvik.vm.madvise.artfile.size]: [4294967295]
[dalvik.vm.madvise.odexfile.size]: [104857600]
[dalvik.vm.madvise.vdexfile.size]: [104857600]
[dalvik.vm.minidebuginfo]: [true]
[dalvik.vm.usejit]: [true]
[dalvik.vm.usejitprofiles]: [true]
[init.svc.zygote]: [running]
[persist.debug.dalvik.vm.core_platform_api_policy]: [just-warn]
[persist.sys.dalvik.vm.lib.2]: [libart.so]
[ro.boot.dalvik.vm.heapsize]: [512m]
[ro.dalvik.vm.native.bridge]: [0]
[ro.zygote]: [zygote64]
[ro.zygote.disable_gl_preload]: [1]
```

### $ adb shell ps -A | grep -E "zygote|system_server"
```text
root           312     1 14380132 42920 0                   0 S zygote64
system         513   312 15566292 172756 0                  0 S system_server
webview_zygote 968   312 14351296 32240 0                   0 S webview_zygote
```

### $ adb shell ls -l /apex
```text
ls: /apex: Permission denied
```

### $ adb shell cmd package list packages --apex-only
```text
package:com.google.android.appsearch
package:com.google.android.tethering
package:com.google.android.tzdata4
package:com.google.android.media.swcodec
package:com.google.android.wifi
package:com.android.i18n
package:com.android.apex.cts.shim
package:com.google.android.media
package:com.google.android.btservices
package:com.google.android.os.statsd
package:com.google.android.vndk.v33
package:com.google.android.ipsec
package:com.google.android.resolv
package:com.google.android.uwb
package:com.google.android.extservices
package:com.google.android.scheduling
package:com.google.android.mediaprovider
package:com.google.android.sdkext
package:com.google.android.adbd
package:com.google.mainline.primary.libs
package:com.google.android.cellbroadcast
package:com.google.android.adservices
package:com.google.android.art
package:com.google.android.runtime
package:com.google.android.ondevicepersonalization
package:com.google.android.neuralnetworks
package:com.google.android.conscrypt
package:com.google.android.permission
```

## network-tls

### $ adb shell getprop | grep -E "dns|net\."
```text
[init.svc.mdnsd]: [running]
[net.bt.name]: [Android]
```

### $ adb shell settings get global http_proxy
```text
null
```

### $ adb shell ip addr
```text
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
    inet6 ::1/128 scope host
       valid_lft forever preferred_lft forever
2: dummy0: <BROADCAST,NOARP,UP,LOWER_UP> mtu 1500 qdisc noqueue state UNKNOWN group default qlen 1000
    link/ether f6:8c:77:89:fb:40 brd ff:ff:ff:ff:ff:ff
    inet6 fe80::f48c:77ff:fe89:fb40/64 scope link
       valid_lft forever preferred_lft forever
3: ifb0: <BROADCAST,NOARP> mtu 1500 qdisc noop state DOWN group default qlen 32
    link/ether ae:fd:ac:80:c7:45 brd ff:ff:ff:ff:ff:ff
4: ifb1: <BROADCAST,NOARP> mtu 1500 qdisc noop state DOWN group default qlen 32
    link/ether 32:31:ff:1f:42:e1 brd ff:ff:ff:ff:ff:ff
5: tunl0@NONE: <NOARP> mtu 1480 qdisc noop state DOWN group default qlen 1000
    link/ipip 0.0.0.0 brd 0.0.0.0
6: gre0@NONE: <NOARP> mtu 1476 qdisc noop state DOWN group default qlen 1000
    link/gre 0.0.0.0 brd 0.0.0.0
7: gretap0@NONE: <BROADCAST,MULTICAST> mtu 1462 qdisc noop state DOWN group default qlen 1000
    link/ether 00:00:00:00:00:00 brd ff:ff:ff:ff:ff:ff
8: erspan0@NONE: <BROADCAST,MULTICAST> mtu 1450 qdisc noop state DOWN group default qlen 1000
    link/ether 00:00:00:00:00:00 brd ff:ff:ff:ff:ff:ff
9: ip_vti0@NONE: <NOARP> mtu 1480 qdisc noop state DOWN group default qlen 1000
    link/ipip 0.0.0.0 brd 0.0.0.0
10: ip6_vti0@NONE: <NOARP> mtu 1364 qdisc noop state DOWN group default qlen 1000
    link/tunnel6 :: brd ::
11: sit0@NONE: <NOARP> mtu 1480 qdisc noop state DOWN group default qlen 1000
    link/sit 0.0.0.0 brd 0.0.0.0
12: ip6tnl0@NONE: <NOARP> mtu 1452 qdisc noop state DOWN group default qlen 1000
    link/tunnel6 :: brd ::
13: ip6gre0@NONE: <NOARP> mtu 1448 qdisc noop state DOWN group default qlen 1000
    link/gre6 00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00 brd 00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00
14: hwsim0: <BROADCAST,MULTICAST> mtu 1500 qdisc noop state DOWN group default qlen 1000
    link/ieee802.11/radiotap 12:00:00:00:00:00 brd ff:ff:ff:ff:ff:ff
15: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP group default qlen 1000
    link/ether 52:54:00:12:34:56 brd ff:ff:ff:ff:ff:ff
    inet 10.0.2.15/8 brd 10.255.255.255 scope global eth0
       valid_lft forever preferred_lft forever
    inet6 fec0::5054:ff:fe12:3456/64 scope site dynamic mngtmpaddr
       valid_lft 86222sec preferred_lft 14222sec
    inet6 fe80::5054:ff:fe12:3456/64 scope link
       valid_lft forever preferred_lft forever
16: wlan0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP group default qlen 1000
    link/ether 02:15:cc:00:00:00 brd ff:ff:ff:ff:ff:ff
    inet 10.0.2.16/24 brd 10.0.2.255 scope global wlan0
       valid_lft forever preferred_lft forever
    inet6 fec0::8dc9:8dd8:9cdc:ca58/64 scope site temporary dynamic
       valid_lft 86214sec preferred_lft 14214sec
    inet6 fec0::3a63:461d:59fa:6a0/64 scope site dynamic mngtmpaddr stable-privacy
       valid_lft 86214sec preferred_lft 14214sec
    inet6 fe80::6286:44fd:f353:ec73/64 scope link stable-privacy
       valid_lft forever preferred_lft forever
```

### $ adb shell ip route
```text
10.0.0.0/8 dev eth0 proto kernel scope link src 10.0.2.15
10.0.2.0/24 dev wlan0 proto kernel scope link src 10.0.2.16
```

## security-services

### $ adb shell service list | grep -E "keystore|gatekeeper|fingerprint|face|auth|security"
```text
1	SurfaceFlinger: [android.ui.ISurfaceComposer]
2	SurfaceFlingerAIDL: [android.gui.ISurfaceComposer]
25	android.hardware.security.keymint.IKeyMintDevice/default: []
26	android.hardware.security.keymint.IRemotelyProvisionedComponent/default: []
27	android.hardware.security.secureclock.ISecureClock/default: []
28	android.hardware.security.sharedsecret.ISharedSecret/default: []
32	android.security.apc: [android.security.apc.IProtectedConfirmation]
33	android.security.authorization: [android.security.authorization.IKeystoreAuthorization]
34	android.security.compat: [android.security.compat.IKeystoreCompatService]
35	android.security.identity: [android.security.identity.ICredentialStoreFactory]
36	android.security.legacykeystore: [android.security.legacykeystore.ILegacyKeystore]
37	android.security.maintenance: [android.security.maintenance.IKeystoreMaintenance]
38	android.security.metrics: [android.security.metrics.IKeystoreMetrics]
39	android.security.remoteprovisioning: [android.security.remoteprovisioning.IRemoteProvisioning]
40	android.security.remoteprovisioning.IRemotelyProvisionedKeyPool: [android.security.remoteprovisioning.IRemotelyProvisionedKeyPool]
41	android.service.gatekeeper.IGateKeeperService: []
42	android.system.keystore2.IKeystoreService/default: [android.system.keystore2.IKeystoreService]
51	attestation_verification: [android.security.attestationverification.IAttestationVerificationManagerService]
53	auth: [android.hardware.biometrics.IAuthService]
97	file_integrity: [android.security.IFileIntegrityService]
98	fingerprint: [android.hardware.fingerprint.IFingerprintService]
192	sec_key_att_app_id_provider: [android.security.keymaster.IKeyAttestationApplicationIdProvider]
```

### $ adb shell pm list features | grep -E "fingerprint|face|keystore|strongbox"
```text
feature:android.hardware.fingerprint
feature:android.hardware.hardware_keystore=200
feature:android.hardware.keystore.app_attest_key
```

### $ adb shell dumpsys biometric
```text
Legacy Settings: false

Sensors:
 ID(0), oemStrength: 15, updatedStrength: 15, modality 2, state: 0, cookie: 0

CurrentSession: null

CoexCoordinator: Enabled: true, Face Haptic Disabled: false, Queue size: 0
```
