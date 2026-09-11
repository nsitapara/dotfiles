"""Exercise the isolated builder against a synthetic dump using real Docker."""

import gzip
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import uuid

spec = importlib.util.spec_from_file_location('snapshot', Path(__file__).with_name('db_snapshot.py'))
snapshot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snapshot)


def docker(*args, check=True):
    return subprocess.run(['docker', *args], text=True, capture_output=True, check=check)


def existing_stacks():
    ids = docker('ps', '-aq', '--filter', 'label=com.docker.compose.project').stdout.split()
    if not ids:
        return {}
    return {c['Id']: (c['State']['Status'], c['State']['StartedAt']) for c in json.loads(docker('inspect', *ids).stdout)}


def main():
    before = existing_stacks()
    suffix = uuid.uuid4().hex[:12]
    image = f'herasight-prod-test:{suffix}'
    reader = f'herasight-prod-test-{suffix}'
    template = snapshot.MAIN / 'docker' / 'Dockerfile.db'
    with tempfile.TemporaryDirectory(prefix='herasight-prod-test-') as temporary:
        fixture = Path(temporary)
        (fixture / 'docker').mkdir()
        shutil.copyfile(template, fixture / 'docker' / 'Dockerfile.db')
        with gzip.open(fixture / 'db.sql.gz', 'wb') as f:
            f.write(b"-- PostgreSQL database dump\n\\restrict fixturebuildtoken\nCREATE TABLE build_proof (value text);\nINSERT INTO build_proof VALUES ('restored from dump');\n\\unrestrict fixturebuildtoken\n")
        snapshot.MAIN = fixture
        snapshot.__file__ = str(fixture / 'db_snapshot.py')
        try:
            snapshot.create(image)
            saved_id = docker('image', 'inspect', '--format', '{{.Id}}', image).stdout.strip()
            with gzip.open(fixture / 'db.sql.gz', 'wb') as f:
                f.write(b'-- PostgreSQL database dump\nTHIS IS NOT VALID SQL;\n')
            try:
                snapshot.create(image)
            except RuntimeError as error:
                assert 'restore failed' in str(error), error
            else:
                raise AssertionError('An invalid production dump was accepted.')
            assert docker('image', 'inspect', '--format', '{{.Id}}', image).stdout.strip() == saved_id, 'Failed restore replaced the saved image.'
            docker('run', '-d', '--name', reader, '--network', 'none', image)
            for _ in range(60):
                if docker('exec', reader, 'pg_isready', '-h', '127.0.0.1', '-U', 'postgres', check=False).returncode == 0:
                    break
                time.sleep(1)
            value = docker('exec', reader, 'psql', '-U', 'postgres', '-Atc', 'SELECT value FROM build_proof').stdout.strip()
            assert value == 'restored from dump', value
            provenance = docker('image', 'inspect', '--format', '{{ index .Config.Labels "' + snapshot.PROVENANCE_LABEL + '" }}', image).stdout.strip()
            assert provenance == 'sql-dump', provenance
        finally:
            docker('rm', '-fv', reader, check=False)
            docker('image', 'rm', image, check=False)
    assert existing_stacks() == before, 'An existing Compose stack changed during the test.'
    assert not docker('ps', '-aq', '--filter', 'name=herasight-prod-build-').stdout.strip(), 'Builder container leaked.'
    print('PASS: real Docker image contains restored fixture rows; failed restore preserves baseline; provenance verified; temporary containers removed; existing Compose stacks unchanged.')


if __name__ == '__main__':
    main()
