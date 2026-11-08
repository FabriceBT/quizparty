/* Revue des réponses : une question à la fois, navigation précédente / suivante. */
const app = $('#app'), code = app.dataset.code;
let data, idx = 0;

function show() {
  const q = data.questions[idx];
  const dots = h('div', { class: 'dots' }, data.questions.map((_, i) =>
    h('button', { class: i === idx ? 'on' : '', 'aria-label': `Question ${i + 1}`, onclick: () => { idx = i; show(); } })));
  fill(app, 
    h('h1', { class: 'center' }, '🔍 Revoir les réponses'), dots,
    h('div', { class: 'card' },
      h('div', { class: 'muted center' }, `Question ${q.index + 1} / ${q.total}`),
      mediaNode(q), h('div', { class: 'question' }, q.text),
      h('div', { class: 'correct-box' }, '✔ Bonne réponse : ', q.correct_text),
      explanationNode(q.explanation),
      h('h2', { style: 'margin-top:18px' }, 'Réponses des participants'),
      q.answers.length ? q.answers.map((a) => h('div', { class: 'ans-row' },
        h('span', { class: 'mark' }, a.correct ? '✅' : '❌'),
        h('div', {}, h('div', { class: 'who' }, `${a.rank}. ${a.name}`),
          h('div', { class: 'given' }, a.given || 'Pas de réponse')),
        h('span', { class: 'pts' }, a.points ? `+${a.points}` : '0'))) : h('p', { class: 'muted' }, 'Aucune réponse enregistrée.')),
    h('div', { class: 'grid2 no-print' },
      h('button', { class: 'btn ghost', disabled: idx === 0, onclick: () => { idx--; show(); scrollTo(0, 0); } }, '⬅ Précédente'),
      h('button', { class: 'btn', disabled: idx === data.questions.length - 1, onclick: () => { idx++; show(); scrollTo(0, 0); } }, 'Suivante ➡')),
    h('div', { class: 'stack no-print', style: 'margin-top:14px' },
      h('a', { class: 'btn ghost', href: `/results/${code}` }, '🏆 Retour au podium'), h('a', { class: 'btn ghost', href: '/' }, 'Accueil')));
}

api(`/api/sessions/${code}/review`).then((d) => { data = d; show(); })
  .catch((e) => fill(app, h('div', { class: 'card center' }, h('p', { class: 'error' }, e.message), h('a', { class: 'btn', href: '/' }, 'Accueil'))));
