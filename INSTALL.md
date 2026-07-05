# Installation Guide

This system runs entirely on your local network — no internet access required after initial setup. It installs via Docker and opens in any browser.

---

## What you need

| Requirement | Minimum | Notes |
|-------------|---------|-------|
| Operating System | Windows 10/11, macOS 12+, or Ubuntu 22+ | |
| RAM | 4 GB | 8 GB recommended |
| Disk | 5 GB free | |
| Docker Desktop | 4.x or later | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop) |
| Python | 3.11+ | Only for building the bridge agent |
| NFC card reader | USB PC/SC (e.g. ACR122U) | Optional — for card enrolment |
| Card printer | USB or network (Zebra, Fargo, Evolis, Magicard) | Optional |

---

## Step 1 — Clone or copy the project

Place the `employee-management-app` folder anywhere on your machine.

---

## Step 2 — Create your .env file

```bash
cd employee-management-app
copy .env.example .env        # Windows
# cp .env.example .env        # macOS / Linux
```

Open `.env` and set these **required** values:

```
SECRET_KEY=<64-char random hex>
JWT_SECRET_KEY=<different 64-char random hex>
POSTGRES_PASSWORD=<strong database password>
BRIDGE_AGENT_SECRET=<random secret — must match bridge agent config>
```

Generate random secrets:
```bash
python -c "import secrets; print(secrets.token_hex(64))"
```
Run it twice — one value for `SECRET_KEY`, a different one for `JWT_SECRET_KEY`.

---

## Step 3 — Start the application

```bash
docker compose --profile prod up -d
```

This starts:
- **PostgreSQL** — database (data persisted in Docker volume)
- **Redis** — session cache
- **Backend** — FastAPI API (runs database migrations automatically on first start)
- **Nginx** — serves the React frontend and proxies API calls

Wait about 30 seconds for all services to become healthy, then open **http://localhost** in your browser.

---

## Step 4 — First-time setup wizard

On first visit you will see the setup wizard. Complete it to:
1. Enter your company name (appears on all ID cards)
2. Create the super_admin account (email + strong password)
3. Scan the QR code with an authenticator app (Google Authenticator, Authy, etc.)
4. Verify the 6-digit code — setup complete

You are then logged in and ready to use the system.

---

## Step 5 — Install the Bridge Agent (NFC reader + card printer)

The bridge agent runs on the **host PC** (not inside Docker) because it needs direct USB access to hardware.

### Windows

1. Open a Command Prompt in `bridge_agent\`
2. Run: `build_windows.bat`
3. Edit `dist\bridge_agent.env` — set `BRIDGE_AGENT_SECRET` to the same value as in `.env`
4. Double-click `dist\bridge_agent.exe` to start

### macOS / Linux

```bash
cd bridge_agent
chmod +x build_unix.sh
./build_unix.sh
nano dist/bridge_agent.env    # set BRIDGE_AGENT_SECRET
./dist/bridge_agent
```

**Linux only:** ensure the PC/SC daemon is running:
```bash
sudo systemctl start pcscd
sudo systemctl enable pcscd
```

**macOS only:** you may need to grant the app permission to access USB devices when prompted by the OS.

### Test without hardware

Run in mock mode — simulates NFC taps and print jobs without physical devices:
```bash
bridge_agent\run_dev.bat      # Windows
python bridge_agent/main.py --mock   # any platform
```

---

## Connecting the bridge agent to the app

1. In the app, go to **Settings → Bridge Agent**
2. The sidebar shows the connection status (green = connected)
3. The agent auto-connects when the frontend is open in the browser

---

## Everyday operation

| Task | Command |
|------|---------|
| Start system | `docker compose --profile prod up -d` |
| Stop system | `docker compose down` |
| View logs | `docker compose logs -f backend` |
| Database backup | `docker compose exec db pg_dump -U ems_user ems_db > backup.sql` |
| Restore backup | `docker compose exec -T db psql -U ems_user ems_db < backup.sql` |
| Restart backend | `docker compose restart backend` |

---

## Development mode (hot-reload)

Run just the databases in Docker, then start the backend and frontend locally:

```bash
# Terminal 1 — databases
docker compose up db redis

# Terminal 2 — backend (hot-reload)
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

# Terminal 3 — frontend (Vite dev server)
cd frontend
npm install
npm run dev
```

Frontend: http://localhost:3000  
API: http://localhost:8000  
Vite proxies `/api` → backend automatically.

---

## Upgrading

1. Pull new files into `employee-management-app/`
2. Run: `docker compose --profile prod up -d --build`
3. The backend runs `alembic upgrade head` automatically on restart

---

## Troubleshooting

**"SECRET_KEY is the insecure default" on startup**
→ Open `.env` and set `SECRET_KEY` to a freshly generated 64-char hex value.

**Database connection refused**
→ Wait 30 seconds for PostgreSQL to finish initialising, then `docker compose restart backend`.

**Bridge agent shows "disconnected" in the app**
→ Check that `bridge_agent.exe` is running and `BRIDGE_AGENT_SECRET` matches the backend `.env`.

**NFC reader not detected**
→ Windows: ensure the PC/SC Smart Card service is running (Services → Smart Card).  
→ Linux: `sudo systemctl start pcscd`.  
→ Try `--mock` mode to confirm the bridge agent itself works.

**Photos not loading after restart**
→ The `photos` Docker volume persists data. Run `docker volume ls` to confirm it exists.

**Port 80 already in use**
→ Edit `docker-compose.yml` and change `"80:80"` to `"8080:80"`, then open http://localhost:8080.
