(function () {
  const viewer = document.getElementById('story-viewer');

  function getCsrf() {
    const el = document.getElementById('story-csrf');
    if (el) {
      try { return JSON.parse(el.textContent); } catch (e) { /* noop */ }
    }
    const input = document.querySelector('[name="csrfmiddlewaretoken"]');
    return input ? input.value : '';
  }

  function markViewed(storyId) {
    if (!storyId) return;
    fetch(`/stories/${storyId}/viewed/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCsrf(), 'X-Requested-With': 'XMLHttpRequest' },
    }).catch(() => {});
  }

  if (viewer) {
    const slides = Array.from(viewer.querySelectorAll('.story-slide'));
    const bars = Array.from(viewer.querySelectorAll('.story-viewer__bar'));
    const prevBtn = document.getElementById('story-prev');
    const nextBtn = document.getElementById('story-next');
    let current = 0;
    let timer = null;
    const SLIDE_MS = 5000;

    function show(index) {
      if (index < 0) index = 0;
      if (index >= slides.length) {
        window.location.href = '/'; // end of stories
        return;
      }
      current = index;
      slides.forEach((s, i) => s.classList.toggle('is-active', i === index));
      bars.forEach((bar, i) => {
        bar.classList.toggle('is-done', i < index);
        bar.classList.toggle('is-current', i === index);
      });

      const slide = slides[index];
      markViewed(slide.dataset.storyId);

      const video = slide.querySelector('video');
      if (video) {
        video.currentTime = 0;
        video.play().catch(() => {});
        video.onended = () => show(current + 1);
        clearTimeout(timer);
      } else {
        clearTimeout(timer);
        timer = setTimeout(() => show(current + 1), SLIDE_MS);
      }
    }

    prevBtn.addEventListener('click', () => show(current - 1));
    nextBtn.addEventListener('click', () => show(current + 1));
    document.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowLeft') show(current - 1);
      if (e.key === 'ArrowRight') show(current + 1);
      if (e.key === 'Escape') window.location.href = '/';
    });

    show(0);
  }

  // Story bar loader (used on the feed page)
  const bar = document.getElementById('story-bar');
  if (bar) {
    fetch('/stories/bar/', { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then((r) => (r.ok ? r.json() : { groups: [] }))
      .then((data) => {
        const groups = data.groups || [];
        if (!groups.length) {
          bar.closest('.story-bar-wrap').hidden = true;
          return;
        }
        groups.forEach((g) => {
          const link = document.createElement('a');
          link.className = 'story-ring' + (g.has_unseen ? ' has-unseen' : '');
          link.href = `/stories/view/${g.author_id}/`;
          const avatar = document.createElement('span');
          avatar.className = 'story-ring__avatar';
          if (g.avatar) {
            const img = document.createElement('img');
            img.src = g.avatar;
            img.alt = g.username;
            avatar.appendChild(img);
          } else {
            avatar.textContent = g.initial;
          }
          const name = document.createElement('span');
          name.className = 'story-ring__name';
          name.textContent = g.is_self ? 'Your story' : g.username;
          link.appendChild(avatar);
          link.appendChild(name);
          bar.appendChild(link);
        });
        const add = document.createElement('a');
        add.className = 'story-ring story-ring--add';
        add.href = '/stories/create/';
        add.innerHTML = '<span class="story-ring__avatar"><i class="fa-solid fa-plus"></i></span><span class="story-ring__name">Add story</span>';
        bar.appendChild(add);
      })
      .catch(() => { bar.closest('.story-bar-wrap').hidden = true; });
  }
})();
