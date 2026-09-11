"""Verify destructive command boundaries without touching Docker or real worktrees."""

import contextlib
import importlib.util
import io
import gzip
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

spec = importlib.util.spec_from_file_location('snapshot', Path(__file__).with_name('db_snapshot.py'))
snapshot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snapshot)


class SnapshotTests(unittest.TestCase):
    def test_dev_cache_plan_uses_repository_key_and_configured_directory(self):
        root = Path('/checkout')
        key = 'a' * 64
        results = [subprocess.CompletedProcess([], 0, key + '\n', ''), subprocess.CompletedProcess([], 0, '/shared/cache\n', '')]
        with patch.object(snapshot, 'just', side_effect=results) as just:
            plan = snapshot.dev_cache_plan(root)
        self.assertEqual(plan['file'], Path('/shared/cache') / f'{key}.sql.gz')
        self.assertEqual(plan['args'], ['--report', '0'])
        self.assertEqual(just.call_args_list[0].args, (root, '--command', 'bash', 'scripts/bootstrap-cache-key.sh', str(root), '--report 0'))

    def test_development_cache_hit_restores_then_seeds_branch_without_bootstrap(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            cached = root / 'saved.sql.gz'
            cached.touch()
            plan = {'file': cached, 'key': 'cached-key', 'directory': root, 'args': ['--report', '0']}
            ports = {'API_PORT': '8123', 'DB_PORT': '5543', 'REDIS_PORT': '6480'}
            calls = []
            def recipe(root, environment, *args):
                self.assertEqual(environment['DB_CACHE_KEY'], 'cached-key')
                self.assertEqual(environment['API_PORT'], '8123')
                calls.append(args)
            with patch.object(snapshot, 'dev_recipe', side_effect=recipe), patch.object(snapshot, 'start_api', side_effect=lambda *args: calls.append(('start-api',))), patch.object(snapshot, 'migrate', side_effect=lambda *args: calls.append(('migrate',))), patch.object(snapshot, 'record_dev_state', side_effect=lambda *args: calls.append(('record-state',))):
                snapshot.restore_development_data(root, ports, plan)
            self.assertEqual(calls, [('restore-db',), ('start-api',), ('migrate',), ('seed-worktree',), ('record-state',)])

    def test_development_cache_miss_bootstraps_and_caches_before_branch_seed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan = {'file': root / 'missing.sql.gz', 'key': 'new-key', 'directory': root, 'args': ['--report', '0']}
            calls = []
            with patch.object(snapshot, 'dev_recipe', side_effect=lambda root, env, *args: calls.append(args)), patch.object(snapshot, 'start_api'), patch.object(snapshot, 'record_dev_state'):
                snapshot.restore_development_data(root, {'API_PORT': '8123'}, plan)
            self.assertEqual(calls, [('bootstrap', '--report', '0'), ('ensure-smoke-clinician',), ('dump-db',), ('seed-worktree',)])

    def test_failed_dev_restore_does_not_start_api_or_record_success(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            cached = root / 'cached.sql.gz'
            cached.touch()
            plan = {'file': cached, 'key': 'key', 'directory': root, 'args': ['--report', '0']}
            with patch.object(snapshot, 'dev_recipe', side_effect=RuntimeError('restore failed')), patch.object(snapshot, 'start_api') as start, patch.object(snapshot, 'record_dev_state') as record:
                with self.assertRaisesRegex(RuntimeError, 'restore failed'):
                    snapshot.restore_development_data(root, {}, plan)
                start.assert_not_called()
                record.assert_not_called()

    def test_dev_state_matches_just_dev_volume_identity_format(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            container = {'Id': 'container-id', 'Mounts': [{'Destination': '/var/lib/postgresql/data', 'Source': '/docker/volume/data'}]}
            with patch.object(snapshot, 'compose', return_value=subprocess.CompletedProcess([], 0, 'container-id', '')), patch.object(snapshot, 'output', return_value=json.dumps([container])):
                snapshot.record_dev_state(root, 'cache-key')
            self.assertEqual((root / '.local/dev-db-state').read_text(), 'cache-key /docker/volume/data\n')

    def test_remove_restores_dev_data_with_writers_stopped_and_no_frontend_launch(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / snapshot.OVERRIDE).write_text(snapshot.MARKER + 'services: {}\n')
            plan = {'key': 'cache-key'}
            ports = {'API_PORT': '8123'}
            with patch.object(snapshot, 'target_root', return_value=root), patch.object(snapshot, 'output', return_value=''), patch.object(snapshot, 'config', return_value={'services': {'db': {'image': 'postgres:17.4'}}}), patch.object(snapshot, 'dev_cache_plan', return_value=plan), patch.object(snapshot, 'replace_database', return_value=ports) as replace, patch.object(snapshot, 'restore_development_data') as restore, patch.object(snapshot, 'compose_with_ports') as compose, patch.object(snapshot, 'just') as just:
                snapshot.remove()
                replace.assert_called_once_with(root, start_api_after_reset=False)
                restore.assert_called_once_with(root, ports, plan)
                compose.assert_called_once_with(root, ports, 'up', '-d', '--no-deps', 'celery')
                just.assert_not_called()

    def test_backend_readiness_retries_connection_reset_during_startup(self):
        ready = HTTPError('http://127.0.0.1:8000/graphql/type/', 400, 'Bad Request', {}, None)
        with patch.object(snapshot, 'urlopen', side_effect=[ConnectionResetError(54, 'Connection reset by peer'), ready]) as request, patch.object(snapshot.time, 'sleep') as sleep:
            snapshot.wait_for_backend('8000')
            self.assertEqual(request.call_count, 2)
            sleep.assert_called_once_with(1)

    def test_backend_readiness_keeps_timeout_when_connections_keep_resetting(self):
        with patch.object(snapshot, 'urlopen', side_effect=ConnectionResetError(54, 'Connection reset by peer')), patch.object(snapshot.time, 'sleep'), patch.object(snapshot.time, 'monotonic', side_effect=[0, 0, 121]):
            with self.assertRaisesRegex(RuntimeError, 'did not start on its existing port 8000'):
                snapshot.wait_for_backend('8000')

    def test_progress_reports_activity_and_size_before_step_finishes(self):
        progress_seen = threading.Event()
        terminal = io.StringIO()
        def detail():
            progress_seen.set()
            return 'compressed archive: 12.0 MiB written'
        with contextlib.redirect_stdout(terminal):
            with snapshot.build_step('Compressing database files', detail=detail, interval=0.01):
                self.assertTrue(progress_seen.wait(2), 'No live progress appeared while the step was running.')
        text = terminal.getvalue()
        self.assertIn('still running | elapsed', text)
        self.assertIn('compressed archive: 12.0 MiB written', text)
        self.assertLess(text.index('still running'), text.index('done in'))
        self.assertFalse(any(t.name == 'prod-build-progress' for t in threading.enumerate()))

    def test_failed_step_stops_timer_and_never_reports_success(self):
        terminal = io.StringIO()
        with contextlib.redirect_stdout(terminal):
            with self.assertRaisesRegex(RuntimeError, 'test failure'):
                with snapshot.build_step('Restoring production SQL dump', interval=0.01):
                    raise RuntimeError('test failure')
        self.assertIn('failed in', terminal.getvalue())
        self.assertNotIn('done in', terminal.getvalue())
        self.assertFalse(any(t.name == 'prod-build-progress' for t in threading.enumerate()))

    def test_build_restores_dump_without_accessing_existing_compose_stack(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'docker').mkdir()
            (root / 'docker' / 'Dockerfile.db').write_text('FROM postgres:17.4-alpine3.21\nENV PGDATA=/pgdata\nADD pgdata.tgz /pgdata/\n')
            with gzip.open(root / 'db.sql.gz', 'wb') as f:
                f.write(b'-- PostgreSQL database dump\nCREATE TABLE proof (id integer);\n')
            commands = []
            def command(args, *a, **kw):
                commands.append(args)
                return subprocess.CompletedProcess(args, 0, '', '')
            with patch.object(snapshot, 'MAIN', root), patch.object(snapshot, 'compose', side_effect=AssertionError('prod_build must not access an existing Compose stack')), patch.object(snapshot, 'output', return_value='dev'), patch.object(snapshot, 'image_id', side_effect=['old-id', 'new-id']), patch.object(snapshot, 'cleanup_previous_image'), patch.object(snapshot, 'run', side_effect=command):
                snapshot.create(snapshot.DEFAULT_IMAGE)
            restore = next(i for i, c in enumerate(commands) if 'psql' in ' '.join(c))
            build = next(i for i, c in enumerate(commands) if c[:2] == ['docker', 'build'])
            publish = next(i for i, c in enumerate(commands) if c[:2] == ['docker', 'tag'])
            self.assertLess(restore, build)
            self.assertLess(build, publish)
            start = next(c for c in commands if c[:2] == ['docker', 'run'])
            self.assertIn('none', start)
            self.assertNotIn('-p', start)
            self.assertTrue(any(c[:3] == ['docker', 'rm', '-fv'] for c in commands))

    def test_main_worktree_is_allowed_when_it_owns_its_containers(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            for name in ('.env.local', 'compose.yml', 'justfile'):
                (root / name).touch()
            containers = json.dumps([{'Config': {'Labels': {'com.docker.compose.project.working_dir': str(root)}}}])
            with patch.object(snapshot, 'MAIN', root), patch.object(snapshot, 'output', side_effect=[str(root), '/same/git', '/same/git', 'db-id', containers]), patch.object(snapshot, 'config', return_value={'name': 'main-project'}) as config:
                self.assertEqual(snapshot.target_root(), root)
                config.assert_called_once_with(root)

    def test_main_worktree_cannot_use_another_checkout_containers(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            for name in ('.env.local', 'compose.yml', 'justfile'):
                (root / name).touch()
            containers = json.dumps([{'Config': {'Labels': {'com.docker.compose.project.working_dir': '/another/checkout'}}}])
            with patch.object(snapshot, 'MAIN', root), patch.object(snapshot, 'output', side_effect=[str(root), '/same/git', '/same/git', 'db-id', containers]), patch.object(snapshot, 'config', return_value={'name': 'main-project'}):
                with self.assertRaisesRegex(RuntimeError, 'belongs to another directory'):
                    snapshot.target_root()

    def test_shared_project_name_is_protected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name in ('.env.local', 'compose.yml', 'justfile'):
                (root / name).touch()
            with patch.object(snapshot, 'output', side_effect=[d, '/same/git', '/same/git']), patch.object(snapshot, 'config', return_value={'name': 'shared'}):
                with self.assertRaisesRegex(RuntimeError, 'shares the main'):
                    snapshot.target_root()

    def test_existing_override_is_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            path = root / snapshot.OVERRIDE
            path.write_text('services: {}\n')
            with self.assertRaisesRegex(RuntimeError, 'not owned'):
                snapshot.managed_override(root)
            self.assertEqual(path.read_text(), 'services: {}\n')

    def test_missing_image_never_changes_worktree(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with patch.object(snapshot, 'target_root', return_value=root), patch.object(snapshot, 'run', side_effect=subprocess.CalledProcessError(1, 'docker')), patch.object(snapshot, 'replace_database') as replace:
                with self.assertRaises(subprocess.CalledProcessError):
                    snapshot.seed(snapshot.DEFAULT_IMAGE)
                self.assertFalse((root / snapshot.OVERRIDE).exists())
                replace.assert_not_called()

    def test_ignored_override_is_rolled_back_before_reset(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with patch.object(snapshot, 'target_root', return_value=root), patch.object(snapshot, 'run', return_value=subprocess.CompletedProcess([], 0, 'sql-dump\n', '')), patch.object(snapshot, 'output', return_value=''), patch.object(snapshot, 'config', return_value={'services': {'db': {'image': 'postgres:17'}}}), patch.object(snapshot, 'replace_database') as replace:
                with self.assertRaisesRegex(RuntimeError, 'did not select'):
                    snapshot.seed(snapshot.DEFAULT_IMAGE)
                self.assertFalse((root / snapshot.OVERRIDE).exists())
                replace.assert_not_called()

    def test_remove_rejects_nonplain_base_before_reset(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            path = root / snapshot.OVERRIDE
            original = snapshot.MARKER + 'services: {}\n'
            path.write_text(original)
            with patch.object(snapshot, 'target_root', return_value=root), patch.object(snapshot, 'output', return_value=''), patch.object(snapshot, 'config', return_value={'services': {'db': {'image': 'saved:data'}}}), patch.object(snapshot, 'replace_database') as replace:
                with self.assertRaisesRegex(RuntimeError, 'not plain Postgres'):
                    snapshot.remove()
                self.assertEqual(path.read_text(), original)
                replace.assert_not_called()

    def test_backend_ports_use_actual_bindings_without_rewriting_frontend_settings(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            content = 'API_PORT=8000\nDB_PORT=5432\nREDIS_PORT=6379\nSTAFF_PORT=3014\nVITE_API_URL=http://localhost:8123\n'
            (root / '.env.ports').write_text(content)
            containers = [json.dumps([{'HostConfig': {'PortBindings': {key: [{'HostPort': value}]}}}]) for key, value in [('8000/tcp', '8123'), ('5432/tcp', '5543'), ('6379/tcp', '6480')]]
            with patch.object(snapshot, 'compose', return_value=subprocess.CompletedProcess([], 0, 'container-id', '')), patch.object(snapshot, 'output', side_effect=containers):
                self.assertEqual(snapshot.backend_ports(root), {'API_PORT': '8123', 'DB_PORT': '5543', 'REDIS_PORT': '6480'})
            self.assertEqual((root / '.env.ports').read_text(), content)

    def test_backend_ports_can_reuse_saved_ports_when_containers_are_absent(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / '.env.ports').write_text('API_PORT=8123\nDB_PORT=5543\nREDIS_PORT=6480\n')
            with patch.object(snapshot, 'compose', return_value=subprocess.CompletedProcess([], 0, '', '')):
                self.assertEqual(snapshot.backend_ports(root), {'API_PORT': '8123', 'DB_PORT': '5543', 'REDIS_PORT': '6480'})

    def test_reset_preserves_ports_and_only_starts_backend_services(self):
        calls = []
        ports = {'API_PORT': '8123', 'DB_PORT': '5543', 'REDIS_PORT': '6480'}
        with patch.object(snapshot, 'backend_ports', return_value=ports), patch.object(snapshot, 'compose', side_effect=lambda root, *args: calls.append(('compose', *args))), patch.object(snapshot, 'compose_with_ports', side_effect=lambda root, saved, *args: calls.append(('compose_with_ports', saved, *args))), patch.object(snapshot, 'wait_for_backend') as wait, patch.object(snapshot, 'just') as just:
            self.assertEqual(snapshot.replace_database(Path('/test')), ports)
            just.assert_not_called()
            wait.assert_called_once_with('8123')
        self.assertEqual(calls, [('compose', 'stop', 'api', 'celery'), ('compose', 'rm', '-fsv', 'db', 'redis'), ('compose_with_ports', ports, 'up', '-d', '--wait', '--wait-timeout', '120', 'db', 'redis'), ('compose_with_ports', ports, 'up', '-d', '--no-deps', 'api')])

    def test_missing_ports_stop_reset_before_any_mutation(self):
        with patch.object(snapshot, 'backend_ports', side_effect=RuntimeError('missing ports')), patch.object(snapshot, 'compose') as compose:
            with self.assertRaisesRegex(RuntimeError, 'missing ports'):
                snapshot.replace_database(Path('/test'))
            compose.assert_not_called()

    def test_seed_returns_without_launching_frontends(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ports = {'API_PORT': '8123', 'DB_PORT': '5543', 'REDIS_PORT': '6480'}
            with patch.object(snapshot, 'target_root', return_value=root), patch.object(snapshot, 'run', return_value=subprocess.CompletedProcess([], 0, 'sql-dump\n', '')), patch.object(snapshot, 'output', return_value=''), patch.object(snapshot, 'config', return_value={'services': {'db': {'image': snapshot.DEFAULT_IMAGE}}}), patch.object(snapshot, 'exclude_override'), patch.object(snapshot, 'replace_database', return_value=ports), patch.object(snapshot, 'migrate') as migrate, patch.object(snapshot, 'compose_with_ports') as compose, patch.object(snapshot, 'just') as just:
                snapshot.seed(snapshot.DEFAULT_IMAGE)
                migrate.assert_called_once_with(root)
                compose.assert_called_once_with(root, ports, 'up', '-d', '--no-deps', 'celery')
                just.assert_not_called()

    def test_no_pending_migrations_never_prompts(self):
        result = subprocess.CompletedProcess([], 0, '', '')
        with patch.object(snapshot, 'compose', return_value=result), patch('builtins.input') as prompt, patch.object(snapshot, 'just') as just:
            snapshot.migrate(Path('/test'))
            prompt.assert_not_called()
            just.assert_not_called()

    def test_pending_migrations_run_automatically_without_input(self):
        result = subprocess.CompletedProcess([], 1, '', '')
        with patch.object(snapshot, 'compose', return_value=result) as compose, patch('builtins.input', side_effect=AssertionError('Migration must not prompt')):
            snapshot.migrate(Path('/test'))
            self.assertEqual(compose.call_args.args[1:], ('exec', '-T', 'api', 'uv', 'run', 'manage.py', 'migrate', '--noinput'))

    def test_missing_dump_does_not_touch_docker(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(snapshot, 'MAIN', Path(d)), patch.object(snapshot, 'run') as run:
                with self.assertRaisesRegex(RuntimeError, 'missing or empty'):
                    snapshot.create(snapshot.DEFAULT_IMAGE)
                run.assert_not_called()

    def test_seed_refuses_old_running_database_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with patch.object(snapshot, 'target_root', return_value=root), patch.object(snapshot, 'run', return_value=subprocess.CompletedProcess([], 0, '<no value>\n', '')), patch.object(snapshot, 'replace_database') as replace:
                with self.assertRaisesRegex(RuntimeError, 'isolated builder'):
                    snapshot.seed(snapshot.DEFAULT_IMAGE)
                self.assertFalse((root / snapshot.OVERRIDE).exists())
                replace.assert_not_called()

    def test_failed_restore_cleans_temporary_database_without_publishing(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'docker').mkdir()
            (root / 'docker' / 'Dockerfile.db').write_text('FROM postgres:17.4-alpine3.21\n')
            with gzip.open(root / 'db.sql.gz', 'wb') as f:
                f.write(b'-- PostgreSQL database dump\ninvalid SQL;\n')
            commands = []
            def command(args, *a, **kw):
                commands.append(args)
                return subprocess.CompletedProcess(args, 1 if args[0] == 'bash' else 0, '', '')
            with patch.object(snapshot, 'MAIN', root), patch.object(snapshot, '__file__', str(root / 'db_snapshot.py')), patch.object(snapshot, 'image_id', return_value='old-id'), patch.object(snapshot, 'run', side_effect=command):
                with self.assertRaisesRegex(RuntimeError, 'restore failed'):
                    snapshot.create(snapshot.DEFAULT_IMAGE)
            self.assertFalse(any(c[:2] in (['docker', 'build'], ['docker', 'tag']) for c in commands))
            self.assertTrue(any(c[:3] == ['docker', 'rm', '-fv'] for c in commands))

    def test_cleanup_preserves_images_in_use(self):
        with patch.object(snapshot, 'output', return_value='container-id'), patch.object(snapshot, 'run') as run:
            snapshot.cleanup_previous_image('old-id', 'new-id')
            run.assert_not_called()

    def test_cleanup_removes_only_specific_unused_image_without_force(self):
        with patch.object(snapshot, 'output', return_value=''), patch.object(snapshot, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')) as run:
            snapshot.cleanup_previous_image('old-id', 'new-id')
            run.assert_called_once_with(['docker', 'image', 'rm', 'old-id'], snapshot.MAIN, capture=True, check=False)

    def test_cleanup_preserves_current_image(self):
        with patch.object(snapshot, 'run') as run, patch.object(snapshot, 'output') as output:
            snapshot.cleanup_previous_image('same-id', 'same-id')
            snapshot.cleanup_previous_image(None, 'new-id')
            run.assert_not_called()
            output.assert_not_called()


class SqlSnapshotTests(unittest.TestCase):
    def fixture(self, root, name='checkpoint'):
        directory = root / '.db-snapshots'
        directory.mkdir(exist_ok=True)
        with gzip.open(directory / f'{name}.sql.gz', 'wb') as stream:
            stream.write(b'-- PostgreSQL database dump\nSELECT 1;\n')
        (directory / f'{name}.meta.json').write_text('{}')
        return directory

    def test_latest_and_generated_names_stay_in_worktree(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / 'first'
            second = root / 'second'
            first.mkdir(); second.mkdir()
            directory = self.fixture(first, 'branch-1')
            self.fixture(second, 'different')
            self.assertEqual(snapshot.select_snapshot(first, directory, None), 'branch-1')
            with patch.object(snapshot, 'output', return_value='branch'):
                self.assertEqual(snapshot.select_snapshot(first, directory, None, saving=True), 'branch-2')
            for name in ('../escape', '-flag', 'a/b', 'a;echo', 'a$(whoami)', ''):
                with self.assertRaises(RuntimeError):
                    snapshot.snapshot_name(name)

    def test_directory_ignores_shared_environment_and_detaches_shared_symlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.dict(snapshot.os.environ, {'DB_SNAPSHOTS_DIR': '/shared'}), patch.object(snapshot, 'output', return_value='.git/info/exclude'):
                self.assertEqual(snapshot.snapshot_directory(root), root / '.db-snapshots')
                self.assertIn('/.db-snapshots/', (root / '.git/info/exclude').read_text())
            (root / '.db-snapshots').rmdir()
            shared = root / 'shared'
            shared.mkdir()
            (shared / 'keep.sql.gz').write_bytes(b'preserved shared data')
            (root / '.db-snapshots').symlink_to(shared)
            with patch.object(snapshot, 'output', return_value='.git/info/exclude'):
                directory = snapshot.snapshot_directory(root)
            self.assertFalse(directory.is_symlink())
            self.assertEqual(list(directory.iterdir()), [])
            self.assertEqual((shared / 'keep.sql.gz').read_bytes(), b'preserved shared data')

    def test_lock_rejects_concurrent_commands(self):
        with tempfile.TemporaryDirectory() as temp:
            with snapshot.snapshot_lock(Path(temp)):
                with self.assertRaisesRegex(RuntimeError, 'already running'):
                    with snapshot.snapshot_lock(Path(temp)):
                        self.fail('Acquired duplicate lock')

    def test_failed_save_preserves_existing_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory = self.fixture(root)
            before = {p.name: p.read_bytes() for p in directory.iterdir()}
            with patch.object(snapshot, 'target_root', return_value=root), patch.object(snapshot, 'snapshot_directory', return_value=directory), patch.object(snapshot, 'dev_recipe', side_effect=RuntimeError('dump failed')):
                with self.assertRaisesRegex(RuntimeError, 'dump failed'):
                    snapshot.save_snapshot('checkpoint')
            self.assertEqual(before, {p.name: p.read_bytes() for p in directory.iterdir() if p.name != '.lock'})

    def test_save_uses_existing_recipe_with_private_staging(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory = self.fixture(root)
            def recipe(checkout, environment, command, name):
                self.assertEqual(checkout, root)
                self.assertEqual(command, 'save-snapshot')
                staging = Path(environment['DB_SNAPSHOTS_DIR'])
                self.assertEqual(staging.parent, directory)
                with gzip.open(staging / f'{name}.sql.gz', 'wb') as stream:
                    stream.write(b'new dump')
                (staging / f'{name}.meta.json').write_text('{"name":"checkpoint"}')
            with patch.object(snapshot, 'target_root', return_value=root), patch.object(snapshot, 'snapshot_directory', return_value=directory), patch.object(snapshot, 'dev_recipe', side_effect=recipe):
                snapshot.save_snapshot('checkpoint')
            with gzip.open(directory / 'checkpoint.sql.gz') as stream:
                self.assertEqual(stream.read(), b'new dump')
            self.assertEqual((directory / 'checkpoint.sql.gz').stat().st_mode & 0o777, 0o600)
            self.assertFalse(list(directory.glob('.saving-*')))

    def test_invalid_archive_blocks_before_backend_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory = self.fixture(root)
            (directory / 'checkpoint.sql.gz').write_text('broken archive')
            with patch.object(snapshot, 'target_root', return_value=root), patch.object(snapshot, 'snapshot_directory', return_value=directory), patch.object(snapshot, 'compose') as compose, patch.object(snapshot, 'backend_ports') as ports:
                with self.assertRaises(subprocess.CalledProcessError):
                    snapshot.load_snapshot('checkpoint')
                compose.assert_not_called()
                ports.assert_not_called()

    def test_incompatible_or_broken_metadata_cannot_be_forced(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory = self.fixture(root)
            for code, error in ((2, ''), (1, 'Traceback: bad metadata'), (5, 'unexpected error')):
                with self.subTest(code=code), patch.object(snapshot, 'target_root', return_value=root), patch.object(snapshot, 'snapshot_directory', return_value=directory), patch.object(snapshot, 'just', return_value=subprocess.CompletedProcess([], code, '', error)), patch.object(snapshot, 'compose') as compose:
                    with self.assertRaisesRegex(RuntimeError, 'compatibility check failed'):
                        snapshot.load_snapshot('checkpoint', force=True)
                    compose.assert_not_called()

    def test_restore_order_migrations_and_no_frontend(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory = self.fixture(root)
            state = root / '.local/dev-db-state'
            state.parent.mkdir(); state.write_text('old-state')
            calls = []
            ports = {'API_PORT': '8123', 'DB_PORT': '5543', 'REDIS_PORT': '6480'}
            def just(checkout, *args, **kwargs):
                calls.append(('just', *args))
                return subprocess.CompletedProcess([], 0, '', '')
            with patch.object(snapshot, 'target_root', return_value=root), patch.object(snapshot, 'snapshot_directory', return_value=directory), patch.object(snapshot, 'backend_ports', return_value=ports), patch.object(snapshot, 'just', side_effect=just), patch.object(snapshot, 'compose', side_effect=lambda root, *args, **kwargs: calls.append(('compose', *args))), patch.object(snapshot, 'compose_with_ports', side_effect=lambda root, saved, *args: calls.append(('ports', saved, *args))), patch.object(snapshot, 'start_api', side_effect=lambda *args: calls.append(('start-api',))), patch.object(snapshot, 'migrate', side_effect=lambda *args: calls.append(('migrate',))):
                snapshot.load_snapshot()
            self.assertFalse(state.exists())
            stop = calls.index(('compose', 'stop', 'api', 'celery'))
            drop = next(i for i, call in enumerate(calls) if 'dropdb' in call)
            restore = next(i for i, call in enumerate(calls) if any('ON_ERROR_STOP=1' in str(part) for part in call))
            self.assertLess(stop, drop)
            self.assertLess(drop, restore)
            self.assertLess(restore, calls.index(('start-api',)))
            self.assertLess(calls.index(('start-api',)), calls.index(('migrate',)))
            self.assertEqual(calls[-1], ('ports', ports, 'up', '-d', '--no-deps', 'celery'))
            self.assertFalse(any('pnpm' in str(call) for call in calls))

    def test_list_reuses_just_recipe_in_current_worktree(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory = self.fixture(root)
            with patch.object(snapshot, 'target_root', return_value=root), patch.object(snapshot, 'snapshot_directory', return_value=directory), patch.object(snapshot, 'dev_recipe') as recipe:
                snapshot.list_snapshots()
            recipe.assert_called_once_with(root, {'DB_SNAPSHOTS_DIR': str(directory)}, 'list-snapshots')


class WorktreeSetupTests(unittest.TestCase):
    def test_setup_keeps_shared_cache_but_detaches_named_snapshots(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            main = root / 'main'
            worktree = root / 'feature'
            cache = root / 'cache'
            cache.mkdir()
            (cache / 'existing.sql.gz').write_bytes(b'cached baseline')
            subprocess.run(['git', 'init', '-q', str(main)], check=True)
            subprocess.run(['git', '-c', 'user.name=Snapshot Test', '-c', 'user.email=snapshot-test@example.invalid', 'commit', '-q', '--allow-empty', '-m', 'fixture'], cwd=main, check=True)
            subprocess.run(['git', 'worktree', 'add', '-q', '--detach', str(worktree)], cwd=main, check=True)
            shared = main / '.db-snapshots'
            shared.mkdir()
            (shared / 'keep.sql.gz').write_bytes(b'shared checkpoint')
            (worktree / '.db-snapshots').symlink_to(shared)
            environment = {**snapshot.os.environ, 'DB_CACHE_DIR': str(cache), 'DB_SNAPSHOTS_DIR': str(shared)}
            script = Path(__file__).with_name('link-worktree-db.sh')
            for _ in range(2):
                result = subprocess.run(['bash', str(script)], cwd=worktree, env=environment, text=True, capture_output=True, check=True)
                self.assertIn('Shared just dev cache:', result.stdout)
                self.assertIn('Worktree SQL checkpoints:', result.stdout)
                self.assertFalse((worktree / '.db-snapshots').is_symlink())
                self.assertTrue((worktree / '.db-snapshots').is_dir())
                self.assertEqual((worktree / '.db-cache').resolve(), cache.resolve())
                self.assertEqual((cache / 'existing.sql.gz').read_bytes(), b'cached baseline')
                self.assertEqual((shared / 'keep.sql.gz').read_bytes(), b'shared checkpoint')


if __name__ == '__main__':
    with contextlib.redirect_stdout(io.StringIO()):
        unittest.main()
