#!/bin/bash
# Post-flash health check over adb (Git Bash, read-only): crashes, denials, our HALs, evox9 PIF/hide state.
a(){ adb shell "$1" 2>/dev/null | tr -d '\r'; }
echo "== uptime: $(a uptime)"
echo "== build: slot $(a 'getprop ro.boot.slot_suffix') | SPL $(a 'getprop ro.build.version.security_patch') | vendor SPL $(a 'getprop ro.vendor.build.security_patch') | $(a 'getprop ro.build.date')"
echo "== crash buffer since boot"
a 'logcat -b crash -d | grep -E "FATAL EXCEPTION|Process: |Fatal signal|Abort message|>>> " | head -30'
echo "== avc denials (count scontext -> tcontext class perms)"
a 'logcat -d | grep "avc:  denied"' | sed -E 's/.*avc:  denied  \{ ([^}]*) \}.*scontext=u:r:([^:]*):.*tcontext=u:object_r:([^:]*):.*tclass=([a-z_]*).*/\2 -> \3 \4 {\1}/' | sort | uniq -c | sort -rn | head -15
echo "== lineage HALs"
a 'service list | grep -iE "lineage|powershare|charging|fastcharge"'
echo "== key processes"
for p in system_server surfaceflinger zygote64 camerahalserver vendor.lineage.health-service.default vendor.lineage.powershare-service.default; do echo "  $p: $(a "pidof $p" | head -1)"; done
echo "== PIF / spoof props"
a 'getprop' | grep -iE 'pif|spoof|pihooks|droidguard|fingerprint\]' | head -15
echo "== system apps that crashed/ANR'd (dropbox, since boot)"
a 'dumpsys dropbox --print 2>/dev/null | grep -E "^(=+ |Process:)" | grep -B1 "Process:" | grep -E "Process:|crash|anr|tombstone" | head -20'
