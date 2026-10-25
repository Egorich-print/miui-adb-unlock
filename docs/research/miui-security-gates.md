# miui-security-gates — research notes

> Reverse engineering of the MIUI 12 gates that block adb on a Redmi Note 5
> (whyred, Android 9, MIUI 12 V12.0.2.0.PEIMIXM, kernel 4.4.153).
>
> Method: the MIUI applications were pulled with `adb pull` and decompiled with
> `apktool`/`jadx`; the framework classes were read from the device's
> `boot-framework.vdex`. Every claim below is tied to a code path that was
> executed on the device, not to documentation.

## 1. The two developer options

### USB debugging (security settings)

UI row: `Отладка по USB (Настройки безопасности)` (summary: *Разрешить
предоставление разрешений и имитацию ввода с помощью отладки через USB*).

* Preference controller: `com.android.settings.development.c`
  (`getPreferenceKey() == "adb_input"`).
* On enable it starts
  `com.miui.securitycenter/com.miui.permcenter.install.AdbInputApplyActivity`
  with the action `com.miui.securitycenter.action.ADB_INPUT_APPLY`.
* `AdbInputApplyActivity` writes the state through
  `AdbInputApplyActivity.a(boolean)` →
  `SystemPropertiesCompat.set("persist.security.adbinput", "1" | "0")`.
* `com.android.a.a.isInputEnabled()` reads the very same property — that is why
  the checkbox state follows the property.

### Install over USB

UI row: `Установка через USB` (summary: *Разрешить установку приложений через USB*).

* Preference controller: `com.android.settings.development.d`
  (`getPreferenceKey() == "adb_install"`).
* On enable it starts
  `com.miui.securitycenter/com.miui.permcenter.install.AdbInstallVerifyActivity`
  (action `com.miui.securitycenter.action.ADB_INSTALL_VERIFY`).
* `AdbInstallVerifyActivity.c()` stores the state through
  `com.miui.permcenter.install.d.a(boolean)`, which writes the MIUI preference
  `security_adb_install_enable` **and** mirrors it into the property
  `persist.security.adbinstall`.
* The preference lives in MIUI's own store, reached through
  `content://com.miui.securitycenter.remoteprovider` (method `callPreference`,
  bundle `{type: 1, key: …, value: …}`). That provider is protected by
  `com.miui.securitycenter.permission.ACCESS_SECURITY_CENTER_PROVIDER`
  (`signature|privileged`); `dumpsys package` shows it held by **uid 1000** only.

Both `com.android.settings` and `com.miui.securitycenter` declare
`android:sharedUserId="android.uid.system"`, i.e. they run as uid 1000 — that is
the only identity allowed to write either flag.

## 2. What MIUI's verification does

`AdbInstallVerifyActivity.d()`:

```java
ConnectivityManager cm = getSystemService("connectivity");
NetworkInfo info = cm.getActiveNetworkInfo();
if (info != null && info.isConnected()) {
    new AdbInstallVerifyActivity$a(this).executeOnExecutor(...);  // HTTPS request
} else {
    Toast.makeText(getApplicationContext(), R.string..., LENGTH_LONG).show();
    finish();     // "Подключитесь к сети и повторите попытку"
}
```

The asynchronous task posts to `https://srv.sec.miui.com/data/adb`
(`https://srv.sec.intl.miui.com/data/adb` on international builds) with a JSON
body (`xiaomi_id`, `time`) and reads `status` / `message` from the answer.

Consequences (measured on the device, 2026-10-25):

* **offline** — the option cannot be enabled at all, not even by hand: the toast
  is *"Подключитесь к сети и повторите попытку"*;
* **online** — the request goes out with an empty `xiaomi_id` (no account is
  signed in) and the vendor answers *"Sign in with your Mi Account"* — for
  **both** options;
* **with an account signed in** — `AdbInputApplyActivity` takes another branch
  (`v.a(context)` returns a non-empty account name) and shows a local dialog
  that sets the property without contacting the server.

So the account is a hard vendor requirement on this build, not a detail of the
network check.

## 3. Gates on the adb identity

`dumpsys package com.android.shell` reports the shell package as holding
`WRITE_SECURE_SETTINGS`, `GRANT_RUNTIME_PERMISSIONS`,
`INSTALL_GRANT_RUNTIME_PERMISSIONS` and `MANAGE_DEVICE_ADMINS` — all
`granted=true`. The runtime checks nevertheless deny them:

| Call | Result |
|---|---|
| `settings put secure …` | `SecurityException: Permission denial: writing to settings requires: android.permission.WRITE_SECURE_SETTINGS` |
| `settings put global …` | same |
| `settings put system …` | **works** |
| `pm grant …` | `SecurityException: Neither user 2000 nor current process has android.permission.GRANT_RUNTIME_PERMISSIONS` |
| `adb install -g` | `SecurityException: … INSTALL_GRANT_RUNTIME_PERMISSIONS` |
| `dpm set-device-owner …` | `SecurityException: Neither user 2000 nor current process has android.permission.MANAGE_DEVICE_ADMINS` |
| `input tap` / `input keyevent` | `injectInputEvent` returns success, the event never reaches the app |
| `setprop persist.x 1` | `setprop: failed to set property` (SELinux denies property writes for the shell domain) |

The MIUI patch lives in `system_server` (`/system/framework/oat/arm64/services.vdex`
contains the string `persist.security.adbinput`), so the block is not a property
of the shell package but of the framework.

## 4. Paths that were tried and closed

| Idea | Why it does not work |
|---|---|
| `adb shell settings put secure …` | blocked (see above) |
| `setprop persist.security.adbinput 1` | SELinux: the shell domain may not write properties; even `persist.sys.*` fails |
| `adb root`, `su` | production build, no root |
| `/dev/input/event*` | group `input`, the shell is not in it (`getevent`: *Permission denied*) |
| `/dev/uhid` | the kernel has no HID driver (`/proc/misc` lists no `uhid`, every ioctl answers `ENOTTY`) |
| own APK with `WRITE_SECURE_SETTINGS` | signature\|privileged — a third-party app cannot hold it |
| `WifiManager.addNetwork` from an own APK | the framework strips the security fields from `WifiConfiguration` (`preSharedKey` becomes `*`) and rejects the request (`-1`) |
| instrumentation with `targetPackage="android"` | PMS only accepts an instrumentation whose target is signed with the same certificate; the platform key is Xiaomi's (`release-keys`, `CN=MIUI`) |
| signing an app with the platform key | the key is not public |
| the stock `uiautomator` harness + `UiDevice.click(x, y)` | goes through `injectInputEvent` and is blocked |
| the stock `uiautomator` harness + `UiObject.click()` / `performAction(ACTION_CLICK)` | **works** — accessibility actions are not routed through the input filter |

The last row is the whole basis of this project.

## 5. Practical notes about the harness

* `UiAutomation.getRootInActiveWindow()` waits for the UI to become *idle*. MIUI's
  Settings list animates and a damaged digitiser produces phantom touches, so
  the wait never ends and the call returns `null`. The driver therefore
  enumerates `UiAutomation.getWindows()` and uses the active window's root, and
  lowers the idle timeout through the hidden `setWaitForIdleTimeout()`.
* Nodes obtained from the window enumeration go stale after the list moved:
  `performAction()` on them is rejected. Scrolling therefore always re-fetches
  the root.
* Android allows one `UiAutomation` client at a time. A harness process that did
  not exit keeps the service registered and the next run fails with
  *UiAutomationService … already registered!* — every run kills leftovers first.
* The Settings app on the test device crashes on start
  (`InflateException: Error inflating class android.support.v7.widget.CardView`),
  so screens are opened with an explicit component
  (`com.android.settings/.Settings$…`) and the `CLEAR_TASK` flag, otherwise the
  intent is delivered to an already running top-most instance.

## 6. Wi-Fi side note

The saved profile of the test network contained only `KeyMgmt: SAE`
(WPA3-SAE). The router's strong access points are WPA2, so
`SavedNetworkEvaluator` rejected every candidate and the framework logged
`did not see any good candidates` for all SSIDs. `wpa_supplicant` was also stuck
in `SCANNING`; a radio restart (`svc wifi disable` / `svc wifi enable`) fixed
that part. MIUI does not offer a way to change the security type of a saved
network, and a third-party app may not rewrite the profile, so the profile has to
be recreated from MIUI's own connect dialog.
