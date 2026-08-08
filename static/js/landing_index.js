/* ==========================================================================
   SKILL UP — INTERACTION LAYER
   --------------------------------------------------------------------------
   Everything that responds to a person: the cursor, the navigation, the
   command palette, the counters, the accordion, the pricing switch, and the
   live diagnosis demo that the whole page is built around.

   Two rules govern this file.

   1. Every module is wrapped in `safe()`. A module that throws logs once and
      is skipped; it cannot take the rest of the page down with it. There is
      also a hard backstop that reveals all content after 3 seconds no matter
      what happened before it.

   2. Nothing here is load-bearing for reading the page. Content is rendered
      by Django and readable with JavaScript disabled entirely. This file adds
      behaviour on top; it never supplies the substance.

   Contents
     00  Utilities
     01  Safety backstop
     02  Preloader
     03  Theme
     04  Custom cursor & magnetic targets
     05  Navigation
     06  Mobile drawer
     07  Command palette
     08  Scroll progress & back-to-top
     09  Reveal fallback (no GSAP)
     10  Counters
     11  Tilt, bloom & ripple
     12  Hero HUD stream
     13  Hero rotator
     14  Inline capability demos
     15  Live diagnosis demo
     16  FAQ accordion
     17  Pricing billing switch
     18  CTA form
     19  Keyboard extras
     20  Boot
   ========================================================================== */

(function (global) {
  'use strict';

  var doc = document;
  var html = doc.documentElement;

  /* ======================================================================
     00  UTILITIES
     ====================================================================== */

  function $(sel, root) { return (root || doc).querySelector(sel); }

  function $$(sel, root) {
    return Array.prototype.slice.call((root || doc).querySelectorAll(sel));
  }

  function on(target, type, fn, opts) {
    if (!target) return;
    target.addEventListener(type, fn, opts === undefined ? false : opts);
  }

  function clamp(v, lo, hi) { return v < lo ? lo : (v > hi ? hi : v); }

  function lerp(a, b, t) { return a + (b - a) * t; }

  function prefersReduced() {
    return !!(global.matchMedia && global.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }

  function isFinePointer() {
    return !!(global.matchMedia && global.matchMedia('(pointer: fine)').matches);
  }

  function isMac() {
    var p = global.navigator && (global.navigator.userAgentData
      ? global.navigator.userAgentData.platform
      : global.navigator.platform);
    return /mac|iphone|ipad|ipod/i.test(String(p || ''));
  }

  /** Fire fn at most once per animation frame. */
  function rafThrottle(fn) {
    var queued = false;
    var lastArgs = null;
    return function () {
      lastArgs = arguments;
      if (queued) return;
      queued = true;
      global.requestAnimationFrame(function () {
        queued = false;
        fn.apply(null, lastArgs);
      });
    };
  }

  function debounce(fn, wait) {
    var t = 0;
    return function () {
      var args = arguments;
      global.clearTimeout(t);
      t = global.setTimeout(function () { fn.apply(null, args); }, wait);
    };
  }

  /** Run a module, swallowing (and reporting once) any failure inside it. */
  function safe(name, fn) {
    try {
      fn();
    } catch (err) {
      if (global.console && global.console.warn) {
        global.console.warn('[SkillUp] module "' + name + '" skipped:',
          err && err.message ? err.message : err);
      }
    }
  }

  /** Sequential timers that a later call can cancel wholesale. */
  function Sequence() {
    this.timers = [];
    this.cancelled = false;
  }

  Sequence.prototype.at = function (ms, fn) {
    var self = this;
    var id = global.setTimeout(function () {
      if (!self.cancelled) fn();
    }, ms);
    this.timers.push(id);
    return this;
  };

  Sequence.prototype.cancel = function () {
    this.cancelled = true;
    for (var i = 0; i < this.timers.length; i++) global.clearTimeout(this.timers[i]);
    this.timers.length = 0;
  };

  /* --- Toasts ----------------------------------------------------------- */

  var toastHost = null;

  function toast(message, kind) {
    if (!toastHost) toastHost = $('[data-toast-host]');
    if (!toastHost) return;

    var el = doc.createElement('div');
    el.className = 'toast' + (kind ? ' toast--' + kind : '');

    var icon = doc.createElementNS('http://www.w3.org/2000/svg', 'svg');
    var use = doc.createElementNS('http://www.w3.org/2000/svg', 'use');
    var href = kind === 'warn' ? '#i-alert' : (kind === 'info' ? '#i-info' : '#i-check-circle');
    use.setAttribute('href', href);
    icon.appendChild(use);
    icon.setAttribute('aria-hidden', 'true');

    var text = doc.createElement('span');
    text.textContent = message;

    el.appendChild(icon);
    el.appendChild(text);
    toastHost.appendChild(el);

    global.setTimeout(function () {
      el.classList.add('is-leaving');
      global.setTimeout(function () {
        if (el.parentNode) el.parentNode.removeChild(el);
      }, 300);
    }, 3200);
  }

  /* --- Scroll lock ------------------------------------------------------ */

  var lockCount = 0;

  function lockScroll(lock) {
    lockCount = Math.max(0, lockCount + (lock ? 1 : -1));
    doc.body.classList.toggle('is-locked', lockCount > 0);
  }

  /** Smooth-scroll to an element, accounting for the floating navbar. */
  function scrollToTarget(target) {
    var el = typeof target === 'string' ? $(target) : target;
    if (!el) return;

    var navH = parseFloat(getComputedStyle(html).getPropertyValue('--nav-h')) || 68;
    var inset = parseFloat(getComputedStyle(html).getPropertyValue('--nav-inset')) || 14;
    var top = el.getBoundingClientRect().top + global.pageYOffset - navH - inset - 18;

    global.scrollTo({
      top: Math.max(0, top),
      behavior: prefersReduced() ? 'auto' : 'smooth'
    });
  }

  /* ======================================================================
     01  SAFETY BACKSTOP
     ----------------------------------------------------------------------
     Whatever else happens, no visitor is left staring at invisible content.
     ====================================================================== */

  /**
   * A [data-reveal] element sits at opacity 0 until something animates it in.
   * If that something never happens — GSAP failed to load, a ScrollTrigger
   * was skipped by a large programmatic jump, a tween got overwritten — the
   * visitor is looking at blank space where content should be. That is the
   * single worst failure this page can have, so it gets a watchdog rather
   * than trust.
   *
   * The rule: any reveal element that has been sitting inside the viewport
   * while still fully transparent gets shown, full stop. Elements that are
   * merely mid-animation have a non-zero opacity and are left alone, so this
   * never interrupts a running entrance.
   */
  function revealBackstop() {
    var targets = $$('[data-reveal]');
    if (!targets.length) return;

    function sweep() {
      var vh = global.innerHeight;
      var remaining = 0;

      targets.forEach(function (el) {
        if (el.classList.contains('is-revealed') && parseFloat(getComputedStyle(el).opacity) > 0.9) return;
        remaining++;

        var box = el.getBoundingClientRect();
        var inViewport = box.top < vh * 1.1 && box.bottom > -vh * 0.1;
        if (!inViewport) return;

        // Genuinely stuck: visible on screen and still completely transparent.
        if (parseFloat(getComputedStyle(el).opacity) < 0.02) {
          el.classList.add('is-revealed');
          el.style.opacity = '1';
          el.style.transform = 'none';
        }
      });

      return remaining;
    }

    // Elements need to have been on screen for a beat before we call them
    // stuck, otherwise we would pre-empt every legitimate entrance.
    var pending = null;

    var schedule = rafThrottle(function () {
      global.clearTimeout(pending);
      pending = global.setTimeout(sweep, 1200);
    });

    on(global, 'scroll', schedule, { passive: true });
    on(global, 'resize', schedule);

    // And a slow patrol for anything the scroll handler never sees.
    var patrol = global.setInterval(function () {
      if (sweep() === 0) global.clearInterval(patrol);
    }, 2500);

    global.setTimeout(sweep, 3000);
  }

  /* ======================================================================
     02  PRELOADER
     ====================================================================== */

  function initPreloader() {
    var el = $('[data-preloader]');
    if (!el) {
      html.classList.add('is-booted');
      return;
    }

    var fill = $('[data-preloader-fill]', el);
    var status = $('[data-preloader-status]', el);
    var steps = [
      'Booting diagnostic engine',
      'Loading attempt history',
      'Warming the prompt cache',
      'Ready'
    ];

    var progress = 0;
    var step = 0;
    var done = false;
    var tick = 0;

    function setProgress(p) {
      progress = clamp(p, 0, 1);
      if (fill) fill.style.transform = 'scaleX(' + progress.toFixed(3) + ')';
    }

    function finish() {
      if (done) return;
      done = true;
      global.clearInterval(tick);
      setProgress(1);
      if (status) status.textContent = 'Ready';

      global.setTimeout(function () {
        el.classList.add('is-done');
        html.classList.add('is-booted');
        lockScroll(false);
        // Trigger position depends on final layout; recompute once the
        // preloader has stopped occupying the viewport.
        if (global.SkillUpMotion && global.SkillUpMotion.refresh) {
          global.SkillUpMotion.refresh();
        }
        el.setAttribute('aria-hidden', 'true');
        global.setTimeout(function () {
          if (el.parentNode) el.parentNode.removeChild(el);
        }, 800);
      }, 260);
    }

    lockScroll(true);

    // Creep forward on a timer so the bar always moves, even on a fast load.
    tick = global.setInterval(function () {
      setProgress(progress + (0.9 - progress) * 0.18);
      var next = Math.min(steps.length - 1, Math.floor(progress * steps.length));
      if (next !== step && status) {
        step = next;
        status.textContent = steps[step];
      }
    }, 180);

    if (doc.readyState === 'complete') {
      global.setTimeout(finish, 420);
    } else {
      on(global, 'load', function () { global.setTimeout(finish, 260); });
    }

    // Hard ceiling. A stalled font or a slow CDN must never hold the page.
    global.setTimeout(finish, 2600);
  }

  /* ======================================================================
     03  THEME
     ====================================================================== */

  var Theme = {
    get: function () {
      return html.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
    },

    set: function (next, announce) {
      var value = next === 'light' ? 'light' : 'dark';
      html.setAttribute('data-theme', value);

      try { localStorage.setItem('skillup-theme', value); } catch (e) { /* private mode */ }

      var btn = $('[data-theme-toggle]');
      if (btn) btn.setAttribute('aria-pressed', value === 'light' ? 'true' : 'false');

      var meta = $('meta[name="theme-color"]');
      if (meta) meta.setAttribute('content', value === 'light' ? '#f7f8fc' : '#060913');

      if (global.SkillUpScene && global.SkillUpScene.setTheme) {
        global.SkillUpScene.setTheme(value);
      }

      if (announce) toast(value === 'light' ? 'Light theme' : 'Dark theme', 'info');
    },

    toggle: function () {
      this.set(this.get() === 'light' ? 'dark' : 'light', true);
    }
  };

  function initTheme() {
    var btn = $('[data-theme-toggle]');
    Theme.set(Theme.get(), false);

    on(btn, 'click', function () { Theme.toggle(); });

    // Follow the OS only while the visitor has not made an explicit choice.
    if (global.matchMedia) {
      var q = global.matchMedia('(prefers-color-scheme: light)');
      var handler = function (e) {
        var stored = null;
        try { stored = localStorage.getItem('skillup-theme'); } catch (err) { stored = null; }
        if (!stored) Theme.set(e.matches ? 'light' : 'dark', false);
      };
      if (q.addEventListener) q.addEventListener('change', handler);
      else if (q.addListener) q.addListener(handler);
    }
  }

  /* ======================================================================
     04  CUSTOM CURSOR & MAGNETIC TARGETS
     ====================================================================== */

  function initCursor() {
    var el = $('[data-cursor]');
    if (!el || !isFinePointer() || prefersReduced()) return;

    var label = $('[data-cursor-label]', el);
    var pos = { x: global.innerWidth / 2, y: global.innerHeight / 2 };
    var target = { x: pos.x, y: pos.y };
    var raf = 0;
    var visible = false;

    function loop() {
      // The ring trails the pointer slightly; that lag is the whole effect.
      pos.x = lerp(pos.x, target.x, 0.22);
      pos.y = lerp(pos.y, target.y, 0.22);
      el.style.transform = 'translate3d(' + pos.x + 'px,' + pos.y + 'px,0)';
      raf = global.requestAnimationFrame(loop);
    }

    on(doc, 'pointermove', function (e) {
      if (e.pointerType && e.pointerType !== 'mouse') return;
      target.x = e.clientX;
      target.y = e.clientY;

      if (!visible) {
        visible = true;
        pos.x = target.x;
        pos.y = target.y;
        html.classList.add('has-cursor');
        if (!raf) raf = global.requestAnimationFrame(loop);
      }

      // Feed the WebGL scene the same pointer, normalised.
      if (global.SkillUpScene && global.SkillUpScene.setPointer) {
        global.SkillUpScene.setPointer(
          (e.clientX / global.innerWidth) * 2 - 1,
          (e.clientY / global.innerHeight) * 2 - 1
        );
      }
    }, { passive: true });

    on(doc, 'pointerdown', function () { html.classList.add('cursor-down'); });
    on(doc, 'pointerup', function () { html.classList.remove('cursor-down'); });

    on(doc, 'mouseleave', function () {
      html.classList.remove('has-cursor');
      visible = false;
    });

    on(doc, 'mouseenter', function () {
      if (visible) html.classList.add('has-cursor');
    });

    // Delegated hover state — survives any DOM the demo re-renders.
    var HOVER_SELECTOR = 'a, button, [role="tab"], [role="option"], input, textarea, select, [data-cursor], [tabindex]:not([tabindex="-1"])';

    on(doc, 'pointerover', function (e) {
      var t = e.target && e.target.closest ? e.target.closest(HOVER_SELECTOR) : null;
      if (!t) return;

      var text = t.getAttribute('data-cursor');
      if (text) {
        html.classList.add('cursor-label');
        html.classList.remove('cursor-hover');
        if (label) label.textContent = text;
      } else {
        html.classList.add('cursor-hover');
        html.classList.remove('cursor-label');
      }
    }, true);

    on(doc, 'pointerout', function (e) {
      var t = e.target && e.target.closest ? e.target.closest(HOVER_SELECTOR) : null;
      if (!t) return;
      var to = e.relatedTarget;
      if (to && to.closest && to.closest(HOVER_SELECTOR)) return;
      html.classList.remove('cursor-hover', 'cursor-label');
    }, true);
  }

  /**
   * Magnetic buttons. The element leans a few pixels toward the pointer while
   * it is nearby, then springs back. Capped hard so it never shifts layout or
   * overlaps a neighbour.
   */
  function initMagnetic() {
    if (!isFinePointer() || prefersReduced()) return;

    var STRENGTH = 0.28;
    var MAX = 9;

    $$('[data-magnetic]').forEach(function (el) {
      var raf = 0;
      var cur = { x: 0, y: 0 };
      var to = { x: 0, y: 0 };

      function tick() {
        cur.x = lerp(cur.x, to.x, 0.18);
        cur.y = lerp(cur.y, to.y, 0.18);
        el.style.transform = 'translate3d(' + cur.x.toFixed(2) + 'px,' + cur.y.toFixed(2) + 'px,0)';

        if (Math.abs(cur.x - to.x) < 0.05 && Math.abs(cur.y - to.y) < 0.05) {
          global.cancelAnimationFrame(raf);
          raf = 0;
          if (to.x === 0 && to.y === 0) el.style.transform = '';
          return;
        }
        raf = global.requestAnimationFrame(tick);
      }

      function kick() { if (!raf) raf = global.requestAnimationFrame(tick); }

      on(el, 'pointermove', function (e) {
        if (e.pointerType && e.pointerType !== 'mouse') return;
        var r = el.getBoundingClientRect();
        to.x = clamp((e.clientX - (r.left + r.width / 2)) * STRENGTH, -MAX, MAX);
        to.y = clamp((e.clientY - (r.top + r.height / 2)) * STRENGTH, -MAX, MAX);
        kick();
      }, { passive: true });

      on(el, 'pointerleave', function () {
        to.x = 0;
        to.y = 0;
        kick();
      });
    });
  }

  /* ======================================================================
     05  NAVIGATION
     ====================================================================== */

  function initNav() {
    var nav = $('[data-nav]');
    if (!nav) return;

    var links = $$('[data-nav-link]');
    var pill = $('[data-nav-pill]');
    var lastY = global.pageYOffset;

    /* --- condense + hide on scroll-down --- */
    var onScroll = rafThrottle(function () {
      var y = global.pageYOffset;
      nav.classList.toggle('is-stuck', y > 40);

      // Only hide once past the hero, and never while a menu is open.
      var goingDown = y > lastY && y > 320;
      var menuOpen = doc.body.classList.contains('is-locked');
      nav.classList.toggle('is-hidden', goingDown && !menuOpen);

      lastY = y;
    });

    on(global, 'scroll', onScroll, { passive: true });
    onScroll();

    /* --- sliding pill --- */
    function movePill(el) {
      if (!pill || !el) return;
      var parent = el.parentNode;
      var pr = parent.getBoundingClientRect();
      var r = el.getBoundingClientRect();
      pill.style.setProperty('--pill-x', (r.left - pr.left) + 'px');
      pill.style.setProperty('--pill-w', r.width + 'px');
      pill.style.top = (r.top - pr.top) + 'px';
      pill.style.height = r.height + 'px';
    }

    function activeLink() {
      return links.filter(function (l) { return l.classList.contains('is-active'); })[0] || null;
    }

    links.forEach(function (link) {
      on(link, 'pointerenter', function () {
        movePill(link);
        if (pill) pill.classList.add('is-on');
      });
    });

    var linkBar = $('[data-nav-links]');
    on(linkBar, 'pointerleave', function () {
      var act = activeLink();
      if (act) {
        movePill(act);
      } else if (pill) {
        pill.classList.remove('is-on');
      }
    });

    /* --- active section tracking ---
       IntersectionObserver rather than a scroll handler: it costs nothing
       when nothing is crossing, and it stays correct through the pinned
       pipeline section, where computed offsets would not. */
    var sections = links.map(function (l) {
      var id = l.getAttribute('href');
      return id && id.charAt(0) === '#' ? $(id) : null;
    });

    if ('IntersectionObserver' in global) {
      var visible = Object.create(null);

      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          visible[entry.target.id] = entry.isIntersecting ? entry.intersectionRatio : 0;
        });

        var bestId = null;
        var bestRatio = 0;
        Object.keys(visible).forEach(function (id) {
          if (visible[id] > bestRatio) {
            bestRatio = visible[id];
            bestId = id;
          }
        });

        links.forEach(function (l) {
          l.classList.toggle('is-active', bestId !== null && l.getAttribute('href') === '#' + bestId);
        });

        var act = activeLink();
        var hovering = !!(linkBar && linkBar.matches && linkBar.matches(':hover'));
        if (act && pill && !hovering) {
          movePill(act);
          pill.classList.add('is-on');
        } else if (!act && pill) {
          pill.classList.remove('is-on');
        }
      }, { threshold: [0, 0.15, 0.35, 0.6], rootMargin: '-20% 0px -45% 0px' });

      sections.forEach(function (s) { if (s) io.observe(s); });
    }

    on(global, 'resize', debounce(function () {
      var act = activeLink();
      if (act) movePill(act);
    }, 160));

    /* --- smooth in-page navigation --- */
    on(doc, 'click', function (e) {
      var a = e.target && e.target.closest ? e.target.closest('a[href^="#"]') : null;
      if (!a) return;

      var href = a.getAttribute('href');
      if (!href || href === '#') return;

      var target = $(href);
      if (!target) return;

      e.preventDefault();
      scrollToTarget(target);

      // Keep the URL honest without adding a history entry per click.
      if (global.history && global.history.replaceState) {
        global.history.replaceState(null, '', href);
      }
    });

    /* --- ⌘ vs Ctrl in the palette hint --- */
    if (isMac()) {
      var modKey = $('[data-mod-key]');
      if (modKey) modKey.textContent = '⌘';
    }
  }

  /* ======================================================================
     06  MOBILE DRAWER
     ====================================================================== */

  function initDrawer() {
    var drawer = $('[data-drawer]');
    var openBtn = $('[data-drawer-open]');
    var closeBtn = $('[data-drawer-close]');
    if (!drawer || !openBtn) return;

    var lastFocus = null;

    function focusables() {
      return $$('a[href], button:not([disabled])', drawer).filter(function (el) {
        return el.offsetParent !== null;
      });
    }

    function open() {
      lastFocus = doc.activeElement;
      drawer.classList.add('is-open');
      openBtn.setAttribute('aria-expanded', 'true');
      lockScroll(true);
      var f = focusables();
      if (f.length) f[0].focus();
    }

    function close() {
      drawer.classList.remove('is-open');
      openBtn.setAttribute('aria-expanded', 'false');
      lockScroll(false);
      if (lastFocus && lastFocus.focus) lastFocus.focus();
    }

    on(openBtn, 'click', open);
    on(closeBtn, 'click', close);

    $$('[data-drawer-link]', drawer).forEach(function (l) {
      on(l, 'click', function () { global.setTimeout(close, 90); });
    });

    on(doc, 'keydown', function (e) {
      if (!drawer.classList.contains('is-open')) return;

      if (e.key === 'Escape') {
        close();
        return;
      }

      // Trap focus inside the drawer while it is modal.
      if (e.key === 'Tab') {
        var f = focusables();
        if (!f.length) return;
        var first = f[0];
        var last = f[f.length - 1];

        if (e.shiftKey && doc.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && doc.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    });

    // Close if the viewport grows back to a size where the drawer is hidden.
    on(global, 'resize', debounce(function () {
      if (global.innerWidth > 1080 && drawer.classList.contains('is-open')) close();
    }, 200));
  }

  /* ======================================================================
     07  COMMAND PALETTE
     ====================================================================== */

  function initPalette() {
    var palette = $('[data-palette]');
    if (!palette) return;

    var input = $('[data-palette-input]', palette);
    var list = $('[data-palette-list]', palette);
    var empty = $('[data-palette-empty]', palette);
    var items = $$('[data-palette-item]', palette);
    var openBtn = $('[data-palette-open]');
    var closeBtn = $('[data-palette-close]', palette);

    var cursor = 0;
    var lastFocus = null;

    function shown() {
      return items.filter(function (i) { return !i.classList.contains('u-hide'); });
    }

    function paintCursor() {
      var vis = shown();
      cursor = clamp(cursor, 0, Math.max(0, vis.length - 1));
      items.forEach(function (i) { i.classList.remove('is-cursor'); });
      if (vis[cursor]) {
        vis[cursor].classList.add('is-cursor');
        vis[cursor].scrollIntoView({ block: 'nearest' });
      }
    }

    function filter(q) {
      var needle = q.trim().toLowerCase();

      items.forEach(function (item) {
        if (!needle) {
          item.classList.remove('u-hide');
          return;
        }
        var hay = (item.textContent + ' ' + (item.getAttribute('data-keywords') || '')).toLowerCase();
        item.classList.toggle('u-hide', hay.indexOf(needle) === -1);
      });

      // Group headings only make sense when something under them survived.
      $$('.palette__group-title', list).forEach(function (title) {
        var any = false;
        var node = title.nextElementSibling;
        while (node && !node.classList.contains('palette__group-title')) {
          if (node.hasAttribute('data-palette-item') && !node.classList.contains('u-hide')) {
            any = true;
            break;
          }
          node = node.nextElementSibling;
        }
        title.classList.toggle('u-hide', !any);
      });

      if (empty) empty.classList.toggle('u-hide', shown().length > 0);
      cursor = 0;
      paintCursor();
    }

    function open() {
      lastFocus = doc.activeElement;
      palette.classList.add('is-open');
      lockScroll(true);
      if (input) {
        input.value = '';
        filter('');
        global.setTimeout(function () { input.focus(); }, 60);
      }
    }

    function close() {
      palette.classList.remove('is-open');
      lockScroll(false);
      if (lastFocus && lastFocus.focus) lastFocus.focus();
    }

    function run(item) {
      if (!item) return;
      close();

      var action = item.getAttribute('data-action');
      var target = item.getAttribute('data-target');

      global.setTimeout(function () {
        if (target) {
          scrollToTarget(target);
        } else if (action === 'theme') {
          Theme.toggle();
        } else if (action === 'top') {
          global.scrollTo({ top: 0, behavior: prefersReduced() ? 'auto' : 'smooth' });
        } else if (action === 'rerun') {
          scrollToTarget('#diagnosis');
          global.setTimeout(function () {
            if (global.SkillUpDemo && global.SkillUpDemo.rerun) global.SkillUpDemo.rerun();
          }, 620);
        }
      }, 140);
    }

    on(openBtn, 'click', open);
    on(closeBtn, 'click', close);
    on(input, 'input', function () { filter(input.value); });

    items.forEach(function (item) {
      on(item, 'click', function () { run(item); });
    });

    on(palette, 'click', function (e) {
      if (e.target === palette) close();
    });

    on(doc, 'keydown', function (e) {
      var mod = e.metaKey || e.ctrlKey;

      if (mod && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        if (palette.classList.contains('is-open')) close();
        else open();
        return;
      }

      if (!palette.classList.contains('is-open')) return;

      if (e.key === 'Escape') {
        e.preventDefault();
        close();
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        cursor++;
        paintCursor();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        cursor--;
        paintCursor();
      } else if (e.key === 'Enter') {
        e.preventDefault();
        run(shown()[cursor]);
      }
    });
  }

  /* ======================================================================
     08  SCROLL PROGRESS & BACK-TO-TOP
     ====================================================================== */

  function initScrollChrome() {
    var bar = $('[data-scroll-bar]');
    var toTop = $('[data-to-top]');

    var update = rafThrottle(function () {
      var scrollable = doc.documentElement.scrollHeight - global.innerHeight;
      var p = scrollable > 0 ? clamp(global.pageYOffset / scrollable, 0, 1) : 0;

      html.style.setProperty('--scroll-progress', p.toFixed(4));
      if (bar) bar.style.transform = 'scaleX(' + p.toFixed(4) + ')';
      if (toTop) toTop.classList.toggle('is-on', global.pageYOffset > global.innerHeight * 0.8);
    });

    on(global, 'scroll', update, { passive: true });
    on(global, 'resize', update);
    update();

    on(toTop, 'click', function () {
      global.scrollTo({ top: 0, behavior: prefersReduced() ? 'auto' : 'smooth' });
    });
  }

  /* ======================================================================
     09  REVEAL FALLBACK
     ----------------------------------------------------------------------
     Only used when GSAP is absent. IntersectionObserver adds `.is-revealed`
     and the CSS transition in animations.css does the rest.
     ====================================================================== */

  function initRevealFallback() {
    if (global.SkillUpMotion && global.SkillUpMotion.available()) return;

    var targets = $$('[data-reveal]');
    if (!targets.length) return;

    if (!('IntersectionObserver' in global) || prefersReduced()) {
      targets.forEach(function (el) { el.classList.add('is-revealed'); });
      return;
    }

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry, i) {
        if (!entry.isIntersecting) return;
        var el = entry.target;
        global.setTimeout(function () { el.classList.add('is-revealed'); }, i * 70);
        io.unobserve(el);
      });
    }, { threshold: 0.08, rootMargin: '0px 0px -8% 0px' });

    targets.forEach(function (el) { io.observe(el); });
  }

  /* ======================================================================
     10  COUNTERS
     ====================================================================== */

  function initCounters() {
    var nodes = $$('[data-count-to]');
    if (!nodes.length) return;

    function run(el) {
      var raw = el.getAttribute('data-count-to');
      var end = parseFloat(raw);

      // Anything that is not a plain number is left exactly as authored.
      if (!isFinite(end)) {
        el.textContent = raw;
        return;
      }

      if (prefersReduced()) {
        el.textContent = String(end);
        return;
      }

      var decimals = (String(raw).split('.')[1] || '').length;
      var duration = 1400;
      var start = 0;
      var t0 = 0;

      function step(now) {
        if (!t0) t0 = now;
        var p = clamp((now - t0) / duration, 0, 1);
        // easeOutExpo — fast then settling, which reads as "counting up".
        var eased = p === 1 ? 1 : 1 - Math.pow(2, -10 * p);
        var value = start + (end - start) * eased;
        el.textContent = decimals ? value.toFixed(decimals) : String(Math.round(value));
        if (p < 1) global.requestAnimationFrame(step);
      }

      global.requestAnimationFrame(step);
    }

    if (!('IntersectionObserver' in global)) {
      nodes.forEach(run);
      return;
    }

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        run(entry.target);
        io.unobserve(entry.target);
      });
    }, { threshold: 0.4 });

    nodes.forEach(function (el) { io.observe(el); });
  }

  /* ======================================================================
     11  TILT, BLOOM & RIPPLE
     ====================================================================== */

  function initTilt() {
    if (!isFinePointer() || prefersReduced()) return;

    $$('[data-tilt]').forEach(function (el) {
      var MAX = 6;

      on(el, 'pointermove', function (e) {
        if (e.pointerType && e.pointerType !== 'mouse') return;
        var r = el.getBoundingClientRect();
        var px = (e.clientX - r.left) / r.width - 0.5;
        var py = (e.clientY - r.top) / r.height - 0.5;
        el.style.setProperty('--ry', (px * MAX * 2).toFixed(2) + 'deg');
        el.style.setProperty('--rx', (-py * MAX * 2).toFixed(2) + 'deg');
      }, { passive: true });

      on(el, 'pointerleave', function () {
        el.style.setProperty('--rx', '0deg');
        el.style.setProperty('--ry', '0deg');
      });
    });
  }

  function initBloom() {
    if (!isFinePointer()) return;

    // Delegated so cards re-rendered by the demo keep working.
    on(doc, 'pointermove', function (e) {
      var card = e.target && e.target.closest ? e.target.closest('[data-bloom]') : null;
      if (!card) return;
      var r = card.getBoundingClientRect();
      card.style.setProperty('--mx', (e.clientX - r.left) + 'px');
      card.style.setProperty('--my', (e.clientY - r.top) + 'px');
    }, { passive: true });
  }

  function initRipple() {
    if (prefersReduced()) return;

    on(doc, 'pointerdown', function (e) {
      var btn = e.target && e.target.closest ? e.target.closest('[data-ripple]') : null;
      if (!btn) return;

      var r = btn.getBoundingClientRect();
      var size = Math.max(r.width, r.height) * 1.1;

      var ink = doc.createElement('span');
      ink.className = 'btn__ripple';
      ink.style.width = ink.style.height = size + 'px';
      ink.style.left = (e.clientX - r.left - size / 2) + 'px';
      ink.style.top = (e.clientY - r.top - size / 2) + 'px';

      btn.appendChild(ink);
      global.setTimeout(function () {
        if (ink.parentNode) ink.parentNode.removeChild(ink);
      }, 640);
    });
  }

  /* ======================================================================
     12  HERO HUD STREAM
     ====================================================================== */

  function initHeroHud() {
    var hud = $('[data-hud]');
    if (!hud) return;

    var lines = $$('.hero__line-item', hud).filter(function (l) {
      return !l.classList.contains('is-in');
    });

    if (prefersReduced() || !lines.length) {
      lines.forEach(function (l) { l.classList.add('is-in'); });
      return;
    }

    function play() {
      lines.forEach(function (l) { l.classList.remove('is-in'); });
      lines.forEach(function (line, i) {
        global.setTimeout(function () {
          line.classList.add('is-in');
          // The last line is the diagnosis landing — punch the 3D scene.
          if (i === lines.length - 1 && global.SkillUpScene && global.SkillUpScene.pulse) {
            global.SkillUpScene.pulse();
          }
        }, 520 + i * 480);
      });
    }

    if (!('IntersectionObserver' in global)) {
      play();
      return;
    }

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        play();
        io.unobserve(entry.target);
      });
    }, { threshold: 0.25 });

    io.observe(hud);
  }

  /* ======================================================================
     13  HERO ROTATOR
     ====================================================================== */

  function initRotator() {
    var box = $('[data-rotator]');
    if (!box) return;

    var words = $$('.hero__rotator-word', box);
    if (words.length < 2) return;

    // Fix the window width to the longest word so nothing reflows mid-cycle.
    var widest = 0;
    words.forEach(function (w) {
      w.style.position = 'absolute';
      widest = Math.max(widest, w.scrollWidth);
    });
    if (widest) box.style.minWidth = (widest + 4) + 'px';

    if (prefersReduced()) return;

    var index = 0;
    var timer = 0;

    function step() {
      var current = words[index];
      index = (index + 1) % words.length;
      var next = words[index];

      current.classList.remove('is-in');
      current.classList.add('is-out');
      next.classList.remove('is-out');
      next.classList.add('is-in');

      global.setTimeout(function () { current.classList.remove('is-out'); }, 420);
    }

    function start() { if (!timer) timer = global.setInterval(step, 2400); }
    function stop() { global.clearInterval(timer); timer = 0; }

    on(doc, 'visibilitychange', function () {
      if (doc.hidden) stop();
      else start();
    });

    start();
  }

  /* ======================================================================
     14  INLINE CAPABILITY DEMOS
     ====================================================================== */

  function initMiniChat() {
    var chat = $('[data-minichat]');
    if (!chat) return;

    var rows = $$('.minichat__row', chat);

    if (prefersReduced() || !('IntersectionObserver' in global)) {
      rows.forEach(function (r) { r.classList.add('is-in'); });
      return;
    }

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        rows.forEach(function (row, i) {
          global.setTimeout(function () { row.classList.add('is-in'); }, i * 420);
        });
        io.unobserve(entry.target);
      });
    }, { threshold: 0.3 });

    io.observe(chat);
  }

  /**
   * Maya's conviction meter. It holds near the top, dips as a "demonstration"
   * lands, then settles — a compressed version of the real session curve.
   */
  function initBeliefMeter() {
    var meter = $('[data-belief-meter]');
    var label = $('[data-belief-label]');
    if (!meter) return;

    if (prefersReduced() || !('IntersectionObserver' in global)) return;

    var stages = [
      { v: 88, t: 'strong' },
      { v: 82, t: 'questioning' },
      { v: 54, t: 'wavering' },
      { v: 19, t: 'updated' }
    ];

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;

        stages.forEach(function (stage, i) {
          global.setTimeout(function () {
            meter.style.setProperty('--meter-value', stage.v);
            if (label) label.textContent = stage.t;
          }, 700 + i * 1150);
        });

        io.unobserve(entry.target);
      });
    }, { threshold: 0.4 });

    io.observe(meter);
  }

  /* ======================================================================
     15  LIVE DIAGNOSIS DEMO
     ----------------------------------------------------------------------
     The centrepiece.

     Selecting a student replays their attempt stream, runs a staged
     "analysis", assembles the diagnosis card, then highlights the exact
     attempts the diagnosis cites. That last step is the argument the whole
     page is making, so it is deliberately the final beat.

     Data comes from the #demo-data JSON island (Django's json_script). The
     first student is already rendered server-side, so this never has to build
     the panel from nothing — it only re-renders on interaction.
     ====================================================================== */

  function initDemo() {
    var frame = $('[data-demo]');
    if (!frame) return;

    var dataEl = $('#demo-data');
    var students = [];

    try {
      students = dataEl ? JSON.parse(dataEl.textContent) : [];
    } catch (err) {
      // No data island: leave the server-rendered panel exactly as it is.
      if (global.console && global.console.warn) {
        global.console.warn('[SkillUp] demo data unreadable; static panel retained.');
      }
      return;
    }

    if (!students.length) return;

    var byId = Object.create(null);
    students.forEach(function (s) { byId[s.id] = s; });

    /* --- element handles --- */
    var stage = $('#demo-stage', frame);
    var tabs = $$('[data-student]', frame);
    var attemptsBox = $('[data-attempts]', frame);
    var attemptCount = $('[data-attempt-count]', frame);
    var stageName = $('[data-stage-name]', frame);
    var stageSubject = $('[data-stage-subject]', frame);

    var result = $('[data-result]', frame);
    var scrim = $('[data-result-scrim]', frame);
    var status = $('[data-result-status]', frame);
    var labelEl = $('[data-result-label]', frame);
    var confEl = $('[data-result-conf]', frame);
    var meterEl = $('[data-result-meter]', frame);
    var ruleEl = $('[data-result-rule]', frame);
    var noteEl = $('[data-result-note]', frame);
    var spreadEl = $('[data-result-spread]', frame);
    var actionEl = $('[data-result-action]', frame);
    var rerunBtn = $('[data-demo-rerun]');

    var current = students[0].id;
    var seq = null;
    var reduced = prefersReduced();

    var STATUS_STEPS = [
      'Reading attempt history…',
      'Aligning expected against submitted…',
      'Testing candidate procedures…',
      'Scoring rule consistency…',
      'Writing diagnosis…'
    ];

    /* --- rendering helpers --- */

    function svgIcon(href) {
      var svg = doc.createElementNS('http://www.w3.org/2000/svg', 'svg');
      var use = doc.createElementNS('http://www.w3.org/2000/svg', 'use');
      use.setAttribute('href', href);
      svg.appendChild(use);
      return svg;
    }

    function buildAttempt(a) {
      var row = doc.createElement('div');
      row.className = 'attempt';
      row.setAttribute('data-ok', a.ok ? 'true' : 'false');

      var icon = doc.createElement('span');
      icon.className = 'attempt__icon';
      icon.setAttribute('aria-hidden', 'true');
      icon.appendChild(svgIcon(a.ok ? '#i-check' : '#i-close'));

      var q = doc.createElement('span');
      q.className = 'attempt__q';
      q.textContent = a.q;

      var answers = doc.createElement('span');
      answers.className = 'attempt__answers';

      var given = doc.createElement('span');
      given.className = 'attempt__given';
      given.textContent = a.given;
      answers.appendChild(given);

      if (!a.ok) {
        var expected = doc.createElement('span');
        expected.className = 'attempt__expected';
        expected.textContent = a.expected;
        answers.appendChild(expected);
      }

      row.appendChild(icon);
      row.appendChild(q);
      row.appendChild(answers);
      return row;
    }

    function renderChips(container, tags) {
      if (!container) return;
      container.textContent = '';

      if (!tags || !tags.length) {
        var none = doc.createElement('span');
        none.className = 'chip';
        none.textContent = 'nothing — no rule to propagate';
        container.appendChild(none);
        return;
      }

      tags.forEach(function (tag) {
        var chip = doc.createElement('span');
        chip.className = 'chip chip--tag';
        chip.textContent = tag;
        container.appendChild(chip);
      });
    }

    /** Type a string into an element, character by character. */
    function typeInto(el, text, speed, done) {
      if (!el) return;

      if (reduced) {
        el.textContent = text;
        if (done) done();
        return;
      }

      el.textContent = '';
      var i = 0;
      var step = Math.max(1, Math.round(text.length / 90));

      var timer = global.setInterval(function () {
        i = Math.min(text.length, i + step);
        el.textContent = text.slice(0, i);
        if (i >= text.length) {
          global.clearInterval(timer);
          if (done) done();
        }
      }, speed || 16);
    }

    /* --- the run --- */

    function run(id, opts) {
      var student = byId[id];
      if (!student) return;

      var instant = !!(opts && opts.instant) || reduced;

      // A fresh sequence per run, held locally as well as on the module so a
      // rapid second click cancels the first run's pending steps outright
      // rather than interleaving with them.
      if (seq) seq.cancel();
      var mySeq = new Sequence();
      seq = mySeq;
      current = id;

      /* tabs + accent */
      tabs.forEach(function (t) {
        t.setAttribute('aria-selected', t.getAttribute('data-student') === id ? 'true' : 'false');
      });
      if (stage) {
        stage.setAttribute('data-accent', student.accent);
        stage.setAttribute('aria-labelledby', 'tab-' + id);
      }
      if (result) result.classList.toggle('is-low', student.confidence < 40);

      /* breadcrumb */
      if (stageName) stageName.textContent = student.name;
      if (stageSubject) stageSubject.textContent = student.subject;
      if (attemptCount) attemptCount.textContent = student.attempts.length + ' logged';

      /* attempts stream in */
      var rows = [];
      if (attemptsBox) {
        attemptsBox.textContent = '';
        student.attempts.forEach(function (a) {
          var row = buildAttempt(a);
          attemptsBox.appendChild(row);
          rows.push(row);
        });

        rows.forEach(function (row, i) {
          if (instant) {
            row.classList.add('is-in');
          } else {
            mySeq.at(90 + i * 110, function () { row.classList.add('is-in'); });
          }
        });
      }

      var streamEnd = instant ? 0 : 90 + rows.length * 110;

      /* analysis scrim */
      if (scrim && !instant) {
        scrim.classList.add('is-on');
        STATUS_STEPS.forEach(function (text, i) {
          mySeq.at(streamEnd + i * 330, function () {
            if (status) status.textContent = text;
          });
        });
      } else if (scrim) {
        scrim.classList.remove('is-on');
      }

      var analysisEnd = instant ? 0 : streamEnd + STATUS_STEPS.length * 330 + 180;

      /* diagnosis assembles */
      mySeq.at(analysisEnd, function () {
        if (scrim) scrim.classList.remove('is-on');

        typeInto(labelEl, student.label, 14);

        if (confEl) confEl.textContent = '0.' + student.confidence;
        if (meterEl) meterEl.style.setProperty('--meter-value', student.confidence);

        if (ruleEl) typeInto(ruleEl, student.rule, 10);
        if (noteEl) noteEl.textContent = student.note;

        renderChips(spreadEl, student.spread);
        if (actionEl) actionEl.textContent = student.action;

        if (global.SkillUpScene && global.SkillUpScene.pulse) global.SkillUpScene.pulse();
      });

      /* evidence highlight — the beat that ties claim to data */
      mySeq.at(analysisEnd + 620, function () {
        rows.forEach(function (row, i) {
          if (row.getAttribute('data-ok') !== 'false') return;
          if (instant) {
            row.classList.add('is-evidence');
          } else {
            mySeq.at(i * 130, function () { row.classList.add('is-evidence'); });
          }
        });
      });
    }

    /* --- wiring --- */

    tabs.forEach(function (tab) {
      on(tab, 'click', function () {
        var id = tab.getAttribute('data-student');
        if (id) run(id);
      });

      // Roving arrow-key navigation across the roster, as a tablist should.
      on(tab, 'keydown', function (e) {
        if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp' &&
            e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;

        e.preventDefault();
        var i = tabs.indexOf(tab);
        var dir = (e.key === 'ArrowDown' || e.key === 'ArrowRight') ? 1 : -1;
        var next = tabs[(i + dir + tabs.length) % tabs.length];
        if (next) {
          next.focus();
          var id = next.getAttribute('data-student');
          if (id) run(id);
        }
      });
    });

    on(rerunBtn, 'click', function () {
      run(current);
      toast('Re-running the diagnosis', 'info');
    });

    /* Kick off the first animated run when the panel comes into view. The
       server-rendered content is already correct, so this is enrichment, not
       initialisation. */
    if ('IntersectionObserver' in global && !reduced) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          run(current);
          io.unobserve(entry.target);
        });
      }, { threshold: 0.2 });
      io.observe(frame);
    }

    global.SkillUpDemo = {
      run: run,
      rerun: function () { run(current); },
      current: function () { return current; }
    };
  }

  /* ======================================================================
     16  FAQ ACCORDION
     ====================================================================== */

  /**
   * Single-open accordion with an explicit height transition.
   *
   * The CSS cannot do this alone — see the note in sections.css — so the
   * pixel values come from here. An open panel settles back to `height: auto`
   * once its transition ends, so a late font swap or a resize reflowing the
   * answer never leaves it clipped.
   */
  function initFaq() {
    var list = $('[data-faq]');
    if (!list) return;

    var triggers = $$('[data-faq-trigger]', list);
    if (!triggers.length) return;

    function panelFor(trigger) {
      return doc.getElementById(trigger.getAttribute('aria-controls'));
    }

    function contentHeight(panel) {
      var inner = panel.firstElementChild;
      return inner ? inner.getBoundingClientRect().height : 0;
    }

    function setOpen(trigger, open, animate) {
      var panel = panelFor(trigger);
      trigger.setAttribute('aria-expanded', open ? 'true' : 'false');
      if (!panel) return;

      panel.classList.toggle('is-open', open);

      if (!animate) {
        panel.style.height = open ? 'auto' : '0px';
        return;
      }

      // Start from wherever it actually is, so interrupting a transition
      // mid-flight continues smoothly instead of jumping.
      var from = panel.getBoundingClientRect().height;
      var to = open ? contentHeight(panel) : 0;

      panel.style.height = from + 'px';
      void panel.offsetHeight;          // commit the start value
      panel.style.height = to + 'px';
    }

    triggers.forEach(function (trigger) {
      var panel = panelFor(trigger);
      if (!panel) return;

      on(panel, 'transitionend', function (e) {
        if (e.propertyName !== 'height') return;
        if (panel.classList.contains('is-open')) panel.style.height = 'auto';
      });
    });

    // Adopt whatever state the server rendered, without animating on load.
    triggers.forEach(function (trigger) {
      setOpen(trigger, trigger.getAttribute('aria-expanded') === 'true', false);
    });

    triggers.forEach(function (trigger) {
      on(trigger, 'click', function () {
        var isOpen = trigger.getAttribute('aria-expanded') === 'true';

        triggers.forEach(function (other) {
          if (other !== trigger) setOpen(other, false, true);
        });

        setOpen(trigger, !isOpen, true);

        if (!isOpen && global.SkillUpMotion && global.SkillUpMotion.refresh) {
          // The page just got taller; triggers below need recalculating.
          global.setTimeout(global.SkillUpMotion.refresh, 480);
        }
      });
    });

    on(global, 'resize', debounce(function () {
      triggers.forEach(function (trigger) {
        var panel = panelFor(trigger);
        if (panel && panel.classList.contains('is-open')) panel.style.height = 'auto';
      });
    }, 180));
  }

  /* ======================================================================
     17  PRICING BILLING SWITCH
     ====================================================================== */

  function initPricing() {
    var group = $('[data-billing]');
    if (!group) return;

    var thumb = $('[data-billing-thumb]', group);
    var opts = $$('[data-billing-opt]', group);
    var prices = $$('[data-price]');

    function moveThumb(active) {
      if (!thumb || !active) return;
      var gr = group.getBoundingClientRect();
      var ar = active.getBoundingClientRect();
      thumb.style.width = ar.width + 'px';
      thumb.style.transform = 'translateX(' + (ar.left - gr.left - 4) + 'px)';
    }

    function select(period) {
      opts.forEach(function (o) {
        var active = o.getAttribute('data-billing-opt') === period;
        o.classList.toggle('is-active', active);
        o.setAttribute('aria-selected', active ? 'true' : 'false');
        if (active) moveThumb(o);
      });

      prices.forEach(function (el) {
        var value = el.getAttribute('data-' + period);
        if (value === null) return;

        // Swap on the invisible half of a short fade so the digits never
        // appear to glitch mid-change.
        el.classList.add('is-swapping');
        global.setTimeout(function () {
          el.textContent = '$' + value;
          el.classList.remove('is-swapping');
        }, 150);
      });
    }

    opts.forEach(function (o) {
      on(o, 'click', function () { select(o.getAttribute('data-billing-opt')); });
    });

    // Position the thumb once fonts have settled, and again on resize.
    var initial = opts.filter(function (o) { return o.classList.contains('is-active'); })[0] || opts[0];
    global.setTimeout(function () { moveThumb(initial); }, 60);

    if (doc.fonts && doc.fonts.ready) {
      doc.fonts.ready.then(function () { moveThumb(
        opts.filter(function (o) { return o.classList.contains('is-active'); })[0] || opts[0]
      ); }).catch(function () { /* not fatal */ });
    }

    on(global, 'resize', debounce(function () {
      moveThumb(opts.filter(function (o) { return o.classList.contains('is-active'); })[0] || opts[0]);
    }, 140));
  }

  /* ======================================================================
     18  CTA FORM
     ----------------------------------------------------------------------
     There is no endpoint behind this yet, so the confirmation says what
     actually happened and nothing more.
     ====================================================================== */

  function initCtaForm() {
    var form = $('[data-cta-form]');
    if (!form) return;

    var input = $('[data-cta-email]', form);
    var error = $('[data-cta-error]');
    var button = $('button[type="submit"]', form);

    function showError(message) {
      if (input) input.setAttribute('aria-invalid', 'true');
      if (error) error.textContent = message;
    }

    function clearError() {
      if (input) input.removeAttribute('aria-invalid');
      if (error) error.textContent = '';
    }

    on(input, 'input', clearError);

    on(form, 'submit', function (e) {
      e.preventDefault();

      var value = input ? input.value.trim() : '';

      if (!value) {
        showError('Enter an email address so we know where to send the invite.');
        if (input) input.focus();
        return;
      }

      // Deliberately permissive: real addresses are stranger than any regex,
      // and a false rejection costs more than a bad row in a waitlist.
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(value)) {
        showError('That does not look like an email address.');
        if (input) input.focus();
        return;
      }

      clearError();

      if (button) {
        button.setAttribute('aria-disabled', 'true');
        var labelEl = $('.btn__label', button);
        var original = labelEl ? labelEl.textContent : '';
        if (labelEl) labelEl.textContent = 'Adding you…';

        global.setTimeout(function () {
          if (labelEl) labelEl.textContent = 'You’re on the list';
          toast('Saved locally — the waitlist endpoint is not wired up yet.', 'info');
          form.reset();

          global.setTimeout(function () {
            if (labelEl) labelEl.textContent = original;
            button.removeAttribute('aria-disabled');
          }, 2600);
        }, 900);
      }
    });
  }

  /* ======================================================================
     19  KEYBOARD EXTRAS
     ====================================================================== */

  function initKeyboard() {
    // A visible focus ring for keyboard users, suppressed for mouse users —
    // :focus-visible does most of this, but the class lets CSS go further.
    on(doc, 'keydown', function (e) {
      if (e.key === 'Tab') html.classList.add('using-keyboard');
    });

    on(doc, 'pointerdown', function () {
      html.classList.remove('using-keyboard');
    });

    // Shortcuts. Ignored while typing, so they never eat real input.
    on(doc, 'keydown', function (e) {
      var el = doc.activeElement;
      var typing = el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable);
      if (typing || e.metaKey || e.ctrlKey || e.altKey) return;

      if (e.key === 't' || e.key === 'T') {
        Theme.toggle();
      } else if (e.key === 'g' || e.key === 'G') {
        scrollToTarget('#diagnosis');
      }
    });

    /* A small reward for anyone who tries the obvious thing. */
    var KONAMI = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown',
                  'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 'b', 'a'];
    var progress = 0;

    on(doc, 'keydown', function (e) {
      var expected = KONAMI[progress];
      var key = e.key.length === 1 ? e.key.toLowerCase() : e.key;

      if (key === expected) {
        progress++;
        if (progress === KONAMI.length) {
          progress = 0;
          html.classList.toggle('konami');
          if (global.SkillUpScene && global.SkillUpScene.pulse) global.SkillUpScene.pulse();
          toast('Brown & Burton, 1978. Go and read it.', 'info');
        }
      } else {
        progress = key === KONAMI[0] ? 1 : 0;
      }
    });
  }

  /* ======================================================================
     20  BOOT
     ====================================================================== */

  function boot() {
    // Libraries first — later modules ask them what they can do.
    safe('scene', function () {
      if (global.SkillUpScene) global.SkillUpScene.init();
    });

    safe('motion', function () {
      if (global.SkillUpMotion) global.SkillUpMotion.init();
      else html.classList.add('no-gsap');
    });

    safe('preloader', initPreloader);
    safe('theme', initTheme);
    safe('cursor', initCursor);
    safe('magnetic', initMagnetic);
    safe('nav', initNav);
    safe('drawer', initDrawer);
    safe('palette', initPalette);
    safe('scroll-chrome', initScrollChrome);
    safe('reveal-fallback', initRevealFallback);
    safe('counters', initCounters);
    safe('tilt', initTilt);
    safe('bloom', initBloom);
    safe('ripple', initRipple);
    safe('hero-hud', initHeroHud);
    safe('rotator', initRotator);
    safe('minichat', initMiniChat);
    safe('belief', initBeliefMeter);
    safe('demo', initDemo);
    safe('faq', initFaq);
    safe('pricing', initPricing);
    safe('cta-form', initCtaForm);
    safe('keyboard', initKeyboard);
    safe('backstop', revealBackstop);

    // Stop the WebGL loop once the hero is well off-screen; restart on return.
    safe('scene-visibility', function () {
      var hero = $('.hero');
      if (!hero || !('IntersectionObserver' in global) || !global.SkillUpScene) return;

      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) global.SkillUpScene.resume();
          else global.SkillUpScene.pause();
        });
      }, { threshold: 0 });

      io.observe(hero);
    });
  }

  if (doc.readyState === 'loading') {
    on(doc, 'DOMContentLoaded', boot);
  } else {
    boot();
  }

})(window);
