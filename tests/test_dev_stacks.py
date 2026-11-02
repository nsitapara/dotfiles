import calendar
from contextlib import redirect_stdout
import io
import importlib.machinery
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
# Loading the extensionless script would leave a __pycache__ in the stowed bin package.
sys.dont_write_bytecode = True
loader = importlib.machinery.SourceFileLoader('dev_stacks', str(ROOT / 'bin/.local/bin/dev-stacks'))
spec = importlib.util.spec_from_loader('dev_stacks', loader)
assert spec is not None
stacks = importlib.util.module_from_spec(spec)
sys.modules['dev_stacks'] = stacks
loader.exec_module(stacks)

HOUR = 3600
NOW = 1_800_000_000.0


def request_line(epoch, path):
    stamp = time.strftime('%d/%b/%Y %H:%M:%S', time.gmtime(epoch))
    return f'[{stamp}] "POST {path} HTTP/1.1" 200 512\n'


class StateTests(unittest.TestCase):
    def test_state_follows_use_then_idle_time(self):
        cases = [
            # (idle seconds or None, busy reasons, expected)
            (2 * HOUR, [], 'active'),
            (6 * HOUR, [], 'idle'),
            (3 * 24 * HOUR, [], 'idle'),
            (None, [], 'idle'),
            (3 * 24 * HOUR, ['its Start Stack tab (just ndev) is running'], 'busy'),
        ]
        for idle, busy, expected in cases:
            with self.subTest(idle=idle, busy=busy):
                since = None if idle is None else NOW - idle
                stack = stacks.Stack(Path('/wt'), ['api'], since, list(busy))
                self.assertEqual(stacks.state(stack, 6, NOW), expected)


class LastRequestTests(unittest.TestCase):
    def test_newest_real_request_wins_over_later_probes_and_reloads(self):
        real = calendar.timegm((2026, 10, 31, 10, 41, 1, 0, 0, 0))
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp, 'api.log')
            log.write_text(
                request_line(real - HOUR, '/graphql/staff/')
                + request_line(real, '/graphql/auth/')
                + 'x' * 300 + '\n'
                + request_line(real + HOUR, '/')
                + request_line(real + 2 * HOUR, '/health/')
                + 'INFO 2026-11-02 17:21:12,658 middleware GQL query allowlist\n'
            )
            # A small block makes the request line straddle two reads.
            self.assertEqual(stacks.last_request(log, block=64), real)

    def test_missing_log_has_no_request(self):
        self.assertIsNone(stacks.last_request(Path('/nonexistent/api.log')))


class CollectTests(unittest.TestCase):
    def sleeper(self, *words):
        proc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)', *words])
        self.addCleanup(proc.kill)
        return proc.pid

    def test_only_live_services_count_and_a_running_ndev_marks_it_in_use(self):
        with tempfile.TemporaryDirectory() as tmp:
            worktree = Path(tmp).resolve()
            native = worktree / '.local/native'
            (native / 'run').mkdir(parents=True)
            (native / 'pg').mkdir()
            (native / 'log').mkdir()
            (native / 'run/api.pid').write_text(f'{self.sleeper("runserver")}\n')
            # A recycled pid: alive, but not a postgres process.
            (native / 'pg/postmaster.pid').write_text(f'{self.sleeper("unrelated")}\n')
            (native / 'run/celery.pid').write_text('999999\n')
            (native / 'ndev.pid').write_text(f'{self.sleeper("ndev")}\n')
            (native / 'log/api.log').write_text(request_line(NOW - 30 * 24 * HOUR, '/graphql/staff/'))
            time.sleep(1.1)  # ps reports start times to the second

            [stack] = stacks.collect([worktree])

            self.assertEqual(stack.services, ['api'])
            self.assertEqual(stack.busy, ['its Start Stack tab (just ndev) is running'])
            # The api started after the month-old request, so idle time counts from the start.
            self.assertLess(time.time() - stack.idle_since, 120)

    def test_worktree_without_live_services_is_not_a_stack(self):
        with tempfile.TemporaryDirectory() as tmp:
            worktree = Path(tmp)
            (worktree / '.local/native/run').mkdir(parents=True)
            (worktree / '.local/native/run/api.pid').write_text('999999\n')
            self.assertEqual(stacks.collect([worktree]), [])


class StopIdleTests(unittest.TestCase):
    def test_stops_only_stacks_idle_past_the_limit(self):
        now = time.time()
        found = [
            stacks.Stack(Path('/wt/old'), ['api'], now - 3 * 24 * HOUR),
            stacks.Stack(Path('/wt/recent'), ['api'], now - 2 * HOUR),
            stacks.Stack(Path('/wt/tab'), ['api'], now - 3 * 24 * HOUR, ['its Start Stack tab (just ndev) is running']),
        ]
        for argv, expected in [
            (['stop-idle'], ['old']),
            (['stop-idle', '1.5'], ['old', 'recent']),
        ]:
            with self.subTest(argv=argv):
                stopped = []
                with patch.object(stacks, 'collect', return_value=found), \
                        patch.object(stacks, 'stop_stack', side_effect=lambda s: (stopped.append(s.name), (True, s.name))[1]), \
                        redirect_stdout(io.StringIO()):
                    self.assertEqual(stacks.main(argv), 0)
                self.assertEqual(sorted(stopped), expected)


class StopTests(unittest.TestCase):
    def test_stop_runs_native_stack_stop_from_the_worktree(self):
        with tempfile.TemporaryDirectory() as tmp:
            worktree = Path(tmp).resolve()
            (worktree / 'scripts').mkdir()
            (worktree / 'scripts/native-stack.sh').write_text(
                'echo "$PWD $*" > called; echo "⏹  Native stack stopped"\n')
            ok, message = stacks.stop_stack(stacks.Stack(worktree, ['api'], NOW))
            self.assertTrue(ok)
            self.assertEqual((worktree / 'called').read_text().strip(), f'{worktree} stop')
            self.assertTrue(message.endswith('Native stack stopped'))


if __name__ == '__main__':
    unittest.main()
