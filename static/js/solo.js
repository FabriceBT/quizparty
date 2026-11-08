/* Mode « un seul téléphone » : pour chaque question, chaque joueur répond à son tour. */
const stage = $('#stage'), code = stage.dataset.code;
let info, step = 0, timer = null;

const nP = () => info.players.length;
const total = () => info.questions.length * nP();
const who = (s) => info.players[s % nP()];
const qOf = (s) => info.questions[Math.floor(s / nP())];
const isDone = (s) => who(s).done.includes(Math.floor(s / nP()));

function advance() {
  while (step < total() && isDone(step)) step++;
  if (step >= total()) return finish();
  showTurn();
}

function showIntro() {
  fill(stage, h('div', { class: 'card center stack' }, h('h1', {}, info.title),
    h('div', { class: 'chips' }, info.players.map((p) => h('span', { class: 'chip' }, p.name))),
    h('p', { class: 'muted' }, 'Chaque joueur répond à tour de rôle. Passez-vous le téléphone !'),
    h('button', { class: 'btn pink', onclick: () => { Sound.play('start'); advance(); } }, '🚀 Commencer')));
}

function showTurn() {
  const p = who(step), qi = Math.floor(step / nP());
  fill(stage, h('div', { class: 'card center stack' },
    h('div', { class: 'muted' }, `Question ${qi + 1} / ${info.questions.length}`),
    h('h1', {}, `Au tour de ${p.name} !`), h('p', { class: 'muted' }, 'Les autres ne regardent pas 😉'),
    h('button', { class: 'btn', onclick: showQuestion }, `Je suis ${p.name}, c'est parti`),
    h('div', {}, h('b', {}, 'Scores : '), info.players.map((x) => `${x.name} ${x.score}`).join(' · '))));
}

function showQuestion() {
  const q = { ...qOf(step), index: Math.floor(step / nP()), total: info.questions.length };
  const head = questionHeader(q); timer = head.timer;
  const t0 = performance.now();
  let done = false;                       // propre à CETTE question (évite qu'un ancien minuteur se déclenche)
  const limit = setTimeout(() => submit(null), q.time_limit * 1000 + 50);   // temps écoulé = pas de réponse
  const submit = (value) => {
    if (done) return; done = true; clearTimeout(limit); timer.stop();
    send(value, Math.round(performance.now() - t0));
  };
  const input = q.kind === 'libre' ? freeForm((v) => { Sound.play('click'); submit(v); })
    : answerButtons(q, { onPick: (i) => { Sound.play('click'); submit(i); } });
  fill(stage, h('div', { class: 'muted center' }, `🎮 ${who(step).name}`), head.node, ...questionBlock(q), input);
  head.timer.start(q.time_limit * 1000, q.time_limit * 1000);
}

async function send(value, elapsed) {
  const p = who(step), qi = Math.floor(step / nP());
  let r;
  try { r = await api(`/api/solo/${code}/answer`, { method: 'POST', body: { player_id: p.id, question_index: qi, value, elapsed_ms: elapsed } }); }
  catch (e) { toast(e.message); if (e.status === 409) { p.done.push(qi); step++; } return advance(); }
  p.score = r.score; p.done.push(qi);
  Sound.play(r.correct ? 'correct' : 'wrong'); flash(r.correct ? 'good' : 'bad');
  const q = qOf(step);
  const nextP = step + 1 < total() ? who(step + 1) : null;
  const sameQ = Math.floor((step + 1) / nP()) === qi;
  fill(stage, 
    r.correct ? h('div', { class: 'banner good' }, h('div', { class: 'big' }, '🎉 Bravo !'), `+${r.points} points`)
      : h('div', { class: 'banner bad' }, h('div', { class: 'big' }, value == null ? '⏰ Trop tard !' : '😬 Raté…'), `Bonne réponse : ${r.correct_text}`),
    ...questionBlock(q),
    q.kind === 'libre' ? null : answerButtons(q, { correct: r.correct_index, mine: typeof value === 'number' ? value : null }),
    explanationNode(r.explanation),
    h('p', { class: 'center' }, `${p.name} : ${r.score} points`),
    h('button', { class: 'btn green', onclick: () => { step++; advance(); } },
      !nextP ? '🏆 Voir le podium' : sameQ ? `📱 Passer le téléphone à ${nextP.name}` : 'Question suivante ➜'));
}

async function finish() {
  await api(`/api/solo/${code}/finish`, { method: 'POST' });
  location.href = `/results/${code}`;
}

api(`/api/solo/${code}`).then((d) => {
  info = d;
  if (d.status === 'finished') return (location.href = `/results/${code}`);
  showIntro();
}).catch((e) => fill(stage, h('div', { class: 'card center' }, h('p', { class: 'error' }, e.message), h('a', { class: 'btn', href: '/' }, 'Accueil'))));
