from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from inventory.sqlite_tools import (
    SQLiteWorkflowError,
    create_dated_backup,
    get_database_path,
    get_default_backup_directory,
    get_sqlite_sidecars,
    inspect_database,
    require_external_backup_directory,
    restore_database,
)


class Command(BaseCommand):
    help = (
        "Validate and restore a SQLite backup after making a safety backup."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "backup_path",
            type=Path,
            help="Path to the SQLite backup to restore.",
        )
        parser.add_argument(
            "--backup-dir",
            type=Path,
            help=(
                "Directory for the pre-restore safety backup. Defaults to a "
                "sibling directory named <project>-backups."
            ),
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Confirm replacement of the live SQLite database.",
        )

    def handle(self, *args, **options):
        if not options["yes"]:
            raise CommandError(
                "Restore cancelled. Re-run with --yes after stopping every "
                "process that uses the database."
            )

        backup_path = options["backup_path"].expanduser().resolve()

        try:
            database_path = get_database_path()
            safety_directory = require_external_backup_directory(
                options["backup_dir"] or get_default_backup_directory()
            )
            inspect_database(backup_path)
            backup_sidecars = get_sqlite_sidecars(backup_path)
            if backup_sidecars:
                sidecar_names = ", ".join(
                    path.name for path in backup_sidecars
                )
                raise SQLiteWorkflowError(
                    "The selected backup has SQLite sidecar files "
                    f"({sidecar_names}) and may be an active database."
                )

            connections.close_all()

            sidecars = get_sqlite_sidecars(database_path)
            if sidecars:
                sidecar_names = ", ".join(path.name for path in sidecars)
                raise SQLiteWorkflowError(
                    "SQLite sidecar files are present "
                    f"({sidecar_names}). Stop every database process and "
                    "resolve the journal/WAL files before restoring."
                )

            if database_path.exists():
                safety_path, _ = create_dated_backup(
                    database_path,
                    safety_directory,
                    prefix="pre-restore",
                )
            else:
                safety_path = None

            restored_counts = restore_database(
                backup_path,
                database_path,
            )
        except SQLiteWorkflowError as error:
            raise CommandError(str(error)) from error

        if safety_path:
            self.stdout.write(f"Safety backup: {safety_path}")
        self.stdout.write(
            self.style.SUCCESS(f"Database restored from: {backup_path}")
        )
        self.stdout.write("Integrity: ok")
        self.stdout.write(
            "Counts: "
            + ", ".join(
                f"{label}={count}"
                for label, count in restored_counts.items()
            )
        )
