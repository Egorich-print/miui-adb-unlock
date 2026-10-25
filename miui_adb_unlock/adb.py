"""Thin wrapper around the ``adb`` binary."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Sequence

DEFAULT_TIMEOUT = 120


class AdbError(RuntimeError):
    """Raised when an adb invocation fails."""


@dataclass
class AdbResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def output(self) -> str:
        return (self.stdout + "\n" + self.stderr).strip()


class Adb:
    """Runs adb commands against one device."""

    def __init__(self, serial: Optional[str] = None, adb_path: Optional[str] = None) -> None:
        self.serial = serial
        self.adb_path = adb_path or os.environ.get("ADB_PATH") or shutil.which("adb") or "adb"

    # -- low level ---------------------------------------------------------

    def _command(self, args: Sequence[str]) -> List[str]:
        command = [self.adb_path]
        if self.serial:
            command += ["-s", self.serial]
        return command + list(args)

    def run(self, *args: str, timeout: int = DEFAULT_TIMEOUT, check: bool = False) -> AdbResult:
        """Runs an adb command and returns its result."""
        command = self._command(args)
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise AdbError("adb timed out: " + " ".join(command)) from None
        result = AdbResult(completed.returncode, completed.stdout, completed.stderr)
        if check and not result.ok:
            raise AdbError("adb failed: " + " ".join(command) + "\n" + result.output)
        return result

    def shell(self, command: str, timeout: int = DEFAULT_TIMEOUT, check: bool = False) -> AdbResult:
        """Runs a shell command on the device."""
        return self.run("shell", command, timeout=timeout, check=check)

    # -- convenience -------------------------------------------------------

    def devices(self) -> List[str]:
        """Returns the serials of the connected devices."""
        result = self.run("devices", check=True)
        serials = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("List of devices"):
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                serials.append(parts[0])
        return serials

    def push(self, local: str, remote: str) -> AdbResult:
        return self.run("push", local, remote, timeout=300)

    def getprop(self, name: str) -> str:
        return self.shell(f"getprop {name}").stdout.strip()

    def install(self, apk: str) -> AdbResult:
        return self.run("install", "-r", apk, timeout=300)

    def packages(self) -> List[str]:
        result = self.shell("pm list packages")
        return [
            line.split(":", 1)[1].strip()
            for line in result.stdout.splitlines()
            if line.startswith("package:")
        ]
