const http = require('http');
const fs = require('fs');
const path = require('path');
const https = require('https');

const PORT = process.env.PORT || 3000;
const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
const GEMINI_MODEL = process.env.GEMINI_MODEL || 'gemini-2.5-flash-lite';
const ROOT_DIR = __dirname;

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.txt': 'text/plain; charset=utf-8',
  '.pdf': 'application/pdf'
};

function sendJson(res, statusCode, payload) {
  res.writeHead(statusCode, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(payload));
}

function readFile(filePath) {
  return new Promise((resolve, reject) => {
    fs.readFile(filePath, (error, data) => {
      if (error) {
        reject(error);
        return;
      }
      resolve(data);
    });
  });
}

function serveStaticFile(res, filePath) {
  const ext = path.extname(filePath).toLowerCase();
  const contentType = MIME_TYPES[ext] || 'application/octet-stream';

  readFile(filePath)
    .then((data) => {
      res.writeHead(200, { 'Content-Type': contentType });
      res.end(data);
    })
    .catch(() => {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Not found');
    });
}

function getRequestBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', (chunk) => {
      body += chunk;
      if (body.length > 1e6) {
        req.connection.destroy();
      }
    });
    req.on('end', () => {
      try {
        resolve(body ? JSON.parse(body) : {});
      } catch (error) {
        reject(error);
      }
    });
    req.on('error', reject);
  });
}

function proxyGemini(req, res, query) {
  if (!GEMINI_API_KEY) {
    sendJson(res, 500, { error: 'Set the GEMINI_API_KEY environment variable before starting the server.' });
    return;
  }

  const payload = {
    contents: [{ role: 'user', parts: [{ text: query }] }],
    generationConfig: {
      temperature: 0.7,
      maxOutputTokens: 500
    }
  };

  const options = {
    hostname: 'generativelanguage.googleapis.com',
    path: `/v1beta/models/${encodeURIComponent(GEMINI_MODEL)}:generateContent?key=${encodeURIComponent(GEMINI_API_KEY)}`,
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Content-Length': Buffer.byteLength(JSON.stringify(payload))
    }
  };

  const request = https.request(options, (response) => {
    let data = '';
    response.on('data', (chunk) => {
      data += chunk;
    });
    response.on('end', () => {
      try {
        const parsed = data ? JSON.parse(data) : {};
        if (response.statusCode >= 400) {
          sendJson(res, 502, { error: parsed?.error?.message || 'Gemini request failed.' });
          return;
        }

        const reply = parsed?.candidates?.[0]?.content?.parts
          ?.map((part) => part.text)
          .filter(Boolean)
          .join('\n')
          .trim();

        sendJson(res, 200, { reply: reply || 'I could not generate a response right now.' });
      } catch (error) {
        sendJson(res, 502, { error: 'The Gemini response could not be parsed.' });
      }
    });
  });

  request.on('error', () => {
    sendJson(res, 502, { error: 'Unable to reach the Gemini API right now.' });
  });

  request.write(JSON.stringify(payload));
  request.end();
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);

  if (req.method === 'POST' && url.pathname === '/api/ai') {
    getRequestBody(req)
      .then((body) => {
        const query = typeof body?.query === 'string' ? body.query.trim() : '';
        if (!query) {
          sendJson(res, 400, { error: 'Please provide a query.' });
          return;
        }
        proxyGemini(req, res, query);
      })
      .catch(() => {
        sendJson(res, 400, { error: 'Invalid JSON body.' });
      });
    return;
  }

  if (req.method === 'GET' && url.pathname === '/') {
    serveStaticFile(res, path.join(ROOT_DIR, 'index.html'));
    return;
  }

  const requestedPath = url.pathname === '/' ? '/index.html' : url.pathname;
  const filePath = path.join(ROOT_DIR, requestedPath);

  if (!filePath.startsWith(ROOT_DIR)) {
    sendJson(res, 403, { error: 'Forbidden' });
    return;
  }

  fs.existsSync(filePath) && fs.statSync(filePath).isFile()
    ? serveStaticFile(res, filePath)
    : serveStaticFile(res, path.join(ROOT_DIR, 'index.html'));
});

server.listen(PORT, () => {
  console.log(`Swapify AI backend is running at http://localhost:${PORT}`);
  console.log('Set GEMINI_API_KEY before starting if you want live Gemini replies.');
});
