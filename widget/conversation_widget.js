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
    let stored = {};
    try{stored = JSON.parse(localStorage.getItem(storageKey) || '{}');}catch(_){stored={};}

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
    const input = document.createElement('input');
    input.type = 'text';
    input.placeholder = 'Send a message...';
    input.className = 'blitz-widget-input';
    const sendBtn = document.createElement('button');
    sendBtn.type = 'submit';
    sendBtn.className = 'blitz-widget-send';
    sendBtn.innerHTML = `<svg xmlns=\"http://www.w3.org/2000/svg\" fill=\"none\" viewBox=\"0 0 24 24\" stroke-width=\"2\" stroke=\"currentColor\" class=\"w-5 h-5\"><path stroke-linecap=\"round\" stroke-linejoin=\"round\" d=\"M12 19l9 2-9-18-9 18 9-2zm0 0v-8\" /></svg>`;
    form.appendChild(input);
    form.appendChild(sendBtn);
    container.appendChild(form);
    wrapper.appendChild(container);
    target.appendChild(wrapper);

    let conversationId = stored.conversationId || '';
    let messageId = stored.messageId || 0;

    form.addEventListener('submit',async(e)=>{
      e.preventDefault();
      const text=input.value.trim();
      if(!text) return;
      addMessage('user',text);
      input.value='';
      messageId+=1;
      const payload={content:text};
      const url = apiBase+`/api/conversations/${conversationId||'new'}/messages/stream`;
      const res = await fetch(url,{method:'POST',headers:{'Content-Type':'application/json','X-API-Key':apiKey},body:JSON.stringify(payload)});
      const data = await res.json();
      poll(data.task_id);
    });

    function addMessage(role,text){
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
      bubble.className = 'blitz-widget-msg-bubble';
      bubble.textContent = text;
      // Layout
      row.appendChild(icon);
      row.appendChild(bubble);
      messages.appendChild(row);
      messages.scrollTop=messages.scrollHeight;
    }

    async function poll(taskId){
      while(true){
        const resp=await fetch(apiBase+`/api/tasks/${taskId}`,{headers:{'X-API-Key':apiKey}});
        const data=await resp.json();
        if(data.status==='complete'){
          if(data.user_message) conversationId=data.user_message.conversation_id||conversationId;
          addMessage('assistant',data.assistant_message?.content||'');
          break;
        }else if(data.status==='error'){
          addMessage('assistant',data.error||'Error');
          break;
        }else if(data.status==='not_found'){
          addMessage('assistant','Task not found');
          break;
        }
        await new Promise(r=>setTimeout(r,1000));
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
