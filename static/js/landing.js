(() => {
  'use strict';
  const app = document.getElementById('app');
  const token = app.dataset.token;
  const $ = s => document.getElementById(s);
  let readSent = false;

  function post(url, body) {
    return fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({token, ...body}), keepalive: true, credentials: 'omit'});
  }

  function markRead() {
    if (readSent) return;
    readSent = true;
    post('/api/e', {type: 'read'}).catch(() => {});
  }

  // "Lectura": la persona llegó al final de la explicación o interactuó con el siguiente paso
  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver(es => { if (es.some(e => e.isIntersecting)) { markRead(); io.disconnect(); } });
    io.observe($('end-sentinel'));
  }

  const form = $('step-form'), ask = $('step-ask'), thanks = $('step-thanks'), send = $('btn-send');

  $('btn-yes').addEventListener('click', () => {
    markRead(); ask.hidden = true; form.hidden = false;
    form.scrollIntoView({behavior: 'smooth', block: 'start'});
  });
  $('btn-no').addEventListener('click', () => {
    markRead(); ask.hidden = true; thanks.hidden = false;
    thanks.scrollIntoView({behavior: 'smooth', block: 'center'});
  });

  function complete() { return ['q1', 'q2', 'q3', 'q4'].every(q => form.querySelector(`input[name=${q}]:checked`)); }
  form.addEventListener('change', () => { send.disabled = !complete(); });

  form.addEventListener('submit', async e => {
    e.preventDefault();
    if (!complete()) return;
    send.disabled = true;
    const body = {};
    ['q1', 'q2', 'q3', 'q4'].forEach(q => { body[q] = form.querySelector(`input[name=${q}]:checked`).value; });
    try {
      const r = await post('/api/r', body);
      if (!r.ok) throw new Error();
      form.hidden = true; thanks.hidden = false;
      $('thanks-text').textContent = 'Tus respuestas se guardaron de forma anónima. La próxima vez, revisa antes de escanear.';
      thanks.scrollIntoView({behavior: 'smooth', block: 'center'});
    } catch (_) {
      $('form-err').hidden = false; send.disabled = false;
    }
  });
})();
