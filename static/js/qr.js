(() => {
  'use strict';
  const base = document.getElementById('base');
  const warn = document.getElementById('base-warn');
  let timer;

  function clean() { return base.value.trim().replace(/\/+$/, ''); }

  function update() {
    const b = clean();
    const ok = /^https?:\/\/[^\s"'<>]+$/i.test(b);
    base.setAttribute('aria-invalid', ok ? 'false' : 'true');
    if (!ok) return;
    warn.hidden = !/^https?:\/\/(localhost|127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|0\.0\.0\.0)/i.test(b);
    document.querySelectorAll('.qrcard').forEach(card => {
      const slug = card.dataset.slug, q = '?base=' + encodeURIComponent(b);
      card.querySelector('.qr-img').src = `/admin/qr/${slug}.svg${q}`;
      card.querySelectorAll('[data-fmt]').forEach(a => { a.href = `/admin/qr/${slug}.${a.dataset.fmt}${q}&dl=1`; });
      card.querySelector('[data-url]').textContent = `${b}/q/${slug}`;
    });
  }

  base.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(update, 250); });
  document.getElementById('btn-print').addEventListener('click', () => window.print());
  update();
})();
