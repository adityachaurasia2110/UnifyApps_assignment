# Multi-stage build: Builds the React frontend and packages the FastAPI backend
# Stage 1: Build the React Frontend
FROM node:18-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# Stage 2: Python Backend with Static UI Serving
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code and SQLite database
COPY backend/ ./

# Copy built frontend assets so FastAPI can serve the single-page application
COPY --from=frontend-builder /app/frontend/dist /frontend/dist

# Expose default port
EXPOSE 8000

# Support dynamic PORT assigned by cloud platforms (Render, Railway, Cloud Run, etc.)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
