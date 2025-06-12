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
    header.style.justifyContent = 'flex-end';
    header.innerHTML = `<img src="blitz.png" alt="Blitz" style="height:28px;width:auto;display:block;margin-right:2px;">`;
    container.appendChild(header);

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
    input.addEventListener('input', function() {
      this.style.height = '36px';
      const maxHeight = 144;
      if (this.scrollHeight > 36) {
        this.style.height = Math.min(this.scrollHeight, maxHeight) + 'px';
      }
    });
    const sendBtn = document.createElement('button');
    sendBtn.type = 'submit';
    sendBtn.className = 'blitz-widget-send';
    sendBtn.innerHTML = `<svg xmlns=\"http://www.w3.org/2000/svg\" fill=\"none\" viewBox=\"0 0 24 24\" stroke-width=\"2\" stroke=\"currentColor\" class=\"w-5 h-5\"><path stroke-linecap=\"round\" stroke-linejoin=\"round\" d=\"M12 19l9 2-9-18-9 18 9-2zm0 0v-8\" /></svg>`;
    form.appendChild(input);
    form.appendChild(sendBtn);
    container.appendChild(form);
    wrapper.appendChild(container);
    target.appendChild(wrapper);

    form.addEventListener('submit',async(e)=>{
      e.preventDefault();
      const text=input.value.trim();
      if(!text) return;
      addMessage('user',text);
      input.value='';
      const payload={ message:text };
      // For followup messages, send conversation_id
      if(conversationId) payload.conversation_id = conversationId;
      const res = await fetch(apiBase+`/conversation`,{
        method:'POST',
        headers:{'Content-Type':'application/json','X-API-Key':apiKey},
        body:JSON.stringify(payload)
      });
      const data = await res.json();
      // Always update conversationId with backend response
      conversationId = data.conversation_id || conversationId;
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
