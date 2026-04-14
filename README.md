# Safe Computer Class

Safe Computer Class (SCC) is a school file-access service with:
- Linux server-side API for RFID and PIN verification
- Samba share for students and teachers
- Windows GUI client and PIN daemon

## Docker Quick Start (Linux/macOS/Windows)

1. Install Docker Desktop (Windows/macOS) or Docker Engine (Linux).
2. Ensure Linux containers mode is enabled (required on Windows).
3. Start the stack:

```bash
docker compose up -d --build
```

4. API will be available at:
- `http://localhost:8080/api/scc/verify_card`

5. SMB share (`school`) will be available on:
- TCP `445` and `139`

## Windows Notes

- Run Docker Desktop with WSL2 backend.
- Use named volumes (already configured in `docker-compose.yml`) for better cross-platform behavior.
- Do not rely on Linux bind-mount ACL behavior when data is on NTFS.

## Security Improvements Included

- Removed `shell=True` in Windows mount code paths.
- Replaced `bash -c` password piping with direct `stdin` for `smbpasswd`.
- Added `SCC_USE_SUDO` switch to run safely inside containers.

## Environment

Copy `.env.example` to `.env` and adjust if needed:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```
