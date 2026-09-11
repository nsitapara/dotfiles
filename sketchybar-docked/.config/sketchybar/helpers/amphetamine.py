"""Amphetamine controls shared by SketchyBar's click, hover, and power events."""

import fcntl
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time

STATE_DIR = Path.home() / ".local/state/sketchybar"
PAUSE_FILE = STATE_DIR / "amphetamine-pause.json"
POWER_FILE = STATE_DIR / "amphetamine-power.json"


def pointer_inside(rectangles, point):
    return any(
        rect["origin"][0] <= point[0] < rect["origin"][0] + rect["size"][0]
        and rect["origin"][1] <= point[1] < rect["origin"][1] + rect["size"][1]
        for rect in rectangles.values()
    )


def hover(watch=False):
    class Point(ctypes.Structure):
        _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]

    graphics = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
    foundation = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    graphics.CGEventCreate.argtypes = [ctypes.c_void_p]
    graphics.CGEventCreate.restype = ctypes.c_void_p
    graphics.CGEventGetLocation.argtypes = [ctypes.c_void_p]
    graphics.CGEventGetLocation.restype = Point
    foundation.CFRelease.argtypes = [ctypes.c_void_p]
    query = subprocess.run(
        [os.environ.get("BAR_NAME", "sketchybar"), "--query", "Amphetamine,Amphetamine"],
        capture_output=True, text=True, check=True, timeout=5,
    )
    rectangles = json.loads(query.stdout)["bounding_rects"]
    deadline = time.monotonic() + (10 if watch else 0)
    while True:
        event = graphics.CGEventCreate(None)
        if not event:
            return {"inside": False}
        point = graphics.CGEventGetLocation(event)
        foundation.CFRelease(event)
        inside = pointer_inside(rectangles, (point.x, point.y))
        if not inside or time.monotonic() >= deadline:
            return {"inside": inside}
        time.sleep(0.1)


def applescript(source):
    result = subprocess.run(
        ["/usr/bin/osascript", "-e", source],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Amphetamine did not respond")
    return result.stdout.strip()


def power_source():
    result = subprocess.run(
        ["/usr/bin/pmset", "-g", "batt"],
        capture_output=True, text=True, check=True, timeout=5,
    )
    if "'AC Power'" in result.stdout:
        return "AC"
    if "'Battery Power'" in result.stdout:
        return "BATTERY"
    raise RuntimeError("Could not determine power source")


def read_pause():
    if not PAUSE_FILE.exists():
        return None
    return json.loads(PAUSE_FILE.read_text())


def write_pause(power):
    temp = PAUSE_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps({"last_power": power}))
    os.replace(temp, PAUSE_FILE)


def clear_pause():
    PAUSE_FILE.unlink(missing_ok=True)


def sync_power(power=None):
    pause = read_pause()
    power = power or power_source()
    if power not in ("AC", "BATTERY"):
        raise ValueError("Unknown power source")
    previous = (
        json.loads(POWER_FILE.read_text())["last_power"]
        if POWER_FILE.exists()
        else pause["last_power"] if pause else None
    )
    connected = power == "AC" and previous == "BATTERY"
    resume = pause is not None and power == "AC" and pause["last_power"] == "BATTERY"
    if connected or resume:
        # A manual session takes priority over triggers until it ends. Only
        # hand off on connection, so a manual session started on AC survives.
        applescript('''
if application "Amphetamine" is running then
  tell application "Amphetamine"
    if (Triggers are enabled) or ''' + str(resume).lower() + ''' then
      if (session is active) and not (session is Trigger) then end session
    end if
  end tell
end if
''')
    if resume:
        applescript('tell application "Amphetamine" to enable Triggers')
        clear_pause()
    elif pause is not None and power != pause["last_power"]:
        write_pause(power)
    if previous != power:
        temp = POWER_FILE.with_suffix(".tmp")
        temp.write_text(json.dumps({"last_power": power}))
        os.replace(temp, POWER_FILE)


def status():
    result = applescript("""
if application "Amphetamine" is not running then return "-3|false"
tell application "Amphetamine"
  set secondsLeft to session time remaining
  set automaticEnabled to Triggers are enabled
end tell
return (secondsLeft as text) & "|" & (automaticEnabled as text)
""")
    seconds, automatic = result.split("|")
    # A user can also resume automatic mode directly in Amphetamine.
    if automatic == "true":
        clear_pause()
    return {
        "seconds": int(seconds),
        "automatic": automatic == "true",
        "paused_until_reconnect": read_pause() is not None,
    }


def toggle():
    sync_power()
    current = status()
    if current["seconds"] == -3:
        # No explicit options: follow the user's current Session Defaults.
        applescript('tell application "Amphetamine" to start new session')
    else:
        if current["automatic"]:
            # Persist the intent before disabling so a restart can still restore it.
            write_pause(power_source())
            applescript('tell application "Amphetamine" to disable Triggers')
        applescript('tell application "Amphetamine" to end session')
    return status()


def main():
    action = sys.argv[1]
    # Pointer watching must not hold the session lock or delay clicks/power events.
    if action in ("hover-check", "hover-watch"):
        print(json.dumps(hover(action == "hover-watch")))
        return
    if action not in ("status", "toggle", "sync"):
        raise ValueError("Unknown action")
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    # Serialize clicks and power events across both bar layouts.
    with (STATE_DIR / "amphetamine.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if action == "sync":
            sync_power(sys.argv[2] if len(sys.argv) > 2 else None)
            print("{}")
        elif action == "toggle":
            print(json.dumps(toggle()))
        else:
            sync_power()
            print(json.dumps(status()))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"error": str(error)}))
        sys.exit(1)
