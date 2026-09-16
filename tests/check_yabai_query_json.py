"""Compile the actual patched query functions with synthetic display/space data."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile


PRELUDE = r'''
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <assert.h>
#define TIME_FUNCTION
struct window { uint32_t id; };
struct view { uint64_t id; };
struct space_manager { int unused; } g_space_manager;
static int scenario;
static uint32_t displays[] = {1,2};
static uint64_t spaces[][2] = {{11,12},{21,22}};
uint32_t *display_manager_active_display_list(int *count) {
    *count = scenario == 0 ? 0 : 2;
    return scenario == 4 ? NULL : displays;
}
uint64_t *display_space_list(uint32_t id, int *count) {
    *count = scenario == 0 ? 0 : 2;
    return scenario == 3 && id == 1 ? NULL : spaces[id-1];
}
uint64_t *window_space_list(uint32_t id, int *count) {
    (void)id;
    return display_space_list(2, count);
}
struct view *space_manager_query_view(struct space_manager *manager, uint64_t id) {
    (void)manager;
    static struct view view;
    if (scenario == 2 || (scenario == 1 && (id == 11 || id == 22))) return NULL;
    view.id = id;
    return &view;
}
void view_serialize(FILE *rsp, struct view *view, uint64_t flags) {
    (void)flags;
    fprintf(rsp, "%llu", (unsigned long long)view->id);
}
void display_serialize(FILE *rsp, uint32_t id, uint64_t flags) {
    (void)flags;
    fprintf(rsp, "%u", id);
}
'''

MAIN = r'''
int main(void) {
    struct window window = {1};
    for (scenario = 0; scenario < 4; ++scenario) {
        assert(display_manager_query_displays(stdout, 0));
        assert(space_manager_query_spaces_for_displays(stdout, 0));
        assert(space_manager_query_spaces_for_display(stdout, 2, 0));
        assert(space_manager_query_spaces_for_window(stdout, &window, 0));
    }
    scenario = 4;
    FILE *response = tmpfile();
    assert(response);
    assert(!display_manager_query_displays(response, 0));
    assert(!space_manager_query_spaces_for_displays(response, 0));
    assert(ftell(response) == 0);
    fclose(response);
}
'''


def check(source):
    functions = []
    for name, symbols in {
        'display_manager.c': ['display_manager_query_displays'],
        'space_manager.c': ['space_manager_query_spaces_for_displays',
                            'space_manager_query_spaces_for_display',
                            'space_manager_query_spaces_for_window'],
    }.items():
        text = (source / 'src' / name).read_text()
        for symbol in symbols:
            start = text.index('bool ' + symbol + '(')
            functions.append(text[start:text.index('\n}', start) + 2])
    with tempfile.TemporaryDirectory(prefix='yabai-query-json-') as directory:
        root = Path(directory)
        (root / 'check.c').write_text(PRELUDE + '\n'.join(functions) + MAIN)
        subprocess.run(['xcrun', '--sdk', 'macosx', 'clang', '-std=c11', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=undefined', str(root / 'check.c'), '-o', str(root / 'check')], check=True)
        result = subprocess.check_output([str(root / 'check')], text=True)
    arrays = [json.loads(line) for line in result.splitlines()]
    expected = [[], [], [], [],
                [1, 2], [12, 21], [21], [21],
                [1, 2], [], [], [],
                [1, 2], [21, 22], [21, 22], [21, 22]]
    assert arrays == expected, (arrays, expected)
    print('16 native JSON cases passed, plus unavailable-display checks')


if __name__ == '__main__':
    check(Path(sys.argv[1]))
