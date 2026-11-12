#!/system/bin/sh
# Bounded diagnostics only: no root, settings writes, log clearing or notification injection.
umask 077
mode=$1
directory=$2
identifier=${directory#/data/local/tmp/klimt-audio-}
case "$identifier" in ''|*[!0-9-]*) echo 'Invalid capture directory' >&2; exit 2;; esac
[ "${directory%/*}" = /data/local/tmp ] || exit 2
[ "$directory" = "/data/local/tmp/klimt-audio-$identifier" ] || exit 2

start_ticks() { awk '{print $22}' "/proc/$1/stat" 2>/dev/null; }

case "$mode" in
start)
    seconds=$3
    case "$seconds" in ''|*[!0-9]*) exit 2;; esac
    [ "$seconds" -ge 5 ] && [ "$seconds" -le 1800 ] || exit 2
    available=$(df -k /data/local/tmp | tail -1 | awk '{print $4}')
    [ "$available" -ge 262144 ] || { echo 'Need 256 MiB free for diagnostics' >&2; exit 2; }
    mkdir "$directory" || exit 2
    /system/bin/nohup /system/bin/setsid /system/bin/sh "$0" run "$directory" "$seconds" \
        </dev/null >"$directory/launcher.txt" 2>&1 &
    echo "$!"
    ;;
log)
    echo "$$" >"$directory/logcat.pid"
    start_ticks "$$" >"$directory/logcat.start"
    exec logcat -b main -b system -v threadtime -T 1 -f "$directory/logcat.txt" -r 2048 -n 4 \
        MediaFocusControl:V AS.AudioService:V AS.AudioDeviceBroker:V AS.BtHelper:V \
        AudioPolicyProxy:V AudioPolicyService:V APM_AudioPolicyManager:V AudioFlinger:I \
        MediaRouter:V MediaRouterService:V MR2ServiceImpl:V \
        NotificationPlayer:V RingtonePlayer:V MediaPlayer:I AS.PlaybackActivityMon:V \
        BluetoothA2dp:V A2dpService:V HeadsetService:V '*:S'
    ;;
run)
    seconds=$3
    echo "$$" >"$directory/supervisor.pid"
    start_ticks "$$" >"$directory/supervisor.start"
    date -u '+%Y-%m-%dT%H:%M:%SZ' >"$directory/started.txt"
    uname -r >"$directory/kernel.txt"
    getprop ro.config.media_vol_steps >"$directory/media-steps.txt"
    reason=completed
    finish() {
        trap - EXIT INT TERM
        if [ -f "$directory/logcat.pid" ] && [ -f "$directory/logcat.start" ]; then
            logger=$(cat "$directory/logcat.pid")
            expected=$(cat "$directory/logcat.start")
            actual=$(start_ticks "$logger")
            if [ -n "$expected" ] && [ "$actual" = "$expected" ]; then
                kill -TERM "$logger" 2>/dev/null || :
            fi
        fi
        wait "$timer" 2>/dev/null || :
        printf '%s\n' "$reason" >"$directory/DONE"
        date -u '+%Y-%m-%dT%H:%M:%SZ' >"$directory/finished.txt"
    }
    trap finish EXIT
    trap 'reason=interrupted; exit 0' INT TERM
    # An independent timeout also bounds logcat if the sampling supervisor dies.
    timeout -k 5 "$seconds" /system/bin/sh "$0" log "$directory" \
        >"$directory/logcat-launcher.txt" 2>&1 &
    timer=$!
    deadline=$(($(date +%s) + seconds))
    dumpsys -t 8 bluetooth_manager >"$directory/before-bluetooth.txt" 2>&1
    dumpsys -t 8 media_session >"$directory/before-media-session.txt" 2>&1
    dumpsys -t 8 media.metrics >"$directory/before-media-metrics.txt" 2>&1
    dumpsys -t 8 media_router >"$directory/before-media-router.txt" 2>&1
    sample=0
    while [ "$(date +%s)" -lt "$deadline" ]; do
        [ ! -f "$directory/STOP" ] || { reason=stopped; break; }
        stamp=$(printf '%04d' "$sample")
        date -u '+%Y-%m-%dT%H:%M:%SZ' >"$directory/$stamp-time.txt"
        dumpsys -t 8 audio >"$directory/$stamp-audio.txt" 2>&1
        dumpsys -t 8 media.audio_policy >"$directory/$stamp-policy.txt" 2>&1
        dumpsys -t 8 media.audio_flinger >"$directory/$stamp-flinger.txt" 2>&1
        size=$(du -sk "$directory" | awk '{print $1}')
        [ "$size" -lt 65536 ] || { reason=size-limit; break; }
        remaining=$((deadline - $(date +%s)))
        [ "$remaining" -gt 0 ] || break
        pause=15
        [ "$remaining" -ge "$pause" ] || pause=$remaining
        sleep "$pause"
        sample=$((sample + 1))
    done
    dumpsys -t 8 bluetooth_manager >"$directory/after-bluetooth.txt" 2>&1
    dumpsys -t 8 media_session >"$directory/after-media-session.txt" 2>&1
    dumpsys -t 8 media.metrics >"$directory/after-media-metrics.txt" 2>&1
    dumpsys -t 8 media_router >"$directory/after-media-router.txt" 2>&1
    ;;
status)
    if [ -f "$directory/DONE" ]; then
        printf 'DONE: '; cat "$directory/DONE"
    elif [ -f "$directory/supervisor.pid" ]; then
        pid=$(cat "$directory/supervisor.pid")
        expected=$(cat "$directory/supervisor.start")
        if [ -n "$expected" ] && [ "$(start_ticks "$pid")" = "$expected" ]; then
            echo RUNNING
        else
            echo EXITED_WITHOUT_MARKER
        fi
    else
        echo NOT_STARTED
    fi
    ;;
stop)
    [ -d "$directory" ] || exit 2
    : >"$directory/STOP"
    echo STOP_REQUESTED
    ;;
*) echo 'Usage: recorder.sh start|status|stop DIRECTORY [SECONDS]' >&2; exit 2;;
esac
