// Social Nest – shared frontend behavior
document.addEventListener('DOMContentLoaded', function () {
  // Password visibility toggles (FontAwesome)
  document.querySelectorAll('.js-eye, [data-toggle-password]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var targetId = btn.dataset.target || btn.getAttribute('data-toggle-password');
      var target = document.getElementById(targetId) || document.querySelector(targetId);
      if (!target) return;
      var isPassword = target.getAttribute('type') === 'password';
      target.setAttribute('type', isPassword ? 'text' : 'password');

      if (btn.classList.contains('fa-eye') || btn.classList.contains('fa-eye-slash')) {
        btn.classList.toggle('fa-eye');
        btn.classList.toggle('fa-eye-slash');
      } else {
        var icon = btn.querySelector('i');
        if (icon) {
          icon.classList.toggle('fa-eye');
          icon.classList.toggle('fa-eye-slash');
        }
      }
    });
  });

  // Image preview for avatar / cover uploads
  document.querySelectorAll('[data-preview-target]').forEach(function (input) {
    input.addEventListener('change', function () {
      var file = input.files && input.files[0];
      if (!file) return;
      var target = document.querySelector(input.getAttribute('data-preview-target'));
      if (!target) return;
      var reader = new FileReader();
      reader.onload = function (e) {
        if (target.tagName === 'IMG') {
          target.src = e.target.result;
          target.style.display = '';
        } else {
          target.style.backgroundImage = 'url(' + e.target.result + ')';
        }
      };
      reader.readAsDataURL(file);
    });
  });

  // Trigger hidden file inputs from overlay buttons
  document.querySelectorAll('[data-trigger-input]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var input = document.querySelector(btn.getAttribute('data-trigger-input'));
      if (input) input.click();
    });
  });

  // Auto-dismiss alert messages / flash banners / toasts
  document.querySelectorAll('.flash, .toast').forEach(function (toast) {
    setTimeout(function () {
      toast.style.transition = 'opacity .4s ease, transform .4s ease';
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(-10px)';
      setTimeout(function () {
        if (toast.parentNode) {
          toast.remove();
        }
      }, 400);
    }, 4500);
  });

  // Notification badge polling
  var badge = document.getElementById('navNotifBadge') || document.querySelector('.header-nav__link[href*="notifications"] .badge');
  function refreshBadge() {
    if (!badge) return;
    fetch('/notifications/unread-count/', {
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data) return;
        if (data.unread_count > 0) {
          badge.textContent = data.unread_count;
          badge.style.display = '';
          badge.hidden = false;
        } else {
          badge.style.display = 'none';
          badge.hidden = true;
        }
      })
      .catch(function () {});
  }
  if (badge) {
    setInterval(refreshBadge, 30000);
  }

  // Seamless AJAX Like Toggling
  document.querySelectorAll('form[action*="/like/"]').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var actionUrl = form.getAttribute('action');
      var csrfEl = form.querySelector('[name=csrfmiddlewaretoken]');
      var csrfToken = csrfEl ? csrfEl.value : '';
      var btn = form.querySelector('button.post-action') || form.querySelector('button');
      if (!btn) {
        form.submit();
        return;
      }

      fetch(actionUrl, {
        method: 'POST',
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': csrfToken,
          'Accept': 'application/json'
        }
      })
      .then(function (res) {
        if (!res.ok) throw new Error('Network error');
        return res.json();
      })
      .then(function (data) {
        if (typeof data.liked !== 'undefined') {
          var countSpan = btn.querySelector('span');
          var heartIcon = btn.querySelector('i');
          if (data.liked) {
            btn.classList.add('is-liked');
            if (heartIcon) {
              heartIcon.className = 'fa-solid fa-heart';
            }
          } else {
            btn.classList.remove('is-liked');
            if (heartIcon) {
              heartIcon.className = 'fa-regular fa-heart';
            }
          }
          if (countSpan) {
            countSpan.textContent = data.likes_count;
          }
        }
      })
      .catch(function () {
        // Fallback to normal form submit if fetch fails
        form.submit();
      });
    });
  });

  // --- Global Fullscreen Media Lightbox Viewer ---
  var lightbox = document.getElementById('mediaLightbox');
  var lightboxImg = document.getElementById('lightboxImg');
  var lightboxVideo = document.getElementById('lightboxVideo');
  var lightboxClose = document.getElementById('lightboxClose');
  var lightboxExternal = document.getElementById('lightboxOpenExternal');

  function openLightbox(url, isVideo) {
    if (!lightbox || !url) return;
    if (isVideo) {
      if (lightboxImg) {
        lightboxImg.classList.add('hidden');
        lightboxImg.src = '';
      }
      if (lightboxVideo) {
        lightboxVideo.src = url;
        lightboxVideo.classList.remove('hidden');
        lightboxVideo.play().catch(function () {});
      }
    } else {
      if (lightboxVideo) {
        lightboxVideo.pause();
        lightboxVideo.classList.add('hidden');
        lightboxVideo.src = '';
      }
      if (lightboxImg) {
        lightboxImg.src = url;
        lightboxImg.classList.remove('hidden');
      }
    }
    if (lightboxExternal) lightboxExternal.href = url;
    lightbox.classList.remove('hidden');
    lightbox.classList.add('flex');
    document.body.style.overflow = 'hidden';
  }

  function closeLightbox() {
    if (!lightbox) return;
    lightbox.classList.add('hidden');
    lightbox.classList.remove('flex');
    if (lightboxVideo) {
      lightboxVideo.pause();
      lightboxVideo.src = '';
      lightboxVideo.classList.add('hidden');
    }
    if (lightboxImg) {
      lightboxImg.src = '';
      lightboxImg.classList.add('hidden');
    }
    document.body.style.overflow = '';
  }

  if (lightboxClose) lightboxClose.addEventListener('click', closeLightbox);
  if (lightbox) {
    lightbox.addEventListener('click', function (e) {
      if (e.target === lightbox || e.target.id === 'mediaLightbox') {
        closeLightbox();
      }
    });
  }
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && lightbox && !lightbox.classList.contains('hidden')) {
      closeLightbox();
    }
  });

  document.addEventListener('click', function (e) {
    var btn = e.target.closest('.js-lightbox-btn');
    if (btn) {
      e.preventDefault();
      e.stopPropagation();
      var mediaUrl = btn.dataset.media;
      var isVideo = btn.dataset.type === 'video';
      openLightbox(mediaUrl, isVideo);
      return;
    }

    var targetMedia = e.target.closest('.lightbox-media');
    if (targetMedia) {
      var anchor = targetMedia.closest('a');
      if (anchor) {
        e.preventDefault();
      }
      var isVideo = targetMedia.tagName === 'VIDEO';
      var src = isVideo ? (targetMedia.currentSrc || targetMedia.src) : (targetMedia.currentSrc || targetMedia.src);
      if (src) {
        openLightbox(src, isVideo);
      }
    }
  });
});
