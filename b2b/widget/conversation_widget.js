(function(global){
  function createWidget(options){
    const target = document.getElementById(options.targetId);
    if(!target){throw new Error('Target element not found');}
    target.innerHTML = '';
    const apiBase = options.apiBase || '';
    const apiKey = options.apiKey || '';
    const device = options.device || 'desktop'; // desktop/tablet/phone
    const widthMode = options.widthMode || 'normal'; // wide/normal/narrow
    const border = options.border !== false;
    const theme = options.theme || 'dark';
    const userId = options.userId || '';
    const storageKey = `blitz_stream_${userId}_${apiBase}`;
    let conversations = [];
    // Remove localStorage persistence for conversationId
    // let stored = {};
    // try{stored = JSON.parse(localStorage.getItem(storageKey) || '{}');}catch(_){stored={};}

    // Always start with a fresh conversationId for each page load
    let conversationId = '';
    console.log('conversationId', conversationId);

    // Create a wrapper for scaling
    const wrapper = document.createElement('div');
    wrapper.className = `blitz-device-${device}`;
    wrapper.style.display = 'flex';
    wrapper.style.justifyContent = 'center';

    // Widget container
    const container = document.createElement('div');
    container.className = `blitz-widget-container blitz-width-${widthMode}`;
    if(!border) container.classList.add('blitz-no-border');
    if(theme==='dark') container.classList.add('blitz-theme-dark');
    if(theme==='light') container.classList.add('blitz-theme-light');

    // Header with logo in top right
    const header = document.createElement('div');
    header.className = 'blitz-widget-header';
    header.style.padding = '1.25rem 1rem 0.5rem 1rem';
    header.style.display = 'flex';
    header.style.alignItems = 'center';
    header.style.justifyContent = 'space-between';
    // Left: icons, Right: logo
    header.innerHTML = `
      <div class="blitz-header-left" style="display:flex;align-items:center;gap:0.5rem;">
        <button class="blitz-history-btn" style="background:none;border:none;cursor:pointer;color:inherit;">
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 256 256">
            <g transform="translate(1.4065934065934016 1.4065934065934016) scale(2.81 2.81)" fill="currentColor" stroke="none">
              <path d="M 48.831 86.169 c -13.336 0 -25.904 -6.506 -33.62 -17.403 c -2.333 -3.295 -4.163 -6.901 -5.437 -10.717 l 5.606 -1.872 c 1.09 3.265 2.657 6.352 4.654 9.174 c 6.61 9.336 17.376 14.908 28.797 14.908 c 19.443 0 35.26 -15.817 35.26 -35.26 c 0 -19.442 -15.817 -35.259 -35.26 -35.259 C 29.389 9.74 13.571 25.558 13.571 45 h -5.91 c 0 -22.701 18.468 -41.169 41.169 -41.169 C 71.532 3.831 90 22.299 90 45 C 90 67.701 71.532 86.169 48.831 86.169 z"/>
              <polygon points="64.67,61.69 45.88,46.41 45.88,19.03 51.78,19.03 51.78,43.59 68.4,57.1"/>
              <polygon points="21.23,40.41 10.62,51.02 0,40.41"/>
            </g>
          </svg>
        </button>
        <button class="blitz-newchat-btn" style="background:none;border:none;cursor:pointer;color:inherit;">
          <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" fill="none" viewBox="0 0 24 24"><path d="M12 4v16m8-8H4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </button>
      </div>
      <img src="blitz.png" alt="Blitz" style="height:28px;width:auto;display:block;margin-right:2px;">
    `;
    container.appendChild(header);

    const historyPanel = document.createElement('div');
    historyPanel.className = 'blitz-history-panel';
    historyPanel.style.display = 'none';
    historyPanel.style.position = 'absolute';
    // Position the panel below the history button, left-aligned
    historyPanel.style.left = '0';
    historyPanel.style.top = '100%';
    historyPanel.style.background = '#18181b';
    historyPanel.style.border = '1.5px solid #333';
    historyPanel.style.borderRadius = '0.75rem';
    historyPanel.style.padding = '0.5rem 0';
    historyPanel.style.maxHeight = '260px';
    historyPanel.style.overflowY = 'auto';
    historyPanel.style.minWidth = '220px';
    historyPanel.style.boxShadow = '0 8px 32px 0 rgba(0,0,0,0.22), 0 1.5px 6px 0 rgba(0,0,0,0.10)';
    historyPanel.style.marginTop = '0.5rem';
    historyPanel.style.zIndex = '100';
    historyPanel.style.opacity = '0';
    historyPanel.style.transition = 'opacity 0.18s ease';
    header.appendChild(historyPanel);

    async function fetchConversationsList(){
      if(!userId) return;
      try{
        const resp = await fetch(apiBase+`/api/users/${encodeURIComponent(userId)}/conversations`,{headers:{'X-API-Key':apiKey}});
        if(resp.ok){
          conversations = await resp.json();
          historyPanel.innerHTML = '';
          conversations.forEach(c => {
            const item = document.createElement('div');
            item.style.display = 'flex';
            item.style.alignItems = 'center';
            item.style.justifyContent = 'space-between';
            item.style.padding = '0.55rem 1.1rem';
            item.style.cursor = 'pointer';
            item.style.fontSize = '1rem';
            // Highlight if this is the current conversationId
            const isActive = c.id === conversationId;
            item.style.color = isActive ? '#fff' : '#cbd5e1';
            item.style.background = isActive ? '#23232a' : 'transparent';
            item.style.border = 'none';
            item.style.borderRadius = '0.5rem';
            item.style.margin = '0 0.25rem 2px 0.25rem';
            item.style.transition = 'background 0.15s, color 0.15s';
            const titleSpan = document.createElement('span');
            titleSpan.textContent = c.title || 'New Chat';
            item.appendChild(titleSpan);
            // Trash icon to the right
            const trashBtn = document.createElement('button');
            trashBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" version="1.1" width="18" height="18" viewBox="0 0 256 256" xml:space="preserve"><g style="stroke: none; stroke-width: 0; stroke-dasharray: none; stroke-linecap: butt; stroke-linejoin: miter; stroke-miterlimit: 10; fill: none; fill-rule: nonzero; opacity: 1;" transform="translate(1.4065934065934016 1.4065934065934016) scale(2.81 2.81)"><path d="M 64.71 90 H 25.291 c -4.693 0 -8.584 -3.67 -8.859 -8.355 l -3.928 -67.088 c -0.048 -0.825 0.246 -1.633 0.812 -2.234 c 0.567 -0.601 1.356 -0.941 2.183 -0.941 h 59.002 c 0.826 0 1.615 0.341 2.183 0.941 c 0.566 0.601 0.86 1.409 0.813 2.234 l -3.928 67.089 C 73.294 86.33 69.403 90 64.71 90 z M 18.679 17.381 l 3.743 63.913 C 22.51 82.812 23.771 84 25.291 84 H 64.71 c 1.52 0 2.779 -1.188 2.868 -2.705 l 3.742 -63.914 H 18.679 z" style="stroke: none; stroke-width: 1; stroke-dasharray: none; stroke-linecap: butt; stroke-linejoin: miter; stroke-miterlimit: 10; fill: rgb(191,46,46); fill-rule: nonzero; opacity: 1;" transform=" matrix(1 0 0 1 0 0) " stroke-linecap="round"/><path d="M 80.696 17.381 H 9.304 c -1.657 0 -3 -1.343 -3 -3 s 1.343 -3 3 -3 h 71.393 c 1.657 0 3 1.343 3 3 S 82.354 17.381 80.696 17.381 z" style="stroke: none; stroke-width: 1; stroke-dasharray: none; stroke-linecap: butt; stroke-linejoin: miter; stroke-miterlimit: 10; fill: rgb(191,46,46); fill-rule: nonzero; opacity: 1;" transform=" matrix(1 0 0 1 0 0) " stroke-linecap="round"/><path d="M 58.729 17.381 H 31.271 c -1.657 0 -3 -1.343 -3 -3 V 8.789 C 28.271 3.943 32.214 0 37.061 0 h 15.879 c 4.847 0 8.789 3.943 8.789 8.789 v 5.592 C 61.729 16.038 60.386 17.381 58.729 17.381 z M 34.271 11.381 h 21.457 V 8.789 C 55.729 7.251 54.478 6 52.939 6 H 37.061 c -1.538 0 -2.789 1.251 -2.789 2.789 V 11.381 z" style="stroke: none; stroke-width: 1; stroke-dasharray: none; stroke-linecap: butt; stroke-linejoin: miter; stroke-miterlimit: 10; fill: rgb(191,46,46); fill-rule: nonzero; opacity: 1;" transform=" matrix(1 0 0 1 0 0) " stroke-linecap="round"/><path d="M 58.33 74.991 c -0.06 0 -0.118 -0.002 -0.179 -0.005 c -1.653 -0.097 -2.916 -1.517 -2.819 -3.171 l 2.474 -42.244 c 0.097 -1.655 1.508 -2.933 3.171 -2.819 c 1.653 0.097 2.916 1.516 2.819 3.17 l -2.474 42.245 C 61.229 73.761 59.906 74.991 58.33 74.991 z" style="stroke: none; stroke-width: 1; stroke-dasharray: none; stroke-linecap: butt; stroke-linejoin: miter; stroke-miterlimit: 10; fill: rgb(191,46,46); fill-rule: nonzero; opacity: 1;" transform=" matrix(1 0 0 1 0 0) " stroke-linecap="round"/><path d="M 31.669 74.991 c -1.577 0 -2.898 -1.23 -2.992 -2.824 l -2.473 -42.245 c -0.097 -1.654 1.165 -3.073 2.819 -3.17 c 1.646 -0.111 3.073 1.165 3.17 2.819 l 2.473 42.244 c 0.097 1.654 -1.165 3.074 -2.819 3.171 C 31.788 74.989 31.729 74.991 31.669 74.991 z" style="stroke: none; stroke-width: 1; stroke-dasharray: none; stroke-linecap: butt; stroke-linejoin: miter; stroke-miterlimit: 10; fill: rgb(191,46,46); fill-rule: nonzero; opacity: 1;" transform=" matrix(1 0 0 1 0 0) " stroke-linecap="round"/><path d="M 45 74.991 c -1.657 0 -3 -1.343 -3 -3 V 29.747 c 0 -1.657 1.343 -3 3 -3 c 1.657 0 3 1.343 3 3 v 42.244 C 48 73.648 46.657 74.991 45 74.991 z" style="stroke: none; stroke-width: 1; stroke-dasharray: none; stroke-linecap: butt; stroke-linejoin: miter; stroke-miterlimit: 10; fill: rgb(191,46,46); fill-rule: nonzero; opacity: 1;" transform=" matrix(1 0 0 1 0 0) " stroke-linecap="round"/></g></svg>`;
            trashBtn.style.background = 'none';
            trashBtn.style.border = 'none';
            trashBtn.style.cursor = 'pointer';
            trashBtn.style.marginLeft = '0.5rem';
            trashBtn.style.opacity = '0.7';
            trashBtn.style.transition = 'opacity 0.15s';
            trashBtn.addEventListener('mouseenter',()=>{trashBtn.style.opacity='1';});
            trashBtn.addEventListener('mouseleave',()=>{trashBtn.style.opacity='0.7';});
            trashBtn.addEventListener('click', async (e)=>{
              e.stopPropagation();
              await fetch(apiBase+`/api/conversations/${c.id}`,{method:'DELETE',headers:{'X-API-Key':apiKey}});
              await fetchConversationsList();
            });
            item.appendChild(trashBtn);
            item.addEventListener('mouseenter',()=>{
              item.style.background = '#23232a';
              item.style.color = '#fff';
            });
            item.addEventListener('mouseleave',()=>{
              item.style.background = (c.id === conversationId) ? '#23232a' : 'transparent';
              item.style.color = (c.id === conversationId) ? '#fff' : '#cbd5e1';
            });
            item.addEventListener('click', async ()=>{
              conversationId = c.id;
              historyPanel.style.display = 'none';
              await loadMessages();
              await fetchConversationsList();
            });
            historyPanel.appendChild(item);
          });
        }
      }catch(_){/* ignore */}
    }

    async function loadMessages(){
      messages.innerHTML = '';
      if(!conversationId) return;
      const resp = await fetch(apiBase+`/api/conversations/${conversationId}/messages`,{headers:{'X-API-Key':apiKey}});
      if(resp.ok){
        const data = await resp.json();
        data.forEach(m=>addMessage(m.role,m.content));
      }
    }

    const historyBtn = header.querySelector('.blitz-history-btn');
    historyBtn.addEventListener('click', async ()=>{
      if(historyPanel.style.display==='none'){
        // Position the panel below the button
        const btnRect = historyBtn.getBoundingClientRect();
        const headerRect = header.getBoundingClientRect();
        historyPanel.style.left = (historyBtn.offsetLeft) + 'px';
        historyPanel.style.top = (historyBtn.offsetTop + historyBtn.offsetHeight) + 'px';
        await fetchConversationsList();
        historyPanel.style.display='block';
        setTimeout(()=>{historyPanel.style.opacity='1';}, 10);
      }else{
        historyPanel.style.opacity='0';
        setTimeout(()=>{historyPanel.style.display='none';}, 180);
      }
    });

    // Add event for new chat button
    const newChatBtn = header.querySelector('.blitz-newchat-btn');
    newChatBtn.addEventListener('click', async ()=>{
      const resp = await fetch(apiBase+`/api/conversations`,{method:'POST',headers:{'Content-Type':'application/json','X-API-Key':apiKey},body:JSON.stringify({user_id:userId})});
      if(resp.ok){
        const data = await resp.json();
        conversationId = data.id;
        messages.innerHTML = '';
        await fetchConversationsList();
      }
    });

    if(userId){
      fetchConversationsList();
    }

    // Messages
    const messages = document.createElement('div');
    messages.className = 'blitz-widget-messages';
    container.appendChild(messages);

    // Form
    const form = document.createElement('form');
    form.className = 'blitz-widget-form';
    const input = document.createElement('textarea');
    input.rows = 1;
    input.maxLength = 2000;
    input.placeholder = 'Send a message...';
    input.className = 'blitz-widget-input';
    input.style.overflowY = 'auto';
    input.style.resize = 'none';
    let baseHeight;
    let maxHeight;
    const adjustHeight = function() {
      this.style.height = baseHeight + 'px';
      if (this.scrollHeight > baseHeight) {
        this.style.height = Math.min(this.scrollHeight, maxHeight) + 'px';
      }
    };
    input.addEventListener('input', adjustHeight);
    const sendBtn = document.createElement('button');
    sendBtn.type = 'submit';
    sendBtn.className = 'blitz-widget-send';
    sendBtn.innerHTML = `<svg xmlns=\"http://www.w3.org/2000/svg\" fill=\"none\" viewBox=\"0 0 24 24\" stroke-width=\"2\" stroke=\"currentColor\" class=\"w-5 h-5\"><path stroke-linecap=\"round\" stroke-linejoin=\"round\" d=\"M12 19l9 2-9-18-9 18 9-2zm0 0v-8\" /></svg>`;
    form.appendChild(input);
    form.appendChild(sendBtn);
    container.appendChild(form);
    wrapper.appendChild(container);
    target.appendChild(wrapper);

    // Calculate dynamic heights after element is in the DOM
    baseHeight = input.scrollHeight || 36;
    maxHeight = baseHeight * 4;
    input.style.height = baseHeight + 'px';
    input.style.minHeight = baseHeight + 'px';
    input.style.maxHeight = maxHeight + 'px';
    // Ensure correct height on initial load
    adjustHeight.call(input);

    form.addEventListener('submit',async(e)=>{
      e.preventDefault();
      const text=input.value.trim();
      if(!text) return;
      addMessage('user',text);
      input.value='';
      const payload={ message:text, user_id: userId };
      const isNew = !conversationId;
      if(conversationId) payload.conversation_id = conversationId;
      if(isNew) payload.generate_title = true;
      const res = await fetch(apiBase+`/conversation`,{
        method:'POST',
        headers:{'Content-Type':'application/json','X-API-Key':apiKey},
        body:JSON.stringify(payload)
      });
      const data = await res.json();
      // Always update conversationId with backend response
      conversationId = data.conversation_id || conversationId;
      if(isNew){
        fetchConversationsList();
      }
      poll(data.response_id);
    });

    function addMessage(role,text,typing){
      const row = document.createElement('div');
      row.className = 'blitz-widget-msg-row ' + role;
      // Icon
      const icon = document.createElement('div');
      icon.className = 'blitz-widget-msg-icon ' + role;
      if(role === 'user') {
        icon.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z" /></svg>`;
      } else {
        icon.innerHTML = `<img src="blitzbot.png" alt="Bot" style="border-radius:50%;background:#fff;">`;
      }
      // Bubble
      const bubble = document.createElement('div');
      bubble.className = 'blitz-widget-msg-bubble ' + role;
      if(typing){
        bubble.classList.add('typing');
        bubble.innerHTML = '<span class="blitz-typing"><span class="dot"></span><span class="dot"></span><span class="dot"></span></span>';
      } else {
        bubble.textContent = text;
      }
      // Wrapper for bubble and feedback
      const content = document.createElement('div');
      content.className = 'blitz-widget-msg-content';
      content.appendChild(bubble);
      // Layout
      row.appendChild(icon);
      row.appendChild(content);
      messages.appendChild(row);
      messages.scrollTop=messages.scrollHeight;
      return bubble;
    }

    function addFeedback(bubble, responseId){
      const fb = document.createElement('div');
      fb.className = 'blitz-widget-feedback';
      const up = document.createElement('button');
      up.className = 'good';
      up.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-6"><path stroke-linecap="round" stroke-linejoin="round" d="M6.633 10.25c.806 0 1.533-.446 2.031-1.08a9.041 9.041 0 0 1 2.861-2.4c.723-.384 1.35-.956 1.653-1.715a4.498 4.498 0 0 0 .322-1.672V2.75a.75.75 0 0 1 .75-.75 2.25 2.25 0 0 1 2.25 2.25c0 1.152-.26 2.243-.723 3.218-.266.558.107 1.282.725 1.282m0 0h3.126c1.026 0 1.945.694 2.054 1.715.045.422.068.85.068 1.285a11.95 11.95 0 0 1-2.649 7.521c-.388.482-.987.729-1.605.729H13.48c-.483 0-.964-.078-1.423-.23l-3.114-1.04a4.501 4.501 0 0 0-1.423-.23H5.904m10.598-9.75H14.25M5.904 18.5c.083.205.173.405.27.602.197.4-.078.898-.523.898h-.908c-.889 0-1.713-.518-1.972-1.368a12 12 0 0 1-.521-3.507c0-1.553.295-3.036.831-4.398C3.387 9.953 4.167 9.5 5 9.5h1.053c.472 0 .745.556.5.96a8.958 8.958 0 0 0-1.302 4.665c0 1.194.232 2.333.654 3.375Z" /></svg>`;
      const down = document.createElement('button');
      down.className = 'bad';
      down.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-6"><path stroke-linecap="round" stroke-linejoin="round" d="M7.498 15.25H4.372c-1.026 0-1.945-.694-2.054-1.715a12.137 12.137 0 0 1-.068-1.285c0-2.848.992-5.464 2.649-7.521C5.287 4.247 5.886 4 6.504 4h4.016a4.5 4.5 0 0 1 1.423.23l3.114 1.04a4.5 4.5 0 0 0 1.423.23h1.294M7.498 15.25c.618 0 .991.724.725 1.282A7.471 7.471 0 0 0 7.5 19.75 2.25 2.25 0 0 0 9.75 22a.75.75 0 0 0 .75-.75v-.633c0-.573.11-1.14.322-1.672.304-.76.93-1.33 1.653-1.715a9.04 9.04 0 0 0 2.86-2.4c.498-.634 1.226-1.08 2.032-1.08h.384m-10.253 1.5H9.7m8.075-9.75c.01.05.027.1.05.148.593 1.2.925 2.55.925 3.977 0 1.487-.36 2.89-.999 4.125m.023-8.25c-.076-.365.183-.75.575-.75h.908c.889 0 1.713.518 1.972 1.368.339 1.11.521 2.287.521 3.507 0 1.553-.295 3.036-.831 4.398-.306.774-1.086 1.227-1.918 1.227h-1.053c-.472 0-.745-.556-.5-.96a8.95 8.95 0 0 0 .303-.54" /></svg>`;
      fb.appendChild(up);
      fb.appendChild(down);
      if (bubble.parentNode) {
        bubble.parentNode.appendChild(fb);
      }

      async function send(val){
        try{
          await fetch(apiBase+'/feedback',{method:'POST',headers:{'Content-Type':'application/json','X-API-Key':apiKey},body:JSON.stringify({call_id:responseId, helpful:val})});
          if(val){
            up.classList.add('active');
            down.classList.remove('active');
          }else{
            down.classList.add('active');
            up.classList.remove('active');
          }
        }catch(_){/* ignore */}
      }
      up.addEventListener('click',()=>send(true));
      down.addEventListener('click',()=>send(false));
    }

    async function poll(responseId){
      const bubble = addMessage('assistant','',true);
      while(true){
        const resp = await fetch(apiBase+`/conversation/${responseId}`,{headers:{'X-API-Key':apiKey}});
        if(!resp.ok){
          await new Promise(r=>setTimeout(r,1000));
          continue;
        }
        const data = await resp.json();
        if(data.status && data.status==='processing'){
          await new Promise(r=>setTimeout(r,1000));
          continue;
        }
        let text = 'Error';
        if(data.response){ text = data.response; }
        else if(data.error){ text = data.error; }
        bubble.classList.remove('typing');
        bubble.textContent = text;
        addFeedback(bubble, responseId);
        break;
      }
    }
  }

  // Expose a re-create function for toggling options
  global.BlitzWidget={
    createWidget,
    recreateWidget: function(options){
      createWidget(options);
    }
  };
})(this);
