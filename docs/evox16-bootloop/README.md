# evox16 boot loop evidence

Excerpts only. The full phone logs (bugreport, logcat, dropbox, getprop) stay on the build PC in
`D:\android_rom_building\diagnostics\builds\evox16\device-bootloop-20261014\` because they contain personal data.

| File | What it shows |
|---|---|
| [system_server-crash.txt](system_server-crash.txt) | The first of 53 identical `system_server` crashes: `ITelecomLoader$Stub` received an `ITelecomService` call |
| [packagemanager.txt](packagemanager.txt) | PackageManager kept `/system/priv-app/Telecom` and skipped `TelecomShim` as a duplicate |
| [system-img-telecom.txt](system-img-telecom.txt) | `debugfs` listing of the shipped `system.img`: both Telecom APKs are in it |
| [telecom-apks.txt](telecom-apks.txt) | Both APKs are `com.android.server.telecom` version 37; Telecom.apk was installed at 18:11 (precheck), TelecomShim at 19:20 (full build) |
| [staged-not-installed.txt](staged-not-installed.txt) | Every staged file that is not in the product's install list |
| [verifier-duplicate-packages.json](verifier-duplicate-packages.json) | The evox16 verifier recorded the duplicate and did not fail |

See [the review](../evox16-review.md) for the explanation.
