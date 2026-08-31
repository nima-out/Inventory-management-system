from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from inventory.database.sqlite import (
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
    help = "Validate and restore SQLite after making a safety backup."

    def add_arguments(self, parser):
        parser.add_argument("backup_path", type=Path)
        parser.add_argument("--backup-dir", type=Path)
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Confirm replacement of the live SQLite database.",
        )

    def handle(self, *args, **options):
        if not options["yes"]:
            raise CommandError(
                "Restore cancelled. Stop every database process and re-run "
                "with --yes."
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
                names = ", ".join(path.name for path in backup_sidecars)
                raise SQLiteWorkflowError(
                    "The selected backup has SQLite sidecar files "
                    f"({names}) and may be active."
                )

            connections.close_all()
            live_sidecars = get_sqlite_sidecars(database_path)
            if live_sidecars:
                names = ", ".join(path.name for path in live_sidecars)
                raise SQLiteWorkflowError(
                    "The live database has SQLite sidecar files "
                    f"({names}). Stop all database processes first."
                )

            if database_path.exists():
                safety_path, _ = create_dated_backup(
                    database_path,
                    safety_directory,
                    prefix="pre-restore",
                )
            else:
                safety_path = None
            restored_counts = restore_database(backup_path, database_path)
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
