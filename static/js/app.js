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
});
