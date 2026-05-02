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
    if (typeof THREE === "undefined") return;
    const canvas = document.getElementById("quoin-bg-canvas");
    if (!canvas) return;

    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x06111f, 0.003);

    const camera = new THREE.PerspectiveCamera(
      75,
      window.innerWidth / window.innerHeight,
      0.1,
      1000,
    );
    camera.position.z = 220;

    const renderer = new THREE.WebGLRenderer({
      canvas,
      alpha: true,
      antialias: true,
    });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    scene.add(new THREE.AmbientLight(0x0c4a6e, 3));
    const spotlight = new THREE.PointLight(0x38bdf8, 14, 900);
    spotlight.position.set(0, 60, 180);
    scene.add(spotlight);

    // Floating blocks scattered across the scene
    const blockMat = new THREE.MeshStandardMaterial({
      color: 0x0ea5e9,
      emissive: 0x0ea5e9,
      emissiveIntensity: 0.4,
      metalness: 0.85,
      roughness: 0.15,
    });
    const wireMat = new THREE.LineBasicMaterial({
      color: 0x38bdf8,
      transparent: true,
      opacity: 0.7,
    });

    const blocks = [];
    const sizes = [
      [16, 7, 7],
      [7, 16, 7],
      [7, 7, 16],
      [12, 12, 5],
      [5, 12, 12],
      [10, 5, 14],
      [14, 6, 6],
      [6, 14, 6],
      [8, 8, 8],
      [12, 4, 9],
      [4, 12, 9],
      [9, 9, 4],
      [10, 5, 10],
      [5, 10, 5],
      [13, 5, 8],
      [8, 13, 5],
    ];

    sizes.forEach((dims, i) => {
      const geo = new THREE.BoxGeometry(...dims);
      const mesh = new THREE.Mesh(geo, blockMat);
      const wire = new THREE.LineSegments(
        new THREE.EdgesGeometry(
          new THREE.BoxGeometry(dims[0] + 0.5, dims[1] + 0.5, dims[2] + 0.5),
        ),
        wireMat,
      );

      const container = new THREE.Group();
      container.add(mesh, wire);

      // Spread across a wide area, slightly off-center to avoid hero text overlap
      const side = i % 2 === 0 ? -1 : 1;
      container.position.set(
        side * (140 + Math.random() * 180),
        (Math.random() - 0.5) * 220,
        (Math.random() - 0.5) * 180 - 40,
      );

      container.userData = {
        floatOffset: Math.random() * Math.PI * 2,
        floatSpeed: 0.4 + Math.random() * 0.4,
        floatAmp: 6 + Math.random() * 10,
        rotSpeed: new THREE.Vector3(
          (Math.random() - 0.5) * 0.006,
          (Math.random() - 0.5) * 0.006,
          (Math.random() - 0.5) * 0.004,
        ),
        baseY: container.position.y,
      };

      scene.add(container);
      blocks.push(container);
    });

    // Floating particles
    const particleCount = 160;
    const pPos = new Float32Array(particleCount * 3);
    for (let i = 0; i < particleCount; i++) {
      pPos[i * 3] = (Math.random() - 0.5) * 420;
      pPos[i * 3 + 1] = (Math.random() - 0.5) * 420 - 60;
      pPos[i * 3 + 2] = (Math.random() - 0.5) * 420;
    }
    const pGeo = new THREE.BufferGeometry();
    pGeo.setAttribute("position", new THREE.BufferAttribute(pPos, 3));
    scene.add(
      new THREE.Points(
        pGeo,
        new THREE.PointsMaterial({
          color: 0x0ea5e9,
          size: 2.2,
          transparent: true,
          opacity: 0.7,
          blending: THREE.AdditiveBlending,
        }),
      ),
    );

    let targetX = 0;
    let targetY = 0;
    document.addEventListener("mousemove", (e) => {
      targetX = (e.clientX - window.innerWidth / 2) * 0.04;
      targetY = (e.clientY - window.innerHeight / 2) * 0.04;
    });

    window.addEventListener("resize", () => {
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
    });

    let rafId;
    const cleanup = () => {
      cancelAnimationFrame(rafId);
      renderer.dispose();
    };

    const animate = () => {
      rafId = requestAnimationFrame(animate);
      const time = Date.now() * 0.001;

      blocks.forEach((b) => {
        const d = b.userData;
        b.position.y =
          d.baseY + Math.sin(time * d.floatSpeed + d.floatOffset) * d.floatAmp;
        b.rotation.x += d.rotSpeed.x;
        b.rotation.y += d.rotSpeed.y;
        b.rotation.z += d.rotSpeed.z;
      });

      const pAttr = pGeo.attributes.position;
      for (let i = 0; i < particleCount; i++) {
        pAttr.array[i * 3 + 1] += 0.12;
        if (pAttr.array[i * 3 + 1] > 220) pAttr.array[i * 3 + 1] = -220;
      }
      pAttr.needsUpdate = true;

      camera.position.x += (targetX - camera.position.x) * 0.05;
      camera.position.y += (-targetY - camera.position.y) * 0.05;
      camera.lookAt(scene.position);

      spotlight.position.x += (targetX * 10 - spotlight.position.x) * 0.08;
      spotlight.position.y += (-targetY * 10 + 60 - spotlight.position.y) * 0.08;

      renderer.render(scene, camera);
    };
    animate();

    return cleanup;
  };

  const initHeaderNav = () => {
    const existing = document.querySelector(".quoin-header__nav");
    if (existing) existing.remove();

    const title = document.querySelector(".md-header__title");
    if (!title) return;

    const ghSvgNS = "http://www.w3.org/2000/svg";

    // GitHub icon link
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

    // Docs link
    const docsLink = document.createElement("a");
    docsLink.href = "docs/";
    docsLink.className = "quoin-header__nav-link";
    docsLink.textContent = "Docs";

    const nav = document.createElement("div");
    nav.className = "quoin-header__nav";
    nav.appendChild(ghLink);
    nav.appendChild(docsLink);

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
