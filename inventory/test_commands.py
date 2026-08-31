import sqlite3
from contextlib import closing
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import Sum
from django.test import SimpleTestCase, TestCase

from .models import Category, Item, TransactionHistory


class SQLiteRecoveryCommandTests(SimpleTestCase):
    databases = set()

    def create_database(self, database_path, marker):
        with closing(sqlite3.connect(str(database_path))) as database:
            database.executescript(
                """
                CREATE TABLE auth_user (id INTEGER PRIMARY KEY);
                CREATE TABLE inventory_category (id INTEGER PRIMARY KEY);
                CREATE TABLE inventory_item (id INTEGER PRIMARY KEY);
                CREATE TABLE inventory_transactionhistory (
                    id INTEGER PRIMARY KEY
                );
                CREATE TABLE recovery_marker (value TEXT NOT NULL);
                INSERT INTO auth_user DEFAULT VALUES;
                INSERT INTO inventory_category DEFAULT VALUES;
                INSERT INTO inventory_item DEFAULT VALUES;
                INSERT INTO inventory_transactionhistory DEFAULT VALUES;
                """
            )
            database.execute(
                "INSERT INTO recovery_marker (value) VALUES (?)",
                [marker],
            )
            database.commit()

    def read_marker(self, database_path):
        with closing(sqlite3.connect(str(database_path))) as database:
            return database.execute(
                "SELECT value FROM recovery_marker"
            ).fetchone()[0]

    def test_backup_command_creates_verified_external_copy(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            live_database = root / "live.sqlite3"
            backup_directory = root / "backups"
            self.create_database(live_database, "live")
            output = StringIO()

            with patch(
                "inventory.management.commands.backup_sqlite."
                "get_database_path",
                return_value=live_database,
            ):
                call_command(
                    "backup_sqlite",
                    output_dir=backup_directory,
                    stdout=output,
                )

            backups = list(backup_directory.glob("inventory-*.sqlite3"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(self.read_marker(backups[0]), "live")
            self.assertIn("Integrity: ok", output.getvalue())
            self.assertIn("users=1", output.getvalue())

    def test_restore_drill_uses_only_temporary_databases(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            live_database = root / "live.sqlite3"
            recovery_database = root / "recovery.sqlite3"
            safety_directory = root / "safety"
            self.create_database(live_database, "before-restore")
            self.create_database(recovery_database, "recovered")
            output = StringIO()

            with patch(
                "inventory.management.commands.restore_sqlite."
                "get_database_path",
                return_value=live_database,
            ):
                call_command(
                    "restore_sqlite",
                    str(recovery_database),
                    backup_dir=safety_directory,
                    yes=True,
                    stdout=output,
                )

            safety_backups = list(
                safety_directory.glob("pre-restore-*.sqlite3")
            )
            self.assertEqual(self.read_marker(live_database), "recovered")
            self.assertEqual(len(safety_backups), 1)
            self.assertEqual(
                self.read_marker(safety_backups[0]),
                "before-restore",
            )
            self.assertIn("Database restored from", output.getvalue())
            self.assertIn("Integrity: ok", output.getvalue())

    def test_restore_requires_explicit_confirmation(self):
        with self.assertRaisesMessage(CommandError, "Restore cancelled"):
            call_command("restore_sqlite", "unused.sqlite3")


class SeedGuitarStoreCommandTests(TestCase):
    def test_seed_is_complete_and_idempotent(self):
        actor = get_user_model().objects.create_superuser(
            username="seed-manager",
            password="test-password",
        )

        call_command(
            "seed_guitar_store",
            username=actor.username,
            stdout=StringIO(),
        )
        first_counts = (
            Category.objects.count(),
            Item.objects.count(),
            TransactionHistory.objects.count(),
            Item.objects.aggregate(total=Sum("quantity"))["total"],
        )

        call_command(
            "seed_guitar_store",
            username=actor.username,
            stdout=StringIO(),
        )
        second_counts = (
            Category.objects.count(),
            Item.objects.count(),
            TransactionHistory.objects.count(),
            Item.objects.aggregate(total=Sum("quantity"))["total"],
        )

        self.assertEqual(first_counts, (10, 96, 91, 1345))
        self.assertEqual(second_counts, first_counts)
