
#!/usr/bin/env python3
"""Safely back up AegisTwin's live Docker-mounted SQLite evidence database."""

import hashlib
import os
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKUP_DIR = ROOT / "backups" / "sqlite"
CONTAINER_DB = "/srv/app/data/aegistwin-runtime.db"

# This Python program runs inside the existing API container.
# It uses SQLite's Online Backup API, which includes committed WAL data.
CONTAINER_SCRIPT = r"""
import os
import sqlite3
import sys
import tempfile

source_path = "/srv/app/data/aegistwin-runtime.db"

if not os.path.isfile(source_path):
    raise SystemExit("SQLite source database is missing")

fd, temporary_path = tempfile.mkstemp(
    prefix="aegistwin-evidence-",
    suffix=".db",
)
os.close(fd)

try:
    source_uri = "file:" + source_path + "?mode=ro"

    with sqlite3.connect(source_uri, uri=True, timeout=30) as source:
        with sqlite3.connect(temporary_path) as target:
            source.backup(target, pages=100, sleep=0.1)

    with sqlite3.connect(temporary_path) as connection:
        result = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()

        if not result or result[0] != "ok":
            raise RuntimeError("SQLite backup integrity check failed")

    # Standard output must contain only database bytes.
    with open(temporary_path, "rb") as snapshot:
        while True:
            chunk = snapshot.read(1024 * 1024)
            if not chunk:
                break
            sys.stdout.buffer.write(chunk)

    sys.stdout.buffer.flush()

finally:
    if os.path.exists(temporary_path):
        os.unlink(temporary_path)
"""


def verify_backup(path: Path) -> dict:
    """Verify the exported SQLite file independently on the host."""
    with sqlite3.connect(
        f"file:{path.resolve()}?mode=ro",
        uri=True,
    ) as connection:
        result = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()

        if not result or result[0] != "ok":
            raise RuntimeError("Exported SQLite backup failed integrity check")

        table_names = [
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                ORDER BY name
                """
            )
        ]

        if not table_names:
            raise RuntimeError("Backup contains no database tables")

        return {
            "integrity": result[0],
            "tables": table_names,
        }


def main() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    unique_id = uuid.uuid4().hex[:8]

    destination = BACKUP_DIR / (
        f"aegistwin-evidence_{timestamp}_{unique_id}.db"
    )

    command = [
        "docker",
        "compose",
        "--env-file",
        ".env.docker",
        "exec",
        "-T",
        "api",
        "python",
        "-c",
        CONTAINER_SCRIPT,
    ]

    print("Backing up live SQLite evidence database...", flush=True)
    print(f"Source: {CONTAINER_DB}", flush=True)

    # The exclusive file creation prevents overwriting existing backups.
    # Restrictive permissions help protect sensitive evidence.
    fd = os.open(
        destination,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )

    try:
        with os.fdopen(fd, "wb") as output:
            subprocess.run(
                command,
                cwd=ROOT,
                stdout=output,
                check=True,
            )

        if destination.stat().st_size == 0:
            raise RuntimeError("SQLite backup is empty")

        details = verify_backup(destination)

    except Exception:
        # Remove an incomplete or invalid export, never the source DB.
        destination.unlink(missing_ok=True)
        raise

    checksum = hashlib.sha256(
        destination.read_bytes()
    ).hexdigest()

    print()
    print("SUCCESS: SQLite evidence backup verified")
    print(f"Backup: {destination.relative_to(ROOT)}")
    print(f"Size: {destination.stat().st_size:,} bytes")
    print(f"SHA-256: {checksum}")
    print(f"Integrity: {details['integrity']}")
    print(f"Tables: {', '.join(details['tables'])}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"BACKUP FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
