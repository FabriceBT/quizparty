async function load() {
  const list = $('#list');
  const rows = await api('/api/library/admin');
  list.replaceChildren();
  if (!rows.length) list.append(h('p', { class: 'muted' }, 'Aucun quiz. Créez-en un d’abord.'));
  for (const q of rows) {
    const pub = h('button', { class: 'btn ' + (q.published ? 'green' : 'ghost'), onclick: async () => {
      await api(`/api/library/${q.id}/publish`, { method: 'POST', body: { published: !q.published } }); load();
    } }, q.published ? '✅ Visible' : '🚫 Masqué');
    const reset = h('button', { class: 'btn ghost', onclick: async () => {
      if (!confirm('Remettre le classement à zéro ?')) return;
      await api(`/api/library/${q.id}/reset`, { method: 'POST' }); load();
    } }, '↺ Classement à zéro');
    list.append(h('div', { class: 'stack' },
      h('b', {}, `${q.title} (${q.questions} q. · ${q.players} joueur${q.players > 1 ? 's' : ''})`),
      q.code ? h('a', { class: 'btn ghost', href: `/results/${q.code}` }, '🏆 Classement') : null, pub, reset));
  }
}
load().catch((e) => $('#list').replaceChildren(h('p', { class: 'error' }, e.message)));
