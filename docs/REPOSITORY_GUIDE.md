# Repository guide

## Layout

```
miui-adb-unlock/
├── miui_adb_unlock/        # python package (the tool)
│   ├── cli.py              # command line interface
│   ├── flows.py            # doctor / unlock / verify / wifi
│   ├── driver.py           # client of the on-device driver
│   ├── adb.py              # adb wrapper
│   └── gates.py            # all MIUI-specific knowledge
├── harness/                # the on-device driver
│   ├── java/               # driver source
│   ├── stubs/              # compile-time stubs (device dex cannot be read by javac)
│   └── miui-a11y.jar       # prebuilt artifact
├── scripts/                # build and helper scripts
├── tests/                  # unit tests (pure python, no device needed)
├── docs/                   # architecture, ADRs, research, state
├── media/                  # screenshots and recordings
└── README.md / README.ru.md
```

## Rules

* `gates.py` is the only place where MIUI strings live.
* `harness/miui-a11y.jar` is generated — never edit it by hand; edit the source
  and run `scripts/build-harness.sh`.
* `docs/research/` holds dated evidence. `docs/adr/` holds decisions and their
  rationale; a superseded ADR is marked, not deleted.
* `STATUS.md` is the source of truth for what works. Update it in the same
  commit as the change that affects it.
* Line endings are LF everywhere (`.gitattributes`).

## Dependencies

* Runtime: Python 3.9+, `adb`. Nothing else.
* Development: `pytest`, the Android SDK (build-tools + platform) for the harness.
