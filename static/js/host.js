/* Écran de l'organisateur (à projeter ou à garder en main) : salle d'attente, questions, révélations. */
const stage = $('#stage'), cfg = stage.dataset;
let ws, current = null, lastKey = '', lastCount = 0, hostTimer = null;

function connect() {
  ws = new WebSocket(wsUrl(`/ws/host/${cfg.code}?k=${encodeURIComponent(cfg.key)}`));
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type === 'error') return toast(msg.message);
    current = msg; render(msg);
  };
  ws.onclose = (ev) => {
    if (hostTimer) hostTimer.stop();
    if (ev.code === 4404) {
      fill(stage, h('div', { class: 'card center stack' }, h('h1', {}, 'Partie introuvable'),
        h('p', { class: 'muted' }, 'Le lien est invalide ou le serveur a redémarré.'), h('a', { class: 'btn', href: '/quizzes' }, 'Mes quiz')));
      return;
    }
    setTimeout(connect, 1500);
  };
}
const send = (type, extra) => ws && ws.readyState === 1 && ws.send(JSON.stringify({ type, ...extra }));
const DELAYS = [5, 8, 12, 20, 30];

/** Réglage du mode automatique : enchaîne les questions sans l'organisateur. Modifiable à tout moment. */
function autoControl(s) {
  const box = h('input', { type: 'checkbox', checked: s.auto, onchange: (e) => send('auto', { value: e.target.checked, delay: s.auto_delay }) });
  const delays = DELAYS.includes(s.auto_delay) ? DELAYS : [...DELAYS, s.auto_delay].sort((a, b) => a - b);
  const sel = h('select', { onchange: (e) => send('auto', { value: s.auto, delay: +e.target.value }) },
    delays.map((d) => h('option', { value: d, selected: d === s.auto_delay }, `${d} s`)));
  return h('div', { class: 'card row center auto-ctl', style: 'justify-content:center;gap:12px;margin-top:16px' },
    h('label', { style: 'display:flex;align-items:center;gap:8px;cursor:pointer' }, box, h('b', {}, '⏩ Mode automatique')),
    h('span', { class: 'muted' }, 'pause avant la question suivante :'), sel);
}

function render(s) {
  if (hostTimer) hostTimer.stop();
  const key = `${s.phase}-${s.question ? s.question.index : ''}`;
  const changed = key !== lastKey; lastKey = key;
  if (s.phase === 'lobby') {
    if (s.player_count > lastCount) Sound.play('join');
    lastCount = s.player_count; return renderLobby(s);
  }
  if (s.phase === 'question') { if (changed) Sound.play('start'); return renderQuestion(s); }
  if (s.phase === 'reveal') { if (changed) Sound.play('correct'); return renderReveal(s); }
  if (s.phase === 'finished') location.href = s.results_url;
}

function renderLobby(s) {
  fill(stage, h('div', { class: 'card stack' },
    h('h1', { class: 'center' }, s.title),
    h('div', { class: 'lobby-grid' },
      h('div', { class: 'qr' }, h('img', { src: `/qr/${cfg.code}.svg`, alt: 'QR code pour rejoindre la partie' })),
      h('div', { class: 'center stack' },
        h('div', { class: 'muted' }, 'Scannez le QR code, ou allez sur'),
        h('b', {}, cfg.joinShort), h('div', { class: 'muted' }, 'et saisissez le code'),
        h('div', { class: 'bigcode' }, cfg.code))),
    cfg.local === '1' ? h('div', { class: 'warn' }, '⚠️ Les téléphones doivent être connectés au même Wi-Fi que cet ordinateur. ' +
      'Le QR code utilise l’adresse réseau de l’ordinateur (' + cfg.joinUrl + ').') : null,
    h('h2', { class: 'center' }, `👥 ${s.player_count} joueur${s.player_count > 1 ? 's' : ''}`),
    h('div', { class: 'chips' }, s.players.length ? s.players.map((n) => h('span', { class: 'chip' }, n)) :
      h('span', { class: 'muted' }, 'En attente des participants…')),
    autoControl(s),
    h('button', { class: 'btn green', disabled: !s.player_count, onclick: () => send('start') }, '🚀 Lancer le quiz')));
}

function renderQuestion(s) {
  const q = s.question, head = questionHeader(q);
  hostTimer = head.timer;
  fill(stage, head.node, ...questionBlock(q),
    q.kind === 'libre' ? h('div', { class: 'card center muted' }, '✍️ Les joueurs tapent leur réponse sur leur téléphone') : answerButtons(q),
    h('p', { class: 'center muted' }, `${s.answered} / ${s.player_count} réponse${s.answered > 1 ? 's' : ''}`),
    h('button', { class: 'btn ghost', onclick: () => send('skip') }, 'Afficher la réponse maintenant'),
    autoControl(s));
  head.timer.start(s.remaining_ms, q.time_limit * 1000);
}

function renderReveal(s) {
  const q = s.question, r = s.reveal;
  fill(stage, h('div', { class: 'qhead' }, h('span', {}, `Question ${q.index + 1} / ${q.total}`)),
    ...questionBlock(q),
    q.kind === 'libre' ? h('div', { class: 'correct-box center' }, '✔ ', r.correct_text) :
      answerButtons(q, { correct: r.correct_index, dist: r.distribution }),
    h('div', { class: 'banner wait', style: 'margin-top:16px' }, `${r.right_count} bonne${r.right_count > 1 ? 's' : ''} réponse${r.right_count > 1 ? 's' : ''} sur ${s.player_count}`),
    explanationNode(r.explanation),
    h('div', { class: 'card' }, h('h2', {}, '🏅 Classement'), leaderboardNode(s.leaderboard)),
    r.next_in_ms != null ? countdownNode(r.next_in_ms, r.is_last ? 'Podium' : 'Question suivante') : null,
    h('button', { class: 'btn green', onclick: () => send('next') }, r.is_last ? '🏆 Voir le podium' : 'Question suivante ➜'),
    autoControl(s));
}

connect();
