/* ==========================================================================
   SKILL UP — HERO WEBGL SCENE
   --------------------------------------------------------------------------
   A "misconception lattice": a cloud of nodes (attempts) with faint edges
   drawn between near neighbours (shared concept tags), orbiting a displaced
   core (the inferred rule). It reacts to the pointer and to scroll.

   Design constraints this file is written against:

     · It must be optional. If three.js failed to load, or WebGL is
       unavailable, or the GL context is lost mid-session, the page falls back
       to a CSS aurora and nothing throws. `html.no-webgl` drives that.
     · It must not burn battery off-screen. The render loop stops when the
       hero scrolls away, when the tab is hidden, and when the user prefers
       reduced motion (in which case exactly one frame is drawn).
     · It must not fight the theme. Node colours and overall opacity are
       uniforms that get repointed when the theme flips.

   Public surface (consumed by index.js):
       SkillUpScene.init()        -> boolean, true if a GL scene is running
       SkillUpScene.setTheme(t)   -> 'dark' | 'light'
       SkillUpScene.setPointer(x, y)  normalised -1..1
       SkillUpScene.setScroll(p)      0..1 progress through the hero
       SkillUpScene.pause() / .resume() / .destroy()
   ========================================================================== */

(function (global) {
  'use strict';

  /* ----------------------------------------------------------------------
     Tunables
     ---------------------------------------------------------------------- */

  var CONFIG = {
    nodeCount: 1400,          // scaled down on small screens, see resolveCount
    nodeCountMobile: 480,
    radius: 9.5,              // cloud radius
    coreRadius: 2.35,
    linkDistance: 2.15,       // max distance for an edge between two nodes
    maxLinks: 1600,           // hard cap so the geometry never explodes
    cameraZ: 17,
    /* A slight rightward bias only. A large offset was tried and simply moved
       the problem: the hero has copy on the left and the HUD panel on the
       right, so there is no empty half to hide in. Readability comes from the
       canvas mask and opacity cap in sections.css instead. */
    offsetX: 1.4,
    offsetXNarrow: 0,
    maxPixelRatio: 1.9,
    parallax: 1.35,           // how far the camera drifts with the pointer
    lerp: 0.055               // pointer smoothing
  };

  var PALETTE = {
    dark: {
      nodes: [0x7c6bff, 0x22d3ee, 0xff7a2f, 0x34d399],
      weights: [0.5, 0.28, 0.12, 0.1],
      core: [0x7c6bff, 0x22d3ee],
      link: 0x5b6ad6,
      opacity: 1.0,
      linkOpacity: 0.16
    },
    light: {
      nodes: [0x5433cc, 0x0e7490, 0xc44310, 0x047857],
      weights: [0.5, 0.28, 0.12, 0.1],
      core: [0x6647f0, 0x0891b2],
      link: 0x8b93c9,
      opacity: 0.72,
      linkOpacity: 0.1
    }
  };

  /* ----------------------------------------------------------------------
     Shaders
     ---------------------------------------------------------------------- */

  var NODE_VERT = [
    'attribute float aScale;',
    'attribute float aSeed;',
    'attribute vec3 aColor;',
    'uniform float uTime;',
    'uniform float uSize;',
    'uniform float uPixelRatio;',
    'uniform float uBurst;',
    'varying vec3 vColor;',
    'varying float vFade;',
    'varying float vTwinkle;',
    '',
    'void main() {',
    '  vColor = aColor;',
    '  vec3 pos = position;',
    // Each node breathes on its own phase so the cloud never pulses in unison.
    '  float t = uTime * 0.34 + aSeed * 6.28318;',
    '  pos.x += sin(t) * 0.18;',
    '  pos.y += cos(t * 1.17) * 0.18;',
    '  pos.z += sin(t * 0.81) * 0.18;',
    // uBurst pushes the whole cloud outward briefly when a diagnosis "lands".
    '  pos *= 1.0 + uBurst * 0.14;',
    '',
    '  vec4 mv = modelViewMatrix * vec4(pos, 1.0);',
    '  float dist = -mv.z;',
    '  vFade = smoothstep(34.0, 5.0, dist);',
    '  vTwinkle = 0.65 + 0.35 * sin(uTime * 1.6 + aSeed * 12.0);',
    '  gl_PointSize = uSize * aScale * uPixelRatio * (11.0 / max(dist, 0.001));',
    '  gl_Position = projectionMatrix * mv;',
    '}'
  ].join('\n');

  var NODE_FRAG = [
    'uniform float uOpacity;',
    'varying vec3 vColor;',
    'varying float vFade;',
    'varying float vTwinkle;',
    '',
    'void main() {',
    '  vec2 c = gl_PointCoord - vec2(0.5);',
    '  float d = length(c);',
    '  if (d > 0.5) discard;',
    // Soft round sprite with a hotter centre — cheaper than a texture and
    // sharper than a plain gaussian.
    '  float a = smoothstep(0.5, 0.02, d);',
    '  a = a * a;',
    '  float core = smoothstep(0.16, 0.0, d) * 0.6;',
    '  vec3 col = vColor + core;',
    '  gl_FragColor = vec4(col, a * vFade * vTwinkle * uOpacity);',
    '}'
  ].join('\n');

  var CORE_VERT = [
    'uniform float uTime;',
    'uniform float uAmp;',
    'varying vec3 vNormal;',
    'varying vec3 vView;',
    'varying float vNoise;',
    '',
    // Compact value noise. Enough character for a slow-morphing blob and
    // cheap enough for a 4-subdivision icosahedron.
    'float hash(vec3 p) {',
    '  return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453);',
    '}',
    'float noise(vec3 p) {',
    '  vec3 i = floor(p);',
    '  vec3 f = fract(p);',
    '  vec3 u = f * f * (3.0 - 2.0 * f);',
    '  float n000 = hash(i + vec3(0.0, 0.0, 0.0));',
    '  float n100 = hash(i + vec3(1.0, 0.0, 0.0));',
    '  float n010 = hash(i + vec3(0.0, 1.0, 0.0));',
    '  float n110 = hash(i + vec3(1.0, 1.0, 0.0));',
    '  float n001 = hash(i + vec3(0.0, 0.0, 1.0));',
    '  float n101 = hash(i + vec3(1.0, 0.0, 1.0));',
    '  float n011 = hash(i + vec3(0.0, 1.0, 1.0));',
    '  float n111 = hash(i + vec3(1.0, 1.0, 1.0));',
    '  float nx00 = mix(n000, n100, u.x);',
    '  float nx10 = mix(n010, n110, u.x);',
    '  float nx01 = mix(n001, n101, u.x);',
    '  float nx11 = mix(n011, n111, u.x);',
    '  return mix(mix(nx00, nx10, u.y), mix(nx01, nx11, u.y), u.z);',
    '}',
    'float fbm(vec3 p) {',
    '  float v = 0.0;',
    '  float a = 0.5;',
    '  for (int i = 0; i < 4; i++) {',
    '    v += a * noise(p);',
    '    p *= 2.03;',
    '    a *= 0.5;',
    '  }',
    '  return v;',
    '}',
    '',
    'void main() {',
    '  vNormal = normalize(normalMatrix * normal);',
    '  float n = fbm(position * 0.55 + vec3(0.0, 0.0, uTime * 0.16));',
    '  vNoise = n;',
    '  vec3 pos = position + normal * (n - 0.5) * uAmp;',
    '  vec4 mv = modelViewMatrix * vec4(pos, 1.0);',
    '  vView = -mv.xyz;',
    '  gl_Position = projectionMatrix * mv;',
    '}'
  ].join('\n');

  var CORE_FRAG = [
    'uniform vec3 uColorA;',
    'uniform vec3 uColorB;',
    'uniform float uOpacity;',
    'varying vec3 vNormal;',
    'varying vec3 vView;',
    'varying float vNoise;',
    '',
    'void main() {',
    '  vec3 v = normalize(vView);',
    '  vec3 n = normalize(vNormal);',
    // Rim light: the surface only shows where it turns away from the camera,
    // which reads as a glowing shell rather than a solid ball.
    '  float rim = 1.0 - max(dot(v, n), 0.0);',
    // A high exponent keeps the glow on the silhouette. Lower values fill the
    // sphere in, and with additive blending on a DoubleSide mesh the two
    // faces sum into an opaque ball that competes with the headline.
    '  float edge = pow(rim, 3.6);',
    '  vec3 col = mix(uColorA, uColorB, clamp(vNoise * 1.4, 0.0, 1.0));',
    '  float a = edge * 0.5 + vNoise * 0.015;',
    '  gl_FragColor = vec4(col, a * uOpacity);',
    '}'
  ].join('\n');

  var RING_VERT = [
    'uniform float uTime;',
    'varying vec2 vUv;',
    'void main() {',
    '  vUv = uv;',
    '  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);',
    '}'
  ].join('\n');

  var RING_FRAG = [
    'uniform float uTime;',
    'uniform vec3 uColor;',
    'uniform float uOpacity;',
    'varying vec2 vUv;',
    'void main() {',
    // A single bright arc chasing around the ring, plus a dim base.
    '  float sweep = fract(vUv.x - uTime * 0.08);',
    '  float head = smoothstep(0.0, 0.06, sweep) * smoothstep(0.34, 0.10, sweep);',
    '  float band = smoothstep(0.5, 0.0, abs(vUv.y - 0.5) * 2.0);',
    '  float a = (head * 0.9 + 0.06) * band;',
    '  gl_FragColor = vec4(uColor, a * uOpacity);',
    '}'
  ].join('\n');

  /* ----------------------------------------------------------------------
     State
     ---------------------------------------------------------------------- */

  var THREE = null;
  var canvas = null;
  var renderer = null;
  var scene = null;
  var camera = null;
  var clock = null;

  var nodes = null;         // THREE.Points
  var links = null;         // THREE.LineSegments
  var core = null;          // THREE.Mesh
  var ring = null;          // THREE.Mesh
  var group = null;         // everything, so one rotation drives the lot

  var rafId = 0;
  var running = false;
  var started = false;
  var destroyed = false;
  var reduced = false;

  var pointer = { x: 0, y: 0, tx: 0, ty: 0 };
  var scrollProgress = 0;
  var burst = 0;
  var theme = 'dark';

  var listeners = [];
  // Per-vertex distance fade for the link mesh, kept aside so a theme change
  // can recolour the edges without losing their depth shading.
  var linkFades = null;

  /* ----------------------------------------------------------------------
     Helpers
     ---------------------------------------------------------------------- */

  function on(target, type, handler, opts) {
    target.addEventListener(type, handler, opts || false);
    listeners.push([target, type, handler, opts || false]);
  }

  function offAll() {
    for (var i = 0; i < listeners.length; i++) {
      var l = listeners[i];
      try { l[0].removeEventListener(l[1], l[2], l[3]); } catch (e) { /* gone already */ }
    }
    listeners.length = 0;
  }

  function prefersReduced() {
    return !!(global.matchMedia && global.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }

  function resolveCount() {
    var w = global.innerWidth || 1280;
    var n;

    if (w < 760) n = CONFIG.nodeCountMobile;
    else if (w < 1180) n = Math.round(CONFIG.nodeCount * 0.7);
    else n = CONFIG.nodeCount;

    /* Halve the cloud on low-core machines. This product is aimed at school
       laptops, where a soft-rendered particle field is the difference between
       a smooth page and an unusable one, and hardwareConcurrency is the only
       capability signal available before anything has been drawn. */
    var cores = global.navigator && global.navigator.hardwareConcurrency;
    if (cores && cores <= 4) n = Math.round(n * 0.5);

    return n;
  }

  /**
   * Cheap capability check: does the constructor exist at all?
   *
   * Deliberately NOT a probe context on a throwaway canvas. That approach
   * consumes one of the small number of GL contexts a driver will hand out,
   * and releasing it via WEBGL_lose_context is both asynchronous and noisy —
   * it prints a CONTEXT_LOST_WEBGL warning to the console and, on
   * software renderers, can leave the real canvas unable to acquire a
   * context at all. The authoritative test is simply constructing the real
   * renderer, which throws when WebGL is unavailable and is already wrapped
   * in try/catch at the call site.
   */
  function webglSupported() {
    return typeof global.WebGLRenderingContext !== 'undefined';
  }

  /** Pick an index from a weighted distribution. */
  function weightedPick(weights, r) {
    var acc = 0;
    for (var i = 0; i < weights.length; i++) {
      acc += weights[i];
      if (r <= acc) return i;
    }
    return weights.length - 1;
  }

  /* ----------------------------------------------------------------------
     Geometry construction
     ---------------------------------------------------------------------- */

  /**
   * Distribute points in a shell around the origin. A pure random sphere
   * clumps at the poles, so directions come from a normalised gaussian and
   * radii from a cube root, which gives an even shell with a hollow middle
   * for the core to occupy.
   */
  function buildNodeGeometry(count, palette) {
    var positions = new Float32Array(count * 3);
    var colors = new Float32Array(count * 3);
    var scales = new Float32Array(count);
    var seeds = new Float32Array(count);

    var colorObjs = palette.nodes.map(function (hex) { return new THREE.Color(hex); });
    var inner = CONFIG.coreRadius + 0.8;
    var outer = CONFIG.radius;

    for (var i = 0; i < count; i++) {
      // Marsaglia-ish direction via Box-Muller gaussians.
      var u1 = Math.random() || 1e-6;
      var u2 = Math.random();
      var mag = Math.sqrt(-2 * Math.log(u1));
      var gx = mag * Math.cos(2 * Math.PI * u2);
      var gy = mag * Math.sin(2 * Math.PI * u2);
      var u3 = Math.random() || 1e-6;
      var u4 = Math.random();
      var gz = Math.sqrt(-2 * Math.log(u3)) * Math.cos(2 * Math.PI * u4);

      var len = Math.sqrt(gx * gx + gy * gy + gz * gz) || 1;
      var r = inner + (outer - inner) * Math.cbrt(Math.random());

      // Flatten slightly on Z so the cloud reads as a disc from the front.
      positions[i * 3 + 0] = (gx / len) * r * 1.28;
      positions[i * 3 + 1] = (gy / len) * r * 0.92;
      positions[i * 3 + 2] = (gz / len) * r * 0.62;

      var c = colorObjs[weightedPick(palette.weights, Math.random())];
      colors[i * 3 + 0] = c.r;
      colors[i * 3 + 1] = c.g;
      colors[i * 3 + 2] = c.b;

      scales[i] = 0.45 + Math.random() * Math.random() * 2.1;
      seeds[i] = Math.random();
    }

    var geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.setAttribute('aColor', new THREE.BufferAttribute(colors, 3));
    geo.setAttribute('aScale', new THREE.BufferAttribute(scales, 1));
    geo.setAttribute('aSeed', new THREE.BufferAttribute(seeds, 1));
    return geo;
  }

  /**
   * Edges between nodes that are close enough to count as "same concept".
   *
   * A naive O(n^2) sweep over 1400 nodes is ~1M distance checks, which is
   * fine once at init but wasteful. Nodes are bucketed into a uniform grid
   * first and only neighbouring buckets are compared, which brings it down to
   * roughly linear and keeps startup under a frame.
   */
  function buildLinkGeometry(nodeGeo, palette) {
    var pos = nodeGeo.getAttribute('position');
    var count = pos.count;
    var cell = CONFIG.linkDistance;
    var buckets = Object.create(null);
    var i;

    function key(x, y, z) {
      return Math.floor(x / cell) + '|' + Math.floor(y / cell) + '|' + Math.floor(z / cell);
    }

    for (i = 0; i < count; i++) {
      var k = key(pos.getX(i), pos.getY(i), pos.getZ(i));
      if (!buckets[k]) buckets[k] = [];
      buckets[k].push(i);
    }

    var verts = [];
    var cols = [];
    var fades = [];
    var linkColor = new THREE.Color(palette.link);
    var maxSq = cell * cell;
    var made = 0;

    for (i = 0; i < count && made < CONFIG.maxLinks; i++) {
      var ax = pos.getX(i), ay = pos.getY(i), az = pos.getZ(i);
      var bx = Math.floor(ax / cell), by = Math.floor(ay / cell), bz = Math.floor(az / cell);

      for (var dx = -1; dx <= 1 && made < CONFIG.maxLinks; dx++) {
        for (var dy = -1; dy <= 1 && made < CONFIG.maxLinks; dy++) {
          for (var dz = -1; dz <= 1 && made < CONFIG.maxLinks; dz++) {
            var list = buckets[(bx + dx) + '|' + (by + dy) + '|' + (bz + dz)];
            if (!list) continue;

            for (var n = 0; n < list.length; n++) {
              var j = list[n];
              if (j <= i) continue; // each pair once

              var vx = pos.getX(j) - ax;
              var vy = pos.getY(j) - ay;
              var vz = pos.getZ(j) - az;
              var dsq = vx * vx + vy * vy + vz * vz;
              if (dsq > maxSq) continue;

              verts.push(ax, ay, az, pos.getX(j), pos.getY(j), pos.getZ(j));
              // Fade the edge with distance so the mesh looks depth-sorted.
              var f = 1 - Math.sqrt(dsq) / cell;
              cols.push(
                linkColor.r * f, linkColor.g * f, linkColor.b * f,
                linkColor.r * f, linkColor.g * f, linkColor.b * f
              );
              fades.push(f, f);
              made++;
              if (made >= CONFIG.maxLinks) break;
            }
          }
        }
      }
    }

    linkFades = new Float32Array(fades);

    var geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(verts), 3));
    geo.setAttribute('color', new THREE.BufferAttribute(new Float32Array(cols), 3));
    return geo;
  }

  /* ----------------------------------------------------------------------
     Scene assembly
     ---------------------------------------------------------------------- */

  function buildScene() {
    var palette = PALETTE[theme] || PALETTE.dark;
    var pr = Math.min(global.devicePixelRatio || 1, CONFIG.maxPixelRatio);

    scene = new THREE.Scene();
    group = new THREE.Group();
    // Pushed right so the lattice sits over the HUD half of the hero rather
    // than behind the headline. The canvas mask in sections.css fades the
    // left edge for the same reason; both are needed, because the mask only
    // controls opacity and bright particles still read through a soft fade.
    group.position.x = CONFIG.offsetX;
    scene.add(group);

    camera = new THREE.PerspectiveCamera(52, 1, 0.1, 120);
    camera.position.set(0, 0, CONFIG.cameraZ);

    /* --- nodes --- */
    var nodeGeo = buildNodeGeometry(resolveCount(), palette);
    var nodeMat = new THREE.ShaderMaterial({
      uniforms: {
        uTime: { value: 0 },
        uSize: { value: 3.1 },
        uPixelRatio: { value: pr },
        uOpacity: { value: palette.opacity },
        uBurst: { value: 0 }
      },
      vertexShader: NODE_VERT,
      fragmentShader: NODE_FRAG,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending
    });
    nodes = new THREE.Points(nodeGeo, nodeMat);
    group.add(nodes);

    /* --- links --- */
    links = new THREE.LineSegments(
      buildLinkGeometry(nodeGeo, palette),
      new THREE.LineBasicMaterial({
        vertexColors: true,
        transparent: true,
        opacity: palette.linkOpacity,
        depthWrite: false,
        blending: THREE.AdditiveBlending
      })
    );
    group.add(links);

    /* --- core --- */
    core = new THREE.Mesh(
      new THREE.IcosahedronGeometry(CONFIG.coreRadius, 4),
      new THREE.ShaderMaterial({
        uniforms: {
          uTime: { value: 0 },
          uAmp: { value: 0.62 },
          uColorA: { value: new THREE.Color(palette.core[0]) },
          uColorB: { value: new THREE.Color(palette.core[1]) },
          uOpacity: { value: palette.opacity }
        },
        vertexShader: CORE_VERT,
        fragmentShader: CORE_FRAG,
        transparent: true,
        depthWrite: false,
        side: THREE.DoubleSide,
        blending: THREE.AdditiveBlending
      })
    );
    group.add(core);

    /* --- ring --- */
    ring = new THREE.Mesh(
      new THREE.TorusGeometry(CONFIG.coreRadius * 1.85, 0.035, 8, 220),
      new THREE.ShaderMaterial({
        uniforms: {
          uTime: { value: 0 },
          uColor: { value: new THREE.Color(palette.core[1]) },
          uOpacity: { value: palette.opacity }
        },
        vertexShader: RING_VERT,
        fragmentShader: RING_FRAG,
        transparent: true,
        depthWrite: false,
        side: THREE.DoubleSide,
        blending: THREE.AdditiveBlending
      })
    );
    ring.rotation.x = Math.PI * 0.42;
    ring.rotation.y = Math.PI * 0.12;
    group.add(ring);

    /* --- renderer --- */
    renderer = new THREE.WebGLRenderer({
      canvas: canvas,
      alpha: true,
      antialias: pr < 1.75,
      powerPreference: 'high-performance'
    });
    renderer.setPixelRatio(pr);
    renderer.setClearColor(0x000000, 0);
    // Colour-space API moved in r152; support both without assuming either.
    if ('outputColorSpace' in renderer && THREE.SRGBColorSpace) {
      renderer.outputColorSpace = THREE.SRGBColorSpace;
    } else if ('outputEncoding' in renderer && THREE.sRGBEncoding) {
      renderer.outputEncoding = THREE.sRGBEncoding;
    }

    clock = new THREE.Clock();
    resize();
  }

  /* ----------------------------------------------------------------------
     Frame loop
     ---------------------------------------------------------------------- */

  function resize() {
    if (!renderer || !canvas) return;
    var w = canvas.clientWidth || canvas.parentNode.clientWidth || 1;
    var h = canvas.clientHeight || canvas.parentNode.clientHeight || 1;
    if (w < 1 || h < 1) return;

    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    // Pull the camera back on narrow viewports so the cloud still fits.
    camera.position.z = CONFIG.cameraZ * (w < 760 ? 1.32 : 1);
    camera.updateProjectionMatrix();

    /* Below 1080px the hero collapses to one column and the copy sits on top
       of the canvas, so the lattice recentres instead of hugging the right. */
    if (group) {
      group.position.x = w >= 1080 ? CONFIG.offsetX : CONFIG.offsetXNarrow;
    }

    if (nodes) {
      nodes.material.uniforms.uPixelRatio.value =
        Math.min(global.devicePixelRatio || 1, CONFIG.maxPixelRatio);
    }
  }

  function frame() {
    if (destroyed || !renderer) return;
    rafId = global.requestAnimationFrame(frame);

    var t = clock.getElapsedTime();

    // Pointer easing. Never snap — a 1:1 pointer link feels twitchy.
    pointer.x += (pointer.tx - pointer.x) * CONFIG.lerp;
    pointer.y += (pointer.ty - pointer.y) * CONFIG.lerp;

    burst *= 0.94;

    group.rotation.y = t * 0.045 + pointer.x * 0.34;
    group.rotation.x = Math.sin(t * 0.16) * 0.06 - pointer.y * 0.22;

    // Scroll drives the group away and down, so the hero visual clears out of
    // the way rather than fighting the next section for attention.
    group.position.y = scrollProgress * 3.4;
    group.position.z = scrollProgress * -6.5;
    group.scale.setScalar(1 - scrollProgress * 0.16);

    camera.position.x = pointer.x * CONFIG.parallax;
    camera.position.y = -pointer.y * CONFIG.parallax * 0.7;
    camera.lookAt(0, 0, 0);

    nodes.material.uniforms.uTime.value = t;
    nodes.material.uniforms.uBurst.value = burst;

    core.material.uniforms.uTime.value = t;
    core.rotation.y = -t * 0.09;
    core.rotation.z = t * 0.05;
    core.scale.setScalar(1 + burst * 0.22);

    ring.material.uniforms.uTime.value = t;
    ring.rotation.z = t * 0.14;

    renderer.render(scene, camera);
  }

  function renderOnce() {
    if (!renderer) return;
    nodes.material.uniforms.uTime.value = 0.6;
    core.material.uniforms.uTime.value = 0.6;
    ring.material.uniforms.uTime.value = 0.6;
    group.rotation.y = 0.3;
    renderer.render(scene, camera);
  }

  function start() {
    if (running || destroyed || reduced) return;
    running = true;
    clock.start();
    rafId = global.requestAnimationFrame(frame);
  }

  function stop() {
    running = false;
    if (rafId) {
      global.cancelAnimationFrame(rafId);
      rafId = 0;
    }
  }

  /* ----------------------------------------------------------------------
     Theme
     ---------------------------------------------------------------------- */

  function applyTheme(next) {
    theme = next === 'light' ? 'light' : 'dark';
    if (!nodes) return;
    var p = PALETTE[theme];

    nodes.material.uniforms.uOpacity.value = p.opacity;
    links.material.opacity = p.linkOpacity;
    core.material.uniforms.uOpacity.value = p.opacity;
    core.material.uniforms.uColorA.value.setHex(p.core[0]);
    core.material.uniforms.uColorB.value.setHex(p.core[1]);
    ring.material.uniforms.uOpacity.value = p.opacity;
    ring.material.uniforms.uColor.value.setHex(p.core[1]);

    // Repaint node colours in place rather than rebuilding the buffer.
    var attr = nodes.geometry.getAttribute('aColor');
    var colorObjs = p.nodes.map(function (hex) { return new THREE.Color(hex); });
    for (var i = 0; i < attr.count; i++) {
      var c = colorObjs[weightedPick(p.weights, Math.random())];
      attr.setXYZ(i, c.r, c.g, c.b);
    }
    attr.needsUpdate = true;

    // Recolour the edges, reapplying the depth fade recorded at build time.
    var linkAttr = links.geometry.getAttribute('color');
    var lc = new THREE.Color(p.link);
    for (var j = 0; j < linkAttr.count; j++) {
      var f = linkFades ? linkFades[j] : 1;
      linkAttr.setXYZ(j, lc.r * f, lc.g * f, lc.b * f);
    }
    linkAttr.needsUpdate = true;

    if (reduced) renderOnce();
  }

  /* ----------------------------------------------------------------------
     Teardown
     ---------------------------------------------------------------------- */

  function disposeObject(obj) {
    if (!obj) return;
    if (obj.geometry && obj.geometry.dispose) obj.geometry.dispose();
    if (obj.material) {
      if (Array.isArray(obj.material)) {
        obj.material.forEach(function (m) { if (m.dispose) m.dispose(); });
      } else if (obj.material.dispose) {
        obj.material.dispose();
      }
    }
  }

  function destroy() {
    if (destroyed) return;
    destroyed = true;
    stop();
    offAll();
    disposeObject(nodes);
    disposeObject(links);
    disposeObject(core);
    disposeObject(ring);
    if (renderer) {
      try { renderer.dispose(); } catch (e) { /* already gone */ }
    }
    nodes = links = core = ring = group = scene = camera = renderer = null;
  }

  /** Hard fail-safe: drop to the CSS aurora and never try again. */
  function bail(reason) {
    document.documentElement.classList.add('no-webgl');
    if (canvas) canvas.classList.remove('is-ready');
    destroy();
    if (global.console && global.console.info) {
      global.console.info('[SkillUp] hero scene disabled: ' + reason);
    }
    return false;
  }

  /* ----------------------------------------------------------------------
     Public API
     ---------------------------------------------------------------------- */

  var api = {
    init: function () {
      if (started) return !destroyed;
      started = true;

      THREE = global.THREE || null;
      canvas = document.querySelector('[data-scene]');

      if (!canvas) return bail('no canvas on the page');
      if (!THREE) return bail('three.js did not load');
      if (!webglSupported()) return bail('WebGL unavailable');

      reduced = prefersReduced();
      theme = document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';

      try {
        buildScene();
      } catch (err) {
        return bail('scene build failed — ' + (err && err.message ? err.message : err));
      }

      canvas.classList.add('is-ready');

      /* A lost context is recoverable in principle but not worth the
         complexity here; the CSS fallback is good. Restoration is accepted so
         the browser does not keep retrying. */
      on(canvas, 'webglcontextlost', function (e) {
        e.preventDefault();
        bail('GL context lost');
      });

      on(global, 'resize', function () {
        resize();
        if (reduced) renderOnce();
      });

      on(document, 'visibilitychange', function () {
        if (document.hidden) stop();
        else if (!reduced) start();
      });

      if (reduced) {
        renderOnce();
      } else {
        start();
      }

      return true;
    },

    /** Pointer position, normalised to -1..1 with 0 at the centre. */
    setPointer: function (x, y) {
      pointer.tx = Math.max(-1, Math.min(1, x || 0));
      pointer.ty = Math.max(-1, Math.min(1, y || 0));
    },

    /** 0 at the top of the hero, 1 once it has scrolled fully away. */
    setScroll: function (p) {
      scrollProgress = Math.max(0, Math.min(1, p || 0));
    },

    /** One-shot outward pulse — index.js fires this when a diagnosis lands. */
    pulse: function () {
      burst = 1;
    },

    setTheme: function (next) {
      if (!started || destroyed) { theme = next; return; }
      try { applyTheme(next); } catch (e) { /* cosmetic only */ }
    },

    pause: stop,

    resume: function () {
      if (!destroyed && !reduced && !document.hidden) start();
    },

    isRunning: function () {
      return running && !destroyed;
    },

    destroy: destroy
  };

  global.SkillUpScene = api;

})(window);
