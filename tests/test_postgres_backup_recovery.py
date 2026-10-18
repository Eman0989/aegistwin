
"""Integration test for recovery of real AegisTwin PostgreSQL records."""

import json
import os
import subprocess
from uuid import uuid4

import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_BACKUP_TEST") != "1",
    reason="Set RUN_POSTGRES_BACKUP_TEST=1 to enable Docker backup integration.",
)

COMPOSE = ["docker", "compose", "--env-file", ".env.docker"]

TABLES = (
    "tenants",
    "agents",
    "sessions",
    "requests",
    "security_events",
    "execution_receipts",
)

PREFIX = "aegistwin_backup_it_"


def docker(*arguments, input_data=None):
    return subprocess.run(
        [*COMPOSE, *arguments],
        input=input_data,
        capture_output=True,
        check=True,
    )


def postgres(command, input_data=None):
    return docker(
        "exec", "-T", "postgres",
        "sh", "-c", command,
        input_data=input_data,
    )


def psql(database, statement):
    assert database.startswith(PREFIX)

    command = (
        'psql -X -qAt -v ON_ERROR_STOP=1 '
        f'-U "$POSTGRES_USER" -d "{database}"'
    )

    result = postgres(command, statement.encode("utf-8"))
    return result.stdout.decode("utf-8").strip()


def create_database(name):
    assert name.startswith(PREFIX)
    postgres(f'createdb -U "$POSTGRES_USER" "{name}"')


def drop_database(name):
    assert name.startswith(PREFIX)
    postgres(f'dropdb --if-exists -U "$POSTGRES_USER" "{name}"')


def migrate_database(name):
    assert name.startswith(PREFIX)

    docker(
        "run", "--rm", "--no-deps", "-T",
        "-e", f"DB_NAME={name}",
        "migrate",
    )


def insert_fixture(database):
    tenant_id = str(uuid4())
    agent_id = str(uuid4())
    session_id = str(uuid4())
    request_id = str(uuid4())
    event_id = str(uuid4())
    receipt_id = str(uuid4())
    public_request_id = f"backup-verification-{uuid4().hex}"

    # All identifiers and record values are generated locally by this test.
    statement = f"""
    BEGIN;

    INSERT INTO tenants (id, name, created_at)
    VALUES (
        '{tenant_id}',
        'Backup Recovery Test Tenant',
        '2026-10-18T12:00:00+00'
    );

    INSERT INTO agents (id, tenant_id, name, description, status)
    VALUES (
        '{agent_id}',
        '{tenant_id}',
        'Recovery Test Agent',
        'Agent used to verify PostgreSQL disaster recovery',
        'active'
    );

    INSERT INTO sessions (id, tenant_id, agent_id, started_at)
    VALUES (
        '{session_id}',
        '{tenant_id}',
        '{agent_id}',
        '2026-10-18T12:01:00+00'
    );

    INSERT INTO requests (
        id,
        tenant_id,
        agent_id,
        session_id,
        provider,
        model,
        status,
        public_request_id,
        started_at,
        completed_at,
        latency,
        input_tokens,
        output_tokens,
        estimated_cost
    )
    VALUES (
        '{request_id}',
        '{tenant_id}',
        '{agent_id}',
        '{session_id}',
        'ollama',
        'llama3',
        'completed',
        '{public_request_id}',
        '2026-10-18T12:02:00+00',
        '2026-10-18T12:02:01+00',
        125.5,
        120,
        80,
        0.00025000
    );

    INSERT INTO security_events (
        id,
        tenant_id,
        request_id,
        event_type,
        severity,
        details,
        created_at
    )
    VALUES (
        '{event_id}',
        '{tenant_id}',
        '{request_id}',
        'prompt_injection_detected',
        'high',
        'Synthetic security event for backup verification',
        '2026-10-18T12:03:00+00'
    );

    INSERT INTO execution_receipts (
        id,
        tenant_id,
        request_id,
        outcome,
        receipt_data,
        created_at
    )
    VALUES (
        '{receipt_id}',
        '{tenant_id}',
        '{request_id}',
        'blocked',
        '{{"reason": "policy_denied", "verified": true}}',
        '2026-10-18T12:04:00+00'
    );

    COMMIT;
    """

    psql(database, statement)

    return {
        "tenant_id": tenant_id,
        "agent_id": agent_id,
        "session_id": session_id,
        "request_id": request_id,
        "public_request_id": public_request_id,
    }


def database_snapshot(database):
    """Capture complete JSON values for the known application tables."""
    snapshot = {}

    for table in TABLES:
        query = (
            "SELECT COALESCE("
            "jsonb_agg(to_jsonb(t) ORDER BY t.id), "
            "'[]'::jsonb"
            ")::text "
            f"FROM public.{table} AS t;"
        )

        snapshot[table] = json.loads(psql(database, query))

    revision = psql(
        database,
        "SELECT version_num FROM alembic_version;",
    )

    snapshot["alembic_revision"] = revision

    return snapshot


def verify_relationships(database, identifiers):
    """Check that restored records retain their foreign-key links."""
    request_id = identifiers["request_id"]

    query = f"""
    SELECT COUNT(*)
    FROM requests r
    JOIN tenants t ON t.id = r.tenant_id
    JOIN agents a ON a.id = r.agent_id
                 AND a.tenant_id = t.id
    JOIN sessions s ON s.id = r.session_id
                   AND s.tenant_id = t.id
                   AND s.agent_id = a.id
    JOIN security_events e ON e.request_id = r.id
                          AND e.tenant_id = t.id
    JOIN execution_receipts x ON x.request_id = r.id
                             AND x.tenant_id = t.id
    WHERE r.id = '{request_id}'
      AND r.status = 'completed'
      AND r.provider = 'ollama'
      AND r.input_tokens = 120
      AND r.output_tokens = 80;
    """

    assert psql(database, query) == "1"


def test_postgres_backup_recovers_actual_application_records():
    # Explicit opt-in above prevents accidental execution in regular tests.
    # Both database names are generated and restricted to this prefix.
    suffix = uuid4().hex[:12]
    source = f"{PREFIX}source_{suffix}"
    restored = f"{PREFIX}restored_{suffix}"

    live_database = postgres(
        'printf "%s" "$POSTGRES_DB"'
    ).stdout.decode().strip()

    assert live_database
    assert live_database not in (source, restored)

    created = []

    try:
        print("\nCreating isolated source database", flush=True)
        create_database(source)
        created.append(source)

        print("Applying Alembic migrations", flush=True)
        migrate_database(source)

        print("Inserting linked application records", flush=True)
        identifiers = insert_fixture(source)

        expected = database_snapshot(source)
        verify_relationships(source, identifiers)

        print("Creating PostgreSQL custom-format backup", flush=True)
        archive = postgres(
            f'pg_dump -U "$POSTGRES_USER" -d "{source}" -Fc'
        ).stdout

        assert len(archive) > 1000
        assert archive.startswith(b"PGDMP")

        # Archive inspection is separate from restore validation.
        postgres("pg_restore --list", archive)

        print("Creating isolated restore database", flush=True)
        create_database(restored)
        created.append(restored)

        print("Restoring the backup", flush=True)
        postgres(
            'pg_restore -U "$POSTGRES_USER" '
            f'-d "{restored}" --no-owner --no-acl --exit-on-error',
            archive,
        )

        actual = database_snapshot(restored)

        assert actual == expected, (
            "Restored application records differ from original records."
        )

        assert len(actual["tenants"]) == 1
        assert len(actual["agents"]) == 1
        assert len(actual["sessions"]) == 1
        assert len(actual["requests"]) == 1
        assert len(actual["security_events"]) == 1
        assert len(actual["execution_receipts"]) == 1

        assert actual["requests"][0]["public_request_id"] == (
            identifiers["public_request_id"]
        )

        assert actual["requests"][0]["estimated_cost"] == (
            expected["requests"][0]["estimated_cost"]
        )

        assert actual["execution_receipts"][0]["receipt_data"] == {
            "reason": "policy_denied",
            "verified": True,
        }

        verify_relationships(restored, identifiers)

        # Confirm that the restore brought back foreign-key constraints.
        fk_count = int(
            psql(
                restored,
                """
                SELECT COUNT(*)
                FROM pg_constraint
                WHERE contype = 'f'
                  AND connamespace = 'public'::regnamespace;
                """,
            )
        )
        assert fk_count >= 1

        print(
            "PASS: Actual application records and relationships restored",
            flush=True,
        )

    finally:
        # Never drop the original application database.
        # Clean up only databases this test successfully created.
        for database in reversed(created):
            print(f"Removing temporary database: {database}", flush=True)
            drop_database(database)
