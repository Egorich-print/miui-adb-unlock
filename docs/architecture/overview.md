# Architecture

> Snapshot of how the pieces fit together. See `docs/adr/` for the decisions
> behind them.

```
        host (macOS / Linux)                        device (MIUI 12, Android 9)
 ┌───────────────────────────────┐          ┌─────────────────────────────────────┐
 │ miui_adb_unlock.cli           │          │  /system/bin/uiautomator            │
 │   ├─ flows.Unlocker           │          │    └─ uiautomator.jar (stock)        │
 │   │    ├─ doctor / unlock     │  adb     │                                     │
 │   │    └─ verify / wifi       │ ──────► │  miui-a11y.jar  (this project)      │
 │   ├─ driver.Driver            │         │    └─ com.miuiadblock.A11yDriver      │
 │   │    └─ push / cmd / parse  │ ◄────── │         │                           │
 │   ├─ gates.KNOWLEDGE          │  stdout │         ▼ performAction(ACTION_*)   │
 │   └─ adb.Adb                  │         │  accessibility service            │
 └───────────────────────────────┘          │    → Settings UI (no touch needed) │
                                              └─────────────────────────────────────┘
```

## Layers

| Layer | Module | Responsibility |
|---|---|---|
| Interface | `miui_adb_unlock/cli.py` | argument parsing, device selection, reporting |
| Flow | `miui_adb_unlock/flows.py` | doctor / unlock / verify / wifi: the user-visible procedures |
| Transport | `miui_adb_unlock/driver.py` | pushes the harness, feeds one command, parses one result line |
| Transport | `miui_adb_unlock/adb.py` | a thin, typed wrapper around the `adb` binary |
| Knowledge | `miui_adb_unlock/gates.py` | every MIUI-specific string: labels, properties, provider, endpoint, gate probes |
| On device | `harness/java/…/A11yDriver.java` | performs the accessibility actions |

## The command protocol

The host writes one command line to `/data/local/tmp/miui_a11y_cmd.txt` and runs
the stock harness:

```shell
adb shell "uiautomator runtest /data/local/tmp/miui-a11y.jar \
           -e class com.miuiadblock.A11yDriver"
```

The driver prints exactly one result line, prefixed with `[miui-a11y]`, and any
number of trace lines:

```
[miui-a11y] TRACE scroll 1 -> true
[miui-a11y] TRACE scroll 2 -> true
[miui-a11y] OK click Отладка по USB (Настройки безопасности)
```

The host parses the last `OK`/`ERR` line and treats the traces as diagnostics.

## Why an on-device Java driver

* The stock `uiautomator` harness already runs with the privileges that the
  shell identity lost: it connects to the accessibility service as the
  `uiautomator` client, which is allowed to act on any window.
* `AccessibilityNodeInfo.performAction(ACTION_CLICK)` does not go through
  `InputManager.injectInputEvent()`, so MIUI's input filter never sees it.
* The driver runs on the device, so the coordinates and the UI tree are read
  where they live; the host only sends verbs.

## Failure handling

| Failure | Handling |
|---|---|
| stale harness holds the `UiAutomation` service | `pkill -f uiautomator` before every run |
| screen never goes idle | window enumeration instead of `getRootInActiveWindow()`, idle timeout lowered to 1.5 s |
| stale node after a scroll | the root is re-fetched before every action |
| phantom touches from a damaged digitiser | irrelevant — no coordinates are injected, actions are dispatched to nodes |
| MIUI labels differ on another build | all labels live in `gates.py` |

## Boundaries

* The tool does not install anything on the device and does not modify the
  system partition.
* It does not create accounts and does not log in anywhere.
* It never stores or prints a password: the password is read from an
  environment variable and handed to the device in one action.
