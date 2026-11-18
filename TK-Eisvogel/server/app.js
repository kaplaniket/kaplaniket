/* TK Eisvogel – Reiter „Fragen“ (Claude 17.11.2026). Symbole kommen als window.IK vom Server. */
(() => {
const $ = id => document.getElementById(id);
const L = $('liste'), F = $('frage'), S = $('los'), IK = window.IK || {};
let verlauf = [], runden = [], beschaeftigt = false, abbruch = null, bild = null, spricht = null;
const esc = t => String(t).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const mac = !!(window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.tkki);

function inline(t) {
  t = esc(t);
  t = t.replace(/`([^`]+)`/g, '<code>$1</code>').replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
  t = t.replace(/\[\[([^\]|]+)(\|([^\]]+))?\]\]/g, (m, a, b, c) => '<span class="seite">' + (c || a) + '</span>');
  t = t.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  t = t.replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g, '$1<a href="$2" target="_blank" rel="noopener">$2</a>');
  return t;
}
function formatieren(text) {
  const zeilen = text.replace(/\r/g, '').split('\n'); let h = '', liste = '';
  const zu = () => { if (liste) { h += '</' + liste + '>'; liste = ''; } };
  const auf = art => { if (liste !== art) { zu(); h += '<' + art + '>'; liste = art; } };
  for (const z of zeilen) { const r = z.trim();
    if (!r) { zu(); continue; }
    if (/^[—–-]{1,3}$/.test(r)) { zu(); h += '<hr>'; continue; }
    if (/^#{1,4}\s/.test(r)) { zu(); h += '<h3>' + inline(r.replace(/^#+\s*/, '')) + '</h3>'; continue; }
    if (/^\*\*[^*]+\*\*.{0,30}$/.test(r) && !liste && h === '') { h += '<h3>' + inline(r.replace(/\*\*/g, '')) + '</h3>'; continue; }
    if (/^[•\-*]\s+/.test(r)) { auf('ul'); h += '<li>' + inline(r.replace(/^[•\-*]\s+/, '')) + '</li>'; continue; }
    if (/^\d{1,2}[.)]\s+/.test(r)) { auf('ol'); h += '<li>' + inline(r.replace(/^\d{1,2}[.)]\s+/, '')) + '</li>'; continue; }
    const m = r.match(/^(Kurz|Zu deiner Frage):\s*(.*)$/);
    if (m) { zu(); h += '<h4>' + m[1] + '</h4>' + (m[2] ? '<p>' + inline(m[2]) + '</p>' : ''); continue; }
    if (/^[^•.!?]{2,70}:$/.test(r)) { zu(); h += '<h4>' + inline(r.replace(/:$/, '')) + '</h4>'; continue; }
    zu(); h += '<p>' + inline(r) + '</p>'; }
  zu(); return h;
}
const unten = () => window.scrollTo(0, document.documentElement.scrollHeight);
function wachse() { F.style.height = '40px'; F.style.height = Math.min(F.scrollHeight, 140) + 'px'; }
function sag(t, fehler) { const e = $('toast'); if (!e) return; e.textContent = t; e.className = 'da' + (fehler ? ' fehler' : ''); clearTimeout(sag.t); sag.t = setTimeout(() => e.className = '', fehler ? 6000 : 3200); }

/* Zustand im Kopf */
function lampe(k, t) { $('zustand').innerHTML = '<i class="lampe ' + k + '"></i>' + esc(t); }
async function pruefen() { if (beschaeftigt || document.visibilityState === 'hidden') return;
  try { const j = await (await fetch('/api/gesund', {cache: 'no-store'})).json(); lampe(j.bereit ? 'gut' : j.ok ? 'arbeit' : 'schlecht', j.text || (j.bereit ? 'Bereit' : 'Startet …')); }
  catch (_) { lampe('schlecht', 'Rechner nicht erreichbar'); } }
pruefen(); setInterval(pruefen, 15000); document.addEventListener('visibilitychange', pruefen);

/* Antwort-Baustein */
function fussHtml(quellen, sek, hinweis) {
  const qs = [...new Set((quellen || []).map(x => x.seite || x).filter(Boolean))];
  return '<div class="fuss">' + (hinweis ? '<span>' + esc(hinweis) + '</span>' : '')
    + (qs.length ? qs.slice(0, 6).map(x => '<span class="pille grau">' + esc(x) + '</span>').join('') : (hinweis ? '' : '<span>aus eigenem Wissen</span>'))
    + (sek != null ? '<span class="dauer">' + Number(sek).toFixed(1) + ' s</span>' : '') + '</div>'
    + '<div class="werkzeug"><button type="button" data-w="laut">' + (IK.laut || '') + 'Vorlesen</button><button type="button" data-w="kopie">' + (IK.kopie || '') + 'Kopieren</button><button type="button" data-w="gut" title="Richtig – merken">👍</button><button type="button" data-w="schlecht" title="Falsch – korrigieren lassen">👎</button></div>';
}
function runde(frage, antwort, quellen, sek, hinweis, mitFoto) {
  L.insertAdjacentHTML('beforeend', '<div class="du"><div>' + esc(frage) + '</div>' + (mitFoto ? '<time>mit Foto</time>' : '') + '</div>'
    + '<div class="er" data-roh="' + esc(antwort) + '"><div class="text">' + formatieren(antwort) + '</div>' + fussHtml(quellen, sek, hinweis) + '</div>');
}
function merken() { try { sessionStorage.setItem('eisvogel-runden', JSON.stringify(runden.slice(-30))); sessionStorage.setItem('eisvogel-verlauf', JSON.stringify(verlauf)); } catch (_) {} }
function start_weg() { const b = $('leer'); if (b) b.remove(); }

/* Vorlesen und Kopieren */
L.addEventListener('click', ev => { const b = ev.target.closest('button[data-w]'); if (!b) return; const er = b.closest('.er');
  if (b.dataset.w === 'gut' || b.dataset.w === 'schlecht') { const du = er.previousElementSibling; const frage = du ? (du.querySelector('div') || du).innerText : '';
    fetch('/api/bewertung', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({frage, text: er.dataset.roh || er.querySelector('.text').innerText, gut: b.dataset.w === 'gut'})})
      .then(r => r.json()).then(j => { sag(j.meldung || 'Gespeichert'); b.parentNode.querySelectorAll('[data-w=gut],[data-w=schlecht]').forEach(x => x.disabled = true); b.classList.add('an'); }).catch(() => sag('Nicht gespeichert', 1)); return; }
  if (b.dataset.w === 'kopie') { const t = er.dataset.roh || er.querySelector('.text').innerText;
    (navigator.clipboard ? navigator.clipboard.writeText(t) : Promise.reject()).then(() => sag('Kopiert')).catch(() => { const a = document.createElement('textarea'); a.value = t; document.body.appendChild(a); a.select(); try { document.execCommand('copy'); sag('Kopiert'); } catch (_) { sag('Kopieren nicht möglich', 1); } a.remove(); }); }
  else if (window.speechSynthesis) { speechSynthesis.cancel(); if (spricht === b) { spricht = null; return; }
    const u = new SpeechSynthesisUtterance(er.querySelector('.text').innerText); u.lang = 'de-DE'; u.rate = 1.05; u.onend = () => { if (spricht === b) spricht = null; }; spricht = b; speechSynthesis.speak(u); } });

/* Foto mitschicken */
window.fotoweg = () => { bild = null; $('anhang').hidden = true; $('datei').value = ''; };
$('datei').addEventListener('change', ev => { const d = ev.target.files[0]; if (!d) return; const r = new FileReader();
  r.onload = e => { const im = new Image(); im.onload = () => { const s = Math.min(1, 1600 / Math.max(im.width, im.height)), c = document.createElement('canvas');
    c.width = im.width * s; c.height = im.height * s; c.getContext('2d').drawImage(im, 0, 0, c.width, c.height); bild = c.toDataURL('image/jpeg', 0.8);
    $('vbild').src = bild; $('anhang').hidden = false; unten(); }; im.src = e.target.result; }; r.readAsDataURL(d); });

/* Frage senden */
async function senden() {
  if (beschaeftigt) { if (abbruch) abbruch.abort(); return; }
  let frage = F.value.trim(); const foto = bild;
  if (!frage && !foto) return;
  if (!frage) frage = 'Was ist auf dem Foto, und was muss ich tun?';
  start_weg(); beschaeftigt = true; abbruch = new AbortController();
  S.classList.add('stopp'); S.innerHTML = IK.stopp || '■'; S.setAttribute('aria-label', 'Antwort beenden'); F.value = ''; wachse(); window.fotoweg(); lampe('arbeit', 'Arbeitet …');
  L.insertAdjacentHTML('beforeend', '<div class="du"><div>' + esc(frage) + '</div>' + (foto ? '<time>mit Foto</time>' : '') + '</div>');
  const er = document.createElement('div'); er.className = 'er';
  er.innerHTML = '<div class="text"></div><div class="lauf"><span class="punkte"><i></i><i></i><i></i></span><span class="lt">Suche …</span><span class="sek"></span></div>';
  L.appendChild(er); unten();
  const box = er.querySelector('.text'), lauf = er.querySelector('.lauf'), t0 = Date.now();
  const uhr = setInterval(() => { const s = lauf.querySelector('.sek'); if (s) s.textContent = Math.round((Date.now() - t0) / 1000) + ' s'; }, 1000);
  let txt = '', quellen = [], fehler = '', malen = 0;
  const zeichnen = () => { malen = 0; box.innerHTML = formatieren(txt); if (window.innerHeight + window.scrollY > document.documentElement.scrollHeight - 260) unten(); };
  try {
    const r = await fetch('/api/frage', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({frage, verlauf, bild: foto}), signal: abbruch.signal});
    if (!r.ok) throw new Error('Server meldet ' + r.status);
    const rd = r.body.getReader(), dec = new TextDecoder(); let rest = '';
    while (true) { const {value, done} = await rd.read(); if (done) break; rest += dec.decode(value, {stream: true}); const z = rest.split('\n'); rest = z.pop();
      for (const l of z) { if (!l) continue; let j; try { j = JSON.parse(l); } catch (_) { continue; }
        if (j.status) lauf.querySelector('.lt').textContent = j.status;
        if (j.reset) txt = '';
        if (j.quellen) quellen = j.quellen;
        if (j.fehler) fehler = j.fehler;
        if (j.t) txt += j.t;
        if ((j.t || j.reset) && !malen) malen = requestAnimationFrame(zeichnen); } }
  } catch (err) { fehler = err.name === 'AbortError' ? 'beendet' : String(err.message || err); }
  clearInterval(uhr); cancelAnimationFrame(malen); lauf.remove(); box.innerHTML = formatieren(txt);
  const sek = (Date.now() - t0) / 1000; let hinweis = '';
  if (fehler === 'beendet') { hinweis = 'beendet'; }
  else if (!txt.trim()) { er.classList.add('fehler'); box.innerHTML = '<p>' + (fehler ? 'Es hat nicht geklappt: ' + esc(fehler) + '.' : 'Keine Antwort bekommen.') + ' Bitte noch einmal versuchen.</p>'; }
  else if (fehler) hinweis = 'unvollständig: ' + fehler;
  if (txt.trim()) { er.dataset.roh = txt; er.insertAdjacentHTML('beforeend', fussHtml(quellen, sek, hinweis));
    verlauf.push({role: 'user', content: frage}, {role: 'assistant', content: txt}); verlauf = verlauf.slice(-6);
    runden.push({f: frage, a: txt, q: quellen, s: sek, h: hinweis, b: !!foto}); merken(); }
  beschaeftigt = false; abbruch = null; S.classList.remove('stopp'); S.innerHTML = IK.senden || '↑'; S.setAttribute('aria-label', 'Senden');
  if (window.innerWidth > 700) F.focus(); unten(); pruefen();
}
S.addEventListener('click', senden); S.addEventListener('pointerdown', ev => ev.preventDefault());
F.addEventListener('input', wachse);
F.addEventListener('keydown', ev => { if (ev.key === 'Enter' && !ev.shiftKey && !ev.isComposing && window.innerWidth > 700) { ev.preventDefault(); senden(); } });
document.querySelectorAll('.schnell button').forEach(b => b.addEventListener('click', () => { F.value = b.dataset.t; wachse(); if (b.dataset.t.endsWith(' ')) F.focus(); else senden(); }));
document.addEventListener('focusin', ev => { if (ev.target.matches('textarea,input:not([type=file])')) document.body.classList.add('tippt'); });
document.addEventListener('focusout', () => setTimeout(() => { const a = document.activeElement; if (!a || !a.matches('textarea,input')) document.body.classList.remove('tippt'); }, 150));

/* Gespräch dieser Sitzung wiederherstellen (Reiterwechsel lädt die Seite neu) */
try { runden = JSON.parse(sessionStorage.getItem('eisvogel-runden') || '[]'); verlauf = JSON.parse(sessionStorage.getItem('eisvogel-verlauf') || '[]'); } catch (_) { runden = []; verlauf = []; }
if (runden.length) { start_weg(); runden.forEach(r => runde(r.f, r.a, r.q, r.s, r.h, r.b)); setTimeout(unten, 30); }
$('neu').addEventListener('click', () => { if (beschaeftigt) return; runden = []; verlauf = []; merken(); location.href = '/'; });

/* Karteikarten */
const KM = $('kmain'), HM = $('haupt'), KR = $('kraster'), KQ = $('kq'); let kt = null;
async function karten(q) {
  try { const l = await (await fetch('/api/karten?q=' + encodeURIComponent(q || ''), {cache: 'no-store'})).json();
    KR.innerHTML = l.length ? '' : '<div class="leer">' + (q ? 'Keine Karte gefunden.' : 'Noch keine Karten – jede Frage wird hier gespeichert.') + '</div>';
    l.forEach(k => { const d = document.createElement('div'); d.className = 'karte'; d.tabIndex = 0;
      const vor = k.antwort.replace(/\*\*|\[\[|\]\]|^[#•\-]\s*/gm, '').replace(/\s+/g, ' ').slice(0, 220), z = k.zeit.split(' ');
      d.innerHTML = '<div class="meta">' + esc(z[0].split('-').reverse().join('.') + ' ' + (z[1] || '')) + (k.quellen && k.quellen.length ? ' · ' + esc(k.quellen.slice(0, 2).join(', ')) : '') + '</div><div class="kf">' + esc(k.frage) + '</div><div class="ka">' + esc(vor) + '</div>';
      const auf = () => { kzu(); start_weg(); runde(k.frage, k.antwort, k.quellen || [], null, 'Karteikarte vom ' + z[0].split('-').reverse().join('.') + ' ' + (z[1] || '')); unten(); };
      d.addEventListener('click', auf); d.addEventListener('keydown', ev => { if (ev.key === 'Enter') auf(); }); KR.appendChild(d); });
  } catch (_) { KR.innerHTML = '<div class="leer">Karten konnten nicht geladen werden.</div>'; }
}
function kzu() { KM.hidden = true; HM.hidden = false; $('kbtn').classList.remove('an'); }
$('kbtn').addEventListener('click', () => { if (KM.hidden) { KM.hidden = false; HM.hidden = true; window.scrollTo(0, 0); karten(KQ.value); if (window.innerWidth > 700) KQ.focus(); } else { kzu(); unten(); } });
KQ.addEventListener('input', () => { clearTimeout(kt); kt = setTimeout(() => karten(KQ.value), 250); });
if (location.hash === '#karteikarten') $('kbtn').click();

/* Mac-Programm: Knopf „Beenden“ schließt das Programm ganz */
if (mac) { const x = $('xbtn'); x.hidden = false; x.addEventListener('click', () => { try { if (abbruch) abbruch.abort(); } catch (_) {} window.webkit.messageHandlers.tkki.postMessage('beenden'); }); }
if (window.innerWidth > 700 && !runden.length) F.focus();
})();
