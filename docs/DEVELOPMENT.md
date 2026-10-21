# Development

[← Project home](../README.md)

## Run from source

Use 64-bit Windows 10/11 and Python 3.13 with Tkinter. Run these commands from the repository root:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src/setup_maps.py
.\.venv\Scripts\python.exe src/app.py
```

Alternatively, run `scripts/setup.ps1`, then `scripts/run.ps1`. The map installer reads data literals without executing upstream JavaScript. Downloaded map files are ignored by Git. They are required for vision and map tests.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover
```

Tests use disposable ledgers and loopback relay instances. Desktop tests require a Windows desktop session. The tests package adds `src/` to the import path, matching the standalone application modules. Keep regressions under `tests/` and never commit personal captures or databases.

## Build the Windows executable

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm "packaging/Aniimo Tracker.spec"
```

Or run `scripts/build.ps1` after installing PyInstaller. The output is `dist/AniimoTracker.exe`. The specification resolves paths from the repository, bundles the app icon and anonymized tutorial examples, and excludes downloaded map art/data. Users install the maps through the app on first use.

## Release checklist

1. Update `src/version.py` and `updates.json` with the same version and exact GitHub asset URL.
2. Run the tests, build, and exercise the packaged app using temporary data.
3. Inspect bundled assets for personal files and downloaded third-party map files.
4. Commit the source, create the corresponding version tag/release, and upload `AniimoTracker.exe` with a SHA-256 checksum.
5. Verify the release digest, download URL and update feed.

Release binaries belong in GitHub Releases, not Git history. Preserve library licenses and [third-party notices](../THIRD_PARTY_NOTICES.md).
