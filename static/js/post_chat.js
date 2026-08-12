// static/js/post_chat.js
(function(){
  const POST_ID = window.SWAPIFY_POST_ID || '1';
  const messagesEl = document.getElementById('messages');
  const titleEl = document.getElementById('postTitle');
  const descEl = document.getElementById('postDesc');
  const attachmentsEl = document.getElementById('attachments');
  const input = document.getElementById('messageInput');
  const nameInput = document.getElementById('chatName');
  const sendBtn = document.getElementById('sendBtn');

  function fetchPost(){
    fetch('/swapify-data.json').then(r=>r.json()).then(data=>{
      const items = data.items || [];
      const post = items.find(p=>String(p.id) === String(POST_ID)) || items[0] || {title:'Post', description:'No description', file_url:null, image_url:null};
      titleEl.textContent = post.title || 'Post';
      descEl.textContent = post.description || '';
      attachmentsEl.innerHTML = '';
      if(post.file_url){
        const a = document.createElement('a');
        a.href = post.file_url;
        a.target = '_blank';
        a.rel = 'noopener';
        a.download = '';
        a.textContent = 'Download / Open Attachment';
        attachmentsEl.appendChild(a);
      }
      if(post.image_url){
        const a = document.createElement('a');
        a.href = post.image_url;
        a.target = '_blank';
        a.rel = 'noopener';
        const img = document.createElement('img'); img.src = post.image_url; img.alt = 'image'; img.style.maxWidth='400px';
        a.appendChild(img);
        attachmentsEl.appendChild(a);
      }
    }).catch(()=>{
      titleEl.textContent = 'Post (offline)';
      descEl.textContent = '';
    });
  }

  function appendMessage(m){
    const d = document.createElement('div'); d.className='msg';
    d.innerHTML = `<strong>${escapeHtml(m.sender||'User')}:</strong> ${escapeHtml(m.content)} <div style="font-size:11px;color:#666">${new Date(m.createdAt).toLocaleString()}</div>`;
    messagesEl.appendChild(d);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function loadMessages(){
    fetch(`/api/posts/${POST_ID}/messages`).then(r=>r.json()).then(list=>{
      messagesEl.innerHTML = '';
      list.forEach(appendMessage);
    }).catch(console.error);
  }

  function sendMessage(){
    const content = input.value.trim();
    if(!content) return;
    const sender = (nameInput.value || '').trim() || 'Guest';
    fetch(`/api/posts/${POST_ID}/messages`, {
      method:'POST',headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ sender, content })
    }).then(r=>r.json()).then(res=>{
      if(res && res.ok){
        input.value='';
        loadMessages();
      }
    }).catch(console.error);
  }

  sendBtn.addEventListener('click', sendMessage);
  input.addEventListener('keydown', function(e){ if(e.key==='Enter') sendMessage(); });

  function escapeHtml(s){ return String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'","&#39;"); }

  // initial load and polling
  fetchPost();
  loadMessages();
  setInterval(loadMessages, 2500);
})();
