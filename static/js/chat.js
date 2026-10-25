(() => {
  const roomElement = document.getElementById('room-id');
  const meElement = document.getElementById('me-id');
  const log = document.getElementById('chat-log');
  const input = document.getElementById('chat-text');
  const sendButton = document.getElementById('chat-send');
  const status = document.getElementById('chat-status');
  const typingLine = document.getElementById('typing-line');

  if (!roomElement || !meElement || !log || !input || !sendButton || !status || !typingLine) {
    return;
  }

  let roomId;
  let meId;
  try {
    roomId = JSON.parse(roomElement.textContent);
    meId = JSON.parse(meElement.textContent);
  } catch (error) {
    status.textContent = 'Unable to load chat.';
    console.error('Invalid chat room data.', error);
    return;
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const socketUrl = `${protocol}//${window.location.host}/ws/chat/${encodeURIComponent(roomId)}/`;
  const initialRetryDelay = 1000;
  const maxRetryDelay = 15000;
  let retryDelay = initialRetryDelay;
  let reconnectTimer = null;
  let manuallyClosed = false;
  let typingTimer = null;
  let socket;
  const renderedMessageIds = new Set(
    Array.from(log.querySelectorAll('[data-id]'), (element) => element.dataset.id),
  );

  function setStatus(text) {
    status.textContent = text;
  }

  function scrollToLatest() {
    log.scrollTop = log.scrollHeight;
  }

  function send(payload) {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(payload));
      return true;
    }
    return false;
  }

  function formatTime(timestamp) {
    if (!timestamp) {
      return '';
    }
    const date = new Date(timestamp);
    if (Number.isNaN(date.getTime())) {
      return '';
    }
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  function renderMessage(message) {
    if (!message || message.id == null) {
      return;
    }

    const id = String(message.id);
    if (renderedMessageIds.has(id)) {
      return;
    }

    renderedMessageIds.add(id);
    const emptyState = log.querySelector('.chat-room__empty');
    if (emptyState) {
      emptyState.remove();
    }

    const bubble = document.createElement('div');
    bubble.classList.add(
      'chat-message',
      Number(message.sender_id) === Number(meId) ? 'mine' : 'theirs',
    );
    bubble.dataset.id = id;

    const sender = document.createElement('span');
    sender.className = 'chat-message__sender';
    sender.textContent = typeof message.sender === 'string' ? message.sender : '';
    bubble.appendChild(sender);

    const content = document.createElement('p');
    content.textContent = typeof message.content === 'string' ? message.content : '';
    content.style.whiteSpace = 'pre-wrap';
    bubble.appendChild(content);

    const timeText = formatTime(message.timestamp);
    if (timeText) {
      const time = document.createElement('time');
      time.dateTime = message.timestamp;
      time.textContent = timeText;
      bubble.appendChild(time);
    }

    log.appendChild(bubble);
    scrollToLatest();
  }

  function scheduleReconnect() {
    if (manuallyClosed || reconnectTimer !== null) {
      return;
    }

    const delay = retryDelay;
    retryDelay = Math.min(retryDelay * 2, maxRetryDelay);
    setStatus(`Disconnected. Reconnecting in ${Math.ceil(delay / 1000)}s...`);
    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = null;
      connect();
    }, delay);
  }

  function connect() {
    setStatus('Connecting...');
    socket = new WebSocket(socketUrl);

    socket.addEventListener('open', () => {
      retryDelay = initialRetryDelay;
      setStatus('Online');
      send({ type: 'read' });
      scrollToLatest();
    });

    socket.addEventListener('message', (event) => {
      let data;
      try {
        data = JSON.parse(event.data);
      } catch (error) {
        console.error('Received invalid chat data.', error);
        return;
      }

      if (data.type === 'message') {
        renderMessage(data.message);
        if (data.message && Number(data.message.sender_id) !== Number(meId)) {
          send({ type: 'read' });
        }
      } else if (data.type === 'typing') {
        typingLine.textContent = data.is_typing ? 'Typing...' : '';
        typingLine.hidden = !data.is_typing;
      } else if (data.type === 'read') {
        log.querySelectorAll('.chat-message.mine').forEach((bubble) => {
          bubble.dataset.read = 'true';
        });
      } else if (data.type === 'error') {
        setStatus(data.message || 'Unable to send message.');
      }
    });

    socket.addEventListener('close', (event) => {
      typingLine.hidden = true;
      if (event.code === 4403) {
        manuallyClosed = true;
        setStatus('Access denied.');
        return;
      }
      scheduleReconnect();
    });

    socket.addEventListener('error', () => {
      setStatus('Connection error.');
    });
  }

  function sendMessage() {
    const message = input.value.trim();
    if (!message || message.length > 2000) {
      return;
    }
    if (send({ type: 'message', message })) {
      input.value = '';
      send({ type: 'typing', is_typing: false });
    }
  }

  sendButton.addEventListener('click', sendMessage);
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  });

  input.addEventListener('input', () => {
    send({ type: 'typing', is_typing: true });
    window.clearTimeout(typingTimer);
    typingTimer = window.setTimeout(() => {
      send({ type: 'typing', is_typing: false });
    }, 1000);
  });

  window.addEventListener('beforeunload', () => {
    manuallyClosed = true;
    window.clearTimeout(reconnectTimer);
    if (socket) {
      socket.close();
    }
  });

  scrollToLatest();
  connect();
})();
