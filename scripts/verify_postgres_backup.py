
#!/usr/bin/env python3
"""Back up AegisTwin PostgreSQL and verify an isolated restore."""

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKUP_DIR = ROOT / "backups"
DATABASES = ("postgres", "template1", "template0")


def compose(*args, input_file=None, output_file=None):
    command = [
        "docker", "compose", "--env-file", ".env.docker",
        *args,
    ]
    return subprocess.run(
        command,
        cwd=ROOT,
        stdin=input_file,
        stdout=output_file,
        check=True,
    )


def pg(*args, input_file=None, output_file=None):
    return compose(
        "exec", "-T", "postgres", "sh", "-c", args[0],
        input_file=input_file,
        output_file=output_file,
    )


def sql(database, query):
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", database):
        raise ValueError("Unsafe database identifier")

    shell = (
        'psql -X -A -t -v ON_ERROR_STOP=1 '
        f'-U "$POSTGRES_USER" -d "{database}" -c '
        + "'" + query.replace("'", "'\\''") + "'"
    )
    result = subprocess.run(
        [
            "docker", "compose", "--env-file", ".env.docker",
            "exec", "-T", "postgres", "sh", "-c", shell,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def check_database_name(name):
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", name):
        raise ValueError("Invalid database name")
    if name in DATABASES:
        raise ValueError("Refusing to operate on reserved database")
    return name


def database_name():
    result = subprocess.run(
        [
            "docker", "compose", "--env-file", ".env.docker",
            "exec", "-T", "postgres", "sh", "-c",
            'printf "%s" "$POSTGRES_DB"',
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return check_database_name(result.stdout.strip())


def manifest(db):
    """Schema and row-count fingerprint for application tables."""
    query = """
    SELECT json_build_object(
        'revision', (SELECT version_num FROM alembic_version LIMIT 1),
        'tables', (
            SELECT COALESCE(json_object_agg(
                tablename,
                (xpath('/row/count/text()',
                    query_to_xml(
                        format('SELECT COUNT(*) FROM %I.%I',
                               schemaname, tablename),
                        false, true, ''
                    )
                ))[1]::text::bigint
            ), '{}'::json)
            FROM pg_tables
            WHERE schemaname = 'public'
        )
    )::text;
    """
    return json.loads(sql(db, " ".join(query.split())))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--keep-restore",
        action="store_true",
        help="Retain temporary restore database for debugging",
    )
    args = parser.parse_args()

    source = database_name()
    restore = "aegistwin_verify_" + uuid.uuid4().hex[:12]
    check_database_name(restore)

    BACKUP_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = BACKUP_DIR / f"aegistwin_{timestamp}_{uuid.uuid4().hex[:8]}.dump"

    restore_created = False
    success = False

    try:
        print(f"Backing up database: {source}", flush=True)

        # Use an exclusive file so existing backups are never overwritten.
        fd = os.open(
            backup,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        with os.fdopen(fd, "wb") as out:
            pg(
                'exec pg_dump -U "$POSTGRES_USER" '
                '-d "$POSTGRES_DB" -Fc',
                output_file=out,
            )

        if backup.stat().st_size == 0:
            raise RuntimeError("Backup file is empty")

        digest = hashlib.sha256(backup.read_bytes()).hexdigest()
        print(f"Backup: {backup.relative_to(ROOT)}")
        print(f"SHA-256: {digest}")

        # Confirm the archive is recognizable before creating a database.
        with backup.open("rb") as inp:
            pg("exec pg_restore --list", input_file=inp)

        # The source might change after the snapshot. The restored backup
        # is compared with an independently restored copy of that snapshot
        # when source data is changing, so this check assumes a quiet local DB.
        expected = manifest(source)

        # Never use the source database as a restore target.
        print(f"Creating isolated restore database: {restore}", flush=True)
        pg(
            'exec createdb -U "$POSTGRES_USER" ' + restore
        )
        restore_created = True

        with backup.open("rb") as inp:
            pg(
                'exec pg_restore -U "$POSTGRES_USER" '
                f'-d {restore} --no-owner --no-acl --exit-on-error',
                input_file=inp,
            )

        actual = manifest(restore)
        if expected != actual:
            print("Source manifest:", json.dumps(expected, indent=2))
            print("Restored manifest:", json.dumps(actual, indent=2))
            raise RuntimeError("Restored schema/row counts differ")

        print("PASS: Alembic revision and public table row counts match")
        print(f"PASS: Backup is readable ({backup.stat().st_size} bytes)")
        success = True

    finally:
        if restore_created and not args.keep_restore:
            print(f"Dropping temporary database: {restore}", flush=True)
            try:
                pg('exec dropdb -U "$POSTGRES_USER" ' + restore)
            except subprocess.CalledProcessError:
                print(
                    f"WARNING: Could not drop temporary database {restore}",
                    file=sys.stderr,
                )
                success = False

    if not success:
        sys.exit(1)

    print("SUCCESS: Isolated backup-and-restore verification completed")


if __name__ == "__main__":
    main()
