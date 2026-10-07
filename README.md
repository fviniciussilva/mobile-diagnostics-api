# Mobile Diagnostics API
FastAPI service for mobile device diagnostics via ADB (Android) and libimobiledevice (iOS)

## Features
- **Android**: Device info, battery, storage, security, hardware, software, network, IMEI, backup via ADB
- **iOS**: Device info, battery, storage, security, hardware, software, network, IMEI/MEID, backup via libimobiledevice
- **PostgreSQL** persistence with SQLAlchemy 2.0 + async
- **Background tasks** for long-running diagnostics
- **REST API** with OpenAPI docs
- **Docker** ready with docker-compose

## Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 15+
- ADB (Android SDK Platform Tools)
- libimobiledevice (for iOS): `idevice_id`, `ideviceinfo`, `idevicebackup2`

### Local Development
```bash
# Clone and enter
cd mobile-diagnostics-api

# Create virtual env
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install deps
pip install -e ".[dev]"

# Copy env and configure
cp .env.example .env
# Edit .env with your DATABASE_URL, SECRET_KEY, etc.

# Run migrations
alembic upgrade head

# Start API
uvicorn app.main:app --reload
```

### Docker
```bash
# Build and run
docker-compose up --build

# API at http://localhost:8000
# Docs at http://localhost:8000/docs
```

## API Endpoints

### Devices
- `GET /api/v1/devices` - List devices (paginated, filterable)
- `POST /api/v1/devices` - Register device manually
- `GET /api/v1/devices/{id}` - Get device by ID
- `GET /api/v1/devices/serial/{serial}` - Get device by serial
- `PATCH /api/v1/devices/{id}` - Update device
- `DELETE /api/v1/devices/{id}` - Delete device
- `POST /api/v1/devices/scan/android` - Scan & register Android devices via ADB
- `POST /api/v1/devices/scan/ios` - Scan & register iOS devices via libimobiledevice

### Diagnostics
- `POST /api/v1/diagnostics/run` - Start diagnostic (async, returns diagnostic_id)
- `GET /api/v1/diagnostics` - List diagnostics (paginated, filterable)
- `GET /api/v1/diagnostics/{id}` - Get diagnostic result
- `GET /api/v1/diagnostics/device/{serial}` - Get diagnostics for device
- `POST /api/v1/diagnostics/imei-check` - Validate IMEI (Luhn algorithm)

### Health
- `GET /api/v1/health` - Basic health
- `GET /api/v1/health/db` - Database connectivity
- `GET /api/v1/health/adb` - ADB availability
- `GET /api/v1/health/ios` - iOS tools availability

## Diagnostic Types
| Type | Android | iOS | Description |
|------|---------|-----|-------------|
| `basic_info` | ✅ | ✅ | Model, OS version, serial, hardware |
| `battery` | ✅ | ✅ | Level, health, temperature, charging |
| `storage` | ✅ | ✅ | Total/used/free space |
| `network` | ✅ | ✅ | Interfaces, WiFi, cellular |
| `security` | ✅ | ✅ | Root/jailbreak, encryption, passcode |
| `hardware` | ✅ | ✅ | CPU, hardware model |
| `software` | ✅ | ✅ | Installed packages/apps |
| `full` | ✅ | ✅ | All of the above |
| `backup` | ✅ | ✅ | Full device backup |
| `imei_check` | ✅ | ✅ | IMEI/MEID validation |

## Project Structure
```
mobile-diagnostics-api/
├── app/
│   ├── api/v1/          # FastAPI routers
│   ├── core/            # Config, database, security
│   ├── models/          # SQLAlchemy models
│   ├── schemas/         # Pydantic schemas
│   ├── services/        # ADB, iOS business logic
│   └── main.py          # App factory
├── tests/               # Pytest tests
├── scripts/             # Utility scripts
├── alembic/             # DB migrations
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

## Environment Variables
See `.env.example` for all options. Key ones:
- `DATABASE_URL` - PostgreSQL async connection string
- `SECRET_KEY` - JWT signing key (change in production!)
- `ADB_PATH` - Path to adb binary
- `IDEVICE_ID_PATH` - Path to idevice_id
- `LOG_LEVEL` - DEBUG, INFO, WARNING, ERROR

## Testing
```bash
pytest -v --cov=app --cov-report=term-missing
```

## License
MIT