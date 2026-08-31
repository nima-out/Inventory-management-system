import os
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model

from .models import Category, Item, TransactionHistory


class SQLiteWorkflowError(Exception):
    """Raised when a SQLite backup or restore cannot be completed safely."""


def get_database_path():
    database = settings.DATABASES["default"]
    if database["ENGINE"] != "django.db.backends.sqlite3":
        raise SQLiteWorkflowError(
            "The default database is not configured to use SQLite."
        )

    database_name = database["NAME"]
    if not database_name or str(database_name) == ":memory:":
        raise SQLiteWorkflowError(
            "A file-backed SQLite database is required."
        )

    return Path(database_name).expanduser().resolve()


def get_default_backup_directory():
    base_dir = Path(settings.BASE_DIR).resolve()
    return base_dir.parent / f"{base_dir.name}-backups"


def require_external_backup_directory(output_directory):
    base_dir = Path(settings.BASE_DIR).resolve()
    output_directory = Path(output_directory).expanduser().resolve()
    if output_directory == base_dir or base_dir in output_directory.parents:
        raise SQLiteWorkflowError(
            "The backup directory must be outside the repository."
        )
    return output_directory


def get_sqlite_sidecars(database_path):
    database_path = Path(database_path)
    suffixes = ("-journal", "-shm", "-wal")
    return [
        database_path.with_name(f"{database_path.name}{suffix}")
        for suffix in suffixes
        if database_path.with_name(f"{database_path.name}{suffix}").exists()
    ]


def inspect_database(database_path):
    database_path = Path(database_path).expanduser().resolve()
    if not database_path.is_file():
        raise SQLiteWorkflowError(
            f"SQLite database does not exist: {database_path}"
        )

    table_names = {
        "users": get_user_model()._meta.db_table,
        "categories": Category._meta.db_table,
        "items": Item._meta.db_table,
        "transactions": TransactionHistory._meta.db_table,
    }
    try:
        with closing(_connect_read_only(database_path)) as database:
            integrity = database.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]
            if integrity != "ok":
                raise SQLiteWorkflowError(
                    f"SQLite integrity check failed: {integrity}"
                )

            counts = {}
            for label, table_name in table_names.items():
                quoted_name = table_name.replace('"', '""')
                counts[label] = database.execute(
                    f'SELECT COUNT(*) FROM "{quoted_name}"'
                ).fetchone()[0]
    except sqlite3.Error as error:
        raise SQLiteWorkflowError(
            f"Could not inspect SQLite database: {error}"
        ) from error
    return counts


def create_dated_backup(database_path, output_directory, prefix="inventory"):
    database_path = Path(database_path).expanduser().resolve()
    if not database_path.is_file():
        raise SQLiteWorkflowError(
            f"SQLite database does not exist: {database_path}"
        )

    output_directory = require_external_backup_directory(output_directory)
    try:
        output_directory.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise SQLiteWorkflowError(
            f"Could not create backup directory: {error}"
        ) from error

    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    backup_path = output_directory / f"{prefix}-{timestamp}.sqlite3"
    counter = 1
    while backup_path.exists():
        backup_path = output_directory / (
            f"{prefix}-{timestamp}-{counter}.sqlite3"
        )
        counter += 1

    _copy_database(database_path, backup_path)
    counts = inspect_database(backup_path)
    return backup_path, counts


def restore_database(backup_path, database_path):
    backup_path = Path(backup_path).expanduser().resolve()
    database_path = Path(database_path).expanduser().resolve()
    if backup_path == database_path:
        raise SQLiteWorkflowError(
            "The backup and live database paths must be different."
        )

    expected_counts = inspect_database(backup_path)
    try:
        database_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise SQLiteWorkflowError(
            f"Could not create database directory: {error}"
        ) from error

    try:
        with (
            closing(_connect_read_only(backup_path)) as source,
            closing(sqlite3.connect(str(database_path), timeout=1))
            as destination,
        ):
            source.backup(destination)
            destination.commit()
    except sqlite3.Error as error:
        raise SQLiteWorkflowError(
            f"Could not restore SQLite database: {error}"
        ) from error

    restored_counts = inspect_database(database_path)
    if restored_counts != expected_counts:
        raise SQLiteWorkflowError(
            "The restored database row counts do not match the backup."
        )
    return restored_counts


def _copy_database(source_path, destination_path):
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination_path.name}.",
        suffix=".tmp",
        dir=destination_path.parent,
    )
    os.close(file_descriptor)
    temporary_path = Path(temporary_name)
    try:
        with (
            closing(_connect_read_only(source_path)) as source,
            closing(sqlite3.connect(str(temporary_path))) as destination,
        ):
            source.backup(destination)
            destination.commit()
            integrity = destination.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]
            if integrity != "ok":
                raise SQLiteWorkflowError(
                    f"SQLite integrity check failed: {integrity}"
                )
        os.replace(temporary_path, destination_path)
    except (OSError, sqlite3.Error) as error:
        raise SQLiteWorkflowError(
            f"Could not create SQLite backup: {error}"
        ) from error
    finally:
        temporary_path.unlink(missing_ok=True)


def _connect_read_only(database_path):
    uri = f"{Path(database_path).resolve().as_uri()}?mode=ro"
    return sqlite3.connect(uri, uri=True)
