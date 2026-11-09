/* Mode « quand on veut » : le joueur fait le quiz seul, à son rythme, les questions s'enchaînent toutes seules. */
const stage = $('#stage'), code = stage.dataset.code, store = `qp_open_${code}`;
const AFTER_MS = 5000;     // durée d'affichage de la correction avant la question suivante
let player = null, timer = null, pending = null;
try { player = JSON.parse(localStorage.getItem(store) || 'null'); } catch (_) { /* stockage indisponible */ }

function stopTimers() { if (timer) timer.stop(); clearTimeout(pending); pending = null; }

function showJoin(message) {
  stopTimers();
  const name = h('input', { type: 'text', maxlength: 20, placeholder: 'Votre prénom', autocomplete: 'given-name',
    value: localStorage.getItem('qp_name') || '' });
  const err = h('div', { class: 'error' }, message || '');
  const team = teamPicker();
  let useTeams = false;                  // les équipes n'ont pas de sens dans la bibliothèque en libre-service
  const go = async () => {
    err.textContent = '';
    try {
      const r = await api(`/api/open/${code}/join`, { method: 'POST', body: { name: name.value, team: useTeams ? team.get() : '' } });
      player = { token: r.token, name: r.name };
      try { localStorage.setItem(store, JSON.stringify(player)); localStorage.setItem('qp_name', r.name); } catch (_) {}
      Sound.play('join'); next();
    } catch (e) { err.textContent = e.message; }
  };
  name.addEventListener('keydown', (e) => e.key === 'Enter' && go());
  api(`/api/open/${code}/info`).then((i) => {
    useTeams = !i.library;
    fill(stage, h('div', { class: 'card center stack' },
      h('h1', {}, 'Bienvenue 👋'), h('p', { class: 'muted' }, i.title),
      h('p', { class: 'muted' }, `${i.questions} questions · jouez quand vous voulez, à votre rythme. Chaque question est chronométrée.`),
      name, useTeams ? team.node : null, err, h('button', { class: 'btn pink', onclick: go }, 'Commencer')));
    name.focus();
  }).catch((e) => fill(stage, h('div', { class: 'card center stack' }, h('p', { class: 'error' }, e.message), h('a', { class: 'btn', href: '/play' }, 'Saisir un autre code'))));
}

async function next() {
  stopTimers();
  if (!player) return showJoin();
  let r;
  try { r = await api(`/api/open/${code}/question?token=${encodeURIComponent(player.token)}`); }
  catch (e) {
    if (e.status === 401) { try { localStorage.removeItem(store); } catch (_) {} player = null; return showJoin('Rejoignez la partie pour jouer.'); }
    fill(stage, h('div', { class: 'card center stack' }, h('p', { class: 'error' }, e.message),
      h('button', { class: 'btn', onclick: next }, 'Réessayer')));
    return;
  }
  if (r.state === 'done') return location.replace(`/results/${code}`);
  if (r.state === 'closed') {
    return fill(stage, h('div', { class: 'card center stack' }, h('h1', {}, 'Quiz clôturé'),
      h('p', { class: 'muted' }, `${r.name}, vous avez ${r.score} points.`),
      h('a', { class: 'btn', href: `/results/${code}` }, '🏆 Voir le classement')));
  }
  showQuestion(r);
}

function showQuestion(r) {
  stage.dataset.phase = 'question';
  const q = r.question, head = questionHeader(q);
  timer = head.timer;
  let done = false;
  const submit = (value) => {          // une seule réponse par affichage ; le chrono du serveur fait foi
    if (done) return; done = true; stopTimers();
    send(q, value);
  };
  const input = answerInput(q, { onSubmit: submit, hidden: r.hidden });
  const joker = r.joker_available ? jokerButton(async () => {
    try {
      const res = await api(`/api/open/${code}/joker`, { method: 'POST', body: { token: player.token, question_index: q.index } });
      hideAnswers(input, res.hidden); joker.remove();
    } catch (e) { toast(e.message); joker.disabled = false; }
  }) : null;
  fill(stage, h('div', { class: 'muted center' }, `🎮 ${player.name} · ${r.score} pts`), streakNode(r.streak), head.node,
    ...questionBlock(q), input, joker);
  head.timer.start(r.remaining_ms, q.time_limit * 1000);
  pending = setTimeout(() => submit(null), r.remaining_ms + 50);     // temps écoulé : pas de réponse
}

async function send(q, value) {
  let r;
  try {
    r = await api(`/api/open/${code}/answer`, { method: 'POST',
      body: { token: player.token, question_index: q.index, value } });
  } catch (e) { if (e.status !== 409) toast(e.message); return next(); }
  Sound.play(r.correct ? 'correct' : 'wrong'); flash(r.correct ? 'good' : 'bad');
  if (!r.correct) navigator.vibrate?.([250, 90, 250]);   // vibration longue en cas d'erreur ou de temps écoulé
  stage.dataset.phase = 'reveal';
  let record = null;          // record personnel (gardé sur ce téléphone), pour donner envie de rejouer
  if (r.finished) {
    try {
      const k = `qp_best_${r.quiz_id}`, old = +localStorage.getItem(k) || 0;
      if (r.score > old) { localStorage.setItem(k, r.score); record = old ? `🏅 Nouveau record perso : ${r.score} pts (avant : ${old})` : `🏅 Premier score enregistré : ${r.score} pts`; }
      else record = `🏅 Votre record : ${old} pts`;
    } catch (_) { /* stockage indisponible */ }
  }
  let moved = false;
  const go = () => { if (moved) return; moved = true; stopTimers(); next(); };
  fill(stage,
    r.correct ? h('div', { class: 'banner good' }, h('div', { class: 'big' }, '🎉 Bravo !'), `+${r.points} points`, bonusNode(r.bonus, r.streak))
      : h('div', { class: 'banner bad' }, h('div', { class: 'big' }, value == null ? '⏰ Trop tard !' : '😬 Raté…'), `Bonne réponse : ${r.correct_text}`),
    ...questionBlock(q),
    revealNode(q, r, value),
    explanationNode(r.explanation),
    record ? h('p', { class: 'center', style: 'font-weight:800' }, record) : null,
    h('p', { class: 'center' }, `${r.score} points · ${r.rank}${r.rank === 1 ? 'er' : 'e'} sur ${r.of} pour l’instant`),
    countdownNode(AFTER_MS, r.finished ? 'Résultats' : 'Question suivante'),
    h('button', { class: 'btn green next', onclick: go }, r.finished ? '🏆 Voir le classement' : 'Continuer ➜'));
  pending = setTimeout(go, AFTER_MS);
}

if (player) next(); else showJoin();
