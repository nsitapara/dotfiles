"""SQL checkpoint round-trip using synthetic data and an isolated Compose project."""

import gzip
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('snapshot', Path(__file__).with_name('db_snapshot.py'))
snapshot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snapshot)


def main():
    repository = snapshot.MAIN
    def stacks():
        ids = subprocess.check_output(['docker', 'ps', '-aq', '--filter', 'label=com.docker.compose.project'], text=True).split()
        if not ids:
            return {}
        records = json.loads(subprocess.check_output(['docker', 'inspect', *ids], text=True))
        return {c['Id']: (c['State']['Status'], c['State']['StartedAt']) for c in records}
    before = stacks()
    with tempfile.TemporaryDirectory(prefix='herasight-sql-test-') as temp:
        root = Path(temp).resolve()
        recipes = (repository / 'justfile').read_text()
        save = recipes[recipes.index('save-snapshot name='):recipes.index('# Load a named snapshot.')]
        listing = recipes[recipes.index('list-snapshots:'):recipes.index('# ============================================================', recipes.index('list-snapshots:'))]
        (root / 'justfile').write_text(save + '\n' + listing)
        (root / 'scripts').mkdir()
        shutil.copyfile(repository / 'scripts/check_snapshot_compat.py', root / 'scripts/check_snapshot_compat.py')
        subprocess.run(['git', 'init', '-q', str(root)], check=True)
        (root / 'compose.yml').write_text("""name: herasight-sql-test-""" + uuid.uuid4().hex[:12] + """
services:
  db:
    image: postgres:17.4-alpine3.21
    network_mode: none
    environment:
      POSTGRES_HOST_AUTH_METHOD: trust
    healthcheck:
      test: [CMD, pg_isready, -h, 127.0.0.1, -U, postgres]
      interval: 1s
      timeout: 2s
      retries: 60
  redis:
    image: redis:7.4.2
    network_mode: none
    healthcheck:
      test: [CMD, redis-cli, ping]
      interval: 1s
      timeout: 2s
      retries: 60
  api:
    image: postgres:17.4-alpine3.21
    network_mode: none
    entrypoint: [sh, -c, 'sleep infinity']
  celery:
    image: postgres:17.4-alpine3.21
    network_mode: none
    entrypoint: [sh, -c, 'sleep infinity']
""")
        def sql(query):
            return snapshot.compose(root, 'exec', '-T', 'db', 'psql', '-U', 'postgres', '-Atc', query, capture=True).stdout.strip()
        def start_api(checkout, ports):
            snapshot.compose_with_ports(checkout, ports, 'up', '-d', '--no-deps', 'api')
        try:
            snapshot.compose(root, 'up', '-d', '--wait', '--wait-timeout', '90')
            sql("CREATE TABLE checkpoint_proof (value text); INSERT INTO checkpoint_proof VALUES ('saved value');")
            with patch.object(snapshot, 'target_root', return_value=root), patch.object(snapshot, 'backend_ports', return_value={'API_PORT': 'unused-in-fixture'}), patch.object(snapshot, 'start_api', side_effect=start_api), patch.object(snapshot, 'migrate') as migrate:
                snapshot.save_snapshot('before-edit')
                sql("UPDATE checkpoint_proof SET value = 'changed value';")
                snapshot.compose(root, 'exec', '-T', 'redis', 'redis-cli', 'SET', 'old-cache', 'stale')
                snapshot.list_snapshots()
                snapshot.load_snapshot()
                assert sql('SELECT value FROM checkpoint_proof') == 'saved value'
                assert snapshot.compose(root, 'exec', '-T', 'redis', 'redis-cli', 'DBSIZE', capture=True).stdout.strip() == '0'
                migrate.assert_called_once_with(root)
                # Well-formed gzip with invalid SQL must fail and leave writers stopped.
                archive = root / '.db-snapshots/before-edit.sql.gz'
                with gzip.open(archive, 'wb') as stream:
                    stream.write(b'INVALID SQL;\n')
                try:
                    snapshot.load_snapshot('before-edit')
                except RuntimeError as error:
                    assert 'SQL restore failed' in str(error), error
                else:
                    raise AssertionError('Invalid SQL was accepted')
                for service in ('api', 'celery'):
                    assert not snapshot.compose(root, 'ps', '--status', 'running', '-q', service, capture=True).stdout.strip()
                assert (root / '.db-snapshots/.restore.log').stat().st_mode & 0o777 == 0o600
        finally:
            snapshot.compose(root, 'down', '--volumes', '--remove-orphans')
    assert stacks() == before, 'Existing Compose stacks changed'
    print('PASS: real Just save/list, SQL restore, Redis clearing, strict SQL failure handling, private error log, and existing stack isolation. Django migration invocation is mocked.')


if __name__ == '__main__':
    main()
