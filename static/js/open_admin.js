/* Écran organisateur du mode « quand on veut » : QR code à partager, classement en direct, clôture. */
const app = $('#app'), code = app.dataset.code, cfg = app.dataset;
let refreshTimer = null;

async function render() {
  const r = await api(`/api/sessions/${code}/results`);
  const open = r.status !== 'finished';
  const total = r.total_questions;
  fill(app,
    h('h1', { class: 'center' }, open ? '🕒 Quiz ouvert' : '✅ Quiz clôturé'),
    h('p', { class: 'center muted' }, r.title),
    open ? h('div', { class: 'card stack' },
      h('div', { class: 'lobby-grid' },
        h('div', { class: 'qr' }, h('img', { src: `/qr/${code}.svg`, alt: 'QR code pour jouer' })),
        h('div', { class: 'center stack' },
          h('div', { class: 'muted' }, 'Scannez le QR code, ou allez sur'),
          h('b', {}, cfg.joinShort), h('div', { class: 'muted' }, 'et saisissez le code'),
          h('div', { class: 'bigcode' }, code))),
      h('p', { class: 'center muted' }, 'Chacun joue quand il veut, à son rythme : les questions s’enchaînent toutes seules. Aucun organisateur n’est nécessaire.'),
      cfg.local === '1' ? h('div', { class: 'warn' }, '⚠️ Les téléphones doivent être sur le même Wi-Fi que cet ordinateur, et celui-ci doit rester allumé. ' +
        'Le lien utilise l’adresse réseau de l’ordinateur (' + cfg.joinUrl + ').') : null) : null,
    h('div', { class: 'card' },
      h('h2', {}, `👥 ${r.players.length} joueur${r.players.length > 1 ? 's' : ''}${open ? ' — classement en direct' : ''}`),
      r.players.length ? h('ol', { class: 'board' }, r.players.map((p) => h('li', {},
        h('span', { class: 'rk' }, p.rank), h('span', { class: 'nm' }, p.name),
        h('span', { class: 'muted' }, p.answered >= total ? 'terminé' : `${p.answered}/${total}`),
        h('span', { class: 'pts' }, p.score)))) : h('p', { class: 'muted' }, 'En attente des premiers joueurs…')),
    open ? h('div', { class: 'stack' },
      h('button', { class: 'btn pink', onclick: closeQuiz }, '🏁 Clôturer le quiz'),
      h('p', { class: 'muted center' }, 'À la clôture, plus personne ne peut jouer, et les joueurs peuvent revoir les bonnes réponses.'))
      : h('div', { class: 'stack' },
        h('a', { class: 'btn', href: `/results/${code}` }, '🏆 Podium'),
        h('a', { class: 'btn ghost', href: `/review/${code}` }, '🔍 Revoir les réponses'),
        h('a', { class: 'btn ghost', href: `/api/sessions/${code}/export.xlsx` }, '📊 Exporter en Excel')),
    h('a', { class: 'btn ghost', href: '/quizzes' }, 'Mes quiz'));
  clearTimeout(refreshTimer);
  if (open) refreshTimer = setTimeout(() => render().catch(() => {}), 5000);
}

async function closeQuiz() {
  if (!confirm('Clôturer le quiz ? Plus personne ne pourra jouer.')) return;
  try { await api(`/api/open/${code}/close`, { method: 'POST' }); await render(); } catch (e) { toast(e.message); }
}

render().catch((e) => fill(app, h('div', { class: 'card center' }, h('p', { class: 'error' }, e.message), h('a', { class: 'btn', href: '/quizzes' }, 'Mes quiz'))));
