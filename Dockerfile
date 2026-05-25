FROM node:20 AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

FROM python:3.11-slim
WORKDIR /app

COPY backend/requirements.txt ./backend/
RUN pip install -r backend/requirements.txt

COPY backend/ ./backend/
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

RUN cd backend && python seed.py

EXPOSE 8000
CMD ["sh", "-c", "cd /app/backend && python3 -m uvicorn main:app --host 0.0.0.0 --port $PORT"]