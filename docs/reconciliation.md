# Optional reconciliation schedule

Reconciliation catches exports missed by hooks and differences from interrupted writes.
It uses local transcripts and the current parsers. It does not require a network connection.
The examples contain placeholder paths. Keep real exports and reports outside public repositories.

## Review a manual run

1. Use the installed executable from its absolute path:

   ```bash
   /path/to/agent-sessions/.venv/bin/agent-sessions reconcile --dry-run --json
   ```

2. Review the proposed exports and source errors.
3. Run reconciliation:

   ```bash
   /path/to/agent-sessions/.venv/bin/agent-sessions reconcile --lock-timeout 60
   ```

4. Review `~/.agent-sessions/exports/reconcile.json`.
5. Run the command again to check that exports remain unchanged:

   ```bash
   /path/to/agent-sessions/.venv/bin/agent-sessions reconcile --dry-run --json
   ```

The executable must come from an environment where this package is installed.
The default destination is private and does not depend on the current directory.
Use the same `-o /path/to/private-exports/` argument in every command for a custom destination.
Dry runs do not create directories, lock files, or reports.

## Add an hourly cron entry

Cron is optional. These instructions do not install or enable a schedule automatically.

1. Open the current user's crontab with `crontab -e`.
2. Add this entry after replacing the executable path:

   ```cron
   15 * * * * umask 077; /path/to/agent-sessions/.venv/bin/agent-sessions reconcile --lock-timeout 60 >> "$HOME/.agent-sessions/reconcile.log" 2>&1
   ```

3. Save the crontab.
4. After the next scheduled run, inspect the private log and `reconcile.json`.

The manual run creates the parent directory for the log.
The entry runs at minute 15 of every hour while the computer and cron service are active.
Cron uses the current user's home directory to discover sources.
The absolute executable path avoids dependency on shell activation or the cron search path.
The log can grow over time. Archive or truncate it locally when necessary.

## Handle errors

A successful scan returns exit code `0`. Source, storage, and index errors return `1`.
The report lists source groups as exported, unchanged, empty, or error.
Dry runs use `would_export` instead of `exported`.

Reconciliation reads all discovered sources on every run. It only writes session exports that differ.
A directory lock serializes reconciliation with other export writers.
A long scan can exceed a waiting hook's lock timeout. The next reconciliation can catch that missed export.
If the lock wait expires, the command stops without replacing exports.

If a source changes during parsing, run reconciliation again after the agent finishes.
If an index is invalid or missing, run `doctor` and restore the index from a private backup.
An invalid index stops the run before any exports are replaced.
A write failure can leave complete files from different attempts and an older report.
A later run repairs those differences when the sources and indexes remain readable.

## Remove the schedule

1. Open the current user's crontab with `crontab -e`.
2. Delete only the reconciliation entry.
3. Save the crontab.

The exports remain available after the schedule is removed.
