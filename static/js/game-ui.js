/* Briques d'interface communes à l'écran joueur, à l'écran organisateur et au mode un-téléphone. */

const TEAMS = { rouge: '🔴 Rouges', bleu: '🔵 Bleus', vert: '🟢 Verts', jaune: '🟡 Jaunes' };
const teamEmoji = (t) => (TEAMS[t] || '').split(' ')[0];

/** Titre de la question + média (pour « point sur l'image », l'image fait partie de la zone de réponse). */
function questionBlock(q) {
  return [q.kind === 'point' ? null : mediaNode(q), h('div', { class: 'question' }, q.text)];
}

/**
 * Boutons de réponse (QCM / vrai-faux).
 * opts : onPick(i), disabled, mine (index choisi), correct (index juste, en phase de révélation), dist (compteurs)
 */
function answerButtons(q, opts = {}) {
  const box = h('div', { class: `answers ${q.kind === 'vf' ? 'vf cols2' : q.choices.length > 2 ? 'cols2' : ''}` });
  q.choices.forEach((label, i) => {
    const revealed = opts.correct != null;
    const cls = ['answer'];
    if (opts.hidden && opts.hidden.includes(i)) cls.push('gone');       // masquée par le joker 50/50
    if (revealed) cls.push(i === opts.correct ? 'right' : 'dim');
    if (opts.mine === i) cls.push('mine');
    box.append(h('button', {
      class: cls.join(' '), 'data-i': i, disabled: opts.disabled || revealed || !opts.onPick,
      onclick: () => opts.onPick && opts.onPick(i),
    }, h('span', { class: 'letter' }, q.kind === 'vf' ? (i === 0 ? '✔' : '✖') : LETTERS[i]),
       h('span', {}, label),
       opts.dist ? h('span', { class: 'count' }, `${opts.dist[i]}`) : null));
  });
  return box;
}

/** Champ de réponse libre. */
function freeForm(onSubmit, disabled = false) {
  const input = h('input', { type: 'text', maxlength: 100, placeholder: 'Votre réponse…', autocomplete: 'off',
    autocapitalize: 'off', disabled });
  const btn = h('button', { class: 'btn green', disabled }, 'Valider');
  const go = () => { if (input.value.trim()) onSubmit(input.value.trim()); };
  btn.addEventListener('click', go);
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter') go(); });
  setTimeout(() => !disabled && input.focus(), 50);
  return h('div', { class: 'free-form' }, input, btn);
}

/** En-tête : « Question 3/15 » + chrono. Retourne { node, timer }. */
function questionHeader(q) {
  const bar = h('div', { class: 'timer-bar' }, h('i'));
  const num = h('span', { class: 'timer-num' }, q.time_limit);
  const node = h('div', {}, h('div', { class: 'qhead' }, h('span', {}, `Question ${q.index + 1} / ${q.total}`), num), bar);
  return { node, timer: makeTimer(bar, num) };
}

function explanationNode(text) {
  return text ? h('div', { class: 'explain' }, '💡 ', text) : null;
}

function leaderboardNode(rows, me) {
  return h('ol', { class: 'board' }, rows.map((r) =>
    h('li', { style: me && r.name === me ? 'color:var(--brand)' : null },
      h('span', { class: 'rk' }, r.rank), h('span', { class: 'nm' }, r.team ? `${teamEmoji(r.team)} ${r.name}` : r.name),
      r.gained ? h('span', { class: 'gain' }, `+${r.gained}`) : null,
      h('span', { class: 'pts' }, r.score))));
}

/** Compte à rebours « Question suivante dans N s » (mode automatique). Il s'arrête tout seul quand le nœud quitte la page. */
function countdownNode(ms, label) {
  const end = Date.now() + ms, node = h('div', { class: 'banner wait', style: 'margin-top:16px' });
  const tick = () => {
    if (!node.isConnected && node.dataset.live) return clearInterval(iv);
    const left = Math.max(Math.ceil((end - Date.now()) / 1000), 0);
    node.textContent = `${label} dans ${left} s…`;
  };
  const iv = setInterval(tick, 250);
  tick(); node.dataset.live = '1';
  return node;
}

/** Masque des réponses (joker 50/50) dans un bloc de boutons déjà affiché. */
function hideAnswers(box, hidden) {
  (hidden || []).forEach((i) => box.querySelector(`.answer[data-i="${i}"]`)?.classList.add('gone'));
}

/** Série en cours : encourage à continuer. */
function streakNode(n) {
  return n >= 1 ? h('div', { class: 'streak' }, `🔥 Série de ${n} · prochaine bonne réponse : +${Math.min(50 * n, 250)} pts de bonus`) : null;
}

/** Ligne de bonus affichée dans la bannière « Bravo ». */
function bonusNode(bonus, streak) {
  return bonus ? h('div', { class: 'bonus-line' }, `🔥 Série de ${streak} : +${bonus} pts de bonus`) : null;
}

/** Bouton joker 50/50 (un seul par partie). */
function jokerButton(onUse) {
  const b = h('button', { class: 'btn joker', onclick: () => { b.disabled = true; onUse(); } }, '🃏 Joker 50/50 (points ÷ 2)');
  return b;
}

/** Choix d'équipe (facultatif) à la connexion. Retourne { node, get }. */
function teamPicker() {
  let value = '';
  const btns = Object.entries(TEAMS).map(([k, label]) => h('button', { type: 'button', class: 'team', 'data-t': k, onclick: () => {
    value = value === k ? '' : k;
    btns.forEach((b) => b.classList.toggle('on', b.dataset.t === value));
  } }, label));
  return { node: h('div', { class: 'stack' }, h('div', { class: 'muted' }, 'Équipe (facultatif)'), h('div', { class: 'teams' }, btns)), get: () => value };
}

/** Classement des équipes (moyenne de points par joueur). */
function teamsNode(teams) {
  if (!teams || teams.length < 2) return null;
  return h('div', { class: 'card' }, h('h2', {}, '🏁 Équipes'), h('div', { class: 'team-board' }, teams.map((t) =>
    h('div', { class: 'row-t' }, h('span', {}, t.label), h('span', {}, `${t.avg} pts de moyenne · ${t.players} joueur${t.players > 1 ? 's' : ''}`)))));
}

/** « Remettre dans l'ordre » : on touche les éléments dans l'ordre voulu, puis on valide. */
function orderForm(q, onSubmit) {
  const picked = [];
  const box = h('div', { class: `answers order ${q.choices.length > 2 ? 'cols2' : ''}` });
  const ok = h('button', { class: 'btn green', disabled: true }, 'Valider cet ordre');
  const redraw = () => {
    box.querySelectorAll('.answer').forEach((b) => {
      const pos = picked.indexOf(+b.dataset.i);
      b.classList.toggle('picked', pos >= 0);
      b.querySelector('.num').textContent = pos >= 0 ? pos + 1 : '·';
    });
    ok.disabled = picked.length !== q.choices.length;
  };
  q.choices.forEach((label, i) => box.append(h('button', { class: 'answer', 'data-i': i, onclick: () => {
    const at = picked.indexOf(i);
    if (at >= 0) picked.splice(at, 1); else picked.push(i);
    Sound.play('click'); redraw();
  } }, h('span', { class: 'num' }, '·'), h('span', {}, label))));
  ok.onclick = () => onSubmit([...picked]);
  return h('div', {}, h('p', { class: 'point-hint' }, 'Touchez les éléments dans le bon ordre'), box,
    h('div', { class: 'order-actions' }, h('button', { class: 'btn ghost', onclick: () => { picked.length = 0; redraw(); } }, 'Effacer'), ok));
}

/** Correction « ordre » : la bonne suite, numérotée. */
function orderResult(q, order) {
  const box = h('div', { class: `answers order ${q.choices.length > 2 ? 'cols2' : ''}` });
  (order || []).forEach((di, k) => box.append(h('div', { class: 'answer right', 'data-i': di, style: 'cursor:default' },
    h('span', { class: 'num' }, k + 1), h('span', {}, q.choices[di]))));
  return box;
}

/**
 * Image cliquable (« point sur l'image »). opts : onPlace(x, y) pour répondre, mine [x, y], target {x, y, r} (correction).
 * Les coordonnées sont des pourcentages de l'image : indépendantes de la taille de l'écran.
 */
function pointNode(q, opts = {}) {
  const img = h('img', { src: q.media_url, alt: '', draggable: false });
  const box = h('div', { class: 'pointbox', style: opts.onPlace ? null : 'cursor:default' }, img);
  const dot = (cls, x, y) => h('div', { class: `pt-dot ${cls}`, style: `left:${x}%;top:${y}%` });
  if (opts.target) {
    const t = opts.target;
    box.append(h('div', { class: 'pt-target', style: `left:${t.x - t.r}%;top:${t.y - t.r}%;width:${2 * t.r}%;height:${2 * t.r}%` }));
  }
  let mark = null;
  const place = (x, y, cls = '') => { if (mark) mark.remove(); mark = dot(cls, x, y); box.append(mark); };
  if (opts.mine) place(opts.mine[0], opts.mine[1], opts.target && Math.hypot(opts.mine[0] - opts.target.x, opts.mine[1] - opts.target.y) <= opts.target.r ? 'good' : '');
  if (opts.onPlace) box.addEventListener('click', (e) => {
    const b = img.getBoundingClientRect();
    const x = Math.min(Math.max((e.clientX - b.left) / b.width * 100, 0), 100);
    const y = Math.min(Math.max((e.clientY - b.top) / b.height * 100, 0), 100);
    place(x, y); opts.onPlace(Math.round(x * 10) / 10, Math.round(y * 10) / 10);
  });
  return box;
}

/** Réponse à une question « point sur l'image » : on touche l'image puis on valide. */
function pointForm(q, onSubmit) {
  let pos = null;
  const ok = h('button', { class: 'btn green', disabled: true, onclick: () => pos && onSubmit(pos) }, 'Valider');
  return h('div', {}, h('p', { class: 'point-hint' }, 'Touchez l’image à l’endroit demandé'),
    pointNode(q, { onPlace: (x, y) => { pos = [x, y]; ok.disabled = false; Sound.play('click'); } }), ok);
}

/** Zone de réponse adaptée au type de question. ctx : { onSubmit(value), disabled, mine, hidden }. */
function answerInput(q, ctx) {
  if (q.kind === 'libre') return ctx.disabled ? null : freeForm((v) => { Sound.play('click'); ctx.onSubmit(v); });
  if (ctx.disabled && (q.kind === 'ordre' || q.kind === 'point')) return null;
  if (q.kind === 'ordre') return orderForm(q, ctx.onSubmit);
  if (q.kind === 'point') return pointForm(q, ctx.onSubmit);
  return answerButtons(q, { disabled: ctx.disabled, mine: ctx.mine, hidden: ctx.hidden, onPick: (i) => { Sound.play('click'); ctx.onSubmit(i); } });
}

/** Correction affichée après la réponse. mine : valeur donnée par le joueur (index, tableau ordre, [x, y]…). */
function revealNode(q, r, mine, extra = {}) {
  if (q.kind === 'libre') return null;
  if (q.kind === 'ordre') return orderResult(q, r.correct_order);
  if (q.kind === 'point') return pointNode(q, { target: r.target, mine: Array.isArray(mine) ? mine : null });
  return answerButtons(q, { correct: r.correct_index, mine: typeof mine === 'number' ? mine : null, ...extra });
}
