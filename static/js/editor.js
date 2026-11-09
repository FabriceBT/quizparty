/* Éditeur de quiz : l'état vit dans `quiz`; on ne ré-affiche que lors des changements de structure. */
const quizId = $('#app').dataset.quizId;
const quiz = { title: '', description: '', category: '', questions: [] };
const box = $('#questions');

const blank = () => ({ kind: 'qcm', text: '', media_type: 'none', media_url: '', choices: ['', '', '', ''],
  correct: 0, accepted: [], time_limit: 20, explanation: '' });

function changeKind(q, kind) {
  const prev = q.kind;
  q.kind = kind;
  if (prev === 'point' && kind !== 'point') q.accepted = [];
  if (kind === 'ordre') { if (prev === 'vf' || prev === 'libre' || prev === 'point' || q.choices.length < 2) q.choices = ['', '', '']; q.correct = null; }
  if (kind === 'point') { q.media_type = 'image'; q.choices = []; q.correct = null; if (prev !== 'point') q.accepted = []; }
  if (prev === 'libre' || prev === 'point') { if (kind === 'qcm' && q.choices.length < 2) q.choices = ['', '', '', '']; }
  if (kind === 'qcm' && q.choices.length < 2) { q.choices = ['', '', '', '']; }
  if (kind === 'qcm' && q.choices.length > 4) q.choices = q.choices.slice(0, 4);
  if (kind === 'qcm' && (q.correct == null || q.correct >= q.choices.length)) q.correct = 0;
  if (kind === 'vf') { q.choices = ['Vrai', 'Faux']; if (q.correct == null || q.correct > 1) q.correct = 0; }
  if (kind === 'libre') { q.correct = null; }
}

function field(label, node) { return h('label', { class: 'field' }, label, node); }

function pointEditor(q) {
  if (!q.media_url) return h('p', { class: 'muted' }, '⬆ Ajoutez d’abord une image (importez un fichier ou collez son adresse).');
  const img = h('img', { src: q.media_url, alt: '', draggable: false });
  const box = h('div', { class: 'pointbox' }, img);
  const radius = h('input', { type: 'range', min: 3, max: 40, value: q.accepted[2] || 12 });
  const draw = () => {
    box.querySelector('.pt-target')?.remove();
    if (q.accepted.length >= 3) {
      const [x, y, r] = q.accepted.map(Number);
      box.append(h('div', { class: 'pt-target', style: `left:${x - r}%;top:${y - r}%;width:${2 * r}%;height:${2 * r}%` }));
    }
  };
  box.addEventListener('click', (e) => {
    const b = img.getBoundingClientRect();
    const x = Math.min(Math.max((e.clientX - b.left) / b.width * 100, 0), 100);
    const y = Math.min(Math.max((e.clientY - b.top) / b.height * 100, 0), 100);
    q.accepted = [x.toFixed(1), y.toFixed(1), String(radius.value)]; draw();
  });
  radius.addEventListener('input', () => { if (q.accepted.length >= 3) { q.accepted[2] = String(radius.value); draw(); } });
  draw();
  return h('div', {}, h('b', {}, 'Touchez l’image à l’endroit à trouver'), box,
    field('Tolérance (taille de la zone acceptée)', radius),
    q.accepted.length >= 3 ? null : h('p', { class: 'muted' }, 'Aucune zone placée pour l’instant.'));
}

function answersEditor(q) {
  if (q.kind === 'point') return pointEditor(q);
  if (q.kind === 'ordre') {
    const wrap = h('div', {}, h('b', {}, 'Éléments, dans le BON ordre (l’application les mélange pour les joueurs)'));
    q.choices.forEach((c, i) => wrap.append(h('div', { class: 'choice-row' }, h('span', { class: 'muted', style: 'min-width:2ch' }, `${i + 1}.`),
      h('input', { type: 'text', maxlength: 100, value: c, placeholder: `Élément ${i + 1}`, oninput: (e) => { q.choices[i] = e.target.value; } }),
      q.choices.length > 2 ? h('button', { class: 'icon-btn', title: 'Retirer', onclick: () => { q.choices.splice(i, 1); render(); } }, '✖') : null)));
    if (q.choices.length < 5) wrap.append(h('button', { class: 'btn ghost small', style: 'margin-top:10px', onclick: () => { q.choices.push(''); render(); } }, '+ Ajouter un élément'));
    return wrap;
  }
  if (q.kind === 'vf') {
    return h('div', {}, h('b', {}, 'Bonne réponse'), ['Vrai', 'Faux'].map((t, i) =>
      h('label', { class: 'choice-row' }, h('input', { type: 'radio', name: `ok-${q._id}`, checked: q.correct === i,
        onchange: () => { q.correct = i; } }), t)));
  }
  if (q.kind === 'libre') {
    return field('Réponses acceptées (une par ligne — accents et majuscules ignorés)',
      h('textarea', { rows: 3, placeholder: 'Pacifique\nOcéan Pacifique', oninput: (e) => { q.accepted = e.target.value.split('\n'); } },
        q.accepted.join('\n')));
  }
  const wrap = h('div', {}, h('b', {}, 'Réponses (cochez la bonne)'));
  q.choices.forEach((c, i) => wrap.append(h('div', { class: 'choice-row' },
    h('input', { type: 'radio', name: `ok-${q._id}`, checked: q.correct === i, onchange: () => { q.correct = i; }, 'aria-label': 'Bonne réponse' }),
    h('input', { type: 'text', maxlength: 100, value: c, placeholder: `Réponse ${LETTERS[i]}`, oninput: (e) => { q.choices[i] = e.target.value; } }),
    q.choices.length > 2 ? h('button', { class: 'icon-btn', title: 'Retirer', onclick: () => {
      q.choices.splice(i, 1); if (q.correct === i) q.correct = 0; else if (q.correct > i) q.correct--; render(); } }, '✖') : null)));
  if (q.choices.length < 4) wrap.append(h('button', { class: 'btn ghost small', style: 'margin-top:10px',
    onclick: () => { q.choices.push(''); render(); } }, '+ Ajouter une réponse'));
  return wrap;
}

function mediaEditor(q) {
  const url = h('input', { type: 'url', placeholder: 'https://… ou importez un fichier', value: q.media_url,
    oninput: (e) => { q.media_url = e.target.value.trim(); }, onchange: () => { if (q.kind === 'point') render(); } });
  const file = h('input', { type: 'file', class: 'hidden', accept: 'image/*,video/mp4,video/webm,audio/*',
    onchange: async (e) => {
      const f = e.target.files[0]; if (!f) return;
      const fd = new FormData(); fd.append('file', f);
      try {
        toast('Import en cours…');
        const res = await fetch('/api/upload', { method: 'POST', body: fd });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Import impossible.');
        q.media_url = data.url; q.media_type = data.media_type; render(); toast('Fichier importé ✔');
      } catch (err) { toast(err.message); }
    } });
  if (q.kind === 'point') {
    return h('div', {}, h('b', {}, '🖼 Image'), url, h('div', { class: 'row', style: 'margin-top:8px' },
      h('button', { class: 'btn ghost small', onclick: () => file.click() }, '📁 Importer une image'), file));
  }
  return h('div', {},
    field('Média (facultatif)', h('select', { onchange: (e) => { q.media_type = e.target.value; render(); } },
      [['none', 'Aucun'], ['image', '🖼 Image'], ['video', '🎬 Vidéo (fichier ou YouTube)'], ['audio', '🔊 Son']]
        .map(([v, t]) => h('option', { value: v, selected: q.media_type === v }, t)))),
    q.media_type !== 'none' ? h('div', {}, url, h('div', { class: 'row', style: 'margin-top:8px' },
      h('button', { class: 'btn ghost small', onclick: () => file.click() }, '📁 Importer un fichier'), file),
      q.media_url && q.media_type === 'image' ? h('img', { src: q.media_url, style: 'max-height:120px;border-radius:12px;margin-top:8px', alt: '' }) : null) : null);
}

function card(q, i) {
  return h('section', { class: 'card qcard stack' },
    h('div', { class: 'row between' }, h('h2', { style: 'margin:0' }, `Question ${i + 1}`),
      h('div', {},
        h('button', { class: 'icon-btn', title: 'Monter', disabled: i === 0, onclick: () => move(i, -1) }, '↑'),
        h('button', { class: 'icon-btn', title: 'Descendre', disabled: i === quiz.questions.length - 1, onclick: () => move(i, 1) }, '↓'),
        h('button', { class: 'icon-btn', title: 'Supprimer', onclick: () => { quiz.questions.splice(i, 1); render(); } }, '🗑'))),
    field('Type de question', h('select', { onchange: (e) => { changeKind(q, e.target.value); render(); } },
      [['qcm', 'QCM (2 à 4 réponses)'], ['vf', 'Vrai ou faux'], ['libre', 'Réponse libre'],
        ['ordre', 'Remettre dans l’ordre'], ['point', 'Point sur une image']]
        .map(([v, t]) => h('option', { value: v, selected: q.kind === v }, t)))),
    field('Question', h('input', { type: 'text', maxlength: 300, value: q.text, placeholder: 'Posez votre question…',
      oninput: (e) => { q.text = e.target.value; } })),
    mediaEditor(q),
    answersEditor(q),
    field('Temps de réponse', h('select', { onchange: (e) => { q.time_limit = +e.target.value; } },
      [10, 15, 20, 30].map((s) => h('option', { value: s, selected: q.time_limit === s }, `${s} secondes`)))),
    field('Explication affichée après la réponse (facultatif)', h('textarea', { rows: 2, maxlength: 500,
      oninput: (e) => { q.explanation = e.target.value; } }, q.explanation)));
}

function move(i, d) { const a = quiz.questions; [a[i], a[i + d]] = [a[i + d], a[i]]; render(); }

let uid = 0;
function render() {
  clear(box);
  quiz.questions.forEach((q, i) => { q._id = q._id || ++uid; box.append(card(q, i)); });
}

function payload() {
  return { title: quiz.title.trim(), description: quiz.description.trim(), category: quiz.category.trim(), questions: quiz.questions.map((q) => ({
    kind: q.kind, text: q.text, media_type: q.media_type, media_url: q.media_url, choices: q.choices, correct: q.correct,
    accepted: q.accepted.map(String), time_limit: q.time_limit, explanation: q.explanation })) };
}

$('#title').addEventListener('input', (e) => { quiz.title = e.target.value; });
$('#description').addEventListener('input', (e) => { quiz.description = e.target.value; });
$('#category').addEventListener('input', (e) => { quiz.category = e.target.value; });
$('#add').onclick = () => { quiz.questions.push(blank()); render(); box.lastElementChild.scrollIntoView({ behavior: 'smooth' }); };
$('#save').onclick = async () => {
  $('#err').textContent = '';
  try {
    if (quizId) await api(`/api/quizzes/${quizId}`, { method: 'PUT', body: payload() });
    else await api('/api/quizzes', { method: 'POST', body: payload() });
    location.href = '/quizzes';
  } catch (e) { $('#err').textContent = e.message; scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' }); }
};

(async function init() {
  if (quizId) {
    $('#page-title').textContent = '✏️ Modifier le quiz';
    const data = await api(`/api/quizzes/${quizId}`);
    Object.assign(quiz, { title: data.title, description: data.description, category: data.category || '',
      questions: data.questions.map((q) => ({ ...blank(), ...q, accepted: q.accepted || [] })) });
    $('#title').value = quiz.title; $('#description').value = quiz.description; $('#category').value = quiz.category;
  } else quiz.questions.push(blank());
  api('/api/quizzes').then((all) => $('#categories').append(...[...new Set(all.map((x) => x.category).filter(Boolean))].map((c) => h('option', { value: c })))).catch(() => {});
  render();
})().catch((e) => { $('#err').textContent = e.message; });
