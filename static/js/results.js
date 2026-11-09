/* Podium animé + classement complet. */
const app = $('#app'), code = app.dataset.code;
const MEDALS = { 1: '🥇', 2: '🥈', 3: '🥉' };

function podium(top) {
  // Ordre visuel : 2e, 1er, 3e
  const order = [top.find((p) => p.pos === 2), top.find((p) => p.pos === 1), top.find((p) => p.pos === 3)].filter(Boolean);
  const heights = { 1: 100, 2: 70, 3: 50 };
  const node = h('div', { class: 'podium' }, order.map((p) => h('div', { class: `step p${p.pos}` },
    p.pos === 1 ? h('div', { class: 'crown' }, '👑') : null,
    h('div', { class: 'medal' }, MEDALS[p.pos]),
    h('div', { class: 'who' }, p.name),
    h('div', { class: 'block', 'data-h': heights[p.pos] }, p.score, h('small', {}, `pts · ${p.pct}%`)))));
  return node;
}

function animate(node) {
  const steps = [...node.querySelectorAll('.step')];
  // Les marches montent du 3e au 1er, puis le gagnant est célébré.
  [3, 2, 1].forEach((pos, k) => {
    const st = node.querySelector(`.p${pos}`); if (!st) return;
    setTimeout(() => {
      const b = $('.block', st); b.style.height = `calc(${b.dataset.h}% * 2.4)`; st.classList.add('show'); Sound.play('click');
    }, 500 + k * 1100);
  });
  const delay = 500 + 3 * 1100 + 400;
  setTimeout(() => { Sound.play('fanfare'); confetti(5000); }, delay);
}

async function init() {
  const r = await api(`/api/sessions/${code}/results`);
  const me = localStorage.getItem('qp_name');
  const lib = r.library && r.status !== 'finished';          // classement permanent de la bibliothèque
  const provisional = r.mode === 'open' && r.status !== 'finished';
  const players = r.players;
  const top = players.slice(0, 3).map((p, i) => ({ ...p, pos: i + 1 }));   // même à égalité, 3 marches au plus
  const pod = podium(top);
  const rest = players;
  fill(app, 
    h('h1', { class: 'center' }, lib ? '🏆 Classement' : provisional ? '🏆 Classement provisoire' : '🏆 Podium'), h('p', { class: 'center muted' }, r.title),
    lib ? h('p', { class: 'center muted' }, 'Ce quiz est ouvert à tout moment : le classement se met à jour à chaque partie' + (r.weekly ? ' et repart de zéro chaque lundi.' : '.'))
      : provisional ? h('p', { class: 'center muted' }, 'Le quiz est encore ouvert : d’autres joueurs peuvent encore jouer, le classement évolue.') : null,
    players.length ? pod : h('p', { class: 'center muted' }, 'Aucun participant.'),
    teamsNode(r.teams),
    h('div', { class: 'card' }, h('h2', {}, 'Classement complet'),
      h('ol', { class: 'board' }, rest.map((p) => h('li', { style: p.name === me ? 'color:var(--brand)' : null },
        h('span', { class: 'rk' }, p.rank), h('span', { class: 'nm' }, p.team ? `${teamEmoji(p.team)} ${p.name}` : p.name),
        h('span', { class: 'muted' }, `${p.correct}/${p.total} · ${p.pct}%`), h('span', { class: 'pts' }, p.score))))),
    h('div', { class: 'stack no-print' },
      lib ? h('button', { class: 'btn green', onclick: () => { try { localStorage.removeItem(`qp_open_${code}`); } catch (_) {} location.href = `/j/${code}`; } }, '🔁 Rejouer à ce quiz') : null,
      lib ? h('a', { class: 'btn pink', href: '/play' }, '🎮 Choisir un autre quiz') : null,
      lib ? null : provisional ? h('button', { class: 'btn pink', onclick: () => location.reload() }, '🔄 Actualiser le classement')
        : h('a', { class: 'btn pink', href: `/review/${code}` }, '🔍 Revoir les réponses'),
      !lib && provisional ? h('p', { class: 'center muted' }, 'Les bonnes réponses seront visibles à la clôture du quiz.') : null,
      h('a', { class: 'btn ghost', href: `/api/sessions/${code}/export.xlsx` }, '📊 Exporter en Excel'),
      h('button', { class: 'btn ghost', onclick: () => print() }, '🖨 Imprimer / enregistrer en PDF'),
      h('a', { class: 'btn ghost', href: '/' }, 'Accueil')));
  if (players.length) animate(pod);
}
init().catch((e) => fill(app, h('div', { class: 'card center' }, h('p', { class: 'error' }, e.message), h('a', { class: 'btn', href: '/' }, 'Accueil'))));
