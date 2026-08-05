# Swapify Server (dev)

This simple Node/Express server provides a lightweight API for storing and retrieving Swapify notices during local development.

Quick start

1. Install dependencies:

```bash
cd HTML/server
npm install
```

2. Start server:

```bash
npm start
```

3. The server runs on `http://localhost:3000`. API endpoints:
- `GET /api/notices` — list notices
- `POST /api/notices` — add a notice (JSON body)
- `DELETE /api/notices` — clear notices

The server also serves the parent `HTML` folder so you can open `Swapify1.html` via `http://localhost:3000/Swapify1.html` for testing.
