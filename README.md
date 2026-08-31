# Stockroom inventory system

This is a local, single-user Django inventory system for a guitar store. The
live SQLite database (`db.sqlite3`) is intentionally excluded from Git, so
database backups are the recovery source for real inventory and transaction
history.

## Back up SQLite

Stop the Django development server before planned maintenance. Then run:

```powershell
.\.venv\Scripts\python.exe manage.py backup_sqlite
```

The command creates a dated backup in a sibling directory named
`Inventory-management-system-backups`, outside the repository. It uses
SQLite's online backup API and verifies database integrity plus the user,
category, item, and transaction counts before reporting success.

To choose another external directory:

```powershell
.\.venv\Scripts\python.exe manage.py backup_sqlite `
  --output-dir C:\path\outside\the\repository
```

Keep at least one recent copy on another disk or trusted backup service. Do
not keep the only backup inside this repository.

## Restore SQLite

1. Stop every process using `db.sqlite3`, including `manage.py runserver`.
2. Select a dated `.sqlite3` backup.
3. Run the restore command with the explicit confirmation flag:

```powershell
.\.venv\Scripts\python.exe manage.py restore_sqlite `
  C:\path\to\inventory-YYYYMMDD-HHMMSS.sqlite3 --yes
```

Before changing the live database, the command validates the selected backup
and creates a dated `pre-restore` safety backup outside the repository. It
refuses to continue when SQLite journal/WAL sidecar files suggest the database
may still be in use. After restoration, it verifies integrity and prints the
restored row counts.

Run the normal project checks after restoring:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py check
```

The restore workflow preserves the complete database, including users, live
quantities, and immutable transaction history.

## Seed demo guitar-store data

After migrations and an administrator account exist, seed the catalog with:

```powershell
.\.venv\Scripts\python.exe manage.py seed_guitar_store --username admin
```

The named user must be active and have permission to add categories and items
and record inventory movements; a superuser already has those permissions.
The command creates 10 categories and 96 catalog items in one transaction.
Initial quantities are recorded through the inventory movement service.

The command is idempotent: rerunning it leaves existing categories, items,
quantities, and transaction history untouched and creates only missing demo
records. It is not a substitute for restoring a backup of live data.
