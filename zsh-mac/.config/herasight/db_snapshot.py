#!/usr/bin/env python3
"""Local database image helpers for HeraSight worktrees."""

import argparse
from contextlib import contextmanager
import gzip
import fcntl
import re
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
import uuid

MAIN = Path('/Users/nishsitapara/Documents/web-platform')
DEFAULT_IMAGE = 'herasight-db:prod-baseline'
OVERRIDE = 'compose.override.yaml'
MARKER = '# Managed by local HeraSight snapshot commands.\n'
PROVENANCE_LABEL = 'io.herasight.prod-baseline.source'
BUILD_BASE_IMAGE = 'postgres:17.11-alpine'


def duration(seconds):
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f'{hours}h {minutes:02d}m {seconds:02d}s'
    return f'{minutes}m {seconds:02d}s'


@contextmanager
def build_step(label, detail=None, interval=10):
    started = time.monotonic()
    stopped = threading.Event()
    print(f'--> {label}', flush=True)

    def heartbeat():
        while not stopped.wait(interval):
            extra = ''
            if detail:
                try:
                    extra = f' | {detail()}'
                except OSError:
                    pass
            print(f'    {label}: still running | elapsed {duration(time.monotonic() - started)}{extra}', flush=True)

    timer = threading.Thread(target=heartbeat, name='prod-build-progress', daemon=True)
    timer.start()
    outcome = 'done'
    try:
        yield
    except BaseException as error:
        outcome = 'interrupted' if isinstance(error, KeyboardInterrupt) else 'failed'
        raise
    finally:
        stopped.set()
        timer.join()
        print(f'<-- {label}: {outcome} in {duration(time.monotonic() - started)}', flush=True)


def run(args, cwd, capture=False, check=True, log=None):
    return subprocess.run(args, cwd=cwd, text=True, check=check,
                          stdout=subprocess.PIPE if capture else log,
                          stderr=subprocess.PIPE if capture else log)


def output(args, cwd):
    return run(args, cwd, capture=True).stdout.strip()


def just(root, *args, **kwargs):
    return run(['just', *args], root, **kwargs)


def compose(root, *args, **kwargs):
    return just(root, '--command', 'docker', 'compose', *args, **kwargs)


def config(root):
    return json.loads(compose(root, 'config', '--format', 'json', capture=True).stdout)


def fail(message):
    raise RuntimeError(message)


def target_root():
    root = Path(output(['git', 'rev-parse', '--show-toplevel'], Path.cwd())).resolve()
    def common(path):
        value = output(['git', 'rev-parse', '--git-common-dir'], path)
        return (path / value).resolve()
    if common(root) != common(MAIN):
        fail('This directory is not a worktree of the main web-platform repository.')
    for filename in ('.env.local', 'compose.yml', 'justfile'):
        if not (root / filename).exists():
            fail(f'Missing {filename}. Complete normal worktree setup first.')
    target = config(root)
    if root != MAIN.resolve() and target['name'] == config(MAIN)['name']:
        fail('This worktree shares the main Compose project name. Give it a unique COMPOSE_PROJECT_NAME in .env.local first.')
    ids = output(['docker', 'ps', '-aq', '--filter', f'label=com.docker.compose.project={target["name"]}'], root)
    if ids:
        containers = json.loads(output(['docker', 'inspect', *ids.split()], root))
        for container in containers:
            labels = container['Config'].get('Labels') or {}
            owner = labels.get('com.docker.compose.project.working_dir')
            if not owner or Path(owner).resolve() != root:
                fail(f'Compose project {target["name"]} belongs to another directory. Use a unique COMPOSE_PROJECT_NAME.')
    print(f'Worktree: {root}\nCompose project: {target["name"]}', flush=True)
    return root


def managed_override(root, required=False):
    p = root / OVERRIDE
    if (root / 'compose.override.yml').exists():
        fail('An existing compose.override.yml needs to be reconciled before using these helpers.')
    if p.exists() and not p.read_text().startswith(MARKER):
        fail('An existing compose.override.yaml is not owned by these helpers. It has been left unchanged.')
    if required and not p.exists():
        fail('No local snapshot override is installed here. Nothing was removed.')
    return p


def exclude_override(root):
    path = Path(output(['git', 'rev-parse', '--git-path', 'info/exclude'], root))
    if not path.is_absolute():
        path = root / path
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text() if path.exists() else ''
    if f'/{OVERRIDE}' not in text.splitlines():
        with path.open('a') as f:
            f.write(f'\n/{OVERRIDE}\n')


def image_id(image):
    result = run(['docker', 'image', 'inspect', '--format', '{{.Id}}', image],
                 MAIN, capture=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def cleanup_previous_image(previous, current):
    if not previous or previous == current:
        return
    users = output(['docker', 'ps', '-aq', '--filter', f'ancestor={previous}'], MAIN)
    if users:
        print('The previous image is still used by existing containers; they remain unchanged.', flush=True)
        return
    # No force: Docker also protects images with other tags or dependent images.
    result = run(['docker', 'image', 'rm', previous], MAIN, capture=True, check=False)
    if result.returncode == 0:
        print('Removed the unused previous baseline image.', flush=True)
    else:
        print('The new baseline is saved. Docker retained the previous image because it could not be removed safely.', flush=True)


def create(image):
    started = time.monotonic()
    dump = MAIN / 'db.sql.gz'
    if not dump.is_file() or dump.stat().st_size == 0:
        fail(f'Production dump is missing or empty: {dump}. No containers were changed.')
    with gzip.open(dump, 'rb') as f:
        header = f.read(512)
    if b'PostgreSQL database dump' not in header or header.startswith(b'PGDMP'):
        fail(f'{dump} must contain a gzip-compressed PostgreSQL SQL dump.')
    original_stat = dump.stat()
    dockerfile = MAIN / 'docker' / 'Dockerfile.db'
    from_line = next(line for line in dockerfile.read_text().splitlines() if line.startswith('FROM '))
    repository_base = from_line.split()[1]
    if not repository_base.startswith('postgres:17.'):
        fail('The local builder currently requires the repo Dockerfile to use Postgres 17.')
    # Recent pg_dump releases emit \restrict, unsupported by the repo's old 17.4 client.
    base = BUILD_BASE_IMAGE
    previous = image_id(image)
    identifier = uuid.uuid4().hex[:12]
    container = f'herasight-prod-build-{identifier}'
    build_image = f'herasight-prod-build:{identifier}'
    log_path = Path(__file__).with_name('prod-build-restore.log')
    print(f'Production dump: {dump}\nBuilding in isolated Postgres. Existing databases stay untouched.\nLong steps print an elapsed-time update every 10 seconds.', flush=True)
    with tempfile.TemporaryDirectory(prefix='herasight-prod-build-') as temporary:
        context = Path(temporary)
        (context / 'Dockerfile').write_text(dockerfile.read_text().replace(from_line, f'FROM {base}', 1))
        try:
            with build_step('Starting temporary Postgres'):
                run(['docker', 'run', '-d', '--name', container, '--network', 'none',
                     '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', base], MAIN)
                deadline = time.monotonic() + 60
                while True:
                    ready = run(['docker', 'exec', container, 'pg_isready', '-h', '127.0.0.1', '-U', 'postgres'], MAIN, capture=True, check=False)
                    if ready.returncode == 0:
                        break
                    if time.monotonic() >= deadline:
                        fail('Temporary Postgres did not become ready within 60 seconds.')
                    time.sleep(1)
            # The log is local and private because PostgreSQL errors can include row data.
            fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, 'w') as restore_log, build_step('Restoring production SQL dump'):
                restored = run(['bash', '-o', 'pipefail', '-c',
                                'gzip -dc -- "$1" | docker exec -i "$2" psql -X -q -v ON_ERROR_STOP=1 -U postgres -d postgres',
                                'prod-build', str(dump), container], MAIN, check=False, log=restore_log)
                if restored.returncode != 0:
                    fail(f'Production restore failed. The baseline was not replaced. Details are in {log_path}.')
            after_stat = dump.stat()
            if (original_stat.st_ino, original_stat.st_size, original_stat.st_mtime_ns) != (after_stat.st_ino, after_stat.st_size, after_stat.st_mtime_ns):
                fail('The dump changed during restoration. The baseline was not replaced; rerun prod_build.')
            with build_step('Stopping temporary Postgres for a consistent copy'):
                run(['docker', 'stop', container], MAIN)
            print('The temporary database is now stopped. A separate helper will compress its files; this can take several minutes.', flush=True)
            def archive_size():
                archive = context / 'pgdata.tgz'
                size = archive.stat().st_size if archive.exists() else 0
                return f'compressed archive: {size / 1024**2:,.1f} MiB written'
            with build_step('Compressing database files', detail=archive_size):
                run(['docker', 'run', '--rm', '--network', 'none', '--volumes-from', container,
                     '--mount', f'type=bind,source={context},target=/out', '--entrypoint', 'sh', base,
                     '-c', 'tar -C /var/lib/postgresql/data -czf /out/pgdata.tgz .'], MAIN)
            with build_step('Building Docker image'):
                run(['docker', 'build', '--network', 'none', '--label', f'{PROVENANCE_LABEL}=sql-dump',
                     '-t', build_image, str(context)], MAIN)
            # Publish only after restore and image export have both succeeded.
            run(['docker', 'tag', build_image, image], MAIN)
            current = image_id(image)
            if not current:
                fail('The build finished but the saved image could not be verified.')
            cleanup_previous_image(previous, current)
            log_path.unlink(missing_ok=True)
        finally:
            with build_step('Cleaning up temporary resources'):
                run(['docker', 'rm', '-fv', container], MAIN, capture=True, check=False)
                run(['docker', 'image', 'rm', build_image], MAIN, capture=True, check=False)
    print(f'Saved {image} from {dump.name}.\nprod_build completed in {duration(time.monotonic() - started)}.\nIn the checkout you want to seed, run: prod_seed', flush=True)


def migrate(root):
    result = compose(root, 'exec', '-T', 'api', 'uv', 'run', 'manage.py',
                     'migrate', '--check', capture=True, check=False)
    if result.returncode == 0:
        print('No pending migrations.', flush=True)
        return
    if result.returncode != 1 or 'Traceback (most recent call last)' in result.stderr:
        fail(f'Migration check failed:\n{result.stdout}\n{result.stderr}')
    compose(root, 'exec', '-T', 'api', 'uv', 'run', 'manage.py', 'migrate', '--plan')
    with build_step('Applying database migrations'):
        compose(root, 'exec', '-T', 'api', 'uv', 'run', 'manage.py', 'migrate', '--noinput')


def backend_ports(root):
    """Preserve existing bindings, falling back to the checkout's saved ports."""
    services = {'api': ('API_PORT', '8000/tcp'), 'db': ('DB_PORT', '5432/tcp'), 'redis': ('REDIS_PORT', '6379/tcp')}
    ports = {}
    path = root / '.env.ports'
    if path.exists():
        for line in path.read_text().splitlines():
            key, separator, value = line.partition('=')
            if separator and key.strip() in {'API_PORT', 'DB_PORT', 'REDIS_PORT'}:
                value = value.strip().strip('\"\'')
                if value.isdigit() and 0 < int(value) < 65536:
                    ports[key.strip()] = value
    for service, (key, internal_port) in services.items():
        cid = compose(root, 'ps', '-aq', service, capture=True).stdout.strip()
        if cid:
            container = json.loads(output(['docker', 'inspect', cid], root))[0]
            bindings = container.get('HostConfig', {}).get('PortBindings', {}).get(internal_port) or []
            published = {binding['HostPort'] for binding in bindings if binding.get('HostPort')}
            if len(published) == 1:
                ports[key] = published.pop()
            else:
                fail(f'Cannot preserve the existing {service} port binding. No database was changed.')
    missing = [key for key, _ in services.values() if key not in ports]
    if missing:
        fail(f'Backend ports are not initialized ({", ".join(missing)}). Run just start once, then retry. No database was changed.')
    return ports


def compose_with_ports(root, ports, *args):
    return just(root, '--command', 'env', *(f'{key}={value}' for key, value in ports.items()),
                'docker', 'compose', *args)


def wait_for_backend(port):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        try:
            with urlopen(f'http://127.0.0.1:{port}/graphql/type/', timeout=2):
                return
        except HTTPError as response:
            # Any HTTP response means Django is serving; migrations are checked next.
            response.close()
            return
        except (URLError, TimeoutError, ConnectionError):
            time.sleep(1)
    fail(f'The API did not start on its existing port {port}. Check the api container logs.')


def start_api(root, ports):
    with build_step('Restarting API on its existing port'):
        compose_with_ports(root, ports, 'up', '-d', '--no-deps', 'api')
        wait_for_backend(ports['API_PORT'])


def replace_database(root, start_api_after_reset=True):
    ports = backend_ports(root)
    print('Replacing this worktree database. Its current data will be discarded.', flush=True)
    (root / '.local' / 'dev-db-state').unlink(missing_ok=True)
    compose(root, 'stop', 'api', 'celery')
    compose(root, 'rm', '-fsv', 'db', 'redis')
    with build_step('Starting database and Redis on their existing ports'):
        compose_with_ports(root, ports, 'up', '-d', '--wait', '--wait-timeout', '120', 'db', 'redis')
    # Start only the API until migrations succeed. The user's frontend keeps running.
    if start_api_after_reset:
        start_api(root, ports)
    return ports


def seed(image):
    root = target_root()
    path = managed_override(root)
    provenance = run(['docker', 'image', 'inspect', '--format',
                      '{{ index .Config.Labels "' + PROVENANCE_LABEL + '" }}', image], root, capture=True).stdout.strip()
    if provenance != 'sql-dump':
        fail('This image was not built from a production dump by the isolated builder. Run prod_build first.')
    if output(['git', 'ls-files', '--', OVERRIDE], root):
        fail('The override is tracked by Git. Refusing to modify it.')
    previous = path.read_text() if path.exists() else None
    path.write_text(MARKER + 'services:\n  db:\n    image: ' + json.dumps(image) + '\n    pull_policy: never\n')
    try:
        if config(root)['services']['db']['image'] != image:
            fail('Compose did not select the saved image. Check COMPOSE_FILE or explicit Compose overrides.')
        exclude_override(root)
    except Exception:
        if previous is None:
            path.unlink()
        else:
            path.write_text(previous)
        raise
    ports = replace_database(root)
    migrate(root)
    compose_with_ports(root, ports, 'up', '-d', '--no-deps', 'celery')
    print(f'Production data loaded. Backend ready on API port {ports["API_PORT"]}.\nYour existing frontend session can keep running; refresh the browser.', flush=True)


def dev_cache_plan(root):
    args = ['--report', '0']
    key = just(root, '--command', 'bash', 'scripts/bootstrap-cache-key.sh',
               str(root), ' '.join(args), capture=True).stdout.strip()
    if len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
        fail('The development cache-key script did not return a valid key.')
    directory = just(root, '--command', 'python3', '-c',
                     'import os; print(os.environ.get("DB_CACHE_DIR", ".db-cache"))', capture=True).stdout.strip()
    cache_dir = Path(directory).expanduser()
    if not cache_dir.is_absolute():
        cache_dir = root / cache_dir
    return {'args': args, 'key': key, 'directory': cache_dir, 'file': cache_dir / f'{key}.sql.gz'}


def dev_recipe(root, environment, *args):
    # Keep the repository's cache/bootstrap recipes authoritative, including dotenv setup.
    return just(root, '--command', 'env', *(f'{key}={value}' for key, value in environment.items()), 'just', *args)


def record_dev_state(root, cache_key):
    cid = compose(root, 'ps', '--all', '--quiet', 'db', capture=True).stdout.strip()
    if not cid:
        fail('The database container is missing after development initialization.')
    container = json.loads(output(['docker', 'inspect', cid], root))[0]
    database_id = next((mount['Source'] for mount in container.get('Mounts', [])
                        if mount.get('Destination') == '/var/lib/postgresql/data'), container['Id'])
    state = root / '.local' / 'dev-db-state'
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(f'{cache_key} {database_id}\n')


def restore_development_data(root, ports, plan):
    environment = {**ports, 'DB_CACHE_KEY': plan['key'], 'DB_CACHE_DIR': str(plan['directory'])}
    if plan['file'].is_file():
        print(f'Cache hit: restoring development snapshot from {plan["file"]}', flush=True)
        # API and Celery stay stopped while restore-db drops and recreates the database.
        with build_step('Restoring cached development data'):
            dev_recipe(root, environment, 'restore-db')
        start_api(root, ports)
        migrate(root)
    else:
        print('No matching development cache. Bootstrapping with --report 0.', flush=True)
        start_api(root, ports)
        with build_step('Bootstrapping development data'):
            dev_recipe(root, environment, 'bootstrap', *plan['args'])
            dev_recipe(root, environment, 'ensure-smoke-clinician')
        with build_step('Saving the development cache'):
            dev_recipe(root, environment, 'dump-db')
    with build_step('Applying branch-specific development seed'):
        dev_recipe(root, {**environment, 'BOOTSTRAP_CATALOG_READY': '1'}, 'seed-worktree')
    record_dev_state(root, plan['key'])


def remove():
    root = target_root()
    path = managed_override(root, required=True)
    if output(['git', 'ls-files', '--', OVERRIDE], root):
        fail('The override is tracked by Git. Refusing to remove it.')
    saved = path.read_text()
    path.unlink()
    try:
        clean_image = config(root)['services']['db']['image']
        if not clean_image.startswith('postgres:'):
            fail(f'The base database image is {clean_image}, not plain Postgres. Override restored; database unchanged.')
        plan = dev_cache_plan(root)
    except Exception:
        path.write_text(saved)
        raise
    ports = replace_database(root, start_api_after_reset=False)
    restore_development_data(root, ports, plan)
    compose_with_ports(root, ports, 'up', '-d', '--no-deps', 'celery')
    print('Production data removed. Normal development data is ready using the just dev --report 0 cache/bootstrap workflow.\nYour existing frontend session and backend ports are unchanged; refresh the browser.', flush=True)




def snapshot_directory(root):
    directory = root / '.db-snapshots'
    if directory.is_symlink():
        shared = directory.resolve()
        link = directory.readlink()
        directory.unlink()
        try:
            directory.mkdir(mode=0o700)
        except BaseException:
            if not directory.exists():
                directory.symlink_to(link)
            raise
        print(f'Created a private snapshot directory for this worktree. Existing shared snapshots remain at {shared}.', flush=True)
    directory.mkdir(mode=0o700, exist_ok=True)
    exclude = Path(output(['git', 'rev-parse', '--git-path', 'info/exclude'], root))
    if not exclude.is_absolute():
        exclude = root / exclude
    exclude.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude.read_text() if exclude.exists() else ''
    if '/.db-snapshots/' not in existing.splitlines():
        with exclude.open('a') as stream:
            stream.write('\n/.db-snapshots/\n')
    return directory


@contextmanager
def snapshot_lock(directory):
    with (directory / '.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fail('Another snapshot command is already running in this worktree.')
        yield


def snapshot_name(name):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,119}', name):
        fail('Snapshot names must start with a letter or number and contain only letters, numbers, dots, underscores or dashes, up to 120 characters.')
    return name


def select_snapshot(root, directory, name, saving=False):
    if name:
        return snapshot_name(name)
    if saving:
        branch = output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], root)
        base = re.sub(r'[^A-Za-z0-9]+', '-', branch).strip('-')[:100] or 'snapshot'
        number = 1
        while (directory / f'{base}-{number}.sql.gz').exists():
            number += 1
        return f'{base}-{number}'
    files = [p for p in directory.glob('*.sql.gz') if p.is_file() and not p.is_symlink()]
    if not files:
        fail('No snapshots in this worktree. Run save_snapshot first.')
    return snapshot_name(max(files, key=lambda p: (p.stat().st_mtime_ns, p.name)).name[:-7])


def save_snapshot(name=None):
    root = target_root()
    directory = snapshot_directory(root)
    with snapshot_lock(directory):
        name = select_snapshot(root, directory, name, saving=True)
        # The existing recipe writes both SQL and migration metadata into staging.
        # Failed dumps cannot truncate a previously saved checkpoint.
        with tempfile.TemporaryDirectory(prefix='.saving-', dir=directory) as temporary:
            staging = Path(temporary)
            with build_step(f'Saving snapshot {name}'):
                dev_recipe(root, {'DB_SNAPSHOTS_DIR': str(staging)}, 'save-snapshot', name)
                archive = staging / f'{name}.sql.gz'
                run(['gzip', '-t', str(archive)], root)
                metadata = staging / f'{name}.meta.json'
                json.loads(metadata.read_text())
                archive.chmod(0o600)
                metadata.chmod(0o600)
                # Back up both old files until both replacements are published.
                backups = {}
                published = []
                try:
                    for source in (archive, metadata):
                        destination = directory / source.name
                        if destination.exists() or destination.is_symlink():
                            backup = staging / (source.name + '.previous')
                            destination.replace(backup)
                            backups[destination] = backup
                        source.replace(destination)
                        published.append(destination)
                except BaseException:
                    for destination in published:
                        destination.unlink(missing_ok=True)
                    for destination, backup in backups.items():
                        backup.replace(destination)
                    raise
        print(f'Saved {directory / (name + ".sql.gz")}\nRestore here with: load_snapshot {name}', flush=True)


def load_snapshot(name=None, force=False):
    root = target_root()
    directory = snapshot_directory(root)
    with snapshot_lock(directory):
        name = select_snapshot(root, directory, name)
        archive = directory / f'{name}.sql.gz'
        metadata = directory / f'{name}.meta.json'
        if not archive.is_file() or archive.is_symlink() or not metadata.is_file() or metadata.is_symlink():
            fail(f'Snapshot {name} needs a local SQL archive and metadata in {directory}.')
        with build_step(f'Checking snapshot {name}'):
            run(['gzip', '-t', str(archive)], root)
            # Reuse the repository's migration compatibility policy, failing closed.
            result = just(root, '--command', 'python3', 'scripts/check_snapshot_compat.py',
                          '--check', name, '--snapshots-dir', str(directory), capture=True, check=False)
            print(result.stdout, end='', flush=True)
            if result.returncode and not (force and result.returncode == 1 and not result.stderr.strip()):
                fail('Snapshot compatibility check failed. Changed migration files require --force; missing migrations or metadata errors cannot be overridden.')
        ports = backend_ports(root)
        print(f'Replacing this worktree database with {name}. Current database data and Redis cache will be discarded.', flush=True)
        compose(root, 'stop', 'api', 'celery')
        (root / '.local' / 'dev-db-state').unlink(missing_ok=True)
        with build_step('Starting database and Redis on their existing ports'):
            compose_with_ports(root, ports, 'up', '-d', '--wait', '--wait-timeout', '120', 'db', 'redis')
        log_path = directory / '.restore.log'
        try:
            with build_step(f'Restoring snapshot {name}'):
                compose(root, 'exec', '-T', 'db', 'dropdb', '-U', 'postgres', '--force', '--if-exists', 'postgres')
                compose(root, 'exec', '-T', 'db', 'createdb', '-U', 'postgres', 'postgres')
                fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                os.fchmod(fd, 0o600)
                with os.fdopen(fd, 'w') as log:
                    restored = just(root, '--command', 'bash', '-o', 'pipefail', '-c',
                                    'gzip -dc -- "$1" | docker compose exec -T db psql -X -q -v ON_ERROR_STOP=1 -U postgres -d postgres',
                                    'load-snapshot', str(archive), check=False, log=log)
                if restored.returncode:
                    fail(f'SQL restore failed. Details are in {log_path}.')
                compose(root, 'exec', '-T', 'redis', 'redis-cli', 'FLUSHALL')
                log_path.unlink(missing_ok=True)
            start_api(root, ports)
            migrate(root)
            compose_with_ports(root, ports, 'up', '-d', '--no-deps', 'celery')
        except BaseException:
            compose(root, 'stop', 'api', 'celery', check=False)
            print('Snapshot loading failed. API and Celery were stopped; fix the error and retry load_snapshot.', flush=True)
            raise
        print(f'Loaded {name}. Backend ready on API port {ports["API_PORT"]}. Refresh your existing frontend.', flush=True)


def list_snapshots():
    root = target_root()
    directory = snapshot_directory(root)
    with snapshot_lock(directory):
        dev_recipe(root, {'DB_SNAPSHOTS_DIR': str(directory)}, 'list-snapshots')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('create', 'seed', 'remove', 'save-snapshot', 'load-snapshot', 'list-snapshots'))
    parser.add_argument('name', nargs='?')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    if args.name and args.action not in ('save-snapshot', 'load-snapshot'):
        parser.error('This command does not accept a snapshot name.')
    if args.force and args.action != 'load-snapshot':
        parser.error('--force is only supported by load-snapshot.')
    try:
        if args.action == 'create':
            create(DEFAULT_IMAGE)
        elif args.action == 'seed':
            seed(DEFAULT_IMAGE)
        elif args.action == 'remove':
            remove()
        elif args.action == 'save-snapshot':
            save_snapshot(args.name)
        elif args.action == 'load-snapshot':
            load_snapshot(args.name, args.force)
        else:
            list_snapshots()
    except (RuntimeError, OSError, EOFError, ValueError, subprocess.CalledProcessError) as error:
        print(f'Error: {error}', file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError) and error.stderr:
            print(error.stderr, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == '__main__':
    sys.exit(main())
