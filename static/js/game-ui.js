/* Briques d'interface communes à l'écran joueur, à l'écran organisateur et au mode un-téléphone. */

/** Titre de la question + média. */
function questionBlock(q) {
  return [mediaNode(q), h('div', { class: 'question' }, q.text)];
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
      h('span', { class: 'rk' }, r.rank), h('span', { class: 'nm' }, r.name),
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
