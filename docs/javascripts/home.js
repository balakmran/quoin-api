(function () {
  const initCopy = () => {
    const btn = document.querySelector(".quoin-cli__copy");
    if (!btn) return;
    const cmd = document.querySelector(".quoin-cli__cmd");
    if (!cmd) return;
    const iconCopy = btn.querySelector(".quoin-cli__copy-icon");
    const iconCheck = btn.querySelector(".quoin-cli__copy-check");
    btn.addEventListener("click", () => {
      navigator.clipboard.writeText(cmd.textContent.trim()).then(() => {
        iconCopy.hidden = true;
        iconCheck.hidden = false;
        setTimeout(() => {
          iconCopy.hidden = false;
          iconCheck.hidden = true;
        }, 1800);
      });
    });
  };

  const initBackground = () => {
    const canvas = document.getElementById("quoin-bg-canvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
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
    window.addEventListener("resize", resize);

    let mouseX = 0;
    let mouseY = 0;
    let camX = 0;
    let camY = 0;
    const onMouseMove = (e) => {
      mouseX = (e.clientX - w / 2) * 0.02;
      mouseY = (e.clientY - h / 2) * 0.02;
    };
    document.addEventListener("mousemove", onMouseMove);

    let rafId;

    const draw = () => {
      rafId = requestAnimationFrame(draw);
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
        if (p.y < -5) {
          p.y = h + 5;
          p.x = Math.random() * w;
        }

        const px = p.x + camX * 0.5;
        const py = p.y + camY * 0.5;

        ctx.beginPath();
        ctx.arc(px, py, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(14, 165, 233, ${p.alpha})`;
        ctx.fill();
      }
    };
    draw();

    return () => {
      cancelAnimationFrame(rafId);
      window.removeEventListener("resize", resize);
      document.removeEventListener("mousemove", onMouseMove);
    };
  };

  const initHeaderNav = () => {
    const existing = document.querySelector(".quoin-header__nav");
    if (existing) existing.remove();

    const title = document.querySelector(".md-header__title");
    if (!title) return;

    const ghSvgNS = "http://www.w3.org/2000/svg";

    const ghLink = document.createElement("a");
    ghLink.href = "https://github.com/balakmran/quoin-api";
    ghLink.target = "_blank";
    ghLink.rel = "noopener";
    ghLink.className = "quoin-header__nav-icon";
    ghLink.setAttribute("aria-label", "GitHub");
    const ghSvg = document.createElementNS(ghSvgNS, "svg");
    ghSvg.setAttribute("width", "17");
    ghSvg.setAttribute("height", "17");
    ghSvg.setAttribute("viewBox", "0 0 24 24");
    ghSvg.setAttribute("fill", "currentColor");
    const ghPath = document.createElementNS(ghSvgNS, "path");
    ghPath.setAttribute("d", "M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12");
    ghSvg.appendChild(ghPath);
    ghLink.appendChild(ghSvg);
    const ghText = document.createTextNode("GitHub");
    ghLink.appendChild(ghText);

    const docsLink = document.createElement("a");
    docsLink.href = "docs/";
    docsLink.className = "quoin-header__nav-link";
    docsLink.textContent = "Docs";

    const nav = document.createElement("div");
    nav.className = "quoin-header__nav";
    nav.appendChild(docsLink);
    nav.appendChild(ghLink);

    title.insertAdjacentElement("afterend", nav);
  };

  let bgCleanup = null;

  const start = () => {
    if (!document.querySelector(".quoin-home")) {
      document.body.classList.remove("quoin-home-body");
      const nav = document.querySelector(".quoin-header__nav");
      if (nav) nav.remove();
      if (bgCleanup) {
        bgCleanup();
        bgCleanup = null;
      }
      return;
    }
    document.body.classList.add("quoin-home-body");
    initCopy();
    initHeaderNav();
    if (bgCleanup) {
      bgCleanup();
      bgCleanup = null;
    }
    bgCleanup = initBackground();
  };

  if (typeof document$ !== "undefined") {
    document$.subscribe(start);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
