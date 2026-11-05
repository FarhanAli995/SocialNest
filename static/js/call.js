(() => {
  const roomElement = document.getElementById('room-id');
  const meElement = document.getElementById('me-id');
  const otherElement = document.getElementById('other-id');
  const otherNameElement = document.getElementById('other-name');
  const videoButton = document.getElementById('chat-video');
  const overlay = document.getElementById('call-overlay');
  const statusText = document.getElementById('call-status-text');
  const titleText = document.getElementById('call-title');
  const localVideo = document.getElementById('local-video');
  const remoteVideo = document.getElementById('remote-video');
  const muteBtn = document.getElementById('call-mute');
  const cameraBtn = document.getElementById('call-camera');
  const acceptBtn = document.getElementById('call-accept');
  const rejectBtn = document.getElementById('call-reject');
  const endBtn = document.getElementById('call-end');
  const diagnosticText = document.getElementById('call-diagnostic');

  if (!roomElement || !meElement || !otherElement || !videoButton || !overlay) {
    return;
  }

  let roomId;
  let meId;
  let otherId;
  try {
    roomId = JSON.parse(roomElement.textContent);
    meId = JSON.parse(meElement.textContent);
    otherId = JSON.parse(otherElement.textContent);
  } catch (error) {
    console.error('Invalid call data.', error);
    return;
  }

  const otherName = otherNameElement ? JSON.parse(otherNameElement.textContent) : 'User';
  const iceElement = document.getElementById('ice-servers');
  let ICE_SERVERS = [{ urls: 'stun:stun.l.google.com:19302' }];
  if (iceElement) {
    try {
      const parsed = JSON.parse(iceElement.textContent);
      if (Array.isArray(parsed) && parsed.length > 0) {
        ICE_SERVERS = parsed;
      }
    } catch (error) {
      console.warn('Invalid ICE server config; using default STUN.', error);
    }
  }

  let callId = null;
  let isCaller = false;
  let pc = null;
  let localStream = null;
  let signalingSocket = null;
  let pendingOffer = null;
  let pendingCandidates = [];
  let reconnectAttempts = 0;
  let callActive = false;
  let startingCall = false;

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';

  function getCsrf() {
    const input = document.querySelector('[name="csrfmiddlewaretoken"]');
    return input ? input.value : '';
  }

  function setStatus(text) {
    if (statusText) statusText.textContent = text;
  }

  function setDiagnostic(text) {
    if (!diagnosticText) return;
    diagnosticText.textContent = text || '';
    diagnosticText.hidden = !text;
  }

  function describeError(error) {
    const name = (error && error.name) || 'Error';
    const message = (error && error.message) || String(error);
    const secure = window.isSecureContext ? 'secure' : 'NOT secure';
    const origin = window.location.origin;
    const hasDevices = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
    return `${name}: ${message} | context=${secure} | origin=${origin} | mediaDevices=${hasDevices}`;
  }

  function showOverlay() {
    overlay.hidden = false;
    overlay.classList.remove('hidden');
    overlay.setAttribute('aria-hidden', 'false');
    overlay.style.display = 'flex';
  }

  function hideOverlay() {
    overlay.hidden = true;
    overlay.classList.add('hidden');
    overlay.setAttribute('aria-hidden', 'true');
    overlay.style.display = 'none';
  }

  function setButtons({ accept = false, reject = false, end = false, controls = true }) {
    if (acceptBtn) {
      acceptBtn.hidden = !accept;
      acceptBtn.style.display = accept ? 'grid' : 'none';
    }
    if (rejectBtn) {
      rejectBtn.hidden = true;
      rejectBtn.style.display = 'none';
    }
    if (endBtn) {
      const shouldShowEnd = end || reject;
      endBtn.hidden = !shouldShowEnd;
      endBtn.style.display = shouldShowEnd ? 'grid' : 'none';
      endBtn.title = (reject && !end) ? 'Decline Call' : 'End Call';
    }
    if (muteBtn) {
      muteBtn.hidden = !controls;
      muteBtn.style.display = controls ? 'grid' : 'none';
    }
    if (cameraBtn) {
      cameraBtn.hidden = !controls;
      cameraBtn.style.display = controls ? 'grid' : 'none';
    }
  }

  function cleanupPeer() {
    if (pc) {
      pc.onicecandidate = null;
      pc.ontrack = null;
      pc.onconnectionstatechange = null;
      pc.close();
      pc = null;
    }
    if (localStream) {
      localStream.getTracks().forEach((track) => track.stop());
      localStream = null;
    }
    if (localVideo) localVideo.srcObject = null;
    if (remoteVideo) remoteVideo.srcObject = null;
    const pipWrap = document.getElementById('local-video-wrap');
    if (pipWrap) pipWrap.style.display = '';
  }

  function cleanupAll() {
    cleanupPeer();
    if (signalingSocket) {
      signalingSocket.onclose = null;
      signalingSocket.close();
      signalingSocket = null;
    }
    callActive = false;
    callId = null;
    isCaller = false;
    pendingOffer = null;
    pendingCandidates = [];
    reconnectAttempts = 0;
    startingCall = false;
  }

  function endCallUi(message) {
    setStatus(message || 'Call ended');
    setTimeout(() => {
      cleanupAll();
      hideOverlay();
    }, 1200);
  }

  function sendSignal(type, payload) {
    if (signalingSocket && signalingSocket.readyState === WebSocket.OPEN) {
      signalingSocket.send(JSON.stringify({ type, payload }));
    }
  }

  function mediaErrorMessage(error) {
    const name = (error && error.name) || '';
    if (!window.isSecureContext) {
      return 'Camera/microphone require HTTPS or localhost.';
    }
    if (name === 'NotAllowedError' || name === 'SecurityError') {
      return 'Camera/microphone permission was denied.';
    }
    if (name === 'NotFoundError' || name === 'OverconstrainedError') {
      return 'No camera or microphone was found.';
    }
    if (name === 'NotReadableError' || name === 'AbortError') {
      return 'Camera/microphone is in use by another app.';
    }
    if (name === 'TypeError') {
      return 'Media devices are unavailable in this browser.';
    }
    return (error && error.message) || 'Camera or microphone unavailable.';
  }

  async function getLocalMedia() {
    if (!window.isSecureContext) {
      throw new Error('Camera/microphone require HTTPS or localhost.');
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error('Media devices are not supported in this browser.');
    }
    
    // Explicitly check what devices exist to give a better error
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const hasVideo = devices.some(d => d.kind === 'videoinput');
      const hasAudio = devices.some(d => d.kind === 'audioinput');
      if (!hasVideo && !hasAudio) {
        throw new Error('No camera or microphone found on this device.');
      }
    } catch (e) {
      console.warn('Could not enumerate devices:', e);
    }

    try {
      localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: true });
    } catch (error) {
      console.warn('Full AV failed, trying audio-only', error);
      try {
        localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      } catch (fallbackError) {
        console.warn('Audio-only failed, trying video-only', fallbackError);
        try {
          localStream = await navigator.mediaDevices.getUserMedia({ audio: false, video: true });
        } catch (videoError) {
          throw new Error(mediaErrorMessage(videoError));
        }
      }
    }
    
    if (localVideo) localVideo.srcObject = localStream;
    return localStream;
  }

  function createPeerConnection() {
    pc = new RTCPeerConnection({ iceServers: ICE_SERVERS });

    pc.onicecandidate = (event) => {
      if (event.candidate) {
        sendSignal('ice_candidate', event.candidate);
      }
    };

    pc.ontrack = (event) => {
      if (remoteVideo && event.streams && event.streams[0]) {
        remoteVideo.srcObject = event.streams[0];
        remoteVideo.muted = false;
        const pipWrap = document.getElementById('local-video-wrap');
        if (pipWrap) pipWrap.style.display = 'block';
      }
    };

    // NOTE: onnegotiationneeded is intentionally omitted to prevent SDP glare.
    // Tracks are added before the first offer is created, so renegotiation is not needed.

    pc.onconnectionstatechange = () => {
      const state = pc ? pc.connectionState : 'closed';
      if (state === 'connected') {
        setStatus('Connected');
        setDiagnostic('');
      } else if (state === 'disconnected') {
        setStatus('Reconnecting…');
      } else if (state === 'failed') {
        setStatus('Connection failed');
        endCallUi('Connection failed');
      }
    };

    if (localStream) {
      localStream.getTracks().forEach((track) => pc.addTrack(track, localStream));
    }
    return pc;
  }

  function openSignaling() {
    return new Promise((resolve, reject) => {
      const url = `${protocol}//${window.location.host}/ws/calls/${encodeURIComponent(callId)}/`;
      signalingSocket = new WebSocket(url);

      signalingSocket.onopen = () => {
        reconnectAttempts = 0;
        resolve();
      };

      signalingSocket.onmessage = handleSignalMessage;

      signalingSocket.onclose = (event) => {
        if (event.code === 4403) {
          endCallUi('Call access denied');
          return;
        }
        if (callActive) {
          if (reconnectAttempts < 3) {
            reconnectAttempts += 1;
            setStatus('Signaling reconnecting…');
            setTimeout(() => {
              openSignaling().then(() => {
                if (pendingOffer) {
                  sendSignal('webrtc_offer', pendingOffer);
                  pendingOffer = null;
                }
              }).catch(() => endCallUi('Call disconnected'));
            }, 1200);
          } else {
            endCallUi('Call disconnected');
          }
        }
      };

      signalingSocket.onerror = () => reject(new Error('Signaling connection error.'));
    });
  }

  async function handleSignalMessage(event) {
    let data;
    try {
      data = JSON.parse(event.data);
    } catch (error) {
      return;
    }
    if (!data || !data.type) return;

    if (data.type === 'webrtc_offer') {
      if (!pc || !localStream) {
        // Not ready yet (media not acquired). Remember it for after Accept.
        pendingOffer = data.payload;
        return;
      }
      await applyOfferAndAnswer(data.payload);
    } else if (data.type === 'receiver_ready') {
      // Receiver acquired media and is ready; (re)send our offer.
      if (isCaller && pc) {
        await sendOffer();
      }
    } else if (data.type === 'webrtc_answer') {
      if (pc) {
        await pc.setRemoteDescription(new RTCSessionDescription(data.payload));
        flushCandidates();
      }
    } else if (data.type === 'ice_candidate') {
      if (data.payload) {
        if (pc && pc.remoteDescription) {
          try {
            await pc.addIceCandidate(new RTCIceCandidate(data.payload));
          } catch (error) {
            console.error('ICE add failed', error);
          }
        } else {
          pendingCandidates.push(data.payload);
        }
      }
    } else if (data.type === 'call_ended') {
      endCallUi('Call ended');
    }
  }

  function flushCandidates() {
    if (!pc) return;
    pendingCandidates.forEach((candidate) => {
      pc.addIceCandidate(new RTCIceCandidate(candidate)).catch(() => {});
    });
    pendingCandidates = [];
  }

  async function startCallerSession() {
    showOverlay();
    setButtons({ controls: false });
    setStatus('Calling…');
    if (titleText) titleText.textContent = `Calling ${otherName}`;

    try {
      await getLocalMedia();
      setDiagnostic('');
    } catch (error) {
      console.error('Media error', error);
      setDiagnostic(describeError(error));
      endCallUi(mediaErrorMessage(error));
      await postCallAction('end');
      return;
    }

    // Immediately display user camera feed full screen while calling
    if (remoteVideo) {
      remoteVideo.srcObject = localStream;
      remoteVideo.muted = true;
    }
    const pipWrap = document.getElementById('local-video-wrap');
    if (pipWrap) pipWrap.style.display = 'none';

    try {
      await openSignaling();
    } catch (error) {
      endCallUi('Could not connect signaling');
      await postCallAction('end');
      return;
    }

    callActive = true;
    setButtons({ controls: true, end: true });
    createPeerConnection();
    await sendOffer();
  }

  async function sendOffer() {
    if (!pc) return;
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    sendSignal('webrtc_offer', offer);
  }

  async function initiateCall() {
    if (startingCall || callActive) return;
    startingCall = true;
    if (videoButton) videoButton.disabled = true;

    try {
      const response = await fetch(`/chat/room/${encodeURIComponent(roomId)}/call/start/`, {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'X-CSRFToken': getCsrf(),
          'X-Requested-With': 'XMLHttpRequest',
        },
      });
      if (!response.ok) {
        throw new Error(`Call start failed (${response.status})`);
      }
      const data = await response.json();
      callId = data.call.id;
      isCaller = true;
      await startCallerSession();
    } catch (error) {
      console.error('Unable to start call', error);
      cleanupAll();
      hideOverlay();
      alert('Unable to start the call. Please try again.');
    } finally {
      startingCall = false;
      if (videoButton) videoButton.disabled = false;
    }
  }

  async function acceptCall() {
    if (!callId) return;
    setButtons({ controls: false });
    setStatus('Connecting…');
    try {
      const response = await fetch(`/chat/calls/${encodeURIComponent(callId)}/accept/`, {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'X-CSRFToken': getCsrf(),
          'X-Requested-With': 'XMLHttpRequest',
        },
      });
      if (!response.ok) throw new Error('Accept failed');
    } catch (error) {
      endCallUi('Unable to accept call');
      return;
    }

    // Connect signaling first so the caller's offer is not missed.
    try {
      await openSignaling();
    } catch (error) {
      endCallUi('Could not connect signaling');
      await postCallAction('reject');
      return;
    }

    try {
      await getLocalMedia();
      setDiagnostic('');
    } catch (error) {
      console.error('Media error', error);
      setDiagnostic(describeError(error));
      await postCallAction('reject');
      endCallUi(mediaErrorMessage(error));
      return;
    }

    callActive = true;
    setButtons({ controls: true, end: true });
    createPeerConnection();
    // Ask the caller to (re)send its offer now that our tracks exist.
    sendSignal('receiver_ready', {});
    if (pendingOffer) {
      await applyOfferAndAnswer(pendingOffer);
      pendingOffer = null;
    }
  }

  async function applyOfferAndAnswer(offer) {
    if (!pc) return;
    try {
      await pc.setRemoteDescription(new RTCSessionDescription(offer));
      flushCandidates();
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);
      sendSignal('webrtc_answer', answer);
    } catch (error) {
      console.error('Failed to apply offer:', error);
      setDiagnostic('SDP Error: ' + error.message);
    }
  }

  async function postCallAction(action) {
    if (!callId) return null;
    try {
      const response = await fetch(`/chat/calls/${encodeURIComponent(callId)}/${action}/`, {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'X-CSRFToken': getCsrf(),
          'X-Requested-With': 'XMLHttpRequest',
        },
      });
      return response.ok ? response.json() : null;
    } catch (error) {
      return null;
    }
  }

  async function rejectCall() {
    sendSignal('call_ended', {});
    await postCallAction('reject');
    endCallUi('Call rejected');
  }

  async function hangUp() {
    sendSignal('call_ended', {});
    await postCallAction('end');
    endCallUi('Call ended');
  }

  // --- Incoming calls arrive on the existing chat socket via chat.js.
  window.addEventListener('socialnest:call', (event) => {
    const detail = event.detail || {};
    if (!detail || !detail.call) return;
    const call = detail.call;

    if (detail.event === 'incoming_call') {
      if (Number(call.receiver_id) !== Number(meId)) return;
      if (callActive) {
        return;
      }
      callId = call.id;
      isCaller = false;
      callActive = true;
      showOverlay();
      if (titleText) titleText.textContent = `${call.caller} is calling…`;
      setStatus('Incoming video call');
      setButtons({ accept: true, reject: true, controls: false });
    } else if (detail.event === 'call_rejected') {
      if (callId && call.id === callId) endCallUi('Call rejected');
    } else if (detail.event === 'call_ended') {
      if (callId && call.id === callId) endCallUi('Call ended');
    } else if (detail.event === 'call_accepted') {
      if (isCaller && callId && call.id === callId) setStatus('Connected');
    } else if (detail.event === 'call_missed') {
      if (callId && call.id === callId) endCallUi('Missed call');
    }
  });

  if (videoButton) videoButton.addEventListener('click', initiateCall);
  if (acceptBtn) acceptBtn.addEventListener('click', acceptCall);
  if (rejectBtn) rejectBtn.addEventListener('click', rejectCall);
  if (endBtn) {
    endBtn.addEventListener('click', async () => {
      if (!isCaller && !callActive) {
        await rejectCall();
      } else {
        await hangUp();
      }
    });
  }

  function toggleMute() {
    if (!localStream) return;
    const audioTrack = localStream.getAudioTracks()[0];
    if (!audioTrack) return;
    audioTrack.enabled = !audioTrack.enabled;
    const muted = !audioTrack.enabled;
    if (muteBtn) {
      muteBtn.setAttribute('aria-pressed', String(muted));
      muteBtn.title = muted ? 'Unmute microphone' : 'Mute microphone';
      muteBtn.innerHTML = muted
        ? '<i class="fa-solid fa-microphone-slash" aria-hidden="true"></i>'
        : '<i class="fa-solid fa-microphone" aria-hidden="true"></i>';
    }
  }

  function toggleCamera() {
    if (!localStream) return;
    const videoTrack = localStream.getVideoTracks()[0];
    if (!videoTrack) return;
    videoTrack.enabled = !videoTrack.enabled;
    const off = !videoTrack.enabled;
    if (cameraBtn) {
      cameraBtn.setAttribute('aria-pressed', String(off));
      cameraBtn.title = off ? 'Turn camera on' : 'Turn camera off';
      cameraBtn.innerHTML = off
        ? '<i class="fa-solid fa-video-slash" aria-hidden="true"></i>'
        : '<i class="fa-solid fa-video" aria-hidden="true"></i>';
    }
  }

  if (muteBtn) muteBtn.addEventListener('click', toggleMute);
  if (cameraBtn) cameraBtn.addEventListener('click', toggleCamera);

  window.addEventListener('beforeunload', () => {
    if (callActive) {
      sendSignal('call_ended', {});
    }
    cleanupAll();
  });
})();
