/* Écran du joueur sur son téléphone. */
const stage = $('#stage'), code = stage.dataset.code, store = `qp_${code}`;
let ws, player = JSON.parse(localStorage.getItem(store) || 'null'), lastKey = '', playTimer = null;

function showJoin(message) {
  const name = h('input', { type: 'text', maxlength: 20, placeholder: 'Votre prénom', autocomplete: 'given-name',
    value: localStorage.getItem('qp_name') || '' });
  const err = h('div', { class: 'error' }, message || '');
  const go = async () => {
    err.textContent = '';
    try {
      const r = await api('/api/join', { method: 'POST', body: { code, name: name.value } });
      player = { token: r.token, name: r.name };
      localStorage.setItem(store, JSON.stringify(player)); localStorage.setItem('qp_name', r.name);
      Sound.play('join'); connect();
    } catch (e) { err.textContent = e.message; }
  };
  name.addEventListener('keydown', (e) => e.key === 'Enter' && go());
  fill(stage, h('div', { class: 'card center stack' },
    h('h1', {}, 'Bienvenue 👋'), h('p', { class: 'muted' }, `Partie n° ${code}`), name, err,
    h('button', { class: 'btn pink', onclick: go }, 'Rejoindre la partie')));
  name.focus();
}

function connect() {
  ws = new WebSocket(wsUrl(`/ws/play/${code}?token=${encodeURIComponent(player.token)}`));
  ws.onmessage = (ev) => render(JSON.parse(ev.data));
  ws.onclose = (ev) => {
    if (playTimer) playTimer.stop();
    if (ev.code === 4404) { localStorage.removeItem(store); player = null; return showJoin('Partie introuvable ou expirée. Vérifiez le code.'); }
    setTimeout(connect, 1500);   // coupure réseau : on se reconnecte tout seul
  };
}
const answer = (value) => ws.readyState === 1 && ws.send(JSON.stringify({ type: 'answer', value }));

function render(s) {
  if (playTimer) playTimer.stop();
  const key = `${s.phase}-${s.question ? s.question.index : ''}`, changed = key !== lastKey; lastKey = key;
  if (s.phase === 'lobby') return renderLobby(s);
  if (s.phase === 'question') { if (changed) Sound.play('start'); return renderQuestion(s); }
  if (s.phase === 'reveal') return renderReveal(s, changed);
  if (s.phase === 'finished') location.href = s.results_url;
}

function renderLobby(s) {
  fill(stage, h('div', { class: 'card center stack' },
    h('h1', {}, `Prêt(e), ${player.name} ? 🎉`), h('p', { class: 'muted' }, s.title),
    s.start_in_ms != null ? null : h('div', { class: 'banner wait' }, 'En attente du lancement par l’organisateur…'),
    s.start_in_ms != null ? countdownNode(s.start_in_ms, 'Début du quiz')
      : s.auto ? h('p', { class: 'muted' }, '⏩ Mode automatique : les questions s’enchaîneront toutes seules.') : null,
    h('div', { class: 'chips' }, s.players.map((n) => h('span', { class: 'chip' }, n)))));
}

function renderQuestion(s) {
  const q = s.question, head = questionHeader(q);
  playTimer = head.timer;
  const done = s.has_answered;
  let input;
  if (q.kind === 'libre') input = done ? null : freeForm((v) => { Sound.play('click'); answer(v); });
  else input = answerButtons(q, { disabled: done, mine: s.my_value, onPick: (i) => { Sound.play('click'); answer(i); } });
  fill(stage, head.node, ...questionBlock(q), input,
    done ? h('div', { class: 'banner wait', style: 'margin-top:16px' }, h('div', { class: 'big' }, '✔'), 'Réponse envoyée ! Suspense…') : null);
  head.timer.start(s.remaining_ms, q.time_limit * 1000);
}

function renderReveal(s, changed) {
  const q = s.question, r = s.reveal, me = s.me;
  if (changed) { Sound.play(me.correct ? 'correct' : 'wrong'); flash(me.correct ? 'good' : 'bad'); if (me.correct) navigator.vibrate?.(80); }
  const banner = me.correct
    ? h('div', { class: 'banner good' }, h('div', { class: 'big' }, '🎉 Bravo !'), `+${me.points} points`)
    : h('div', { class: 'banner bad' }, h('div', { class: 'big' }, me.given ? '😬 Raté…' : '⏰ Trop tard !'),
        `Bonne réponse : ${r.correct_text}`);
  fill(stage, banner, ...questionBlock(q),
    q.kind === 'libre' ? null : answerButtons(q, { correct: r.correct_index, mine: me.given ? q.choices.indexOf(me.given) : null }),
    explanationNode(r.explanation),
    h('div', { class: 'card' }, h('h2', {}, `Vous êtes ${me.rank}${me.rank === 1 ? 'er' : 'e'} sur ${me.of} — ${me.score} pts`),
      leaderboardNode(s.leaderboard, player.name)),
    r.next_in_ms != null ? countdownNode(r.next_in_ms, r.is_last ? 'Podium' : 'Question suivante')
      : h('p', { class: 'center muted' }, 'La suite arrive…'));
}

if (player) connect();
else api(`/api/sessions/${code}/exists`).then(() => showJoin()).catch((e) => showJoin(e.message));
