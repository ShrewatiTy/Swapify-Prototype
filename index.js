const express = require('express');
const cors = require('cors');
const bodyParser = require('body-parser');
const fs = require('fs');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;
const DATA_FILE = path.join(__dirname, 'notices.json');

app.use(cors());
app.use(bodyParser.json());
app.use(express.static(path.join(__dirname, '..'))); // serve site files for convenience

function readNotices(){
  try{ const raw = fs.readFileSync(DATA_FILE,'utf8'); return JSON.parse(raw); }catch(e){ return []; }
}
function writeNotices(list){ fs.writeFileSync(DATA_FILE, JSON.stringify(list, null, 2), 'utf8'); }

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

app.listen(PORT, () => {
  console.log(`Swapify notice API running on http://localhost:${PORT}`);
});
