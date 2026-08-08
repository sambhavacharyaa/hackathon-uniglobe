/* ==========================================================================
   SKILL UP — MOTION LAYER (GSAP + ScrollTrigger)
   --------------------------------------------------------------------------
   All scroll-driven and entrance animation lives here. The rules it follows:

     · GSAP is optional. If the CDN is blocked, `html.no-gsap` is set and the
       CSS in animations.css takes over — every [data-reveal] element still
       resolves to visible. Nothing on this page depends on this file running.
     · Only transform / opacity / filter are animated.
     · Every ScrollTrigger is created top-to-bottom in page order, so the
       refresh pass runs in the same order as the layout (pin spacing depends
       on it).
     · ScrollTrigger lives on the timeline, never on a child tween.
     · `scrub` and `toggleActions` are never combined on one trigger.
     · gsap.matchMedia() handles both the responsive breakpoints and
       prefers-reduced-motion, so the reduced branch is a real branch rather
       than a set of disabled tweens.

   Public surface:
       SkillUpMotion.init()     -> boolean, true if GSAP took over
       SkillUpMotion.refresh()  -> recalculate trigger positions
       SkillUpMotion.available()
   ========================================================================== */

(function (global) {
  'use strict';

  var gsap = null;
  var ScrollTrigger = null;
  var mm = null;
  var ready = false;
  var initialised = false;

  /* ----------------------------------------------------------------------
     Utilities
     ---------------------------------------------------------------------- */

  function $(sel, root) {
    return (root || document).querySelector(sel);
  }

  function $$(sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  }

  /* ----------------------------------------------------------------------
     Reveal ownership
     ----------------------------------------------------------------------
     Two rules that exist because breaking either produces a silently blank
     page, which is the worst possible failure mode for a landing page.

     1. NEVER use `gsap.from()` on a [data-reveal] element. The CSS in
        animations.css holds these at `opacity: 0` before JS runs, and
        `from()` animates *towards the current computed value* — which is
        zero. The element would dutifully animate from invisible to
        invisible. Always state the end explicitly with `fromTo()` or `to()`.

     2. Exactly one animation may own an element. Several sections below have
        bespoke choreography for elements that also carry [data-reveal];
        those claim their targets first, and the generic batch skips anything
        already claimed. Two competing tweens on one opacity is a coin flip.
     ---------------------------------------------------------------------- */

  var HIDDEN = { opacity: 0, y: 28 };
  var SHOWN = { opacity: 1, y: 0 };

  function claim(els) {
    els.forEach(function (el) { el.setAttribute('data-claimed', ''); });
    return els;
  }

  function unclaimed(sel) {
    return $$(sel).filter(function (el) { return !el.hasAttribute('data-claimed'); });
  }

  /** Mark an element as finished so the CSS and the backstop both agree. */
  function settle(els) {
    els.forEach(function (el) {
      el.classList.add('is-revealed');
      el.style.transform = '';
    });
  }

  /**
   * Split an element's text into per-character spans.
   *
   * A hand-rolled stand-in for the SplitText plugin (which is a paid GSAP
   * add-on). Words are kept intact in their own wrapper so a line break never
   * lands mid-word, and the original text is preserved on the element for
   * screen readers via aria-label.
   */
  function splitChars(el) {
    if (!el || el.dataset.splitDone === '1') return [];

    /* Refuse to split gradient text.
       `background-clip: text` paints the element's own background through its
       own inline text boxes. Wrapping each character in an inline-block spans
       the parent's text away into descendants, and the gradient ends up
       clipped to nothing — the line renders as an unreadable smear. Better to
       skip the character pass than to silently destroy the headline. */
    var fill = global.getComputedStyle(el).webkitTextFillColor;
    if (fill === 'rgba(0, 0, 0, 0)' || fill === 'transparent') {
      if (global.console && global.console.info) {
        global.console.info('[SkillUp] skipping character split on gradient text');
      }
      return [];
    }

    var text = el.textContent;
    el.setAttribute('aria-label', text);
    el.textContent = '';

    var words = text.split(/(\s+)/);
    var chars = [];

    words.forEach(function (word) {
      if (/^\s+$/.test(word)) {
        el.appendChild(document.createTextNode(word));
        return;
      }
      var wrap = document.createElement('span');
      wrap.style.display = 'inline-block';
      wrap.style.whiteSpace = 'nowrap';
      wrap.setAttribute('aria-hidden', 'true');

      for (var i = 0; i < word.length; i++) {
        var span = document.createElement('span');
        span.className = 'hero__char';
        span.textContent = word[i];
        wrap.appendChild(span);
        chars.push(span);
      }
      el.appendChild(wrap);
    });

    el.dataset.splitDone = '1';
    return chars;
  }

  /* ----------------------------------------------------------------------
     1. Hero
     ---------------------------------------------------------------------- */

  function heroIntro() {
    var hero = $('.hero');
    if (!hero) return;

    var lines = $$('.hero__line-inner', hero);
    var accent = $('[data-split]', hero);
    var chars = accent ? splitChars(accent) : [];
    var reveals = claim($$('[data-reveal]', hero));

    var tl = gsap.timeline({
      defaults: { ease: 'expo.out' },
      delay: 0.12
    });

    /* Lines rise out of their clipping windows.
       `y: 0` is not redundant. animations.css parks these at
       `translateY(105%)` so the effect also works without GSAP, and GSAP
       composes its own `yPercent` on top of the `y` it reads from that
       existing transform — leaving the line 105% displaced at the end of the
       tween. Zeroing `y` explicitly in both states makes GSAP the sole owner
       of the transform. */
    tl.fromTo(lines,
      { yPercent: 105, y: 0 },
      { yPercent: 0, y: 0, duration: 1.15, stagger: 0.085 }
    );

    // Then the accent line's characters get a second, finer pass over the top.
    if (chars.length) {
      tl.fromTo(chars,
        { yPercent: 46, opacity: 0, rotateX: -55 },
        { yPercent: 0, opacity: 1, rotateX: 0, duration: 0.8, stagger: { each: 0.016, from: 'start' } },
        '-=0.75'
      );
    }

    tl.fromTo(reveals,
      HIDDEN,
      {
        opacity: 1,
        y: 0,
        duration: 0.85,
        stagger: 0.075,
        onComplete: function () { settle(reveals); }
      },
      '-=0.65'
    );
  }

  /**
   * Parallax on the hero HUD, and the scroll signal the WebGL scene listens
   * to. Uses a standalone ScrollTrigger with onUpdate rather than a tween,
   * because the consumer is a render loop, not the DOM.
   */
  function heroScroll() {
    var hero = $('.hero');
    if (!hero) return;

    var hud = $('.hero__hud', hero);
    var copy = $('.hero__copy', hero);

    ScrollTrigger.create({
      trigger: hero,
      start: 'top top',
      end: 'bottom top',
      onUpdate: function (self) {
        if (global.SkillUpScene && global.SkillUpScene.setScroll) {
          global.SkillUpScene.setScroll(self.progress);
        }
      }
    });

    if (hud) {
      gsap.to(hud, {
        yPercent: -12,
        ease: 'none',
        scrollTrigger: {
          trigger: hero,
          start: 'top top',
          end: 'bottom top',
          scrub: 0.6
        }
      });
    }

    if (copy) {
      gsap.to(copy, {
        yPercent: 8,
        opacity: 0.15,
        ease: 'none',
        scrollTrigger: {
          trigger: hero,
          start: 'center center',
          end: 'bottom top',
          scrub: 0.6
        }
      });
    }
  }

  /* ----------------------------------------------------------------------
     2. Generic reveals
     ---------------------------------------------------------------------- */

  /**
   * One ScrollTrigger per [data-reveal], batched so everything entering the
   * viewport in the same frame animates together with a stagger — which is
   * both cheaper and better-looking than each element firing independently.
   */
  function reveals() {
    var targets = unclaimed('[data-reveal]');
    if (!targets.length) return;

    gsap.set(targets, HIDDEN);

    ScrollTrigger.batch(targets, {
      start: 'top 92%',
      once: true,
      interval: 0.09,
      batchMax: 6,
      onEnter: function (batch) {
        gsap.to(batch, {
          y: SHOWN.y,
          opacity: SHOWN.opacity,
          duration: 0.85,
          ease: 'expo.out',
          stagger: 0.08,
          overwrite: true,
          onComplete: function () { settle(this.targets()); }
        });
      }
    });

    /* Anything already inside the viewport when the batch is created will
       never fire an onEnter, because it never *enters*. Resolve those now. */
    var vh = global.innerHeight;
    var immediate = targets.filter(function (el) {
      var r = el.getBoundingClientRect();
      return r.top < vh * 0.92 && r.bottom > 0;
    });

    if (immediate.length) {
      gsap.to(immediate, {
        y: SHOWN.y,
        opacity: SHOWN.opacity,
        duration: 0.85,
        ease: 'expo.out',
        stagger: 0.08,
        overwrite: true,
        onComplete: function () { settle(this.targets()); }
      });
    }
  }

  /* ----------------------------------------------------------------------
     3. Section headings — a rule that draws itself in
     ---------------------------------------------------------------------- */

  function headingRules() {
    $$('.eyebrow').forEach(function (el) {
      gsap.from(el, {
        opacity: 0,
        x: -14,
        duration: 0.6,
        ease: 'power3.out',
        scrollTrigger: {
          trigger: el,
          start: 'top 90%',
          toggleActions: 'play none none none'
        }
      });
    });
  }

  /* ----------------------------------------------------------------------
     4. Problem — the two panels converge
     ---------------------------------------------------------------------- */

  function problemSection() {
    var section = $('#problem');
    if (!section) return;

    var book = $('.gradebook', section);
    var verdict = $('.verdict', section);
    var arrow = $('.problem__arrow', section);
    var cells = $$('.gradebook__cell', section);
    if (!book || !verdict) return;

    claim([book, verdict].concat(arrow ? [arrow] : []));

    /* The convergence only makes sense while the panels are side by side.
       Below 900px they stack, and a rightward offset on a full-width panel
       pushes past the viewport edge — which grows the document's scroll width
       mid-animation. Function-based values plus invalidateOnRefresh let the
       same timeline resolve to a vertical entrance on narrow screens. */
    var sideBySide = function () { return global.innerWidth > 900; };
    var offset = function () { return sideBySide() ? 34 : 0; };
    var rise = function () { return sideBySide() ? 0 : 24; };

    var tl = gsap.timeline({
      scrollTrigger: {
        trigger: section,
        start: 'top 70%',
        toggleActions: 'play none none none',
        invalidateOnRefresh: true
      }
    });

    // The two panels converge on the arrow between them.
    tl.fromTo(book,
      { x: function () { return -offset(); }, y: rise, opacity: 0 },
      { x: 0, y: 0, opacity: 1, duration: 0.8, ease: 'expo.out' })
      .fromTo(cells,
        { scale: 0.7, opacity: 0 },
        { scale: 1, opacity: 1, duration: 0.45, stagger: 0.028, ease: 'back.out(2)' }, '-=0.45');

    if (arrow) {
      tl.fromTo(arrow,
        { opacity: 0, scale: 0.8 },
        { opacity: 1, scale: 1, duration: 0.5, ease: 'back.out(2)' }, '-=0.3');
    }

    tl.fromTo(verdict,
      { x: offset, y: rise, opacity: 0 },
      { x: 0, y: 0, opacity: 1, duration: 0.85, ease: 'expo.out', onComplete: function () { settle([book, verdict]); } }, '-=0.4')
      .fromTo($$('.chip', verdict),
        { y: 10, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.4, stagger: 0.035, ease: 'power2.out' }, '-=0.4');
  }

  /* ----------------------------------------------------------------------
     5. Pipeline — pinned horizontal scroll
     ---------------------------------------------------------------------- */

  /**
   * The section pins and the inner track slides left as the page scrolls.
   *
   * The horizontal tween uses ease "none" — mandatory for containerAnimation,
   * because any other ease breaks the 1:1 mapping between scroll distance and
   * horizontal position, and the whole thing starts to feel like it is
   * fighting the wheel.
   */
  function pipelineSection() {
    var section = $('[data-pipeline]');
    var track = $('[data-pipeline-track]');
    var viewport = $('[data-pipeline-viewport]');
    if (!section || !track || !viewport) return null;

    var fill = $('[data-pipeline-fill]');
    var dots = $$('[data-pipeline-dots] span');

    function distance() {
      // Scroll exactly as far as the track overflows its viewport.
      return Math.max(0, track.scrollWidth - viewport.clientWidth);
    }

    if (distance() <= 8) return null; // everything already fits — nothing to do

    var tween = gsap.to(track, {
      x: function () { return -distance(); },
      ease: 'none',
      scrollTrigger: {
        trigger: section,
        start: 'top top',
        end: function () { return '+=' + (distance() + global.innerHeight * 0.4); },
        pin: true,
        scrub: 0.7,
        invalidateOnRefresh: true,
        anticipatePin: 1,
        // The pin inserts a spacer, which shifts everything below it. Refresh
        // it before the reveal batch so those triggers measure the real
        // post-pin layout rather than the pre-pin one.
        refreshPriority: -1,
        onUpdate: function (self) {
          if (fill) fill.style.setProperty('--pipeline-progress', self.progress.toFixed(4));
          if (dots.length) {
            var active = Math.min(dots.length - 1, Math.floor(self.progress * dots.length + 0.15));
            dots.forEach(function (d, i) { d.classList.toggle('is-on', i === active); });
          }
        }
      }
    });

    return tween;
  }

  /* ----------------------------------------------------------------------
     6. Engine — model bars grow, cards cascade
     ---------------------------------------------------------------------- */

  function engineSection() {
    var section = $('#engine');
    if (!section) return;

    claim($$('.model', section)).forEach(function (card, i) {
      var bar = $('.model__share', card);

      var tl = gsap.timeline({
        scrollTrigger: { trigger: card, start: 'top 88%', toggleActions: 'play none none none' }
      });

      tl.fromTo(card, HIDDEN, {
        opacity: 1,
        y: 0,
        duration: 0.7,
        ease: 'expo.out',
        delay: i * 0.05,
        onComplete: function () { settle([card]); }
      });

      // The share bar grows from nothing to its authored --share width.
      if (bar) {
        tl.fromTo(bar,
          { scaleX: 0 },
          { scaleX: (parseFloat(bar.style.getPropertyValue('--share')) || 0) / 100, duration: 1.1, ease: 'expo.out' },
          '-=0.35');
      }
    });
  }

  /* ----------------------------------------------------------------------
     7. Bento cards — a light 3D settle
     ---------------------------------------------------------------------- */

  function bentoSection() {
    var grid = $('.bento');
    if (!grid) return;

    var cells = claim($$('.bento__cell', grid));
    if (!cells.length) return;

    gsap.fromTo(cells,
      { y: 40, opacity: 0, rotateX: -8 },
      {
        y: 0,
        opacity: 1,
        rotateX: 0,
        transformOrigin: 'center top',
        duration: 0.9,
        ease: 'expo.out',
        stagger: 0.09,
        onComplete: function () { settle(cells); },
        scrollTrigger: {
          trigger: grid,
          start: 'top 85%',
          toggleActions: 'play none none none'
        }
      });
  }

  /* ----------------------------------------------------------------------
     8. Numbers, plans, voices
     ---------------------------------------------------------------------- */

  function stripsAndCards() {
    /* .number cells are plain children (the strip itself carries the
       [data-reveal]), so they are safe to `from()`. .plan and .voice are
       reveal elements and must be claimed and given an explicit end state. */

    var numbers = $('.numbers');
    if (numbers) {
      gsap.fromTo($$('.number', numbers),
        { y: 24, opacity: 0 },
        {
          y: 0,
          opacity: 1,
          duration: 0.75,
          ease: 'expo.out',
          stagger: 0.08,
          scrollTrigger: { trigger: numbers, start: 'top 88%', toggleActions: 'play none none none' }
        });
    }

    var plans = claim($$('.plan'));
    if (plans.length) {
      gsap.fromTo(plans,
        { y: 40, opacity: 0 },
        {
          y: 0,
          opacity: 1,
          duration: 0.85,
          ease: 'expo.out',
          stagger: 0.1,
          onComplete: function () { settle(plans); },
          scrollTrigger: { trigger: '.plans', start: 'top 86%', toggleActions: 'play none none none' }
        });
    }

    var voices = claim($$('.voice'));
    if (voices.length) {
      gsap.fromTo(voices,
        { y: 34, opacity: 0, scale: 0.98 },
        {
          y: 0,
          opacity: 1,
          scale: 1,
          duration: 0.8,
          ease: 'expo.out',
          stagger: 0.09,
          onComplete: function () { settle(voices); },
          scrollTrigger: { trigger: '.voices', start: 'top 86%', toggleActions: 'play none none none' }
        });
    }
  }

  /* ----------------------------------------------------------------------
     9. Footer wordmark — a slow scrub as the page bottoms out
     ---------------------------------------------------------------------- */

  function footerMark() {
    var mark = $('.footer__wordmark');
    if (!mark) return;

    gsap.fromTo(mark,
      { yPercent: 22, opacity: 0.15 },
      {
        yPercent: 0,
        opacity: 0.55,
        ease: 'none',
        scrollTrigger: {
          trigger: '.footer',
          start: 'top 85%',
          end: 'bottom bottom',
          scrub: 0.8
        }
      }
    );
  }

  /* ----------------------------------------------------------------------
     Reduced-motion branch
     ---------------------------------------------------------------------- */

  /**
   * With reduced motion requested, nothing travels and nothing pins. Elements
   * are simply made visible and the pipeline becomes an ordinary horizontal
   * scroller — which is still a usable, and arguably better, way to read four
   * panels.
   */
  function reducedSetup() {
    var targets = $$('[data-reveal]');
    gsap.set(targets, { clearProps: 'all' });
    targets.forEach(function (el) { el.classList.add('is-revealed'); });

    var lines = $$('.hero__line-inner');
    gsap.set(lines, { y: '0%', clearProps: 'transform' });

    var viewport = $('[data-pipeline-viewport]');
    if (viewport) {
      viewport.style.overflowX = 'auto';
      viewport.style.scrollSnapType = 'x proximity';
      $$('[data-pipeline-panel]').forEach(function (p) { p.style.scrollSnapAlign = 'start'; });
    }
  }

  /* ----------------------------------------------------------------------
     Boot
     ---------------------------------------------------------------------- */

  /**
   * Mark every element that a bespoke section timeline owns, before any
   * ScrollTrigger exists.
   *
   * This is a separate pass purely so the build below can still run in page
   * order — ScrollTrigger refreshes in creation order, and creating triggers
   * out of order upsets pin spacing. Without the pre-pass, `reveals()` would
   * have to run last to see all the claims, which would put its triggers
   * after the pinned pipeline.
   */
  function claimPass() {
    var hero = $('.hero');
    if (hero) claim($$('[data-reveal]', hero));

    var problem = $('#problem');
    if (problem) {
      claim($$('.gradebook, .verdict, .problem__arrow', problem));
    }

    claim($$('.bento__cell'));
    claim($$('.model'));
    claim($$('.plan'));
    claim($$('.voice'));
  }

  function buildAll() {
    claimPass();

    // Page order from here down.
    heroIntro();
    heroScroll();
    headingRules();
    reveals();
    problemSection();
    bentoSection();
    pipelineSection();
    engineSection();
    stripsAndCards();
    footerMark();
  }

  var api = {
    init: function () {
      if (initialised) return ready;
      initialised = true;

      gsap = global.gsap || null;
      ScrollTrigger = global.ScrollTrigger || null;

      if (!gsap || !ScrollTrigger) {
        document.documentElement.classList.add('no-gsap');
        return false;
      }

      try {
        gsap.registerPlugin(ScrollTrigger);

        gsap.defaults({ ease: 'power3.out', duration: 0.7 });
        gsap.config({ nullTargetWarn: false });

        // ScrollTrigger's own reduced-motion story is matchMedia, so use it
        // rather than hand-rolling a branch.
        mm = gsap.matchMedia();

        mm.add('(prefers-reduced-motion: reduce)', function () {
          reducedSetup();
        });

        mm.add('(prefers-reduced-motion: no-preference)', function () {
          buildAll();
        });

        // Fonts change metrics, which changes where every trigger should sit.
        if (document.fonts && document.fonts.ready) {
          document.fonts.ready.then(function () {
            ScrollTrigger.refresh();
          }).catch(function () { /* not fatal */ });
        }

        global.addEventListener('load', function () {
          ScrollTrigger.refresh();
        });

        ready = true;
        return true;
      } catch (err) {
        // A GSAP failure must not take the page with it.
        document.documentElement.classList.add('no-gsap');
        $$('[data-reveal]').forEach(function (el) { el.classList.add('is-revealed'); });
        if (global.console && global.console.warn) {
          global.console.warn('[SkillUp] motion layer disabled:', err && err.message ? err.message : err);
        }
        return false;
      }
    },

    refresh: function () {
      if (ready && ScrollTrigger) {
        try { ScrollTrigger.refresh(); } catch (e) { /* nothing to do */ }
      }
    },

    available: function () {
      return ready;
    },

    splitChars: splitChars
  };

  global.SkillUpMotion = api;

})(window);
