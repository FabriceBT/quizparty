/* Utilitaires partagés : DOM, thème, sons (synthétisés, aucun fichier), confettis, médias, API. */
const $ = (sel, root = document) => root.querySelector(sel);

/** Crée un élément DOM. Les textes passent par createTextNode : aucun HTML injecté. */
function h(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') e.className = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? '' : v);
  }
  for (const c of kids.flat(Infinity)) if (c != null && c !== false) e.append(c);
  return e;
}
const clear = (node) => { node.replaceChildren(); return node; };
/** Vide `node` puis y place `kids` en ignorant null/false (Element.append écrirait « null »). */
function fill(node, ...kids) {
  node.replaceChildren();
  for (const c of kids.flat(Infinity)) if (c != null && c !== false) node.append(c);
  return node;
}

async function api(url, opts = {}) {
  const res = await fetch(url, {
    headers: opts.body ? { 'Content-Type': 'application/json' } : {},
    ...opts, body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  let data = null;
  try { data = await res.json(); } catch (_) { /* pas de JSON */ }
  if (!res.ok) {
    let msg = (data && data.detail) || 'Une erreur est survenue.';
    if (Array.isArray(msg)) msg = msg.map((m) => {
      const n = (m.loc || []).find((x, i, a) => a[i - 1] === 'questions' && Number.isInteger(x));
      return (n != null ? `Question ${n + 1} : ` : '') + (m.msg || '').replace(/^Value error, /, '');
    }).join(' ');
    const err = new Error(msg); err.status = res.status; throw err;
  }
  return data;
}

function toast(msg) {
  const t = h('div', { class: 'toast' }, msg);
  document.body.append(t);
  setTimeout(() => t.remove(), 2800);
}

/* ---------- Thème clair / sombre ---------- */
const Theme = {
  init() {
    const saved = localStorage.getItem('qp_theme');
    const dark = saved ? saved === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
    document.documentElement.dataset.theme = dark ? 'dark' : 'light';
    this.refresh();
  },
  toggle() {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next; localStorage.setItem('qp_theme', next); this.refresh();
  },
  refresh() { const b = $('#theme-btn'); if (b) b.textContent = document.documentElement.dataset.theme === 'dark' ? '☀️' : '🌙'; },
};

/* ---------- Sons : générés avec WebAudio ---------- */
const Sound = {
  ctx: null, muted: localStorage.getItem('qp_muted') === '1',
  unlock() {
    if (!this.ctx) { const AC = window.AudioContext || window.webkitAudioContext; if (AC) this.ctx = new AC(); }
    if (this.ctx && this.ctx.state === 'suspended') this.ctx.resume();
  },
  tone(freq, start, dur, type = 'sine', vol = 0.15) {
    const c = this.ctx; if (!c) return;
    const o = c.createOscillator(), g = c.createGain(), t0 = c.currentTime + start;
    o.type = type; o.frequency.setValueAtTime(freq, t0);
    g.gain.setValueAtTime(0.0001, t0); g.gain.exponentialRampToValueAtTime(vol, t0 + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    o.connect(g).connect(c.destination); o.start(t0); o.stop(t0 + dur + 0.05);
  },
  play(name) {
    if (this.muted) return; this.unlock(); if (!this.ctx) return;
    const seq = {
      click: [[660, 0, .08, 'triangle']],
      tick: [[880, 0, .06, 'square', .06]],
      start: [[523, 0, .12], [659, .12, .12], [784, .24, .2]],
      correct: [[659, 0, .12, 'triangle'], [880, .12, .12, 'triangle'], [1175, .24, .25, 'triangle']],
      wrong: [[220, 0, .18, 'sawtooth', .1], [165, .18, .3, 'sawtooth', .1]],
      join: [[740, 0, .1, 'triangle'], [988, .1, .14, 'triangle']],
      fanfare: [[523, 0, .15, 'square', .1], [523, .18, .15, 'square', .1], [523, .36, .15, 'square', .1],
                [659, .54, .25, 'square', .1], [784, .84, .5, 'square', .1], [1047, 1.0, .7, 'triangle', .14]],
    }[name] || [];
    for (const [f, s, d, t, v] of seq) this.tone(f, s, d, t, v);
  },
  toggle() { this.muted = !this.muted; localStorage.setItem('qp_muted', this.muted ? '1' : '0'); this.refresh(); },
  refresh() { const b = $('#sound-btn'); if (b) b.textContent = this.muted ? '🔇' : '🔊'; },
};
document.addEventListener('pointerdown', () => Sound.unlock(), { once: true });

/* ---------- Confettis ---------- */
function confetti(ms = 4000) {
  let cv = $('#confetti');
  if (!cv) { cv = h('canvas', { id: 'confetti' }); document.body.append(cv); }
  const ctx = cv.getContext('2d'), dpr = devicePixelRatio || 1;
  const size = () => { cv.width = innerWidth * dpr; cv.height = innerHeight * dpr; };
  size();
  const colors = ['#7c3aed', '#ff4d8d', '#fbbf24', '#10b981', '#22d3ee', '#ff7a1a', '#c026d3'];
  const bits = Array.from({ length: 160 }, () => ({
    x: Math.random() * cv.width, y: -Math.random() * cv.height * .6, r: (4 + Math.random() * 7) * dpr,
    vx: (Math.random() - .5) * 3 * dpr, vy: (2 + Math.random() * 4) * dpr, a: Math.random() * 6, va: (Math.random() - .5) * .3,
    c: colors[Math.floor(Math.random() * colors.length)],
  }));
  const end = performance.now() + ms;
  (function frame(now) {
    ctx.clearRect(0, 0, cv.width, cv.height);
    for (const b of bits) {
      b.x += b.vx; b.y += b.vy; b.a += b.va;
      ctx.save(); ctx.translate(b.x, b.y); ctx.rotate(b.a); ctx.fillStyle = b.c;
      ctx.fillRect(-b.r / 2, -b.r / 2, b.r, b.r * .6); ctx.restore();
    }
    if (now < end) requestAnimationFrame(frame); else cv.remove();
  })(performance.now());
}

/* ---------- Médias d'une question ---------- */
function mediaNode(q) {
  if (!q || !q.media_url || q.media_type === 'none') return null;
  const url = q.media_url;
  if (q.media_type === 'image') return h('img', { class: 'media', src: url, alt: '' });
  if (q.media_type === 'audio') return h('audio', { class: 'media', src: url, controls: true });
  const yt = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([\w-]{11})/);
  if (yt) return h('iframe', { class: 'media', src: `https://www.youtube-nocookie.com/embed/${yt[1]}`,
    allow: 'autoplay; encrypted-media; picture-in-picture', allowfullscreen: true });
  return h('video', { class: 'media', src: url, controls: true, playsinline: true });
}

/* ---------- Chronomètre animé ---------- */
function makeTimer(barEl, numEl, onTick) {
  let raf = null, endAt = 0, total = 1, lastSec = null;
  return {
    start(remainingMs, totalMs) {
      this.stop(); total = totalMs; endAt = performance.now() + remainingMs; lastSec = null;
      const step = () => {
        const left = Math.max(endAt - performance.now(), 0), sec = Math.ceil(left / 1000);
        barEl.firstElementChild.style.width = (100 * left / total) + '%';
        barEl.firstElementChild.style.backgroundPosition = (100 - 100 * left / total) + '% 0';
        numEl.textContent = sec; numEl.classList.toggle('urgent', sec <= 5 && left > 0);
        if (sec !== lastSec) { lastSec = sec; if (sec <= 5 && sec > 0) Sound.play('tick'); if (onTick) onTick(sec); }
        if (left > 0) raf = requestAnimationFrame(step);
      };
      step();
    },
    stop() { if (raf) cancelAnimationFrame(raf); raf = null; },
  };
}

const LETTERS = ['A', 'B', 'C', 'D'];

function flash(kind) { const f = h('div', { class: `flash ${kind}` }); document.body.append(f); setTimeout(() => f.remove(), 800); }

function wsUrl(path) { return `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}${path}`; }

document.addEventListener('DOMContentLoaded', () => {
  Theme.init(); Sound.refresh();
  $('#theme-btn')?.addEventListener('click', () => Theme.toggle());
  $('#sound-btn')?.addEventListener('click', () => Sound.toggle());
});
