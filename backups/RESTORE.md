# Restoring from backup

Backups are written here automatically every 24 hours by the `backup` container:

- `db_YYYYMMDD_HHMMSS.dump` — full PostgreSQL database (custom format, from `pg_dump -Fc`)
- `photos_YYYYMMDD_HHMMSS.tar.gz` — all ID photos

The last 14 days are kept; older files are pruned automatically.

> **Off-machine copy:** this folder lives on the host disk, so it survives a wiped
> Docker volume — but NOT a dead disk. Copy these files to another drive or cloud
> location periodically for real disaster protection.

## Restore the database

Pick the dump you want (usually the newest) and run, from the project folder:

```bash
# 1. Copy the dump into the running db container
docker compose cp ./backups/db_YYYYMMDD_HHMMSS.dump db:/tmp/restore.dump

# 2. Restore it (drops and recreates objects; --clean --if-exists is safe to re-run)
docker compose exec db pg_restore -U ems_user -d ems_db --clean --if-exists /tmp/restore.dump
```

If you'd rather restore into a fresh empty database, stop the app first, recreate
the `db_data` volume, start only `db`, then run the two commands above.

## Restore the photos

```bash
# Extract the archive into the photos volume (via the backup container)
docker compose exec backup sh -c "tar xzf /backups/photos_YYYYMMDD_HHMMSS.tar.gz -C /photos"
```

## Verify

Restart the stack and log in:

```bash
docker compose restart backend
```

Check that people, contracts and photos all appear as expected.
