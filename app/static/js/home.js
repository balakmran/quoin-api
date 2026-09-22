// Landing-page behaviour for app/templates/index.html.
//
// Lives here rather than in an inline <script> so the default CSP
// can keep script-src free of 'unsafe-inline'. Loaded with `defer`,
// so the DOM is parsed before this runs.

// Canvas 2D background — matches docs home.js exactly
(() => {
  const canvas = document.getElementById('bg-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  let w, h, dpr;
  const PARTICLE_COUNT = 80;
  const BLOCK_COUNT = 12;
  const particles = [];
  const blocks = [];

  const initElements = () => {
    particles.length = 0;
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      particles.push({
        x: Math.random() * w,
        y: Math.random() * h,
        r: 1 + Math.random() * 1.5,
        speed: 0.15 + Math.random() * 0.3,
        alpha: 0.3 + Math.random() * 0.5,
      });
    }
    blocks.length = 0;
    for (let i = 0; i < BLOCK_COUNT; i++) {
      const side = i % 2 === 0 ? -1 : 1;
      const y = Math.random() * h;
      blocks.push({
        xRatio: 0.5 + side * (0.15 + Math.random() * 0.25),
        y,
        baseY: y,
        size: 8 + Math.random() * 18,
        rotation: Math.random() * Math.PI * 2,
        rotSpeed: (Math.random() - 0.5) * 0.008,
        floatOffset: Math.random() * Math.PI * 2,
        floatSpeed: 0.3 + Math.random() * 0.4,
        floatAmp: 8 + Math.random() * 14,
        alpha: 0.12 + Math.random() * 0.18,
      });
    }
  };

  const resize = () => {
    dpr = Math.min(window.devicePixelRatio, 2);
    w = window.innerWidth;
    h = window.innerHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  };
  resize();
  initElements();
  window.addEventListener('resize', resize);

  let mouseX = 0, mouseY = 0, camX = 0, camY = 0;
  document.addEventListener('mousemove', (e) => {
    mouseX = (e.clientX - w / 2) * 0.02;
    mouseY = (e.clientY - h / 2) * 0.02;
  });

  const draw = () => {
    requestAnimationFrame(draw);
    const t = Date.now() * 0.001;
    camX += (mouseX - camX) * 0.05;
    camY += (-mouseY - camY) * 0.05;
    ctx.clearRect(0, 0, w, h);

    for (const b of blocks) {
      b.y = b.baseY + Math.sin(t * b.floatSpeed + b.floatOffset) * b.floatAmp;
      b.rotation += b.rotSpeed;
      const bx = b.xRatio * w + camX * 1.5;
      const by = b.y + camY * 1.5;
      ctx.save();
      ctx.translate(bx, by);
      ctx.rotate(b.rotation);
      ctx.strokeStyle = `rgba(56, 189, 248, ${b.alpha})`;
      ctx.lineWidth = 1;
      const half = b.size / 2;
      ctx.strokeRect(-half, -half, b.size, b.size);
      ctx.fillStyle = `rgba(14, 165, 233, ${b.alpha * 0.3})`;
      ctx.fillRect(-half, -half, b.size, b.size);
      ctx.restore();
    }

    for (const p of particles) {
      p.y -= p.speed;
      if (p.y < -5) { p.y = h + 5; p.x = Math.random() * w; }
      ctx.beginPath();
      ctx.arc(p.x + camX * 0.5, p.y + camY * 0.5, p.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(14, 165, 233, ${p.alpha})`;
      ctx.fill();
    }
  };
  draw();
})();

// Copy CLI command. Bound here, not with an onclick attribute: the CSP
// blocks inline event handlers. The clipboard API is absent outside a
// secure context and rejects when permission is denied, so the tick waits
// for the write to resolve - otherwise the button claims a copy that never
// happened. Icons toggle the `hidden` *attribute*: these are SVG elements,
// where `hidden` is not a property, so assigning it sets an expando that
// CSS never sees.
const copyBtn = document.getElementById('copy-btn');
copyBtn?.addEventListener('click', () => {
  const cmd = document.querySelector('.app-cli__cmd');
  const copyIcon = document.getElementById('copy-icon');
  const checkIcon = document.getElementById('check-icon');
  const label = copyBtn.getAttribute('aria-label');
  const showCheck = (on) => {
    copyIcon.toggleAttribute('hidden', on);
    checkIcon.toggleAttribute('hidden', !on);
  };
  const write = navigator.clipboard
    ? navigator.clipboard.writeText(cmd.textContent.trim())
    : Promise.reject(new Error('clipboard unavailable'));
  write
    .then(() => {
      showCheck(true);
      setTimeout(() => showCheck(false), 1800);
    })
    .catch(() => {
      copyBtn.classList.add('app-cli__copy--error');
      copyBtn.setAttribute('aria-label', 'Copy failed - select the command to copy it');
      setTimeout(() => {
        copyBtn.classList.remove('app-cli__copy--error');
        copyBtn.setAttribute('aria-label', label);
      }, 1800);
    });
});

// Status LEDs
let healthOK = true, readyOK = true;

const setDot = (prefix, ok, latency) => {
  const dot = document.getElementById(`${prefix}-dot`);
  const label = document.getElementById(`${prefix}-status`);
  const name = prefix === 'health' ? 'Health' : 'Ready';
  if (ok) {
    dot.style.cssText = 'background:#34d399;border-color:#6ee7b7;box-shadow:0 0 6px rgba(52,211,153,0.8)';
    label.style.color = '#34d399';
    label.textContent = latency != null ? `${name} · ${latency}ms` : name;
  } else {
    dot.style.cssText = 'background:#f43f5e;border-color:#fb7185;box-shadow:0 0 6px rgba(244,63,94,0.8)';
    label.style.color = '#f43f5e';
    label.textContent = `${name} · Error`;
  }
};

const syncPill = () => {
  const pill = document.getElementById('status-pill');
  const text = document.getElementById('status-text');
  if (healthOK && readyOK) {
    pill.className = 'app-hero__status app-hero__status--ok';
    text.textContent = 'ALL SYSTEMS OPERATIONAL';
  } else {
    pill.className = 'app-hero__status app-hero__status--error';
    text.textContent = 'SYSTEM DEGRADED';
  }
};

const pollStatus = async (endpoint, prefix) => {
  try {
    const t0 = performance.now();
    const res = await fetch(endpoint);
    const latency = Math.round(performance.now() - t0);
    const ok = res.ok;
    setDot(prefix, ok, ok ? latency : null);
    if (prefix === 'health') healthOK = ok;
    if (prefix === 'ready') readyOK = ok;
  } catch {
    setDot(prefix, false, null);
    if (prefix === 'health') healthOK = false;
    if (prefix === 'ready') readyOK = false;
  }
  syncPill();
};

setTimeout(() => {
  pollStatus('/health', 'health');
  pollStatus('/ready', 'ready');
}, 800);

setInterval(() => {
  pollStatus('/health', 'health');
  pollStatus('/ready', 'ready');
}, 60000);
