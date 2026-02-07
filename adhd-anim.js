/**
 * ADHD-Anim Library v1.0
 * ========================
 * Reusable animation controller for ADHD-friendly micro-interactions.
 *
 * Auto-initializes on DOMContentLoaded.
 * Uses IntersectionObserver for scroll-triggered animations.
 * Supports staggered delays, custom durations, SVG line drawing,
 * and manual triggering.
 *
 * HTML API:
 *   class="anim"                   — marks element for animation
 *   data-anim="pop|fade|slide-left|slide-right|slide-up|bounce|draw|glow|typewriter"
 *   data-delay="200"               — delay in ms before this element animates
 *   data-duration="600"            — animation duration in ms
 *   data-stagger-group="groupName" — auto-stagger elements in the same group
 *   data-stagger-step="120"        — ms between each element in a stagger group
 *
 * SVG lines:
 *   class="anim-line"              — marks SVG path/line for draw animation
 *   data-delay="500"               — delay before line draws
 *   data-duration="800"            — draw duration
 *
 * JS API:
 *   AdhdAnim.init()                — re-scan and initialize (call after dynamic content)
 *   AdhdAnim.trigger(el)           — manually trigger animation on an element
 *   AdhdAnim.triggerAll()          — trigger all animations immediately (no scroll needed)
 *   AdhdAnim.reset()               — reset all elements to pre-animation state
 *   AdhdAnim.staggerGroup(name)    — trigger a specific stagger group
 */

(function () {
  'use strict';

  const AdhdAnim = {
    _observer: null,
    _elements: [],
    _lines: [],
    _staggerGroups: {},

    init: function () {
      // Collect all anim elements
      this._elements = Array.from(document.querySelectorAll('.anim:not(.anim--initialized)'));
      this._lines = Array.from(document.querySelectorAll('.anim-line:not(.anim--initialized)'));

      // Build stagger groups
      this._staggerGroups = {};
      this._elements.forEach(function (el) {
        const group = el.dataset.staggerGroup;
        if (group) {
          if (!AdhdAnim._staggerGroups[group]) AdhdAnim._staggerGroups[group] = [];
          AdhdAnim._staggerGroups[group].push(el);
        }
      });

      // Apply stagger delays
      Object.keys(this._staggerGroups).forEach(function (groupName) {
        const group = AdhdAnim._staggerGroups[groupName];
        const step = parseInt(group[0].dataset.staggerStep) || 120;
        const baseDelay = parseInt(group[0].dataset.delay) || 0;
        group.forEach(function (el, i) {
          el.dataset.delay = String(baseDelay + i * step);
        });
      });

      // Set custom durations as CSS variables
      this._elements.forEach(function (el) {
        if (el.dataset.duration) {
          el.style.setProperty('--anim-duration', el.dataset.duration + 'ms');
        }
        el.classList.add('anim--initialized');
      });

      // Calculate SVG line lengths
      this._lines.forEach(function (line) {
        let length;
        if (line.getTotalLength) {
          length = line.getTotalLength();
        } else {
          // Fallback for line elements
          const x1 = parseFloat(line.getAttribute('x1') || 0);
          const y1 = parseFloat(line.getAttribute('y1') || 0);
          const x2 = parseFloat(line.getAttribute('x2') || 0);
          const y2 = parseFloat(line.getAttribute('y2') || 0);
          length = Math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2);
        }
        line.style.setProperty('--line-length', String(Math.ceil(length)));
        line.style.strokeDasharray = String(Math.ceil(length));
        if (line.dataset.duration) {
          line.style.setProperty('--anim-duration', line.dataset.duration + 'ms');
        }
        line.classList.add('anim--initialized');
      });

      // Setup IntersectionObserver
      if (this._observer) this._observer.disconnect();

      this._observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            AdhdAnim.trigger(entry.target);
            AdhdAnim._observer.unobserve(entry.target);
          }
        });
      }, {
        threshold: 0.15,
        rootMargin: '0px 0px -30px 0px'
      });

      this._elements.forEach(function (el) {
        AdhdAnim._observer.observe(el);
      });

      this._lines.forEach(function (line) {
        AdhdAnim._observer.observe(line);
      });
    },

    trigger: function (el) {
      const delay = parseInt(el.dataset.delay) || 0;
      setTimeout(function () {
        el.classList.add('anim--active');
      }, delay);
    },

    triggerAll: function () {
      this._elements.forEach(function (el) {
        AdhdAnim.trigger(el);
      });
      this._lines.forEach(function (line) {
        AdhdAnim.trigger(line);
      });
    },

    staggerGroup: function (name) {
      const group = this._staggerGroups[name];
      if (group) {
        group.forEach(function (el) {
          AdhdAnim.trigger(el);
        });
      }
    },

    reset: function () {
      this._elements.forEach(function (el) {
        el.classList.remove('anim--active', 'anim--initialized');
      });
      this._lines.forEach(function (line) {
        line.classList.remove('anim--active', 'anim--initialized');
      });
      this.init();
    }
  };

  // Auto-initialize
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      AdhdAnim.init();
    });
  } else {
    AdhdAnim.init();
  }

  // Expose globally
  window.AdhdAnim = AdhdAnim;

})();
