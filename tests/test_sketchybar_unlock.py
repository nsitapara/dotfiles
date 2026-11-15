"""Compile the pinned native event handlers against a renderer spy.

Run with the SketchyBar source checkout path; no live desktop calls are made.
"""
import pathlib
import subprocess
import sys
import tempfile

def main():
    source = pathlib.Path(sys.argv[1]) / "src/event.c"
    text = source.read_text()

    def function(name):
        start = text.index("static void " + name + "(")
        opening = text.index("{", start)
        depth = 1
        end = opening + 1
        while depth:
            depth += (text[end] == "{") - (text[end] == "}")
            end += 1
        return text[start:end]

    wake = function("event_system_woke")
    # Before the fix, screenIsUnlocked routes straight to the wake handler.
    unlock = (function("event_system_unlocked") if "static void event_system_unlocked(" in text
              else wake.replace("event_system_woke", "event_system_unlocked"))
    harness = r'''
    #include <assert.h>
    #include <stdbool.h>
    #include <stddef.h>
    #include <stdio.h>
    struct bar_manager { bool needs_ordering; } g_bar_manager;
    static int rebuilt, refreshed, spaces, displays, notified, ordered;
    #define COMMAND_SUBSCRIBE_SYSTEM_WOKE "system_woke"
    void bar_manager_handle_system_woke(struct bar_manager* b) { rebuilt++; }
    void bar_manager_handle_space_change(struct bar_manager* b, bool forced) { assert(forced); spaces++; b->needs_ordering = false; }
    void bar_manager_handle_display_change(struct bar_manager* b) { displays++; b->needs_ordering = false; }
    void bar_manager_refresh(struct bar_manager* b, bool forced) { assert(forced); refreshed++; if (b->needs_ordering) ordered++; b->needs_ordering = false; }
    void bar_manager_custom_events_trigger(struct bar_manager* b, const char* name, void* env) { notified++; }
    ''' + wake + "\n" + unlock + r'''
    int main(void) {
        event_system_unlocked(NULL);
        assert(rebuilt == 0 && "unlock must preserve native bar/item windows");
        assert(refreshed == 1 && spaces == 1 && displays == 1 && notified == 1);
        assert(ordered == 1 && "forced unlock redraw must restore window ordering");
        event_system_unlocked(NULL);
        assert(rebuilt == 0 && refreshed == 2 && ordered == 2);
        event_system_woke(NULL);
        assert(rebuilt == 1 && "real sleep/wake must retain renderer recovery");
        puts("Native unlock preserves windows; real wake still recovers renderer");
    }
    '''
    with tempfile.TemporaryDirectory(prefix="sketchybar-unlock-test-") as folder:
        folder = pathlib.Path(folder)
        (folder / "test.c").write_text(harness)
        subprocess.run(["xcrun", "clang", "-std=c99", "-Wall", "-Werror", str(folder / "test.c"), "-o", str(folder / "test")], check=True)
        subprocess.run([str(folder / "test")], check=True)


if __name__ == "__main__":
    main()
