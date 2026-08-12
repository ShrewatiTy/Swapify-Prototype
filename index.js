const express = require('express');
const cors = require('cors');
const bodyParser = require('body-parser');
const fs = require('fs');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;
const DATA_FILE = path.join(__dirname, 'notices.json');
const MESSAGES_FILE = path.join(__dirname, 'messages.json');

app.use(cors());
app.use(bodyParser.json());
app.use(express.static(path.join(__dirname, '.'))); // serve site files

function readNotices(){
  try{ const raw = fs.readFileSync(DATA_FILE,'utf8'); return JSON.parse(raw); }catch(e){ return []; }
}
function writeNotices(list){ fs.writeFileSync(DATA_FILE, JSON.stringify(list, null, 2), 'utf8'); }

function readMessages(){
  try{ const raw = fs.readFileSync(MESSAGES_FILE,'utf8'); return JSON.parse(raw); }catch(e){ return {}; }
}
function writeMessages(obj){ fs.writeFileSync(MESSAGES_FILE, JSON.stringify(obj, null, 2), 'utf8'); }

app.get('/api/notices', (req, res) => {
  res.json(readNotices());
});

app.post('/api/notices', (req, res) => {
  const notice = req.body;
  if(!notice || !notice.text) return res.status(400).json({ error: 'Invalid notice' });
  const list = readNotices();
  notice.createdAt = new Date().toISOString();
  list.push(notice);
  writeNotices(list);
  res.json({ ok: true, notice });
});

app.delete('/api/notices', (req, res) => {
  writeNotices([]);
  res.json({ ok: true });
});

// Messages API for per-post chat (simple file-backed store)
app.get('/api/posts/:id/messages', (req, res) => {
  const postId = req.params.id;
  const all = readMessages();
  const list = all[postId] || [];
  res.json(list);
});

app.post('/api/posts/:id/messages', (req, res) => {
  const postId = req.params.id;
  const payload = req.body || {};
  const content = (payload.content || '').trim();
  const sender = (payload.sender || 'Guest').trim() || 'Guest';
  if(!content) return res.status(400).json({ error: 'Empty message' });

  const all = readMessages();
  if(!all[postId]) all[postId] = [];
  const msg = {
    id: Date.now(),
    sender: sender,
    content: content,
    createdAt: new Date().toISOString()
  };
  all[postId].push(msg);
  writeMessages(all);
  res.json({ ok: true, message: msg });
});

app.listen(PORT, () => {
  console.log(`Swapify API running on http://localhost:${PORT}`);
});
