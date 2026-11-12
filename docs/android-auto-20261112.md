# Android Auto notification interruption: 2026-11-12

The 12:57 event establishes a repeated media-routing failure on build 20261111.2.
Android Auto requests transient duckable focus, then the system repeatedly forces media
away from Bluetooth while Spotify recreates tracks on the phone speaker and Bluetooth.
The Uconnect A2DP connection remains connected throughout the event. The remaining question
is which app/route-restoration interaction starts the legacy routing loop, and which mitigation
stops it without breaking intended route selection. This initial capture alone does not establish a fix.

The later [20261112.2 candidate](20261112.2.md) enables the existing upstream safeguard and passed
full image verification. Its shipped flag table is ENABLED READ_ONLY and the generated accessor returns
true. The 18:58 ADB check identified the active phone as 20261111.2 with the old flag table; the owner
then authorized flashing the correct ZIP without a wipe. At 19:13, ADB confirmed 20261112.2 boot-complete
on slot b and its flag table matches the verified candidate. Car validation remains open.

## Setup and evidence

The owner uses a separate wireless Android Auto dashboard/display powered from the car's USB/12 V
connection. Media audio goes directly from the phone to the Renegade's Uconnect over Bluetooth.
The owner reports a WhatsApp notification around 12:57 followed by both screens showing music
paused and then resumed. This configuration previously worked.

Read-only USB ADB collection began at 13:15 local time (America/Sao_Paulo, UTC-03).
The phone runs kernel `6.6.144-android15-8-g08c56166f188-ab20261111.2`.
Installed apps: Android Auto 18.0.664264-release, Spotify 9.1.98.621, WhatsApp 2.26.44.75.
Raw dumps, full logcat, package dumps, a bugreport and Bluetooth packet files remain private in
`diagnostics/audio/20261112-131533-aa-1257/private/` under the build workspace, outside this repository.
There were no root requests, reboots, settings writes, app-data clears or source changes.

| Local time | Retained evidence |
|---|---|
| 12:57:32.259 | Notification history records a WhatsApp notification with effects disabled. |
| 12:57:32.514 | `com.google.android.projection.gearhead` requests `AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK`, with navigation-guidance usage and sonification content. Spotify receives focus loss `-3`. |
| 12:57:32.518 | Media metrics record `AudioService.setBluetoothA2dpOn(false)` under system-server identity. |
| 12:57:32.522 | Audio policy is forced to `FOR_MEDIA / FORCE_NO_BT_A2DP`. |
| 12:57:32.667 | Spotify and Android Auto tracks are created with `routedDeviceId=3`; audio policy identifies port 3 as the built-in speaker. |
| 12:57:32.518–12:57:42.306 | 49 calls to the A2DP routing API: 28 off, 21 on; 45 recorded media force-use operations. Spotify creates 39 tracks: 19 on speaker port 3, 20 on Bluetooth port 67. |
| 12:57:42.490 | Android Auto abandons focus and Spotify receives focus gain `1`. |
| 12:57:42.624 | Spotify starts a track whose output is explicitly recorded as Bluetooth A2DP. |

AudioService also records repeated internal music mute/unmute transitions throughout that interval.
Bluetooth's Uconnect state machine remains `Connected` while the audio stream repeatedly starts/stops;
its later disconnect occurs at 13:10:05. There is no retained AVRCP media-key pause command at 12:57.
The retained key history spans a play command at 12:51 and pause/stop commands after 13:09.
This supports a software routing loop over a Bluetooth link that remained connected, rather than an
ordinary Uconnect disconnect/reconnect or a recorded remote pause-button command.

The focus request allows ducking; it does not itself require a full pause. The original per-session
Spotify `PAUSED` transition was not retained, so that UI state remains owner-reported. Track recreation,
speaker routing and internal muting are independently observed. The exact trigger cannot be assigned
solely to the app requesting focus: MediaRouterService clears Binder identity before calling AudioService,
so its calls appear as system server even when initiated by another app. Route restoration also uses
the same path.

Maps requests focus before and after the event, and Radarbot makes speakerphone-route requests elsewhere
in the drive. Neither is demonstrated to cause the 12:57 routing loop. Dolby and A2DP offload are also
not implicated by this trace; Bluetooth reports offload already disabled.

## Bluetooth logging limits

The bugreport confirms `persist.bluetooth.btsnooplogmode=full`; the direct shell property read was denied,
so its earlier blank output did not mean logging was disabled. The bugreport contains only two short
`btsnooz_hci.log` captures, covering approximately 13:12:22–13:17:23 and 13:12:22–13:15:01.
Neither covers 12:57. The logging preference alone does not prove a full HCI recording was active during
the event. No Bluetooth toggle or restart was performed to try to activate it.
Main/system logcat had also rolled past 12:57, but service histories and media metrics retained the event.

## Existing upstream safeguard and proposed test

At framework head `e345aea65de68309993264355f482fe90950b0e2`,
`frameworks/base/media/java/android/media/flags/media_better_together.aconfig` declares
`com.android.media.flags.disable_set_bluetooth_ad2p_on_calls` for upstream bug 294968421.
Its description explicitly identifies incorrect routing to built-in speakers.
`MediaRouterService.setBluetoothA2dpOn` and `restoreBluetoothA2dp` both guard their legacy
AudioService calls with this flag. AudioDeviceBroker internally mutes music around A2DP state changes,
matching the observed mute/unmute churn.

The existing build's generated aconfig cache marks the flag `DISABLED`, `READ_ONLY`, storage `NONE`;
generated `Flags.disableSetBluetoothAd2pOnCalls()` returns literal `false`.
It is therefore not a live `device_config` switch in this build. A shell override would not be an
adequate test, and no override was attempted. A device-specific candidate could enable the existing
safeguard at build time, followed by a no-wipe parked-car comparison. Its effect covers legacy routing
globally, so deliberate Bluetooth/speaker selection and other media routes need regression checks.
This is a candidate mitigation, not proof of a safe complete fix or of the initiating app.

Upstream has separately documented app MediaRouter selections causing this API to disable Bluetooth:
[AndroidX routing bug investigation](https://android.googlesource.com/platform/frameworks/support/+/6e2a36d4f92c2ce207b074ff31861b550b7c2998)
and an [empty-route-name correction](https://android.googlesource.com/platform/frameworks/support/+/3ce5b81c79338280d429d9fa303d12c927c224d9).
Those establish the bug family, not that the empty-name trigger occurred on this phone.

For the next parked-car reproduction, keep the display and direct Uconnect connection as used here,
record logcat from before notification arrival, and save media metrics plus audio/Bluetooth/router
histories immediately afterwards. Include `MediaRouter`, `MediaRouterService` and AndroidX route-selection
logs so an initiating app or repeated restoration can be identified before its Binder identity is cleared.
The local bounded phone recorder now includes those routing log tags and before/after media-metrics
and media-router snapshots. Shell syntax and the added logcat filters were checked; this revision has
not been exercised through another live car event. No new recording is armed on the phone.
The first settings comparison is Android Auto's own conversation-alert sound on versus off, if that
setting is available in this version. Phone notification mute alone does not stop the observed Auto
navigation-usage alert. If disabling its chime stops the loop, that is a workaround and trigger isolation;
it still does not establish that intentional Bluetooth/speaker selection is safe with the framework flag.

A candidate build must demonstrate that one incoming WhatsApp notification produces no route oscillation,
phone-speaker leak or Spotify pause, while navigation guidance, calls, deliberate output selection and
Bluetooth-only playback still work. Keep the existing 30-step media change independent of this test.
