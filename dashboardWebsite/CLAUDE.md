# CLAUDE.md — Dashboard (dashboardWebsite/)

This folder contains the web dashboard that triggers client automation workflows.

## Stack
- **Frontend**: React + Vite + Tailwind CSS + DaisyUI (`frontend/`)
- **Backend**: Python Flask (`backend/app.py`)
- **Database**: Firestore (logs workflow trigger calls)

## Commands

### Frontend
```bash
cd dashboardWebsite/frontend
npm run dev       # Start Vite dev server
npm run build     # Production build
npm run lint      # ESLint
npm run preview   # Preview production build
```

### Backend
```bash
pip install -r dashboardWebsite/backend/requirements.txt
python dashboardWebsite/backend/app.py
# Or via Docker:
docker build -t dashboard-backend ./dashboardWebsite/backend
docker run -p 5000:5000 dashboard-backend
```

## Backend API Pattern
- Endpoint: `POST /api/trigger/{workflow}` — dispatches a named GitHub Actions workflow via the GitHub API
- All trigger calls are logged to Firestore (who ran it, when, which workflow)
- Uses `GH_PAT` env var to authenticate with GitHub API

## Key Files
| File | Purpose |
|------|---------|
| `backend/app.py` | Flask REST API — main entry point |
| `backend/addUser.py` | User management utility |
| `backend/user_database.py` | Firestore user database helpers |

## Coding Style & Conventions
<!-- TODO: Component patterns, state management approach, API call conventions, styling rules -->
