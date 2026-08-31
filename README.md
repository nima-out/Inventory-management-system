# Stockroom inventory system

Stockroom is a local Django inventory application for a single-user guitar
store. It manages categories, items, stock movements, low-stock warnings, and
immutable transaction history using SQLite.

## Reproducible local setup

The supported development environment is Python 3.13.13 with the versions in
`requirements.txt`.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py check
python manage.py runserver
```

Open `http://127.0.0.1:8000/` and sign in with the superuser account. Django is
configured for the `Asia/Tehran` timezone. The local `db.sqlite3` file is
ignored by Git and is not branch-specific.

Run the complete test suite with:

```powershell
python manage.py test
```

Tests use Django's isolated temporary database and do not modify `db.sqlite3`.

## Back up SQLite

Stop the development server before planned maintenance, then run:

```powershell
python manage.py backup_sqlite
```

The command creates a dated backup in a sibling directory named
`Inventory-management-system-backups`, outside the repository. It uses
SQLite's backup API and verifies integrity plus the user, category, item, and
transaction counts. Choose another external directory with `--output-dir`.

Keep at least one recent copy on another disk or trusted backup service.

## Restore SQLite

Stop every process using `db.sqlite3`, then run:

```powershell
python manage.py restore_sqlite C:\path\to\inventory-backup.sqlite3 --yes
```

The restore command validates the selected file first and creates a dated
`pre-restore` safety backup outside the repository. It refuses to continue
when journal/WAL sidecars suggest that SQLite may still be active. After the
restore, run `python manage.py migrate` and `python manage.py check`.

## Seed demo guitar-store data

After migrations and a superuser exist, run:

```powershell
python manage.py seed_guitar_store --username admin
```

The command creates 10 categories and 96 items in one transaction. Initial
quantities are recorded through the inventory movement service. Rerunning it
leaves existing records, quantities, and history untouched and creates only
missing demo records. Seeding is not a substitute for restoring live data.
