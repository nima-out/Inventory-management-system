from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from inventory.sqlite_tools import (
    SQLiteWorkflowError,
    create_dated_backup,
    get_database_path,
    get_default_backup_directory,
)


class Command(BaseCommand):
    help = "Create and verify a dated SQLite backup outside the repository."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            type=Path,
            help=(
                "External backup directory. Defaults to a sibling directory "
                "named <project>-backups."
            ),
        )

    def handle(self, *args, **options):
        try:
            database_path = get_database_path()
            output_directory = (
                options["output_dir"] or get_default_backup_directory()
            )
            connections.close_all()
            backup_path, counts = create_dated_backup(
                database_path,
                output_directory,
            )
        except SQLiteWorkflowError as error:
            raise CommandError(str(error)) from error

        self.stdout.write(
            self.style.SUCCESS(f"Backup created: {backup_path}")
        )
        self.stdout.write("Integrity: ok")
        self.stdout.write(
            "Counts: "
            + ", ".join(
                f"{label}={count}" for label, count in counts.items()
            )
        )
