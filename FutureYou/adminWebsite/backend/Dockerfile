# Build context must be the repo root (docker build -f FutureYou/adminWebsite/backend/Dockerfile .)
# This mirrors the repo directory structure so app.py's relative sys.path additions resolve correctly.
FROM python:3.9-slim

WORKDIR /repo

# Install dependencies
COPY FutureYou/adminWebsite/backend/requirements.txt FutureYou/adminWebsite/backend/
RUN pip install --no-cache-dir -r FutureYou/adminWebsite/backend/requirements.txt

# Flask app
COPY FutureYou/adminWebsite/backend/app.py FutureYou/adminWebsite/backend/

# Repo-root Xero auth helpers (added to sys.path via REPO_ROOT)
COPY xeroAuthHelper.py .
COPY xeroAuth.py .

# Shared helpers (dateStringsHelper, emailAttachment, etc.)
COPY helpers/ helpers/

# FutureYou-specific scripts (added to sys.path via FUTUREYOU_DIR)
COPY FutureYou/fetchFYAnnualLeave.py FutureYou/

# Talent map generator (added to sys.path via TALENT_MAP_DIR)
COPY FutureYou/bullhorn/talentMapping/ FutureYou/bullhorn/talentMapping/

# Logo assets referenced by the talent map generator
COPY FutureYou/forecastingWebsite/frontend/public/fy.png FutureYou/forecastingWebsite/frontend/public/
COPY FutureYou/forecastingWebsite/frontend/public/fy_you.png FutureYou/forecastingWebsite/frontend/public/

ENV PORT=8080

# Run gunicorn from the backend directory so __file__ resolves correctly
WORKDIR /repo/FutureYou/adminWebsite/backend
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app"]
