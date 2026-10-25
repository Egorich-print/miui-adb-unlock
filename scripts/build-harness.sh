#!/usr/bin/env bash
# Собирает harness.jar: Java-класс, который выполняется штатным
# `uiautomator runtest` на устройстве и дёргает accessibility-действия.
#
# Требуется Android SDK (build-tools + platform) и JDK 11+.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SDK="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-$HOME/Library/Android/sdk}}"

if [ ! -d "$SDK" ]; then
  echo "Android SDK not found: $SDK" >&2
  echo "Set ANDROID_SDK_ROOT or ANDROID_HOME." >&2
  exit 1
fi

BT="$(ls -d "$SDK"/build-tools/* 2>/dev/null | sort -V | tail -1)"
# Предпочитаем платформу, близкую к целевым устройствам (API 28), иначе — последнюю.
AJ=""
for candidate in "$SDK"/platforms/android-28 "$SDK"/platforms/android-29 "$SDK"/platforms/android-3*; do
  if [ -f "$candidate/android.jar" ]; then AJ="$candidate/android.jar"; break; fi
done
if [ -z "$AJ" ]; then
  AJ="$(ls -d "$SDK"/platforms/android-* 2>/dev/null | sort -V | tail -1)/android.jar"
fi
if [ -z "$BT" ] || [ ! -f "$AJ" ]; then
  echo "Need build-tools and a platform in $SDK" >&2
  exit 1
fi

echo "build-tools: $(basename "$BT")"
echo "platform:    $(basename "$(dirname "$AJ")")"

WORK="$ROOT/harness/build"
rm -rf "$WORK"
mkdir -p "$WORK/classes"

javac --release 11 -nowarn \
  -cp "$AJ" \
  -d "$WORK/classes" \
  "$ROOT/harness/stubs/com/android/uiautomator/testrunner/UiAutomatorTestCase.java" \
  "$ROOT/harness/java/com/miuiadblock/A11yDriver.java"

"$BT/d8" --release --min-api 28 --lib "$AJ" --output "$WORK" \
  "$WORK"/classes/com/miuiadblock/*.class

( cd "$WORK" && jar cf "$ROOT/harness/miui-a11y.jar" classes.dex )

echo "built: harness/miui-a11y.jar ($(wc -c < "$ROOT/harness/miui-a11y.jar") bytes)"
