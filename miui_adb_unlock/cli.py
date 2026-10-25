"""Command line interface for miui-adb-unlock."""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

from .adb import Adb, AdbError
from .driver import Driver
from .flows import Report, Unlocker
from .gates import TARGETS

DEFAULT_PASSWORD_ENV = "MIUI_WIFI_PASSWORD"


def _print_reports(reports: List[Report]) -> int:
    for report in reports:
        print(report)
    return 0


def _select_device(adb: Adb, requested: Optional[str]) -> Optional[str]:
    serials = adb.devices()
    if not serials:
        print("No device connected (adb devices is empty).", file=sys.stderr)
        return None
    if requested:
        if requested not in serials:
            print(f"Device {requested} is not connected. Available: {', '.join(serials)}", file=sys.stderr)
            return None
        return requested
    if len(serials) > 1:
        print("Several devices connected, pick one with --serial: " + ", ".join(serials), file=sys.stderr)
        return None
    return serials[0]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="miui-adb-unlock",
        description=(
            "Enable the MIUI developer options that the vendor blocks for the adb identity "
            "(USB debugging security settings, install over USB) by driving the Settings UI "
            "through accessibility actions instead of input injection."
        ),
    )
    parser.add_argument("--serial", help="device serial (default: the only connected device)")
    parser.add_argument("--adb", help="path to the adb binary")
    parser.add_argument("-v", "--verbose", action="store_true", help="print driver traces")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="report which gates are active on the device")

    unlock = sub.add_parser("unlock", help="flip a gated developer option")
    unlock.add_argument(
        "target",
        choices=sorted(TARGETS),
        help="security-debugging (no account needed) or install-over-usb (needs a Xiaomi account)",
    )

    sub.add_parser("verify", help="check whether the adb capabilities are back")

    wifi = sub.add_parser("wifi", help="connect the device to a Wi-Fi network")
    wifi.add_argument("ssid", help="network name")
    wifi.add_argument(
        "--password-env",
        default=DEFAULT_PASSWORD_ENV,
        help=f"environment variable holding the password (default: {DEFAULT_PASSWORD_ENV})",
    )
    wifi.add_argument(
        "--no-password",
        action="store_true",
        help="do not type a password (open network or manual entry)",
    )

    sub.add_parser("dump", help="print the accessibility tree of the active screen")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    adb = Adb(serial=args.serial, adb_path=args.adb)

    serial = _select_device(adb, args.serial)
    if serial is None:
        return 2
    adb.serial = serial
    driver = Driver(adb)
    unlocker = Unlocker(adb, driver, verbose=args.verbose)

    try:
        if args.command == "doctor":
            return _print_reports(unlocker.doctor())
        if args.command == "unlock":
            reports = unlocker.unlock(args.target)
            target = TARGETS[args.target]
            if target.needs_account:
                print(
                    "Note: MIUI additionally asks for a signed-in Xiaomi account for "
                    f"'{target.title}'. The device screen shows that request; the option "
                    "stays off without the account.",
                    file=sys.stderr,
                )
            return _print_reports(reports)
        if args.command == "verify":
            return _print_reports(unlocker.verify())
        if args.command == "wifi":
            password = None
            if not args.no_password:
                password = os.environ.get(args.password_env)
                if password is None:
                    print(
                        f"Set {args.password_env} to the network password, or pass --no-password.",
                        file=sys.stderr,
                    )
                    return 2
            return _print_reports(unlocker.wifi(args.ssid, password))
        if args.command == "dump":
            for line in driver.dump():
                print(line)
            return 0
    except AdbError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
