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

  function updateReactionState(bubble, reaction) {
    const currentReaction = reaction.user_reaction || null;
    bubble.dataset.userReaction = currentReaction || '';
    bubble.classList.toggle('is-liked', currentReaction === 'like');
    bubble.setAttribute('aria-pressed', String(currentReaction === 'like'));

    const likes = bubble.querySelector('.chat-message__likes');
    const likeCount = Math.max(0, Number(reaction.like_count) || 0);
    likes.querySelector('[data-count="like"]').textContent = String(likeCount);
    likes.setAttribute('aria-label', `${likeCount} ${likeCount === 1 ? 'like' : 'likes'}`);
    likes.hidden = likeCount === 0;
  }

  function addLikeIndicator(bubble, message) {
    const likes = document.createElement('span');
    likes.className = 'chat-message__likes';
    likes.setAttribute('aria-label', '0 likes');
    likes.hidden = true;

    const icon = document.createElement('i');
    icon.className = 'fa-solid fa-heart';
    icon.setAttribute('aria-hidden', 'true');
    likes.appendChild(icon);

    const count = document.createElement('span');
    count.dataset.count = 'like';
    likes.appendChild(count);
    bubble.appendChild(likes);

    updateReactionState(bubble, {
      user_reaction: message.user_reaction,
      like_count: message.like_count,
    });
  }

  function animateLike(bubble) {
    const heart = document.createElement('span');
    heart.className = 'chat-message__heart-burst';
    heart.setAttribute('aria-hidden', 'true');

    const icon = document.createElement('i');
    icon.className = 'fa-solid fa-heart';
    heart.appendChild(icon);
    bubble.appendChild(heart);
    heart.addEventListener('animationend', () => heart.remove(), { once: true });
    window.setTimeout(() => heart.remove(), 900);
  }

  let isLoadingHistory = false;
  let hasMoreHistory = true;

  function createMessageElement(message) {
    if (!message || message.id == null) {
      return null;
    }

    const id = String(message.id);
    if (renderedMessageIds.has(id)) {
      return null;
    }

    renderedMessageIds.add(id);

    const bubble = document.createElement('div');
    bubble.classList.add(
      'chat-message',
      Number(message.sender_id) === Number(meId) ? 'mine' : 'theirs',
    );
    bubble.dataset.id = id;
    bubble.setAttribute('role', 'button');
    bubble.tabIndex = 0;
    bubble.title = 'Double-click to like or unlike';
    bubble.setAttribute(
      'aria-label',
      `Message from ${typeof message.sender === 'string' ? message.sender : 'unknown sender'}. Double-click or press Enter or Space to like.`,
    );

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

    addLikeIndicator(bubble, message);
    return bubble;
  }

  function renderMessage(message) {
    const bubble = createMessageElement(message);
    if (!bubble) {
      return;
    }

    const emptyState = log.querySelector('.chat-room__empty');
    if (emptyState) {
      emptyState.remove();
    }

    log.appendChild(bubble);
    scrollToLatest();
  }

  function getOldestMessageId() {
    const firstMsg = log.querySelector('.chat-message[data-id]');
    return firstMsg ? Number(firstMsg.dataset.id) : null;
  }

  function loadOlderMessages() {
    if (isLoadingHistory || !hasMoreHistory) {
      return;
    }
    const oldestId = getOldestMessageId();
    if (!oldestId) {
      return;
    }

    isLoadingHistory = true;
    const historyUrl = `/chat/room/${encodeURIComponent(roomId)}/history/?before=${encodeURIComponent(oldestId)}`;

    fetch(historyUrl, {
      headers: {
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
      },
    })
      .then((res) => {
        if (!res.ok) throw new Error('Failed to load history');
        return res.json();
      })
      .then((data) => {
        hasMoreHistory = Boolean(data.has_more);
        if (Array.isArray(data.messages) && data.messages.length > 0) {
          const scrollBottomOffset = log.scrollHeight - log.scrollTop;
          const firstCurrentMsg = log.querySelector('.chat-message');

          data.messages.forEach((msg) => {
            const bubble = createMessageElement(msg);
            if (bubble) {
              if (firstCurrentMsg) {
                log.insertBefore(bubble, firstCurrentMsg);
              } else {
                log.appendChild(bubble);
              }
            }
          });

          // Keep reading position stable when prepending older messages
          log.scrollTop = log.scrollHeight - scrollBottomOffset;
        }
      })
      .catch((err) => {
        console.error('Error fetching chat history:', err);
      })
      .finally(() => {
        isLoadingHistory = false;
      });
  }

  log.addEventListener('scroll', () => {
    if (log.scrollTop <= 60 && !isLoadingHistory && hasMoreHistory) {
      loadOlderMessages();
    }
  });

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
      } else if (data.type === 'reaction') {
        const reaction = data.reaction;
        const bubble = reaction && Array.from(
          log.querySelectorAll('.chat-message[data-id]'),
        ).find((message) => message.dataset.id === String(reaction.message_id));
        if (bubble) {
          updateReactionState(bubble, {
            ...reaction,
            user_reaction: Number(reaction.user_id) === Number(meId)
              ? reaction.user_reaction
              : bubble.dataset.userReaction,
          });
        }
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

  function toggleMessageLike(bubble) {
    if (bubble.dataset.reactionPending === 'true') {
      return;
    }

    const csrfInput = document.querySelector('[name="csrfmiddlewaretoken"]');
    if (!bubble || !csrfInput) {
      setStatus('Unable to update reaction.');
      return;
    }

    const previousReaction = bubble.dataset.userReaction;
    bubble.dataset.reactionPending = 'true';
    bubble.setAttribute('aria-busy', 'true');

    fetch(`/chat/room/${encodeURIComponent(roomId)}/message/${encodeURIComponent(bubble.dataset.id)}/react/`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-CSRFToken': csrfInput.value,
        'X-Requested-With': 'XMLHttpRequest',
      },
      body: new URLSearchParams({ reaction: 'like' }),
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Reaction update failed (${response.status}).`);
        }
        return response.json();
      })
      .then((reaction) => {
        updateReactionState(bubble, reaction);
        if (reaction.user_reaction === 'like' && previousReaction !== 'like') {
          animateLike(bubble);
        }
      })
      .catch((error) => {
        console.error('Unable to update message reaction.', error);
        setStatus('Unable to update reaction.');
      })
      .finally(() => {
        delete bubble.dataset.reactionPending;
        bubble.removeAttribute('aria-busy');
      });
  }

  log.addEventListener('dblclick', (event) => {
    const bubble = event.target.closest('.chat-message[data-id]');
    if (!bubble || !log.contains(bubble)) {
      return;
    }

    event.preventDefault();
    toggleMessageLike(bubble);
  });

  log.addEventListener('keydown', (event) => {
    const bubble = event.target.closest('.chat-message[data-id]');
    if (
      (event.key !== 'Enter' && event.key !== ' ')
      || !bubble
      || event.target !== bubble
      || event.repeat
    ) {
      return;
    }

    event.preventDefault();
    toggleMessageLike(bubble);
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
