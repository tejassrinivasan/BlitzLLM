(function(global) {
  function createWidget(options) {
    const target = document.getElementById(options.targetId);
    if (!target) {
      throw new Error('Target element not found');
    }

    const apiBase = options.apiBase || '';
    const apiKey = options.apiKey || '';
    const device = options.device || 'desktop';
    const border = options.border !== false;
    const theme = options.theme || 'light';
    const userId = options.userId || '';
    const storageKey = `blitz_${userId}_${apiBase}`;
    let stored = {};
    try {
      stored = JSON.parse(localStorage.getItem(storageKey) || '{}');
    } catch (_) {
      stored = {};
    }

    // UI elements
    const container = document.createElement('div');
    container.className = `blitz-widget-container blitz-size-${device}`;
    if (!border) container.classList.add('blitz-no-border');
    if (theme === 'dark') container.classList.add('blitz-theme-dark');

    const messages = document.createElement('div');
    messages.className = 'blitz-widget-messages';

    const form = document.createElement('form');
    form.className = 'blitz-widget-form';
    const input = document.createElement('input');
    input.type = 'text';
    input.placeholder = 'Ask a question...';
    input.className = 'blitz-widget-input';
    const sendBtn = document.createElement('button');
    sendBtn.type = 'submit';
    sendBtn.textContent = 'Send';
    sendBtn.className = 'blitz-widget-send';

    form.appendChild(input);
    form.appendChild(sendBtn);

    container.appendChild(messages);
    container.appendChild(form);
    target.appendChild(container);

    let conversationId = stored.conversationId || '';
    let messageId = stored.messageId || 0;

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      addMessage('user', text);
      input.value = '';
      messageId += 1;
      const payload = {
        message: text,
        conversation_id: conversationId || undefined,
        message_id: messageId
      };
      if (userId) {
        const numId = parseInt(userId, 10);
        if (!isNaN(numId)) {
          payload.user_id = numId;
        } else {
          payload.custom_data = { user_identifier: userId };
        }
      }

      const res = await fetch(apiBase + '/conversation', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': apiKey
        },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (!conversationId) conversationId = data.conversation_id;
      localStorage.setItem(storageKey, JSON.stringify({
        conversationId,
        messageId
      }));
      poll(data.response_id);
    });

    function addMessage(role, text) {
      const div = document.createElement('div');
      div.className = 'blitz-widget-msg ' + role;
      div.textContent = text;
      messages.appendChild(div);
      messages.scrollTop = messages.scrollHeight;
    }

    async function poll(responseId) {
      while (true) {
        const resp = await fetch(apiBase + '/conversation/' + responseId, {
          headers: { 'X-API-Key': apiKey }
        });
        const data = await resp.json();
        if (data.status !== 'processing') {
          addMessage('assistant', data.response || data.error_message || 'Error');
          break;
        }
        await new Promise(r => setTimeout(r, 1000));
      }
    }
  }

  global.BlitzWidget = { createWidget };
})(this);
