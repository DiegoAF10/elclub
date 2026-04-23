"""Audit Catalog — Streamlit page.

Spec completo en elclub-catalogo-priv/docs/AUDIT-SYSTEM.md.

3 vistas:
1. Queue — lista paginada con filtros tier/status/categoría, 50/página
2. Audit Detail — vista por "producto madre" agrupando variantes
3. Pending Review — mock preview post-Claude

Features obligatorios:
- Hero selection via click
- Delete foto (soft, reversible)
- Reorder con input numérico
- Flag watermark por foto
- Flag regen con Gemini por foto (checkbox nuevo, pedido Diego)
- Checks globales
- Notas
- Verify/Flag por variante + Verify todas batch
- Next/Prev producto
- Keyboard shortcuts (JS injected)
- Shortcuts box visible (pedido Diego)
"""

import json
import os
import subprocess
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

import audit_db
import audit_enrich


# ═══════════════════════════════════════
# Constants
# ═══════════════════════════════════════

PAGE_SIZE = 50
CATEGORIES = ["adult", "women", "kids", "baby", "jacket", "training",
              "polo", "vest", "sweatshirt"]
TIERS = ["T1", "T2", "T3", "T4", "T5"]
STATUSES = ["pending", "verified", "flagged", "skipped", "needs_rework", "deleted"]
CATEGORY_LABELS = {
    "adult": "👤 Adulto", "women": "♀️ Mujer", "kids": "🧒 Niño",
    "baby": "👶 Bebé", "jacket": "🧥 Chaqueta", "training": "🏋️ Training",
    "polo": "👔 Polo", "vest": "🦺 Vest", "sweatshirt": "🧶 Sweatshirt",
}
TIER_LABELS = {
    "T1": "🟢 T1 · Mundial 2026",
    "T2": "🔵 T2 · Top-5 Europa actual",
    "T3": "🟡 T3 · Ligas importantes",
    "T4": "🟣 T4 · Retros icónicos",
    "T5": "⚫ T5 · Retros otros",
}

SHORTCUTS_HTML = """
<div style="background:#1C1C1C;border:1px solid #4DA8FF;border-radius:8px;padding:12px 16px;font-family:'Space Grotesk',monospace;font-size:12px;color:#F0F0F0;line-height:1.6;">
<b style="color:#4DA8FF;">⌨️ SHORTCUTS</b><br>
<span style="color:#999">Por foto (click primero):</span> <code>1-9</code> foco · <code>X</code> delete · <code>W</code> watermark (→Gemini auto) · <code>G</code> marcar regen manual · <code>Enter</code> set hero · <code>↑↓</code> reorder<br>
<span style="color:#999">Preview modal (click en la imagen):</span> <code>ESC</code> cerrar · <code>←→</code> navegar · <code>scroll</code> zoom · <code>dblclick</code> reset · <code>W/X/G/Enter</code> acciones<br>
<span style="color:#999">Preview modal — mobile:</span> <code>swipe ←→</code> navegar · <code>pinch</code> zoom · <code>double-tap</code> reset · <code>tap fuera</code> cerrar<br>
<span style="color:#999">Global:</span> <code>Ctrl+L</code> abrir PDP live en vault.elclub.club<br>
<span style="color:#999">Por variante:</span> <code>V</code> verify · <code>F</code> flag · <code>Shift+D</code> 🗑 borrar SKU<br>
<span style="color:#999">Producto completo:</span> <code>Shift+V</code> verify todas · <code>Shift+F</code> flag todas · <code>S</code> skip · <code>Tab</code> next variante · <code>J/K</code> next/prev producto
</div>
"""

# CSS — border ice para foto focusada (va injectado en el parent doc, una sola vez)
PHOTO_FOCUS_CSS = """
<style id="audit-photo-focus-css">
  /* Anchor invisible que marca la columna como "foto auditable" con su índice */
  .audit-photo-anchor { display:none; }
  /* Border ice aplicado al stColumn que contiene la foto focusada */
  [data-testid="stColumn"].audit-photo-focused {
    outline: 2px solid #4DA8FF;
    outline-offset: -2px;
    border-radius: 6px;
    box-shadow: 0 0 0 4px rgba(77, 168, 255, 0.18);
    transition: outline 120ms ease, box-shadow 120ms ease;
  }
  /* Cursor pointer sobre fotos auditables */
  [data-testid="stColumn"]:has(> div > .audit-photo-anchor-wrap) {
    cursor: pointer;
  }
</style>
"""

# JavaScript para shortcuts. Dispatchea clicks a buttons:
#   - Globales (verify-all, flag-all, skip, next, prev, verify-current, flag-current) via
#     tags data-audit-action aplicados por _inject_tag_script.
#   - Per-foto (hero, delete, watermark, regen, reorder) via índice de foto focusada.
KEYBOARD_JS = """
<script>
(function(){
  const parentDoc = window.parent && window.parent.document;
  if (!parentDoc) return;

  // 1. Injectar CSS de focus una sola vez en el parent
  if (!parentDoc.getElementById('audit-photo-focus-css')) {
    const existing = document.getElementById('audit-photo-focus-css');
    if (existing) parentDoc.head.appendChild(existing.cloneNode(true));
  }

  // 2. Bindear keydown + click delegation una sola vez por lifecycle del parent window
  if (parentDoc.defaultView.__auditShortcutsBound) {
    // Re-scan de anchors en cada rerun por si cambió la lista
    scanPhotoAnchors();
    return;
  }
  parentDoc.defaultView.__auditShortcutsBound = true;
  parentDoc.defaultView.__focusedPhotoIdx = null;
  parentDoc.defaultView.__focusedPhotoCol = null;

  // ── Helpers ───────────────────────────────────────────
  function getParentCol(el) {
    return el.closest('[data-testid="stColumn"]');
  }

  function scanPhotoAnchors() {
    // Actualiza dataset.photoIdx en el stColumn padre de cada anchor.
    const anchors = parentDoc.querySelectorAll('.audit-photo-anchor');
    anchors.forEach(a => {
      const col = getParentCol(a);
      if (!col) return;
      col.dataset.photoIdx = a.dataset.photoIdx;
      col.dataset.photoFid = a.dataset.photoFid;
      col.classList.add('audit-photo-col');
    });
  }

  function setFocus(idx, col) {
    const win = parentDoc.defaultView;
    if (win.__focusedPhotoCol) {
      win.__focusedPhotoCol.classList.remove('audit-photo-focused');
    }
    win.__focusedPhotoIdx = idx;
    win.__focusedPhotoCol = col;
    if (col) col.classList.add('audit-photo-focused');
  }

  function focusByIdx(idx) {
    // Ops s13 — con tabs por modelo, múltiples columns pueden tener mismo data-photo-idx.
    // Solo el tab activo es visible; filtramos por offsetParent != null.
    const cols = parentDoc.querySelectorAll('[data-testid="stColumn"][data-photo-idx="' + idx + '"]');
    for (const c of cols) {
      if (c.offsetParent !== null) { setFocus(idx, c); return; }
    }
  }

  // Expone dispatcher reutilizable (lo consume también el preview modal de Tarea 2).
  // Identifica botones por emoji (robusto) no por posición (Streamlit duplica buttons
  // y stImage inyecta un "Fullscreen" que rompe el indexing posicional).
  parentDoc.defaultView.__auditDispatchPhotoAction = function(action, idxOverride) {
    const win = parentDoc.defaultView;
    const idx = (idxOverride != null) ? idxOverride : win.__focusedPhotoIdx;
    if (idx == null) return false;
    // Ops s13 — buscar el col visible con ese idx (tabs ocultan inactivos)
    const cols = parentDoc.querySelectorAll('[data-testid="stColumn"][data-photo-idx="' + idx + '"]');
    let col = null;
    for (const c of cols) { if (c.offsetParent !== null) { col = c; break; } }
    if (!col) return false;

    // Reorder: botones ↑ / ↓ (Ops s11 reemplaza el input numérico por swap con
    // foto adyacente). Match por texto; respeta disabled en primera/última foto.
    if (action === 'reorder-up' || action === 'reorder-down') {
      const targetChar = (action === 'reorder-up') ? '↑' : '↓';
      const btn = Array.from(col.querySelectorAll('button[kind="secondary"]'))
        .find(b => b.textContent.trim() === targetChar && !b.disabled);
      if (btn) { btn.click(); return true; }
      return false;
    }

    // Match por emoji. Streamlit renderea cada button dos veces (visible + hidden
    // twin para focus/tooltip). .find() retorna el primero, que es el visible.
    const emojiMap = { hero: '👑', delete: '❌', watermark: '⚠️', regen: '🎨' };
    const targetEmoji = emojiMap[action];
    if (!targetEmoji) return false;
    const btn = Array.from(col.querySelectorAll('button[kind="secondary"]'))
      .find(b => b.textContent.trim() === targetEmoji);
    if (!btn) return false;
    btn.click();
    return true;
  };

  // ── Click delegation: focus on photo column ───────────
  parentDoc.addEventListener('click', function(e){
    // Si el click cayó sobre un botón/input dentro de la foto, también focusear la col antes.
    const col = e.target.closest('[data-testid="stColumn"].audit-photo-col');
    if (col && col.dataset.photoIdx != null) {
      setFocus(parseInt(col.dataset.photoIdx, 10), col);
    }
  }, true);

  // ── Keyboard handler ───────────────────────────────────
  parentDoc.addEventListener('keydown', function(e){
    const tag = (e.target && e.target.tagName) || '';
    // No interferir con inputs de texto; tampoco con un button con focus
    // porque Enter ahí ya lo clickea nativamente (evita doble dispatch).
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'BUTTON' || tag === 'A') return;
    if (e.target.isContentEditable) return;

    const shift = e.shiftKey;
    const ctrl = e.ctrlKey || e.metaKey;  // Cmd en mac
    const key = e.key;
    const win = parentDoc.defaultView;
    const hasFocus = win.__focusedPhotoIdx != null;

    // Ctrl+L / Cmd+L → abrir PDP live en nueva tab (Ops s11)
    if (ctrl && (key === 'l' || key === 'L')) {
      const marker = parentDoc.getElementById('audit-live-url');
      const liveUrl = marker && marker.dataset.liveUrl;
      if (liveUrl) {
        window.open(liveUrl, '_blank');
        e.preventDefault();
      }
      return;
    }

    // ── Global (prioridad baja, después de per-foto) ───
    let globalAction = null;
    if (shift && key === 'V') globalAction = 'verify-all';
    else if (shift && key === 'F') globalAction = 'flag-all';
    else if (shift && (key === 'D' || key === 'd')) globalAction = 'delete-sku';
    else if (key === 'S' || key === 's') globalAction = 'skip';
    else if (key === 'V' || key === 'v') globalAction = 'verify-current';
    else if (key === 'F' || key === 'f') globalAction = 'flag-current';
    else if (key === 'J' || key === 'j') globalAction = 'next';
    else if (key === 'K' || key === 'k') globalAction = 'prev';

    // ── Per-foto (1-9 focus, X/W/G/Enter action, ↑↓ reorder) ───
    let photoDispatched = false;

    // Números 1-9: setea focus a esa foto (0-indexed internamente)
    if (/^[1-9]$/.test(key)) {
      focusByIdx(parseInt(key, 10) - 1);
      e.preventDefault();
      return;
    }

    if (hasFocus) {
      if (key === 'x' || key === 'X') {
        photoDispatched = win.__auditDispatchPhotoAction('delete');
      } else if (key === 'w' || key === 'W') {
        photoDispatched = win.__auditDispatchPhotoAction('watermark');
      } else if (key === 'g' || key === 'G') {
        photoDispatched = win.__auditDispatchPhotoAction('regen');
      } else if (key === 'Enter') {
        photoDispatched = win.__auditDispatchPhotoAction('hero');
      } else if (key === 'ArrowUp') {
        photoDispatched = win.__auditDispatchPhotoAction('reorder-up');
      } else if (key === 'ArrowDown') {
        photoDispatched = win.__auditDispatchPhotoAction('reorder-down');
      }
      if (photoDispatched) {
        e.preventDefault();
        return;
      }
    }

    if (globalAction) {
      const btn = parentDoc.querySelector('[data-audit-action="' + globalAction + '"]');
      if (btn) { btn.click(); e.preventDefault(); }
    }
  });

  // Primer scan
  scanPhotoAnchors();
})();
</script>
"""


# ═══════════════════════════════════════
# Preview modal (Tarea 2 Ops s10) — fullscreen viewer con zoom/pan + keyboard
# Se inyecta en el parent doc. Reusa __auditDispatchPhotoAction de Tarea 1
# para X/W/G/Enter → dispatch al mismo botón del audit form.
# ═══════════════════════════════════════

PREVIEW_MODAL_HTML = """
<style id="audit-preview-modal-css">
  #audit-preview-modal {
    display: none;
    position: fixed;
    inset: 0;
    background: #0D0D0D;
    z-index: 99999;
    font-family: 'Space Grotesk', -apple-system, sans-serif;
    color: #F0F0F0;
    user-select: none;
    -webkit-user-select: none;
  }
  #audit-preview-modal.open { display: flex; flex-direction: column; }

  #audit-preview-modal .apm-top {
    position: absolute; top: 0; left: 0; right: 0;
    display: flex; align-items: center; justify-content: space-between;
    padding: 12px 20px;
    background: linear-gradient(to bottom, rgba(0,0,0,0.6), transparent);
    z-index: 2;
  }
  #audit-preview-modal .apm-counter {
    flex: 1; text-align: center;
    font-family: 'Oswald', sans-serif;
    font-size: 18px; letter-spacing: 2px;
    color: #4DA8FF;
  }
  #audit-preview-modal .apm-close {
    background: transparent; border: 1px solid #333; color: #F0F0F0;
    width: 36px; height: 36px; border-radius: 50%;
    font-size: 18px; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    transition: background 100ms ease, border-color 100ms ease;
  }
  #audit-preview-modal .apm-close:hover { background: rgba(255,255,255,0.08); border-color: #4DA8FF; }

  #audit-preview-modal .apm-stage {
    flex: 1;
    display: flex; align-items: center; justify-content: center;
    overflow: hidden;
    cursor: grab;
  }
  #audit-preview-modal .apm-stage.grabbing { cursor: grabbing; }
  #audit-preview-modal .apm-stage img {
    max-width: 95vw; max-height: 85vh;
    object-fit: contain;
    transform-origin: center center;
    transition: transform 80ms ease-out;
    will-change: transform;
  }

  #audit-preview-modal .apm-nav {
    position: absolute; top: 50%; transform: translateY(-50%);
    background: rgba(13,13,13,0.7); border: 1px solid #333; color: #F0F0F0;
    width: 48px; height: 48px; border-radius: 50%;
    font-size: 24px; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    transition: background 100ms ease, border-color 100ms ease;
    z-index: 2;
  }
  #audit-preview-modal .apm-nav:hover { background: rgba(77,168,255,0.2); border-color: #4DA8FF; }
  #audit-preview-modal .apm-nav.prev { left: 20px; }
  #audit-preview-modal .apm-nav.next { right: 20px; }

  #audit-preview-modal .apm-zoom-ctrl {
    position: absolute; bottom: 80px; right: 20px;
    display: flex; gap: 4px; flex-direction: column;
    z-index: 2;
  }
  #audit-preview-modal .apm-zoom-ctrl button {
    width: 40px; height: 40px; border-radius: 6px;
    background: rgba(13,13,13,0.7); border: 1px solid #333; color: #F0F0F0;
    cursor: pointer; font-size: 16px;
  }
  #audit-preview-modal .apm-zoom-ctrl button:hover { background: rgba(77,168,255,0.2); border-color: #4DA8FF; }

  #audit-preview-modal .apm-meta {
    position: absolute; bottom: 0; left: 0; right: 0;
    padding: 12px 20px 20px;
    background: linear-gradient(to top, rgba(0,0,0,0.8), transparent);
    text-align: center;
    font-size: 12px;
    z-index: 2;
  }
  #audit-preview-modal .apm-meta .fid { color: #F0F0F0; font-weight: 600; }
  #audit-preview-modal .apm-meta .sep { color: #555; margin: 0 8px; }
  #audit-preview-modal .apm-meta .sz { color: #999; }

  #audit-preview-modal .apm-toast {
    position: absolute; bottom: 100px; left: 50%; transform: translateX(-50%);
    background: rgba(77,168,255,0.95); color: #0D0D0D;
    padding: 10px 18px; border-radius: 6px;
    font-size: 13px; font-weight: 600;
    opacity: 0; pointer-events: none;
    transition: opacity 120ms ease;
    z-index: 3;
  }
  #audit-preview-modal .apm-toast.show { opacity: 1; }

  #audit-preview-modal .apm-hint {
    position: absolute; top: 12px; left: 50%; transform: translate(-50%, 52px);
    font-size: 11px; color: #666;
    pointer-events: none;
  }
</style>
<script id="audit-preview-modal-js">
(function(){
  const parentDoc = window.parent && window.parent.document;
  if (!parentDoc) return;

  // CSS al parent (si no está ya)
  if (!parentDoc.getElementById('audit-preview-modal-css')) {
    const existing = document.getElementById('audit-preview-modal-css');
    if (existing) parentDoc.head.appendChild(existing.cloneNode(true));
  }

  // Binding una sola vez
  if (parentDoc.defaultView.__auditPreviewBound) return;
  parentDoc.defaultView.__auditPreviewBound = true;

  // Construir modal en el parent doc
  const modal = parentDoc.createElement('div');
  modal.id = 'audit-preview-modal';
  modal.innerHTML = [
    '<div class="apm-top">',
    '  <div style="width:36px"></div>',
    '  <div class="apm-counter" data-role="counter">— / —</div>',
    '  <button class="apm-close" data-role="close" aria-label="Cerrar">✕</button>',
    '</div>',
    '<div class="apm-hint">ESC cerrar · ←→ navegar · W/X/G/Enter acciones · scroll zoom</div>',
    '<div class="apm-stage" data-role="stage">',
    '  <img data-role="img" alt="preview" draggable="false" />',
    '</div>',
    '<button class="apm-nav prev" data-role="prev" aria-label="Anterior">‹</button>',
    '<button class="apm-nav next" data-role="next" aria-label="Siguiente">›</button>',
    '<div class="apm-zoom-ctrl">',
    '  <button data-role="zoom-in" aria-label="Zoom in">+</button>',
    '  <button data-role="zoom-reset" aria-label="Reset zoom">0</button>',
    '  <button data-role="zoom-out" aria-label="Zoom out">−</button>',
    '</div>',
    '<div class="apm-meta" data-role="meta"></div>',
    '<div class="apm-toast" data-role="toast"></div>'
  ].join('');
  parentDoc.body.appendChild(modal);

  // Estado del viewer
  const state = {
    anchors: [],      // lista ordenada de {idx, fid, url, size}
    cursor: 0,        // posición en anchors
    zoom: 1,
    panX: 0, panY: 0,
    dragging: false,
    lastX: 0, lastY: 0,
  };

  function $(sel) { return modal.querySelector('[data-role="' + sel + '"]'); }

  function applyTransform() {
    $('img').style.transform = 'translate(' + state.panX + 'px,' + state.panY + 'px) scale(' + state.zoom + ')';
  }

  function resetTransform() {
    state.zoom = 1; state.panX = 0; state.panY = 0;
    applyTransform();
  }

  function renderCurrent() {
    if (!state.anchors.length) return;
    const a = state.anchors[state.cursor];
    $('img').src = a.url;
    $('counter').textContent = 'FOTO ' + (state.cursor + 1) + ' / ' + state.anchors.length;
    $('meta').innerHTML =
      '<span class="fid">' + a.fid + '</span>' +
      '<span class="sep">·</span><span>posición ' + (a.idx + 1) + '</span>' +
      (a.size ? '<span class="sep">·</span><span class="sz">' + a.size + '</span>' : '');
    resetTransform();
  }

  function collectAnchors() {
    const nodes = parentDoc.querySelectorAll('.audit-photo-anchor');
    const list = [];
    nodes.forEach(n => {
      list.push({
        idx: parseInt(n.dataset.photoIdx, 10),
        fid: n.dataset.photoFid || '',
        url: n.dataset.photoUrl || '',
      });
    });
    return list;
  }

  function openModal(startIdx) {
    state.anchors = collectAnchors();
    state.cursor = Math.max(0, state.anchors.findIndex(a => a.idx === startIdx));
    if (state.cursor < 0) state.cursor = 0;
    modal.classList.add('open');
    renderCurrent();
  }

  function closeModal() {
    modal.classList.remove('open');
  }

  function nav(delta) {
    if (!state.anchors.length) return;
    state.cursor = (state.cursor + delta + state.anchors.length) % state.anchors.length;
    renderCurrent();
  }

  function showToast(text) {
    const t = $('toast');
    t.textContent = text;
    t.classList.add('show');
    clearTimeout(state._toastT);
    state._toastT = setTimeout(() => t.classList.remove('show'), 1100);
  }

  function dispatchAndToast(action, label) {
    const cur = state.anchors[state.cursor];
    if (!cur) return;
    const ok = parentDoc.defaultView.__auditDispatchPhotoAction &&
               parentDoc.defaultView.__auditDispatchPhotoAction(action, cur.idx);
    showToast(ok ? (label + ' ✓') : (label + ' — no se pudo'));
  }

  // ── Bindings del modal ─────────────────────────────
  $('close').addEventListener('click', closeModal);
  $('prev').addEventListener('click', () => nav(-1));
  $('next').addEventListener('click', () => nav(+1));
  $('zoom-in').addEventListener('click', () => { state.zoom = Math.min(state.zoom * 1.25, 8); applyTransform(); });
  $('zoom-out').addEventListener('click', () => { state.zoom = Math.max(state.zoom / 1.25, 0.5); applyTransform(); });
  $('zoom-reset').addEventListener('click', resetTransform);

  // Click outside image closes (si está en zoom 1)
  modal.addEventListener('click', e => {
    if (e.target === modal || e.target.classList.contains('apm-stage')) {
      if (state.zoom === 1) closeModal();
    }
  });

  // Scroll wheel zoom
  $('stage').addEventListener('wheel', e => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
    state.zoom = Math.min(Math.max(state.zoom * factor, 0.5), 8);
    applyTransform();
  }, { passive: false });

  // Pan con drag (cuando zoom > 1)
  $('stage').addEventListener('mousedown', e => {
    if (state.zoom <= 1) return;
    state.dragging = true;
    state.lastX = e.clientX; state.lastY = e.clientY;
    $('stage').classList.add('grabbing');
  });
  parentDoc.addEventListener('mousemove', e => {
    if (!state.dragging) return;
    state.panX += e.clientX - state.lastX;
    state.panY += e.clientY - state.lastY;
    state.lastX = e.clientX; state.lastY = e.clientY;
    applyTransform();
  });
  parentDoc.addEventListener('mouseup', () => {
    state.dragging = false;
    $('stage').classList.remove('grabbing');
  });

  // Double-click = reset
  $('img').addEventListener('dblclick', e => { e.stopPropagation(); resetTransform(); });

  // ── Touch support (mobile) ─────────────────────────
  // 1 dedo + zoom=1: tracking para swipe horizontal → nav prev/next
  // 1 dedo + zoom>1: pan (drag)
  // 2 dedos: pinch-to-zoom usando distancia inicial
  // Tap simple fuera de imagen: cierra (ya cubierto por el click handler de modal)
  // Doble-tap en imagen: reset (ya cubierto por dblclick, la mayoría de mobile browsers lo disparan)
  const SWIPE_THRESHOLD = 50;     // px mínimos en horizontal para considerar swipe
  const SWIPE_VERT_LIMIT = 80;    // si el dedo se mueve más de esto en vertical, no es swipe
  const touch = { active: false, startX: 0, startY: 0, lastX: 0, lastY: 0,
                   pinchStartDist: 0, pinchStartZoom: 1, mode: null /* 'swipe'|'pan'|'pinch' */ };

  function dist(t1, t2) {
    const dx = t1.clientX - t2.clientX;
    const dy = t1.clientY - t2.clientY;
    return Math.sqrt(dx * dx + dy * dy);
  }

  $('stage').addEventListener('touchstart', e => {
    if (e.touches.length === 2) {
      touch.mode = 'pinch';
      touch.pinchStartDist = dist(e.touches[0], e.touches[1]);
      touch.pinchStartZoom = state.zoom;
      e.preventDefault();
    } else if (e.touches.length === 1) {
      touch.active = true;
      touch.startX = touch.lastX = e.touches[0].clientX;
      touch.startY = touch.lastY = e.touches[0].clientY;
      touch.mode = state.zoom > 1 ? 'pan' : 'swipe';
    }
  }, { passive: false });

  $('stage').addEventListener('touchmove', e => {
    if (touch.mode === 'pinch' && e.touches.length === 2) {
      const d = dist(e.touches[0], e.touches[1]);
      const scale = d / touch.pinchStartDist;
      state.zoom = Math.min(Math.max(touch.pinchStartZoom * scale, 0.5), 8);
      applyTransform();
      e.preventDefault();
    } else if (touch.mode === 'pan' && e.touches.length === 1) {
      const t = e.touches[0];
      state.panX += t.clientX - touch.lastX;
      state.panY += t.clientY - touch.lastY;
      touch.lastX = t.clientX; touch.lastY = t.clientY;
      applyTransform();
      e.preventDefault();
    } else if (touch.mode === 'swipe' && e.touches.length === 1) {
      touch.lastX = e.touches[0].clientX;
      touch.lastY = e.touches[0].clientY;
      // NO preventDefault — permite que el usuario scrollee verticalmente si cambia de idea
    }
  }, { passive: false });

  $('stage').addEventListener('touchend', e => {
    if (touch.mode === 'swipe' && touch.active) {
      const dx = touch.lastX - touch.startX;
      const dy = Math.abs(touch.lastY - touch.startY);
      if (dy < SWIPE_VERT_LIMIT && Math.abs(dx) > SWIPE_THRESHOLD) {
        nav(dx > 0 ? -1 : +1);  // swipe right → prev, swipe left → next
      }
    }
    // Si era pinch y el zoom quedó ~1, resetear pan por limpieza visual
    if (touch.mode === 'pinch' && state.zoom <= 1.05) {
      resetTransform();
    }
    touch.active = false;
    touch.mode = null;
  });

  // Tap en imagen para doble-tap zoom reset (muchos mobile browsers no disparan dblclick).
  // Detecta dos toques cerca en tiempo/espacio.
  let lastTapAt = 0;
  let lastTapX = 0;
  $('img').addEventListener('touchend', e => {
    const now = Date.now();
    const t = e.changedTouches && e.changedTouches[0];
    if (!t) return;
    if (now - lastTapAt < 350 && Math.abs(t.clientX - lastTapX) < 40) {
      resetTransform();
      e.preventDefault();
      lastTapAt = 0;  // reset para evitar triple-tap
    } else {
      lastTapAt = now;
      lastTapX = t.clientX;
    }
  });

  // Keyboard handler (solo cuando modal abierto)
  // Llama stopImmediatePropagation en capture para que el handler global de Tarea 1 NO
  // vuelva a dispatchar la misma acción (evita doble click en el botón subyacente).
  parentDoc.addEventListener('keydown', e => {
    if (!modal.classList.contains('open')) return;
    const key = e.key;
    const consume = () => { e.preventDefault(); e.stopImmediatePropagation(); };
    if (key === 'Escape')     { consume(); closeModal(); return; }
    if (key === 'ArrowLeft')  { consume(); nav(-1); return; }
    if (key === 'ArrowRight') { consume(); nav(+1); return; }
    if (/^[1-9]$/.test(key)) {
      const target = parseInt(key, 10) - 1;
      const hit = state.anchors.findIndex(a => a.idx === target);
      if (hit >= 0) { state.cursor = hit; renderCurrent(); consume(); }
      return;
    }
    if (key === 'w' || key === 'W') { consume(); dispatchAndToast('watermark', 'Watermark flaggeado'); return; }
    if (key === 'g' || key === 'G') { consume(); dispatchAndToast('regen', 'Regen marcada'); return; }
    if (key === 'Enter')             { consume(); dispatchAndToast('hero', 'Hero asignado'); return; }
    if (key === 'x' || key === 'X') {
      consume();
      dispatchAndToast('delete', 'Foto deleteada');
      // Avanza a siguiente (o cierra si era la última)
      setTimeout(() => { if (state.anchors.length > 1) nav(+1); else closeModal(); }, 250);
      return;
    }
    // Teclas sin mapeo → no consumimos, dejamos pasar (ej. la Tarea 1 sigue funcionando)
  }, true);  // capture: sí, para ganar prioridad antes del handler global de Tarea 1

  // ── Trigger: click en <img> de un photo-card abre el modal ─────
  parentDoc.addEventListener('click', e => {
    const img = e.target.closest('[data-testid="stImage"] img');
    if (!img) return;
    const col = img.closest('[data-testid="stColumn"].audit-photo-col');
    if (!col || col.dataset.photoIdx == null) return;
    e.preventDefault();
    openModal(parseInt(col.dataset.photoIdx, 10));
  });
})();
</script>
"""


# ═══════════════════════════════════════
# Init
# ═══════════════════════════════════════

def _ensure_init():
    audit_db.init_audit_schema()
    if "audit_seeded" not in st.session_state:
        conn = audit_db.get_conn()
        count = conn.execute("SELECT COUNT(*) FROM audit_decisions").fetchone()[0]
        conn.close()
        if count == 0:
            result = audit_db.seed_audit_queue()
            st.session_state.audit_seed_result = result
        st.session_state.audit_seeded = True


# ═══════════════════════════════════════
# Helpers
# ═══════════════════════════════════════

def _tag_button_js(action):
    """Genera un attribute para que el botón pueda ser invocado por el shortcut."""
    # Streamlit no permite data-* attrs directos. Workaround: usamos el label
    # único y ejecutamos JS para taggearlo por posición. Aquí sólo retornamos
    # el action como sufijo del key.
    return action


def _inject_tag_script(button_keys_actions):
    """JS que tagguea buttons en Streamlit por key → data-audit-action."""
    if not button_keys_actions:
        return
    mappings = []
    for key, action in button_keys_actions.items():
        mappings.append(f"'{key}': '{action}'")
    js = f"""
<script>
(function(){{
  const map = {{ {', '.join(mappings)} }};
  const parentDoc = window.parent && window.parent.document;
  if (!parentDoc) return;
  Object.entries(map).forEach(([key, action]) => {{
    // Streamlit genera buttons con el key en atributos internos.
    // Los identificamos por el texto/label — acá por selector fallback.
    const selector = '[data-testid="stButton"] button[kind="secondary"], [data-testid="stButton"] button[kind="primary"]';
    const buttons = parentDoc.querySelectorAll(selector);
    buttons.forEach(b => {{
      if (b.textContent && b.textContent.includes(key)) {{
        b.setAttribute('data-audit-action', action);
      }}
    }});
  }});
}})();
</script>
"""
    components.html(js, height=0)


def _render_shortcuts_box():
    st.markdown(SHORTCUTS_HTML, unsafe_allow_html=True)


def _render_stats_header(conn):
    stats = audit_db.queue_stats(conn)
    total = stats.get("total", 0) or 0
    needs_rework = stats.get("needs_rework", 0) or 0
    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    c1.metric("Total", total)
    c2.metric("Pending", stats.get("pending", 0) or 0)
    c3.metric("Verified", stats.get("verified", 0) or 0)
    c4.metric("Flagged", stats.get("flagged", 0) or 0)
    c5.metric("Skipped", stats.get("skipped", 0) or 0)
    # needs_rework visible en el header (antes de s14-mini estaba oculto, causando
    # el bug Diego-2026-04-22: Argentina 2026 Home invisible porque quedó en este
    # estado tras fallos de Gemini y queue default filtra pending).
    c6.metric("⚠️ Needs rework", needs_rework)
    c7.metric("✅ Publicadas", stats.get("final_verified", 0) or 0)


# ═══════════════════════════════════════
# VIEW 1: Queue
# ═══════════════════════════════════════

def render_queue(conn, catalog):
    st.header("📋 Queue de Audit")
    _render_shortcuts_box()
    st.markdown("")

    # Banner needs_rework — fix de s14-mini (2026-04-22). Diego reportó que
    # ARG-2026-L-FS/PS no aparecían. Razón: status='needs_rework' (Gemini
    # watermark falló al publish) + queue default filtra 'pending'. Añado
    # señal visible + shortcut al filter.
    qstats = audit_db.queue_stats(conn)
    nr = qstats.get("needs_rework", 0) or 0
    if nr > 0:
        bc1, bc2 = st.columns([4, 1])
        with bc1:
            st.warning(
                f"⚠️ **{nr} SKU{'s' if nr != 1 else ''} en `needs_rework`** — "
                f"fallaron al publish (Gemini watermark u otra abort). No están en "
                f"el filter default 'pending'. Click derecha para verlos."
            )
        with bc2:
            if st.button("👀 Ver needs_rework", use_container_width=True,
                         key="queue_jump_needs_rework"):
                st.session_state["audit_queue_status"] = "needs_rework"
                st.rerun()

    # Status filter con session_state para permitir navegación programática
    # (banner arriba + bookmark-style persistencia entre reruns).
    if "audit_queue_status" not in st.session_state:
        st.session_state["audit_queue_status"] = "pending"

    # Filters — Ops s13+: default filter = pending para que Diego vea primero lo que falta
    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1:
        tier_filter = st.selectbox(
            "Tier", ["(todos)", "(sin tier)"] + TIERS,
            format_func=lambda t: t if t.startswith("(") else TIER_LABELS.get(t, t),
        )
    with fc2:
        status_options = ["(todos)"] + STATUSES
        status_filter = st.selectbox(
            "Status", status_options,
            key="audit_queue_status",
        )
    with fc3:
        category_filter = st.selectbox(
            "Categoría (madre)", ["(todas)"] + CATEGORIES,
            format_func=lambda c: c if c.startswith("(") else CATEGORY_LABELS.get(c, c),
        )
    with fc4:
        search = st.text_input("Buscar", placeholder="SKU, team, season…")

    tf = tier_filter if tier_filter not in ("(todos)", "(sin tier)") else None
    sf = status_filter if status_filter != "(todos)" else None
    cf = category_filter if category_filter != "(todas)" else None

    # Ops s14 — toggle "Ver borrados". Default OFF: esconde status='deleted' del queue
    # incluso cuando el status_filter es "(todos)". Turn ON para auditoría/recovery.
    tfc1, tfc2 = st.columns([1, 1])
    with tfc1:
        show_deleted = st.checkbox(
            "Ver borrados", value=False, key="audit_show_deleted",
            help="Por defecto se esconden SKUs con status=deleted. Activá para auditar/recuperar.",
        )
    with tfc2:
        # Ops s14d — toggle "🎯 Solo QA priority" — los ~136 SKUs críticos post-refetch
        # (Mundial 48 × home/away fan short + Top-20 clubs 25/26 × home/away fan short).
        # Marcados via scripts/mark-qa-priority.py.
        show_qa_only = st.checkbox(
            "🎯 Solo QA priority", value=False, key="audit_qa_only",
            help="Solo los SKUs TOP para validar visualmente post-refetch. Corré `python scripts/mark-qa-priority.py` para regenerar.",
        )

    # Ops s14d — si show_qa_only, bypassa el status filter (queremos ver los
    # QA priority en CUALQUIER status, especialmente needs_rework donde cayeron
    # los Mundial TOP tras el publish attempt fallido de Gemini).
    effective_sf = None if show_qa_only else sf
    items = audit_db.queue_families(conn, catalog, tf, effective_sf, cf)

    # Tier "(sin tier)": items cuyo tier is NULL
    if tier_filter == "(sin tier)":
        items = [i for i in items if not i.get("tier")]

    # Hide deleted unless explicit (either status_filter='deleted' or show_deleted toggle)
    if not show_deleted and sf != "deleted":
        items = [i for i in items if i.get("status") != "deleted"]

    # QA priority filter — solo los marcados por mark-qa-priority.py
    if show_qa_only:
        items = [i for i in items if i.get("qa_priority")]

    if search:
        s = search.lower()
        items = [
            i for i in items
            if s in (i.get("sku", "").lower())
            or s in (i.get("team", "") or "").lower()
            or s in (i.get("season", "") or "").lower()
        ]

    st.caption(f"**{len(items)} items auditables** en queue (post-filtros) · cada uno es 1 modelo independiente")

    # Pagination
    total_pages = max(1, (len(items) + PAGE_SIZE - 1) // PAGE_SIZE)
    if "queue_page" not in st.session_state:
        st.session_state.queue_page = 1
    page = min(st.session_state.queue_page, total_pages)

    pc1, pc2, pc3 = st.columns([1, 2, 1])
    with pc1:
        if st.button("← Prev page", disabled=page <= 1, key="queue_prev"):
            st.session_state.queue_page = max(1, page - 1)
            st.rerun()
    with pc2:
        st.markdown(f"<div style='text-align:center'>Página <b>{page}</b> de <b>{total_pages}</b></div>", unsafe_allow_html=True)
    with pc3:
        if st.button("Next page →", disabled=page >= total_pages, key="queue_next"):
            st.session_state.queue_page = min(total_pages, page + 1)
            st.rerun()

    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    page_items = items[start:end]

    # Render list — Ops s13+: 1 card por SKU (modelo independiente)
    modelo_label_map = {
        "fan_adult": "Fan", "player_adult": "Player", "retro_adult": "Retro",
        "woman": "Mujer", "kid": "Niño", "baby": "Bebé",
    }
    sleeve_label_map = {"short": "manga corta", "long": "manga larga"}

    for i, it in enumerate(page_items):
        with st.container(border=True):
            row = st.columns([1, 3, 2, 1, 1, 1])
            hero = it.get("hero")
            with row[0]:
                if hero:
                    st.image(hero, width=80)
                if it.get("n_photos"):
                    st.caption(f"📷 {it['n_photos']}")
            with row[1]:
                tier_badge = TIER_LABELS.get(it.get("tier"), "❓ Sin tier")
                qa_badge = " · 🎯 **QA**" if it.get("qa_priority") else ""
                st.markdown(f"**`{it['sku']}`**{qa_badge}  \n{tier_badge}")
                team = it.get("team") or ""
                season = it.get("season") or ""
                variant_label = it.get("variant_label") or it.get("variant") or ""
                # Modelo descriptivo
                mt = it.get("modelo_type")
                sl = it.get("sleeve")
                modelo_desc = ""
                if mt:
                    modelo_desc = modelo_label_map.get(mt, mt)
                    if sl and mt in ("fan_adult", "player_adult", "retro_adult"):
                        modelo_desc += f" {sleeve_label_map.get(sl, sl)}"
                elif it.get("category") and it.get("category") != "adult":
                    modelo_desc = f"[{it['category']}]"
                label = f"{team} · {season} · {variant_label}"
                if modelo_desc:
                    label += f" · **{modelo_desc}**"
                st.markdown(label)
                if it.get("sizes") or it.get("price"):
                    st.caption(f"{it.get('sizes') or '—'} · Q{it.get('price') or '—'}")
            with row[2]:
                status = it.get("status", "pending")
                emoji = {"pending": "⏳", "verified": "🟢", "flagged": "🔴",
                         "skipped": "⏭️", "needs_rework": "⚠️",
                         "deleted": "🗑"}.get(status, "?")
                st.markdown(f"{emoji} **{status}**")
            with row[3]:
                if st.button("Abrir", key=f"open_{it['sku']}", type="primary"):
                    st.session_state.audit_view = "detail"
                    st.session_state.current_family = it["sku"]
                    st.rerun()
            with row[4]:
                current_tier = it.get("tier") or "(sin)"
                new_tier = st.selectbox(
                    "Tier",
                    ["(sin)"] + TIERS,
                    index=(["(sin)"] + TIERS).index(current_tier) if current_tier in (["(sin)"] + TIERS) else 0,
                    key=f"tier_{it['sku']}",
                    label_visibility="collapsed",
                )
                if new_tier != current_tier:
                    audit_db.upsert_decision(
                        conn, it["sku"],
                        tier=None if new_tier == "(sin)" else new_tier,
                    )
                    st.rerun()
            with row[5]:
                if st.button("⏭️", key=f"skip_{it['sku']}", help="Skip"):
                    audit_db.upsert_decision(
                        conn, it["sku"],
                        status="skipped",
                        decided_at=datetime.now().isoformat(timespec="seconds"),
                    )
                    st.rerun()


# ═══════════════════════════════════════
# VIEW 2: Audit Detail (producto madre)
# ═══════════════════════════════════════

def render_detail(conn, catalog):
    """Ops s13+ — detail de UN SKU (un modelo auditable) con sus fotos propias.
    No hay tabs: cada SKU es una vista independiente. Flechas ← → navegan al
    pending anterior/siguiente del mismo scope.
    """
    sku = st.session_state.get("current_family")
    if not sku:
        st.warning("No hay item seleccionado.")
        if st.button("← Volver al queue"):
            st.session_state.audit_view = "queue"
            st.rerun()
        return

    sku_idx = audit_db.build_sku_index(catalog)
    resolved = sku_idx.get(sku)
    if not resolved:
        st.error(f"SKU `{sku}` no encontrado en catalog.json")
        if st.button("← Volver al queue"):
            st.session_state.audit_view = "queue"
            st.rerun()
        return
    fam, modelo = resolved

    # Telemetry hook (por SKU)
    audit_db.telemetry_open(sku)

    deci = audit_db.get_decision(conn, sku) or {}
    tier = deci.get("tier")
    status = deci.get("status", "pending")

    # Header
    team = fam.get("team") or ""
    season = fam.get("season") or ""
    variant_label = fam.get("variant_label") or fam.get("variant") or ""
    modelo_type = (modelo or {}).get("type") if modelo else fam.get("category", "legacy")
    sleeve = (modelo or {}).get("sleeve") if modelo else None
    modelo_label_map = {"fan_adult": "Fan", "player_adult": "Player",
                        "retro_adult": "Retro", "woman": "Mujer", "kid": "Niño", "baby": "Bebé"}
    sleeve_label_map = {"short": "manga corta", "long": "manga larga"}
    modelo_desc = modelo_label_map.get(modelo_type, modelo_type or "—")
    if sleeve and modelo_type in ("fan_adult", "player_adult", "retro_adult"):
        modelo_desc += f" {sleeve_label_map.get(sleeve, sleeve)}"

    hc1, hc2, hc3, hc4, hc5 = st.columns([4, 0.7, 0.7, 1, 1])
    with hc1:
        st.markdown(f"## {team} {season} — {variant_label} · {modelo_desc}")
        st.caption(f"SKU `{sku}` · {TIER_LABELS.get(tier, 'Sin tier')} · canonical `{fam['family_id']}`")
    with hc2:
        # Flecha ← anterior pending
        prev_sku = _find_adjacent_pending(conn, sku, direction=-1)
        if st.button("◀", key="nav_prev_pending", disabled=(prev_sku is None),
                     help="Anterior pending (K)", use_container_width=True):
            st.session_state.current_family = prev_sku
            st.rerun()
    with hc3:
        # Flecha → siguiente pending
        next_sku = _find_adjacent_pending(conn, sku, direction=1)
        if st.button("▶", key="nav_next_pending", disabled=(next_sku is None),
                     help="Siguiente pending (J)", use_container_width=True):
            st.session_state.current_family = next_sku
            st.rerun()
    with hc4:
        if st.button("← Queue", key="back_queue"):
            st.session_state.audit_view = "queue"
            st.rerun()
    with hc5:
        # Tier change
        tiers_opts = ["(sin)"] + TIERS
        idx = tiers_opts.index(tier) if tier in tiers_opts else 0
        new_tier = st.selectbox("Tier", tiers_opts, index=idx, key="detail_tier",
                                label_visibility="collapsed")
        if new_tier != (tier or "(sin)"):
            audit_db.upsert_decision(conn, sku,
                                      tier=None if new_tier == "(sin)" else new_tier)
            st.rerun()

    # Link a PDP live (canonical family para que matchee la URL de vault)
    live_url = f"https://vault.elclub.club/producto?id={fam['family_id']}"
    st.link_button(f"🔗 Ver live {fam['family_id']}", live_url,
                   help="Abre la PDP del producto madre en vault.elclub.club (Ctrl+L)")
    st.markdown(
        f'<span id="audit-live-url" data-live-url="{live_url}" style="display:none"></span>',
        unsafe_allow_html=True,
    )

    _render_shortcuts_box()
    st.markdown("")

    # Panel specs editable (scope: esta family / este modelo)
    _render_scraped_specs_panel(fam, modelo_idx=_find_modelo_idx(fam, sku))

    # Render el modelo — fotos + acciones + checks + verify/flag
    modelo_view = _modelo_view_for_audit(sku, fam, modelo)
    _render_photos_and_actions(conn, modelo_view, form_key_prefix=sku)
    # Ops s14: pasamos catalog_fam + modelo para habilitar botón 🗑 BORRAR SKU
    _render_family_checks_and_verify(conn, {"family_id": sku},
                                      catalog_fam=fam, modelo=modelo)

    # Ops s14 — inject shortcut bindings + preview modal. Antes de s14 esto vivía
    # sólo en el dead _render_variant_form. Moverlo acá habilita V/F/X/W/G/↑↓
    # + el nuevo Shift+D para borrar en el camino activo.
    components.html(
        PHOTO_FOCUS_CSS + KEYBOARD_JS + PREVIEW_MODAL_HTML,
        height=0,
    )
    _inject_tag_script({
        "VERIFY": "verify-current",
        "FLAG": "flag-current",
        "BORRAR SKU": "delete-sku",
    })


def _find_modelo_idx(fam, sku):
    """Retorna el índice del modelo en fam.modelos con SKU dado, o None."""
    modelos = fam.get("modelos") or []
    for i, m in enumerate(modelos):
        if m.get("sku") == sku:
            return i
    return None


def _modelo_view_for_audit(sku, fam, modelo):
    """Construye la 'vista' con family_id=SKU + gallery/hero del modelo (o del
    fam si legacy). _render_photos_and_actions escribe/lee audit_photo_actions
    keyed por SKU, así que cada modelo tiene sus acciones independientes.
    """
    if modelo:
        return {
            "family_id": sku,
            "gallery": modelo.get("gallery") or [],
            "hero_thumbnail": modelo.get("hero_thumbnail"),
            "team": fam.get("team"),
            "season": fam.get("season"),
            "variant": fam.get("variant"),
        }
    # Legacy
    return {
        "family_id": sku,
        "gallery": fam.get("gallery") or [],
        "hero_thumbnail": fam.get("hero_thumbnail"),
        "team": fam.get("team"),
        "season": fam.get("season"),
        "variant": fam.get("variant"),
    }


def _find_adjacent_pending(conn, current_sku, direction=1):
    """Retorna el SKU del próximo (direction=1) o anterior (direction=-1) item
    con status='pending' en el MISMO tier (o en el global order si current no tiene tier).
    Sort: tier asc, family_id asc (mismo orden que queue_families).
    """
    q = """
        SELECT family_id FROM audit_decisions
        WHERE status='pending'
        ORDER BY
          CASE tier
            WHEN 'T1' THEN 1 WHEN 'T2' THEN 2 WHEN 'T3' THEN 3
            WHEN 'T4' THEN 4 WHEN 'T5' THEN 5 ELSE 6
          END ASC, family_id ASC
    """
    rows = [r["family_id"] for r in conn.execute(q).fetchall()]
    if not rows: return None
    if current_sku not in rows:
        # Not in pending list → return first pending
        return rows[0] if direction > 0 else rows[-1]
    i = rows.index(current_sku)
    j = i + direction
    if 0 <= j < len(rows):
        return rows[j]
    return None


VARIANT_OPTIONS = ["home", "away", "third", "special", "goalkeeper", "training"]
MODELO_TYPE_OPTIONS = ["fan_adult", "player_adult", "retro_adult", "woman", "kid", "baby"]
SLEEVE_OPTIONS = ["short", "long"]

# Mapeo variant → variant_label (denormalizado en catalog para UI frontend)
_VARIANT_LABEL_MAP = {
    "home": "Local", "away": "Visita", "third": "Reserva",
    "special": "Especial", "goalkeeper": "Portero", "training": "Training",
}


def _save_family_edits(family_id, new_team, new_season, new_variant, modelo_edits=None):
    """Ops s13 — persiste ediciones manuales a catalog.json para una family.
    Escribe sólo los campos que cambiaron. modelo_edits es lista de (type, sleeve)
    por modelo (None si family legacy).

    Retorna dict {ok, fields: [list of changed field names], error}
    """
    catalog_path = audit_db.CATALOG_PATH
    if not os.path.exists(catalog_path):
        return {"ok": False, "error": f"catalog.json no existe en {catalog_path}"}

    try:
        with open(catalog_path, "r", encoding="utf-8") as f:
            catalog = json.load(f)
    except Exception as e:
        return {"ok": False, "error": f"Error leyendo catalog: {e}"}

    target = None
    for fam in catalog:
        if fam.get("family_id") == family_id:
            target = fam
            break
    if not target:
        return {"ok": False, "error": f"family_id '{family_id}' no encontrado en catalog.json"}

    changed_fields = []

    # Top-level keys
    if new_team and new_team != (target.get("team") or ""):
        target["team"] = new_team
        changed_fields.append("team")
    if new_season and new_season != (target.get("season") or ""):
        target["season"] = new_season
        changed_fields.append("season")
    if new_variant and new_variant != (target.get("variant") or ""):
        target["variant"] = new_variant
        target["variant_label"] = _VARIANT_LABEL_MAP.get(new_variant, new_variant)
        changed_fields.append("variant")

    # Modelos
    if modelo_edits and target.get("modelos"):
        for i, (new_type, new_sleeve) in enumerate(modelo_edits):
            if i >= len(target["modelos"]):
                continue
            m = target["modelos"][i]
            if new_type and new_type != (m.get("type") or ""):
                m["type"] = new_type
                changed_fields.append(f"modelos[{i}].type")
            if new_sleeve and new_sleeve != (m.get("sleeve") or ""):
                m["sleeve"] = new_sleeve
                changed_fields.append(f"modelos[{i}].sleeve")

    if not changed_fields:
        return {"ok": True, "fields": []}  # Nothing to persist

    try:
        with open(catalog_path, "w", encoding="utf-8") as f:
            json.dump(catalog, f, ensure_ascii=False, indent=2)
            f.write("\n")
    except Exception as e:
        return {"ok": False, "error": f"Error escribiendo catalog: {e}"}

    return {"ok": True, "fields": changed_fields}


def _render_scraped_specs_panel(fam, modelo_idx=None):
    """Ops s13 — panel editable con datos del scrape + unificación.

    Si `modelo_idx` se provee, SOLO muestra editable ese modelo (el contexto
    del SKU abierto). Si None, muestra todos los modelos (legacy multi-tab behavior).
    """
    fid = fam.get("family_id", "")
    is_unified = bool(fam.get("modelos"))

    with st.expander("📋 Datos del scrape (editable)", expanded=True):
        st.caption(f"`family_id` (no editable): `{fid}` · categoría: `{fam.get('category', '—')}` · tier: `{fam.get('tier', '—')}`")

        # ── Llave de unificación (team, season, variant) ──
        st.markdown("**🔑 Llave de unificación** — si estas 3 coinciden en otra family, son la misma camisa.")
        k1, k2, k3 = st.columns([2, 1, 1])
        with k1:
            new_team = st.text_input("Equipo", value=fam.get("team") or "", key=f"edit_team_{fid}")
        with k2:
            new_season = st.text_input("Temporada / año", value=fam.get("season") or "", key=f"edit_season_{fid}")
        with k3:
            cur_variant = fam.get("variant") or "home"
            options = list(VARIANT_OPTIONS)
            if cur_variant not in options:
                options.append(cur_variant)
            new_variant = st.selectbox("Variante", options, index=options.index(cur_variant), key=f"edit_variant_{fid}")

        # ── Metadata secundaria (read-only) ──
        st.caption(
            f"🌐 country: **{fam.get('meta_country') or '—'}** · "
            f"league: {fam.get('meta_league') or '—'} · "
            f"confederation: {fam.get('meta_confederation') or '—'} · "
            f"featured: `{fam.get('featured', False)}`"
        )

        # ── Modelos (editable type + sleeve) o variants legacy ──
        modelos = fam.get("modelos") or []
        # Ops s13+ — si modelo_idx especificado, solo mostrar ese modelo
        visible_indices = range(len(modelos))
        if modelo_idx is not None and 0 <= modelo_idx < len(modelos):
            visible_indices = [modelo_idx]
        modelo_edits = []  # lista de (nuevo_type, nuevo_sleeve) por modelo (completa — None si skip)
        if is_unified:
            if modelo_idx is not None:
                st.markdown(f"**🧥 Modelo actual (foco)** — ajustá type/sleeve si está mal clasificado.")
            else:
                st.markdown(f"**🧥 Modelos ({len(modelos)})** — ajustá type/sleeve si algo está mal clasificado.")
            unified_from = fam.get("_unified_from") or []
            if len(unified_from) > 1:
                st.caption(f"_unificó:_ {' + '.join(f'`{x}`' for x in unified_from)}")

            # Inicializar modelo_edits con valores actuales (para los no-visibles, copia actual)
            modelo_edits = [(m.get("type"), m.get("sleeve")) for m in modelos]
            for i in visible_indices:
                m = modelos[i]
                mc1, mc2, mc3, mc4, mc5 = st.columns([2, 1, 1.2, 1.5, 2])
                with mc1:
                    cur_type = m.get("type") or "fan_adult"
                    opts = list(MODELO_TYPE_OPTIONS)
                    if cur_type not in opts:
                        opts.append(cur_type)
                    new_type = st.selectbox(
                        f"Modelo {i+1} — type", opts, index=opts.index(cur_type),
                        key=f"edit_mtype_{fid}_{i}",
                    )
                with mc2:
                    cur_sleeve = m.get("sleeve") or "short"
                    opts_s = list(SLEEVE_OPTIONS)
                    if cur_sleeve not in opts_s:
                        opts_s.append(cur_sleeve)
                    new_sleeve = st.selectbox(
                        "sleeve", opts_s, index=opts_s.index(cur_sleeve),
                        key=f"edit_msleeve_{fid}_{i}",
                    )
                with mc3:
                    st.caption(f"sizes: `{m.get('sizes') or '—'}`")
                    st.caption(f"Q{m.get('price') or '—'}")
                with mc4:
                    st.caption(f"src: `{m.get('source_family_id') or '—'}`")
                with mc5:
                    yupoo = m.get("source_url_yupoo")
                    if yupoo:
                        st.markdown(f"[Yupoo ↗]({yupoo})")
                    n_gallery = len(m.get("gallery") or [])
                    st.caption(f"{n_gallery} fotos")
                    # Mostrar el SKU del modelo
                    if m.get("sku"):
                        st.caption(f"SKU: `{m['sku']}`")
                modelo_edits[i] = (new_type, new_sleeve)
        else:
            # Legacy family — muestra variants[] read-only
            variants = fam.get("variants") or []
            if variants:
                st.markdown("**🧥 Variantes (legacy — no editable)**")
                for v in variants:
                    sub_type = v.get("sub_type")
                    sub_part = f" / sub_type=`{sub_type}`" if sub_type else ""
                    line = (
                        f"- `{v.get('type', '—')}`{sub_part}"
                        f" · sizes: `{v.get('sizes') or 'null'}`"
                        f" · Q{v.get('price', '—')}"
                    )
                    album_id = v.get("album_id")
                    if album_id:
                        store = v.get("store", "minkang")
                        line += f" · [Yupoo ↗](https://{store}.x.yupoo.com/albums/{album_id})"
                    st.markdown(line)

        # ── Botón guardar ──
        st.markdown("")
        if st.button("💾 Guardar cambios a catalog.json", key=f"save_edits_{fid}",
                     type="secondary", use_container_width=True):
            changes = _save_family_edits(
                fid,
                new_team=new_team.strip(),
                new_season=new_season.strip(),
                new_variant=new_variant,
                modelo_edits=modelo_edits if is_unified else None,
            )
            if changes["ok"]:
                st.success(f"✅ Guardado. Campos modificados: {', '.join(changes['fields']) or '(ninguno)'}")
                st.rerun()
            else:
                st.error(f"❌ {changes['error']}")

        # Texto actual (title/description/historia) si existen (de un audit previo)
        title = fam.get("title")
        desc = fam.get("description")
        hist = fam.get("historia")
        if any((title, desc, hist)):
            st.markdown("**✍️ Texto actual (si hay)**")
            if title:
                st.markdown(f"- **title**: {title}")
            if desc:
                st.markdown(f"- **description**: {desc}")
            if hist:
                st.markdown(f"- **historia**: {hist[:200]}{'…' if len(hist) > 200 else ''}")

    st.markdown("---")

    # Global action bar
    st.markdown("### Acciones globales")
    ac1, ac2, ac3, ac4, ac5 = st.columns(5)
    with ac1:
        if st.button("🟢 VERIFY TODAS (⇧V)", key="verify_all", type="primary", use_container_width=True):
            for fam in variants.values():
                audit_db.upsert_decision(
                    conn, fam["family_id"],
                    status="verified",
                    decided_at=datetime.now().isoformat(timespec="seconds"),
                )
            st.success("Todas las variantes verificadas.")
            st.rerun()
    with ac2:
        if st.button("🔴 FLAG TODAS (⇧F)", key="flag_all", use_container_width=True):
            for fam in variants.values():
                audit_db.upsert_decision(
                    conn, fam["family_id"],
                    status="flagged",
                    decided_at=datetime.now().isoformat(timespec="seconds"),
                )
            st.rerun()
    with ac3:
        if st.button("⏭️ SKIP (S)", key="skip_prod", use_container_width=True):
            for fam in variants.values():
                audit_db.upsert_decision(
                    conn, fam["family_id"],
                    status="skipped",
                    decided_at=datetime.now().isoformat(timespec="seconds"),
                )
            st.rerun()
    with ac4:
        if st.button("← Prev (K)", key="prev_prod", use_container_width=True):
            _jump_product(conn, catalog, direction=-1)
    with ac5:
        if st.button("Next → (J)", key="next_prod", use_container_width=True):
            _jump_product(conn, catalog, direction=1)

    # Inject shortcut bindings + preview modal — CSS + JS juntos para que el JS encuentre
    # los <style> en el iframe y los copie al parent document (una sola vez por lifecycle).
    components.html(
        PHOTO_FOCUS_CSS + KEYBOARD_JS + PREVIEW_MODAL_HTML,
        height=0,
    )
    _inject_tag_script({
        "VERIFY TODAS": "verify-all",
        "FLAG TODAS": "flag-all",
        "SKIP (S)": "skip",
        "Prev (K)": "prev",
        "Next → (J)": "next",
    })


def _jump_product(conn, catalog, direction=1):
    """Next/prev producto madre (solo Tier pending)."""
    items = audit_db.queue_families(conn, catalog)
    items = [i for i in items if i.get("status") == "pending"]
    current = st.session_state.get("current_family")
    if not items:
        return
    ids = [i["family_id"] for i in items]
    current_mother = audit_db.mother_family_id(current) if current else None
    if current_mother in ids:
        idx = ids.index(current_mother)
        new_idx = (idx + direction) % len(ids)
    else:
        new_idx = 0
    st.session_state.current_family = ids[new_idx]
    st.rerun()


def _render_variant_form(conn, fam):
    """Form para auditar UNA family. Ops s13: si family tiene `modelos[]`, renderiza
    tabs por modelo; cada tab muestra la gallery del modelo + acciones por foto.
    Legacy (sin modelos): comportamiento original sobre fam.gallery.

    Acciones por foto se persisten con family_id = modelo.source_family_id (el pre-unify).
    Esto preserva disambiguación: fan_adult + kid comparten canonical pero tienen
    galleries distintas → rows independientes en audit_photo_actions.
    """
    fid = fam["family_id"]
    modelos = fam.get("modelos") or []

    if modelos:
        _render_unified_form(conn, fam, modelos)
    else:
        _render_legacy_form(conn, fam)


def _render_unified_form(conn, fam, modelos):
    """Ops s13 — render tabs por modelo para unified families."""
    fid = fam["family_id"]
    # Label por modelo: "Fan adult · S-XXL · Q435" etc
    def _label(i, m):
        t = m.get("type", "?").replace("_", " ").title()
        sleeve = "·L" if m.get("sleeve") == "long" else ""
        sz = m.get("sizes") or "—"
        price = f"Q{m.get('price')}" if m.get("price") else ""
        return f"{t}{sleeve} · {sz} {price}".strip().rstrip("·")
    tab_labels = [_label(i, m) for i, m in enumerate(modelos)]
    tabs = st.tabs(tab_labels)

    for i, (tab, m) in enumerate(zip(tabs, modelos)):
        with tab:
            # modelo → mini "family-view" cargando gallery/hero del modelo pero
            # escribiendo acciones bajo su source_family_id efectivo.
            effective_fid = m.get("source_family_id") or fid
            modelo_view = {
                "family_id": effective_fid,
                "gallery": m.get("gallery") or [],
                "hero_thumbnail": m.get("hero_thumbnail"),
                # Fallback opcional: si hay metadata que el form legacy consulte
                "team": fam.get("team"),
                "season": fam.get("season"),
                "variant": fam.get("variant"),
            }
            _render_photos_and_actions(conn, modelo_view, form_key_prefix=f"{fid}__{i}")

    # Checks globales + verify/flag para TODA la family (Ops s13 conserva 1 set
    # por producto madre, no por modelo).
    _render_family_checks_and_verify(conn, fam)


def _render_legacy_form(conn, fam):
    """Legacy — family sin modelos[]. Usa fam.gallery directo."""
    _render_photos_and_actions(conn, fam, form_key_prefix=fam["family_id"])
    _render_family_checks_and_verify(conn, fam)


def _render_photos_and_actions(conn, fam, form_key_prefix):
    """Renderiza grid de fotos + acciones por-foto. fam puede ser real o modelo-view.
    Writes/reads audit_photo_actions con fam['family_id'] (que es el effective_fid
    de modelo si viene del unified form).
    """
    fid = fam["family_id"]
    gallery = fam.get("gallery") or []
    current_hero = fam.get("hero_thumbnail")

    # Cargar acciones existentes (keyed por el fid efectivo del modelo o family)
    saved_actions = {a["original_index"]: a for a in audit_db.get_photo_actions(conn, fid)}

    if not gallery:
        st.warning("Esta variante no tiene galería. Hero único:")
        if current_hero:
            st.image(current_hero, width=240)
        st.info("Las acciones por foto requieren galería. Solo se puede verificar/flaggear la variante.")
        return

    # Decoder UI para cada foto
    st.caption(f"{len(gallery)} fotos en galería · click para ampliar · ↑↓ reordenar · 👑 set hero")
    # Computar display order actual (excluyendo deletes) — fuente de verdad para ↑↓ swap.
    non_deleted = [
        i for i in range(len(gallery))
        if saved_actions.get(i, {}).get("action") != "delete"
    ]
    def _sort_key(i):
        ni = saved_actions.get(i, {}).get("new_index")
        return (ni if ni is not None else i, i)
    display_order = sorted(non_deleted, key=_sort_key)
    display_pos_of = {idx: pos for pos, idx in enumerate(display_order)}

    cols_per_row = 4
    for row_start in range(0, len(gallery), cols_per_row):
        cols = st.columns(cols_per_row)
        for col_idx in range(cols_per_row):
            i = row_start + col_idx
            if i >= len(gallery):
                break
            with cols[col_idx]:
                _render_photo_card(conn, fid, i, gallery[i], saved_actions.get(i),
                                   current_hero, display_order=display_order,
                                   display_pos=display_pos_of.get(i),
                                   key_prefix=form_key_prefix)


@st.dialog("⚠️ BORRAR SKU permanentemente")
def _borrar_sku_dialog(sku, canonical_fid, source_fid, modelo_desc,
                        sizes, price, photo_count, actions_count, is_only_modelo):
    """Ops s14 — modal de confirmación de delete. Recibe snapshot de metadata
    (no conn ni fam) para evitar issues de lifecycle de Streamlit dialogs."""
    st.markdown(f"Estás por eliminar permanentemente:")
    st.markdown(f"- **SKU:** `{sku}`")
    st.markdown(f"- **{photo_count}** fotos en galería")
    st.markdown(f"- **{actions_count}** audit_photo_actions registradas")
    st.markdown(f"- **family:** `{canonical_fid}`")
    if modelo_desc:
        st.markdown(f"- **variant:** {modelo_desc}")
    if sizes or price:
        st.markdown(f"- **size:** {sizes or '—'} · Q{price or '—'}")

    if is_only_modelo:
        st.warning(
            "⚠️ Es el **único modelo** del family. Borrar → el family completo "
            "queda marcado `status=deleted` y sale del catálogo público."
        )

    st.info(
        "Si hay otro SKU hermano que debería absorber las fotos, **cancelá** "
        "y usá MERGE (feature s15). Soft-delete: audit_photo_actions permanece → "
        "recovery manual posible."
    )

    motivo = st.text_input(
        "Motivo (requerido)",
        key=f"del_motivo_{sku}",
        placeholder="Ej. Duplicado de ARG-2026-L-PS-2",
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Cancelar", key=f"del_cancel_{sku}", use_container_width=True):
            st.rerun()
    with c2:
        confirm_disabled = not (motivo or "").strip()
        if st.button("🗑 BORRAR", key=f"del_confirm_{sku}",
                     type="primary", use_container_width=True,
                     disabled=confirm_disabled):
            conn = audit_db.get_conn()
            catalog = audit_db.load_catalog()
            sku_idx = audit_db.build_sku_index(catalog)
            resolved = sku_idx.get(sku)
            if not resolved:
                st.error(f"SKU {sku} no encontrado en catalog (pudo ya estar borrado).")
                conn.close()
                return
            fam, modelo = resolved
            try:
                result = _delete_sku(conn, sku, fam, modelo, motivo.strip())
                # Capturar próximo pending ANTES de cerrar conn
                next_sku = _find_adjacent_pending(conn, sku, direction=1) if result.get("ok") else None
            finally:
                conn.close()
            if result.get("ok"):
                msg = [f"🗑 `{sku}` borrado."]
                if result["family_deleted"]:
                    msg.append("Family completo marcado deleted.")
                if result["was_published"]:
                    msg.append("commit+push " + ("✅" if result["committed"] else "⚠️ falló"))
                else:
                    msg.append("(no publicado → sin push, catalog mutado local)")
                st.session_state["audit_delete_toast"] = " · ".join(msg)
                # Navegar al siguiente pending o volver al queue
                if next_sku:
                    st.session_state.current_family = next_sku
                else:
                    st.session_state.audit_view = "queue"
                st.rerun()
            else:
                st.error(f"Error: {result.get('error') or 'delete falló'}")


def _render_family_checks_and_verify(conn, fam, catalog_fam=None, modelo=None):
    """Checks globales + verify/flag/needs-rework. UN solo set por producto madre.
    Se renderea fuera de los tabs de modelos (Ops s13) porque la decisión de
    audit es del producto completo, no por modelo.

    Ops s14: `catalog_fam` + `modelo` habilitan el botón 🗑 BORRAR SKU con
    snapshot de metadata para el dialog. Si no se pasan, el botón queda oculto
    (compat con call sites legacy).
    """
    fid = fam["family_id"]
    st.markdown("---")
    st.markdown("##### Checks globales")
    deci = audit_db.get_decision(conn, fid) or {}
    checks = {}
    try:
        checks = json.loads(deci.get("checks_json") or "{}")
    except Exception:
        checks = {}

    cc1, cc2, cc3 = st.columns(3)
    with cc1:
        fotos_ok = st.checkbox("✓ Fotos equipo correcto", value=bool(checks.get("fotos_equipo_ok")),
                                key=f"fotos_ok_{fid}")
    with cc2:
        cat_ok = st.checkbox("✓ Categoría correcta", value=bool(checks.get("categoria_ok")),
                              key=f"cat_ok_{fid}")
    with cc3:
        vers_ok = st.checkbox("✓ Versiones OK", value=bool(checks.get("versiones_ok")),
                               key=f"vers_ok_{fid}")

    notes = st.text_input("Notas", value=deci.get("notes", "") or "",
                          key=f"notes_{fid}", placeholder="Observaciones libres…")

    ba1, ba2 = st.columns(2)
    with ba1:
        if st.button(f"🟢 VERIFY {fid} (V)", key=f"verify_{fid}", type="primary", use_container_width=True):
            _save_variant_decision(conn, fid, "verified", fotos_ok, cat_ok, vers_ok, notes)
            st.success(f"Verificado: {fid}")
            st.rerun()
    with ba2:
        if st.button(f"🔴 FLAG {fid} (F)", key=f"flag_{fid}", use_container_width=True):
            _save_variant_decision(conn, fid, "flagged", fotos_ok, cat_ok, vers_ok, notes)
            st.rerun()

    # Ops s14 — Botón 🗑 BORRAR SKU (abre modal confirmación). Estilo secundario
    # + separado para evitar mis-clicks vs. VERIFY/FLAG.
    if catalog_fam is not None:
        st.markdown("")
        # Snapshot de metadata para el dialog (no se puede cerrar sobre vars del conn)
        canonical_fid = catalog_fam["family_id"]
        source_fid = (modelo or {}).get("source_family_id") or canonical_fid
        modelos = catalog_fam.get("modelos") or []
        is_only_modelo = bool(modelo and len(modelos) == 1)
        gallery = (modelo or {}).get("gallery") or catalog_fam.get("gallery") or []
        photo_count = len(gallery)
        actions_count = len(audit_db.get_photo_actions(conn, source_fid))
        # Descripción humana del modelo
        modelo_label_map = {"fan_adult": "Fan", "player_adult": "Player",
                            "retro_adult": "Retro", "woman": "Mujer",
                            "kid": "Niño", "baby": "Bebé"}
        sleeve_label_map = {"short": "corta", "long": "larga"}
        if modelo:
            mdesc = modelo_label_map.get(modelo.get("type"), modelo.get("type") or "—")
            sl = modelo.get("sleeve")
            if sl and modelo.get("type") in ("fan_adult", "player_adult", "retro_adult"):
                mdesc += f" · manga {sleeve_label_map.get(sl, sl)}"
        else:
            mdesc = catalog_fam.get("category") or "—"
        sizes = (modelo or {}).get("sizes") if modelo else None
        price = (modelo or {}).get("price") if modelo else None

        bd = st.columns([2, 1, 2])
        with bd[1]:
            if st.button("🗑 BORRAR SKU (⇧D)", key=f"del_sku_{fid}",
                         help="Borrar permanentemente el SKU (duplicado, error, etc.) — soft-delete reversible",
                         use_container_width=True):
                _borrar_sku_dialog(
                    fid, canonical_fid, source_fid, mdesc,
                    sizes, price, photo_count, actions_count, is_only_modelo,
                )


def _render_photo_card(conn, fid, index, url, saved_action, current_hero,
                        display_order=None, display_pos=None, key_prefix=None):
    """Una foto con controles: delete, watermark, regen-Gemini, hero, reorder.

    Ops s11: display_order (lista de original_index en orden visual) y display_pos
    (int 0-indexed en display_order) son requeridos para ↑↓ swap con vecinos.
    Ops s13: key_prefix namespacea los botones para tabs por modelo (evita
    collision de keys entre modelo fan_adult idx=0 y kid idx=0).
    """
    action = (saved_action or {}).get("action", "keep")
    is_hero = bool((saved_action or {}).get("is_new_hero")) or (url == current_hero)
    # Prefix para keys Streamlit + data-photo-idx del anchor. Si no se pasa,
    # uso el fid solo (backward-compat con render legacy).
    kp = key_prefix or fid

    # Position visible: 1-indexed en display_order (ej "#3/5"). Fallback al idx original.
    if display_pos is not None and display_order:
        pos_label = f"#{display_pos + 1}/{len(display_order)}"
    else:
        pos_label = f"#{index + 1}"
    crown = "👑" if is_hero else pos_label

    # Anchor para keyboard shortcuts y preview modal (Tarea 1+2 de Ops s10).
    # KEYBOARD_JS usa `data-photo-idx` para saber qué foto está focusada y
    # dispatchar X/W/G/Enter/↑↓ a los botones de ESTE column.
    st.markdown(
        f'<div class="audit-photo-anchor-wrap">'
        f'<span class="audit-photo-anchor" data-photo-idx="{index}" data-photo-kp="{kp}" data-photo-fid="{fid}" data-photo-url="{url}"></span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Image
    st.image(url, use_container_width=True)

    # Status badge
    badge_map = {
        "keep": "", "delete": "❌ delete",
        "flag_watermark": "⚠️ watermark",
        "flag_regen": "🎨 regen",
    }
    badge = badge_map.get(action, "")
    st.caption(f"{crown} {badge}")

    # Controls row
    bc = st.columns(4)
    with bc[0]:
        if st.button("👑", key=f"hero_{kp}_{index}", help="Set hero"):
            _set_hero(conn, fid, url, index)
            st.rerun()
    with bc[1]:
        if st.button("❌", key=f"del_{kp}_{index}", help="Delete foto"):
            audit_db.set_photo_action(conn, fid, url, index, action="delete")
            st.rerun()
    with bc[2]:
        if st.button("⚠️", key=f"wm_{kp}_{index}", help="Flag watermark"):
            audit_db.set_photo_action(conn, fid, url, index, action="flag_watermark")
            st.rerun()
    with bc[3]:
        if st.button("🎨", key=f"regen_{kp}_{index}", help="Flag regen manual (calidad mala, Diego la rehace aparte)"):
            audit_db.set_photo_action(conn, fid, url, index, action="flag_regen")
            st.rerun()

    # Reorder con flechas ↑↓ (Ops s11) — swap con foto adyacente en display_order.
    # Requiere display_order + display_pos del parent. Si la foto está deleteada
    # o sin contexto, no muestra flechas.
    if display_order is not None and display_pos is not None and action != "delete":
        rc = st.columns(2)
        is_first = (display_pos == 0)
        is_last = (display_pos == len(display_order) - 1)
        with rc[0]:
            if st.button("↑", key=f"up_{kp}_{index}", disabled=is_first, use_container_width=True,
                         help="Subir una posición (swap con anterior)"):
                _swap_photos(conn, fid, display_order, display_pos, display_pos - 1)
                st.rerun()
        with rc[1]:
            if st.button("↓", key=f"dn_{kp}_{index}", disabled=is_last, use_container_width=True,
                         help="Bajar una posición (swap con siguiente)"):
                _swap_photos(conn, fid, display_order, display_pos, display_pos + 1)
                st.rerun()

    # Reset a keep
    if action in ("delete", "flag_watermark", "flag_regen"):
        if st.button("↺ reset", key=f"reset_{kp}_{index}"):
            audit_db.set_photo_action(conn, fid, url, index, action="keep")
            st.rerun()


def _swap_photos(conn, fid, display_order, pos_a, pos_b):
    """Swap dos fotos adyacentes reescribiendo new_index para TODA la galería.
    Esto asegura orden estable: pre-swap algunas fotos pueden tener new_index=None
    (default) y el sort las coloca por original_index. Post-swap asignamos new_index
    explícito a cada foto de display_order, para que sucesivos swaps funcionen bien.
    """
    # Reordenar display_order mutando una copia
    new_order = list(display_order)
    new_order[pos_a], new_order[pos_b] = new_order[pos_b], new_order[pos_a]
    # Cargar estado actual para preservar action / is_new_hero / processed_url / original_url
    existing = {a["original_index"]: a for a in audit_db.get_photo_actions(conn, fid)}
    for new_pos, orig_idx in enumerate(new_order):
        row = existing.get(orig_idx, {})
        audit_db.set_photo_action(
            conn, fid,
            original_url=row.get("original_url") or "",  # vacío si nunca tuvo row
            original_index=orig_idx,
            action=row.get("action") or "keep",
            new_index=new_pos,
            is_new_hero=row.get("is_new_hero") or 0,
            processed_url=row.get("processed_url"),
        )


def _set_hero(conn, fid, url, index):
    """Marca una foto como hero. Desmarca las demás."""
    # Clear previous hero flags
    conn.execute(
        "UPDATE audit_photo_actions SET is_new_hero = 0 WHERE family_id = ?", (fid,)
    )
    conn.commit()
    # Upsert new
    audit_db.set_photo_action(
        conn, fid, url, index,
        action="keep", is_new_hero=1,
    )


def _save_variant_decision(conn, fid, status, fotos_ok, cat_ok, vers_ok, notes):
    checks = {
        "fotos_equipo_ok": bool(fotos_ok),
        "categoria_ok": bool(cat_ok),
        "versiones_ok": bool(vers_ok),
    }
    audit_db.upsert_decision(
        conn, fid,
        status=status,
        checks_json=json.dumps(checks),
        notes=(notes or "").strip(),
        decided_at=datetime.now().isoformat(timespec="seconds"),
    )
    # Ops s11 — telemetry: al verify, registrar duration_sec para el mother_id.
    # Solo el mother_id es el "producto" para métricas (una variant no es un item
    # completo de audit).
    if status == "verified":
        mother_id = audit_db.mother_family_id(fid)
        audit_db.telemetry_verify(mother_id)


# ═══════════════════════════════════════
# VIEW 3: Pending Review (post-Claude)
# ═══════════════════════════════════════

def render_pending_review(conn, catalog):
    st.header("🤖 Pending Review (post-Claude)")
    st.caption("Items procesados por Claude esperando tu OK final antes de publicar.")

    # Button para correr batch Claude sobre los verified sin procesar
    br1, br2 = st.columns([1, 3])
    with br1:
        if st.button("▶️ Procesar batch con Claude", type="primary",
                     disabled=not audit_enrich.claude_available()):
            _run_claude_batch(conn, catalog)
            st.rerun()
    with br2:
        if not audit_enrich.claude_available():
            st.warning("⚠️ ANTHROPIC_API_KEY no configurada. Seteá en `erp/.env`.")
        else:
            # Count verified sin pending review
            cnt = conn.execute(
                """SELECT COUNT(*) FROM audit_decisions d
                   LEFT JOIN pending_review p ON d.family_id = p.family_id
                   WHERE d.status = 'verified' AND p.family_id IS NULL"""
            ).fetchone()[0]
            st.info(f"{cnt} verified esperando enriquecimiento Claude")

    pending = audit_db.list_pending_reviews(conn)
    st.caption(f"{len(pending)} items en pending review.")

    if not pending:
        st.info("Vacío. Verificá items en el queue y procesa con Claude.")
        return

    # Ops s11 — Batch publish button. Items elegibles: pending_review sin approved_at
    # que tengan final_verified=1 en audit_decisions (explícito, o implícito si status=verified).
    unapproved = [p for p in pending if not p.get("approved_at")]
    bp1, bp2 = st.columns([1, 3])
    with bp1:
        batch_disabled = len(unapproved) == 0
        if st.button(
            f"✅ Publish all verified ({len(unapproved)})",
            type="primary", disabled=batch_disabled, use_container_width=True,
            key="batch_publish_all",
            help="Procesa en secuencia todos los items del pending review. Si un item falla, el batch para ahí."
        ):
            _run_batch_publish(conn, catalog, unapproved)
            st.rerun()
    with bp2:
        st.caption("Procesa cada item: apply Claude enrichment + Gemini watermark (retry interno) + commit + push. Si Gemini falla en alguna foto, el item se marca `needs_rework` y el batch para — los items previos quedan publicados.")

    # Fix s14m3: pending_review.family_id es SKU post-s13. Resolve via sku_idx
    # para obtener el canonical fam (donde están title/description/historia/
    # gallery). Antes get_family(SKU) retornaba None → no se renderizaba nada.
    sku_idx = audit_db.build_sku_index(catalog)

    for item in pending:
        fid = item["family_id"]
        resolved = sku_idx.get(fid)
        if resolved:
            fam, _modelo = resolved
        else:
            fam = audit_db.get_family(catalog, fid)  # legacy fallback
        if not fam:
            st.warning(f"⚠️ {fid}: no resuelve en catalog (drift)")
            continue

        with st.expander(f"{fid}  ·  {TIER_LABELS.get(item.get('tier'), 'Sin tier')}",
                          expanded=False):
            _render_pending_preview(conn, fam, item)


def _run_batch_publish(conn, catalog, items):
    """Ops s11 — corre publish 1-a-1 sobre la lista de items pending review.
    Muestra progress bar + log streaming. Si un item falla (publish retorna por
    needs_rework u otro error), rompe el batch ahí.
    """
    if not items:
        st.info("Nada para publicar en batch.")
        return
    total = len(items)
    progress = st.progress(0.0, text=f"Batch publish: 0/{total}")
    log_area = st.empty()
    results = {"ok": [], "failed": [], "aborted": False}

    log_lines = []
    def _log(line):
        log_lines.append(line)
        log_area.code("\n".join(log_lines[-15:]))

    # Fix s14m3: pending_review.family_id es SKU. Resolve → canonical fam.
    # _publish_family espera canonical fam (muta catalog por canonical family_id).
    # audit_decisions sigue keyed por SKU (get_decision/upsert_decision usan SKU).
    sku_idx = audit_db.build_sku_index(catalog)

    for i, item in enumerate(items, start=1):
        fid = item["family_id"]  # SKU
        resolved = sku_idx.get(fid)
        if resolved:
            fam, modelo = resolved
        else:
            fam = audit_db.get_family(catalog, fid)
            modelo = None
        if not fam:
            _log(f"[{i}/{total}] {fid} — SKIP (no resuelve en catalog)")
            continue

        try:
            claude_data = json.loads(item.get("claude_enriched_json") or "{}")
        except Exception:
            claude_data = {}
        # Fix s14m6: photo_actions están keyed por SKU (la UI escribe con SKU
        # como fam.family_id). source_family_id = canonical para unified, NO
        # matchea las rows. Uso el SKU directamente.
        effective_fid = fid  # = SKU = item["family_id"]
        if modelo:
            fam_for_apply = {"family_id": effective_fid, "gallery": modelo.get("gallery") or []}
        else:
            fam_for_apply = fam
        new_gallery = _apply_photo_actions_to_gallery(
            conn, fam_for_apply, effective_fid=effective_fid,
        )

        _log(f"[{i}/{total}] {fid} — publishing…")
        pre_dec = audit_db.get_decision(conn, fid) or {}

        _publish_family(conn, fam, claude_data, new_gallery, featured=bool(fam.get("featured")), sku=fid)
        post_dec = audit_db.get_decision(conn, fid) or {}

        if post_dec.get("status") == "needs_rework" and pre_dec.get("status") != "needs_rework":
            _log(f"[{i}/{total}] {fid} — ❌ needs_rework (Gemini watermark fail). BATCH ABORTA.")
            results["failed"].append(fid)
            results["aborted"] = True
            break

        if post_dec.get("final_verified"):
            _log(f"[{i}/{total}] {fid} — ✅ publicado")
            results["ok"].append(fid)
        else:
            _log(f"[{i}/{total}] {fid} — ⚠️ no publicó (estado: {post_dec.get('status')}). BATCH ABORTA.")
            results["failed"].append(fid)
            results["aborted"] = True
            break

        progress.progress(i / total, text=f"Batch publish: {i}/{total}")

    # Resumen final
    progress.progress(1.0 if not results["aborted"] else (len(results["ok"]) / total),
                       text=f"Batch terminó: {len(results['ok'])}/{total} OK")
    if results["aborted"]:
        st.error(f"🚨 Batch abortado. Publicados OK: {len(results['ok'])}. Falló en: {results['failed'][-1] if results['failed'] else '?'}. Revisá el log + `audit_api_errors` + reintentá.")
    else:
        st.success(f"🎉 Batch completo. {len(results['ok'])}/{total} items publicados.")


def _run_claude_batch(conn, catalog):
    """Procesa todos los verified sin pending review.

    Fix s14m2: post-s13 audit_decisions.family_id es SKU, no canonical.
    `get_family(catalog, SKU)` retornaba None → families_ctx vacío → batch
    silencioso (Diego: "no carga nunca"). Ahora usa build_sku_index para
    resolver SKU → (canonical_fam, modelo) y construye fam-view con el
    SKU como family_id (para que Claude lo use en el output `sku` field).
    """
    rows = conn.execute(
        """SELECT d.family_id, d.checks_json, d.notes FROM audit_decisions d
           LEFT JOIN pending_review p ON d.family_id = p.family_id
           WHERE d.status = 'verified' AND p.family_id IS NULL
           LIMIT 50"""
    ).fetchall()

    if not rows:
        st.info("Nada para procesar.")
        return

    sku_idx = audit_db.build_sku_index(catalog)
    families_ctx = []
    skipped_unresolved = 0
    for r in rows:
        sku = r["family_id"]
        resolved = sku_idx.get(sku)
        fam = None
        modelo = None
        if resolved:
            fam, modelo = resolved
        else:
            # Legacy row: family_id tradicional (pre-migration)
            fam = audit_db.get_family(catalog, sku)
        if not fam:
            skipped_unresolved += 1
            continue
        # Build fam-view: shallow copy + family_id=SKU (para output Claude).
        # Inyecta metadata del modelo para que Claude genere description+historia
        # específicos (player vs fan vs kid, etc).
        fam_view = dict(fam)
        fam_view["family_id"] = sku
        if modelo:
            fam_view["_modelo_type"] = modelo.get("type")
            fam_view["_modelo_sleeve"] = modelo.get("sleeve")
            fam_view["_modelo_sizes"] = modelo.get("sizes")
            fam_view["_modelo_price"] = modelo.get("price")
        checks = {}
        try:
            checks = json.loads(r["checks_json"] or "{}")
        except Exception:
            pass
        families_ctx.append({
            "family": fam_view,
            "checks": checks,
            "notes": r["notes"] or "",
            "_sku": sku,                        # preservar para save_pending_review
            "_canonical": fam["family_id"],
            "_modelo": modelo,
        })

    if skipped_unresolved:
        st.warning(f"⚠️ {skipped_unresolved} SKUs saltados (no resolvieron a canonical — probable drift audit_decisions ↔ catalog)")
    if not families_ctx:
        st.error(f"Ninguno de los {len(rows)} verified se pudo resolver. Revisá el drift.")
        return

    # Fix s14m: progress bar con streaming en vez de spinner ciego. Antes el
    # spinner se quedaba infinito si algún request se colgaba (executor.map
    # eager + sin timeout). Ahora cada item completa → update progress.
    total = len(families_ctx)
    progress = st.progress(0.0, text=f"Procesando {total} items con Claude…")
    log_area = st.empty()
    log_lines = []

    def _on_progress(done, tot, fid, ok):
        log_lines.append(f"[{done}/{tot}] {fid}: {'✅' if ok else '❌'}")
        log_area.code("\n".join(log_lines[-12:]))
        progress.progress(done / tot, text=f"Claude batch: {done}/{tot}")

    results = audit_enrich.claude_enrich_batch(
        families_ctx, concurrency=3, on_progress=_on_progress, per_item_timeout=120,
    )
    progress.progress(1.0, text=f"Claude batch terminó: {total} items")

    # Fix s14m2: `fid` acá es SKU (no canonical). Para aplicar photo_actions
    # necesitamos el source_family_id del modelo (donde las photo_actions se
    # guardaron) o caer al canonical fam. save_pending_review keyed por SKU.
    ctx_by_sku = {c["_sku"]: c for c in families_ctx}

    ok_count = 0
    err_count = 0
    for fid, result in results.items():
        if result.get("ok"):
            ctx = ctx_by_sku.get(fid, {})
            canonical_fam = audit_db.get_family(catalog, ctx.get("_canonical"))
            modelo = ctx.get("_modelo")
            source_fid = (modelo or {}).get("source_family_id") or (canonical_fam or {}).get("family_id") or fid

            # Gallery del modelo (unified) o de la family (legacy)
            if modelo:
                base_gallery = modelo.get("gallery") or []
                fam_for_apply = {"family_id": source_fid, "gallery": base_gallery}
            else:
                fam_for_apply = canonical_fam or {"family_id": fid, "gallery": []}
            new_gallery = _apply_photo_actions_to_gallery(
                conn, fam_for_apply, effective_fid=source_fid,
            )
            hero_fallback = (modelo or canonical_fam or {}).get("hero_thumbnail")
            audit_db.save_pending_review(
                conn, fid,   # SKU keying
                claude_json=json.dumps(result["data"], ensure_ascii=False),
                gallery_json=json.dumps(new_gallery, ensure_ascii=False),
                new_hero=new_gallery[0] if new_gallery else hero_fallback,
            )
            ok_count += 1
        else:
            err_count += 1

    st.success(f"Claude procesó {ok_count} ok · {err_count} errores.")


def _apply_photo_actions_to_gallery(conn, fam, run_gemini_watermark=False, effective_fid=None):
    """Aplica las actions del audit_photo_actions a la gallery[] original.
    Retorna la nueva lista de URLs.

    Ops s13: `effective_fid` permite leer actions escritos bajo un family_id
    distinto al canonical (útil para unified modelos donde UI escribe con
    modelo.source_family_id). Si None, cae al canonical fam['family_id'].

    Si run_gemini_watermark=True:
      - Para cada foto con action=flag_watermark sin processed_url:
        - Descarga original de R2
        - Pasa por Gemini (remove watermark)
        - Sube processed a R2 con suffix -cleaned.jpg
        - Actualiza processed_url en audit_photo_actions
    Si run_gemini_watermark=False (preview mode): usa processed_url existente o url original.

    flag_regen NO dispara Gemini — es solo un marcador manual. Diego rehace
    esas fotos aparte y reemplaza el asset en R2 manualmente cuando tenga.
    """
    original = fam.get("gallery") or []
    fid_for_actions = effective_fid or fam["family_id"]
    actions_by_idx = {
        a["original_index"]: a for a in audit_db.get_photo_actions(conn, fid_for_actions)
    }

    # Build list of (new_index, url) skipping deletes
    kept = []
    hero_url = None
    for i, url in enumerate(original):
        a = actions_by_idx.get(i, {})
        action = a.get("action", "keep")
        if action == "delete":
            continue

        # Gemini watermark processing (solo al publicar, no al generar preview)
        processed = a.get("processed_url")
        if run_gemini_watermark and action == "flag_watermark" and not processed:
            processed = _process_watermark_with_gemini(conn, fid_for_actions, url, i)

        final_url = processed or url

        # Si está marcada hero, la ponemos primero
        if a.get("is_new_hero"):
            hero_url = final_url

        new_idx = a.get("new_index")
        kept.append((new_idx if new_idx is not None else i, final_url))

    # Sort por new_index (mismos índices preservan orden estable)
    kept.sort(key=lambda x: (x[0] if x[0] is not None else 999))
    new_gallery = [u for _, u in kept]

    # Si hay hero explícito, ponerlo primero
    if hero_url and hero_url in new_gallery:
        new_gallery.remove(hero_url)
        new_gallery.insert(0, hero_url)

    return new_gallery


def _process_watermark_with_gemini(conn, family_id, original_url, original_index):
    """Descarga foto, pasa por Gemini para remover watermark, sube processed a R2.
    Retorna el processed_url o None si falló. Ops s11: logging explícito de
    cada path de fallo en `audit_api_errors` para evitar failures silenciosos.
    """
    import requests

    def _fail(stage, detail):
        audit_db.log_api_error(
            family_id=family_id,
            photo_index=original_index,
            api="gemini_pipeline",
            error=f"{stage}: {detail}",
            attempt_n=1,
            final_failure=True,
        )
        return None

    # Fix s14o: usar LaMa local en vez de Gemini. Free, 10x más rápido, preserva
    # el resto de la imagen (Gemini re-generaba toda la foto). Fallback a Gemini
    # solo si LaMa no disponible (sin torch.cuda).
    import local_inpaint
    if not local_inpaint.local_inpaint_available():
        if not audit_enrich.gemini_available():
            return _fail("availability", "LaMa local ni Gemini disponibles")
        backend = "gemini"
    else:
        backend = "lama"

    # Strip query string (e.g. ?v=2026-04-22) para download raw
    clean_url = original_url.split("?")[0]

    try:
        resp = requests.get(clean_url, timeout=30)
        if resp.status_code != 200:
            return _fail("download", f"HTTP {resp.status_code} para {clean_url}")
        image_bytes = resp.content
    except Exception as exc:
        return _fail("download", f"{type(exc).__name__}: {exc}")

    if backend == "lama":
        result = local_inpaint.watermark_inpaint_bytes(
            image_bytes, mime_type="image/jpeg",
            family_id=family_id, photo_index=original_index,
        )
        if result.get("skipped") == "no_watermark_detected":
            # LaMa no detectó watermark — no upload, pero marcamos processed
            # para no re-intentar. processed_url = original URL (no cambia).
            audit_db.set_photo_action(
                conn, family_id, original_url, original_index,
                action="flag_watermark", processed_url=original_url,
            )
            return original_url
    else:
        result = audit_enrich.gemini_regen_image(
            image_bytes, mime_type="image/jpeg", prompt_variant="watermark",
            family_id=family_id, photo_index=original_index,
        )

    if not result.get("ok"):
        return _fail(f"{backend}_inpaint", result.get("error", "unknown"))

    # Key en R2: families/<fid>/<NN>-cleaned.jpg
    ord_str = f"{original_index + 1:02d}"
    key = f"families/{family_id}/{ord_str}-cleaned.jpg"
    upload = audit_enrich.upload_image_to_r2(result["image_bytes"], key,
                                              content_type=result.get("mime_type", "image/jpeg"))
    if not upload.get("ok"):
        return _fail("r2_upload", upload.get("error", "unknown"))

    new_url = upload["public_url"]
    # Save processed_url en la audit_photo_actions row
    audit_db.set_photo_action(
        conn, family_id, original_url, original_index,
        action="flag_watermark", processed_url=new_url,
    )
    return new_url


def _render_pending_preview(conn, fam, item):
    # Fix s14m4: fam es canonical (ej. 'argentina-2026-away'), pero puede haber
    # múltiples pending items del mismo canonical (ARG-V-FS + ARG-V-PS ambos
    # comparten canonical argentina-2026-away). Widget keys deben usar el SKU
    # para no colisionar. audit_decisions también keyed por SKU post-s13.
    canonical_fid = fam["family_id"]
    sku = item["family_id"]   # SKU usado para keys widget + audit_decisions lookups
    try:
        claude_data = json.loads(item.get("claude_enriched_json") or "{}")
    except Exception:
        claude_data = {}
    try:
        new_gallery = json.loads(item.get("new_gallery_json") or "[]")
    except Exception:
        new_gallery = []

    # photo_actions están keyed por source_family_id (del modelo) o canonical en legacy.
    # Para simplicidad leemos ambos y mergeamos.
    actions = audit_db.get_photo_actions(conn, canonical_fid)
    wm_pending = [a for a in actions if a.get("action") == "flag_watermark" and not a.get("processed_url")]
    regen_pending = [a for a in actions if a.get("action") == "flag_regen"]
    if wm_pending:
        st.info(f"💧 {len(wm_pending)} fotos con watermark → Gemini las procesa al click PUBLISH")
    if regen_pending:
        st.warning(
            f"🎨 {len(regen_pending)} fotos flaggeadas para REGEN MANUAL. "
            f"Diego: rehacelas aparte y sube a R2 con mismo path antes de publicar."
        )

    pc1, pc2 = st.columns([2, 3])
    with pc1:
        st.markdown("##### 📷 Gallery preview (post-audit)")
        if new_gallery:
            st.image(new_gallery[0], caption="Hero (01)", use_container_width=True)
            if len(new_gallery) > 1:
                thumb_cols = st.columns(min(4, len(new_gallery) - 1))
                for idx, url in enumerate(new_gallery[1:5]):
                    with thumb_cols[idx % len(thumb_cols)]:
                        st.image(url, caption=f"#{idx+2}", use_container_width=True)
    with pc2:
        st.markdown("##### 🤖 Claude suggested (factual only)")
        st.markdown(f"**Title:** {claude_data.get('title', '—')}")
        st.markdown(f"**SKU sugerido:** `{claude_data.get('sku', '—')}`")
        kw = claude_data.get("keywords", [])
        st.markdown(f"**Keywords:** {', '.join(kw) if kw else '—'}")
        val = claude_data.get("validation_issues", [])
        if val:
            st.warning(f"Validation: {', '.join(val)}")
        st.caption(
            "📝 Description + Historia no se generan automáticamente (Claude "
            "confundía 'Midnight Stadium' con el fabricante). Diego las rellena "
            "post-publish desde panel Publicados con deep research."
        )

    # Featured toggle — marca como "TOP" para el badge destacado en la Card del catálogo.
    # Key usa SKU (no canonical) para evitar duplicate key si múltiples pending
    # items comparten canonical family (ej. ARG-V-FS + ARG-V-PS).
    current_featured = bool(fam.get("featured", False))
    featured = st.checkbox(
        "⭐ Destacar (TOP badge en la Card)",
        value=current_featured,
        key=f"featured_{sku}",
        help="Marca esta family como TOP. El badge aparece en la Card del catálogo. Default: off.",
    )

    ac1, ac2, ac3 = st.columns(3)
    with ac1:
        if st.button(f"✅ PUBLISH", key=f"publish_{sku}", type="primary", use_container_width=True):
            _publish_family(conn, fam, claude_data, new_gallery, featured=featured, sku=sku)
            st.rerun()
    with ac2:
        if st.button(f"❌ REJECT", key=f"reject_{sku}", use_container_width=True):
            st.session_state[f"rejecting_{sku}"] = True
            st.rerun()
    with ac3:
        if st.button(f"🔄 Re-run Claude", key=f"rerun_{sku}", use_container_width=True):
            # audit_decisions keyed por SKU post-s13
            deci = audit_db.get_decision(conn, sku) or {}
            checks = json.loads(deci.get("checks_json") or "{}")
            r = audit_enrich.claude_enrich(fam, checks, deci.get("notes", ""))
            if r.get("ok"):
                audit_db.save_pending_review(
                    conn, sku,   # pending_review keyed por SKU
                    claude_json=json.dumps(r["data"], ensure_ascii=False),
                    gallery_json=item.get("new_gallery_json"),
                    new_hero=item.get("new_hero_url"),
                )
            else:
                st.error(r.get("error", "Error"))
            st.rerun()

    # Rejection notes — keyed por SKU
    if st.session_state.get(f"rejecting_{sku}"):
        reason = st.text_area(f"Razón del reject de {sku}", key=f"reason_{sku}")
        rc1, rc2 = st.columns(2)
        with rc1:
            if st.button("Confirmar reject", key=f"confirm_reject_{sku}"):
                audit_db.mark_rejected(conn, sku, reason)
                st.session_state[f"rejecting_{sku}"] = False
                st.rerun()
        with rc2:
            if st.button("Cancelar", key=f"cancel_reject_{sku}"):
                st.session_state[f"rejecting_{sku}"] = False
                st.rerun()


# ═══════════════════════════════════════
# COMPONENT 4: Publish flow
# ═══════════════════════════════════════

def _publish_family(conn, fam, claude_data, new_gallery, featured=False, sku=None):
    """Aplica cambios al catalog.json + git commit + push.

    sku: el SKU que Diego publica (post-s13 audit_decisions + pending_review
    están keyed por SKU). Si None (compat legacy), usa fam["family_id"] como
    key de mark_approved. Mutations al catalog.json siguen siendo por
    canonical fam["family_id"].
    """
    catalog_path = audit_db.CATALOG_PATH
    if not os.path.exists(catalog_path):
        st.error(f"catalog.json no encontrado en {catalog_path}")
        return

    # Cargar catalog fresh
    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    # Find and update family
    target = None
    for f_ in catalog:
        if f_.get("family_id") == fam["family_id"]:
            target = f_
            break
    if not target:
        st.error(f"Family {fam['family_id']} no encontrada en catalog.json")
        return

    # Apply Claude enrichment
    if claude_data.get("title"):
        target["title"] = claude_data["title"]
    # Fix s14m4: NO aplicar description ni historia de Claude — confundía
    # "Midnight Stadium" como fabricante. Diego escribe esos post-publish
    # desde el panel Publicados con deep research manual.
    # (Preservar si Claude los manda por runs viejos: ignorar silenciosamente.)
    if claude_data.get("sku"):
        target["sku"] = claude_data["sku"]
    if claude_data.get("keywords"):
        target["keywords"] = claude_data["keywords"]

    # Featured toggle (U-001) — persiste el TOP badge
    target["featured"] = bool(featured)

    # Ops s14g — al publicar, la family queda visible en el vault live.
    # El frontend (Vault UX) filtra `families.filter(f => f.published === true)`.
    # Default de todas las families post-refetch: published=false (via script
    # mark-all-unpublished.py).
    target["published"] = True

    # Ops s13 — iterar modelos si la family es unified.
    # Fix s14m6: audit_photo_actions está keyed por SKU (la UI en el audit detail
    # escribe con fam["family_id"]=SKU). El comentario original s13 decía
    # "source_family_id" pero eso NUNCA fue real — data inspection post Diego
    # publish de Argentina away confirmó 84 rows bajo SKU y 0 bajo canonical.
    # Entonces el key correcto para apply_photo_actions es modelo.sku.
    modelos = target.get("modelos") or []
    fid = fam["family_id"]
    unprocessed_report = []  # [(modelo_idx, sku, idxs), ...]

    if modelos:
        for i, modelo in enumerate(modelos):
            modelo_key = modelo.get("sku") or modelo.get("source_family_id") or fid
            # Mini-fam para reusar la función con gallery del modelo
            modelo_view = {"family_id": modelo_key, "gallery": modelo.get("gallery") or []}
            new_mg = _apply_photo_actions_to_gallery(
                conn, modelo_view, run_gemini_watermark=True, effective_fid=modelo_key,
            )
            # Chequear unprocessed watermarks en este modelo
            actions = audit_db.get_photo_actions(conn, modelo_key)
            unproc = [a for a in actions
                      if a.get("action") == "flag_watermark" and not a.get("processed_url")]
            if unproc:
                unprocessed_report.append((i, modelo_key, [a["original_index"] for a in unproc]))
            else:
                # Actualizar modelo in-place
                if new_mg:
                    modelo["gallery"] = new_mg
                    modelo["hero_thumbnail"] = new_mg[0]
        # Post-loop: si hay unprocessed, abort
        if unprocessed_report:
            audit_db.upsert_decision(
                conn, fid, status="needs_rework",
                decided_at=datetime.now().isoformat(timespec="seconds"),
            )
            msg_parts = "; ".join(
                f"modelo[{i}] ({fid_}): idx {idxs}" for i, fid_, idxs in unprocessed_report
            )
            st.error(
                f"🚨 Gemini watermark falló en {len(unprocessed_report)} modelo(s). "
                f"{msg_parts}. Family marcada `needs_rework` — no se publicó. "
                f"Ver `audit_api_errors` y reintentá cuando Gemini esté disponible."
            )
            return
        # Sync top-level fallback del primary modelo (para vault.elclub.club)
        prim_idx = target.get("primary_modelo_idx")
        if prim_idx is not None and 0 <= prim_idx < len(modelos):
            prim = modelos[prim_idx]
            if prim.get("gallery"):
                target["gallery"] = prim["gallery"]
                target["hero_thumbnail"] = prim["gallery"][0]
    else:
        # Legacy: gallery a nivel family
        new_gallery = _apply_photo_actions_to_gallery(conn, fam, run_gemini_watermark=True)
        actions = audit_db.get_photo_actions(conn, fid)
        unproc = [a for a in actions
                  if a.get("action") == "flag_watermark" and not a.get("processed_url")]
        if unproc:
            idxs = [a["original_index"] for a in unproc]
            audit_db.upsert_decision(
                conn, fid, status="needs_rework",
                decided_at=datetime.now().isoformat(timespec="seconds"),
            )
            st.error(
                f"🚨 Gemini watermark falló en {len(unproc)} foto(s) (índices {idxs}). "
                f"Family marcada `needs_rework` — no se publicó."
            )
            return
        if new_gallery:
            target["gallery"] = new_gallery
            target["hero_thumbnail"] = new_gallery[0]

    # Save catalog
    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # Mark approved — keyed por SKU post-s13 (pending_review + audit_decisions).
    # Si sku no se pasa (compat legacy), falls back a fam.family_id (canonical).
    approved_key = sku or fam["family_id"]
    audit_db.mark_approved(conn, approved_key)

    # Git commit + push
    repo_dir = os.path.dirname(os.path.dirname(catalog_path))
    try:
        subprocess.run(
            ["git", "add", "data/catalog.json"],
            cwd=repo_dir, capture_output=True, timeout=30,
        )
        subprocess.run(
            ["git", "commit", "-m", f"audit: {fam['family_id']} verified by Diego"],
            cwd=repo_dir, capture_output=True, timeout=30,
        )
        push_result = subprocess.run(
            ["git", "push"],
            cwd=repo_dir, capture_output=True, timeout=60,
        )
        if push_result.returncode == 0:
            st.success(f"✅ {fam['family_id']} publicada. Auto-deploy en vault.elclub.club.")
        else:
            st.warning(
                f"⚠️ {fam['family_id']} guardada local y marcada verified, pero git push falló: "
                f"{push_result.stderr.decode('utf-8', errors='ignore')[:200]}"
            )
    except Exception as e:
        st.warning(f"⚠️ git push falló: {e}. catalog.json actualizado localmente.")


# ═══════════════════════════════════════
# Ops s14 — 🗑 BORRAR SKU (soft-delete)
# ═══════════════════════════════════════

def _remove_modelo_from_catalog(canonical_fid, sku):
    """Remueve un modelo con `sku` del catalog.json.

    - Unified family (modelos[]): filtra el modelo con ese SKU.
      Si era el único → marca fam.status='deleted' y deja modelos=[].
      Si quedan otros → re-sincroniza primary_modelo_idx + top-level gallery/hero.
    - Legacy family (fam.sku == sku): marca fam.status='deleted'.

    No elimina físicamente el object del array — usa soft-delete para recovery.
    Escribe catalog.json. Retorna {ok, modified, family_deleted, error}.
    """
    catalog_path = audit_db.CATALOG_PATH
    if not os.path.exists(catalog_path):
        return {"ok": False, "error": f"catalog.json no existe", "modified": False, "family_deleted": False}

    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    modified = False
    family_deleted = False
    for fam in catalog:
        if fam.get("family_id") != canonical_fid:
            continue
        modelos = fam.get("modelos") or []
        if modelos:
            new_modelos = [m for m in modelos if m.get("sku") != sku]
            if len(new_modelos) == len(modelos):
                break  # SKU no encontrado en modelos[]
            if new_modelos:
                fam["modelos"] = new_modelos
                prim = fam.get("primary_modelo_idx", 0) or 0
                if prim >= len(new_modelos):
                    fam["primary_modelo_idx"] = 0
                prim_m = new_modelos[fam.get("primary_modelo_idx", 0)]
                if prim_m.get("gallery"):
                    fam["gallery"] = prim_m["gallery"]
                    fam["hero_thumbnail"] = prim_m.get("hero_thumbnail") or prim_m["gallery"][0]
                modified = True
            else:
                fam["status"] = "deleted"
                fam["modelos"] = []
                family_deleted = True
                modified = True
        else:
            if fam.get("sku") == sku:
                fam["status"] = "deleted"
                family_deleted = True
                modified = True
        break

    if not modified:
        return {"ok": False, "error": f"SKU {sku} no encontrado en {canonical_fid}",
                "modified": False, "family_deleted": False}

    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
        f.write("\n")

    return {"ok": True, "modified": True, "family_deleted": family_deleted}


def _commit_catalog_delete(sku, canonical_fid, motivo, family_deleted):
    """Commit + push del catalog.json tras delete. Sólo se llama si was_published=True.
    Retorna True si push OK, False si git falló."""
    catalog_path = audit_db.CATALOG_PATH
    repo_dir = os.path.dirname(os.path.dirname(catalog_path))
    verb = "delete family" if family_deleted else "delete SKU"
    msg_motivo = (motivo or "").split("\n")[0][:60]
    commit_msg = f"audit: {verb} {sku} ({canonical_fid}) — {msg_motivo}"
    try:
        subprocess.run(
            ["git", "add", "data/catalog.json"],
            cwd=repo_dir, capture_output=True, timeout=30,
        )
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=repo_dir, capture_output=True, timeout=30,
        )
        push_result = subprocess.run(
            ["git", "push"],
            cwd=repo_dir, capture_output=True, timeout=60,
        )
        return push_result.returncode == 0
    except Exception:
        return False


def _delete_sku(conn, sku, fam, modelo, motivo):
    """Ejecuta soft-delete completo de un SKU:
      1. audit_decisions.status='deleted' + motivo en notes
      2. catalog.json — remueve modelo o marca family deleted
      3. audit_delete_log — append row
      4. Si was_published → git commit + push

    audit_photo_actions NO se toca (recovery manual posible).

    Returns: {ok, family_deleted, was_published, committed, error}
    """
    now = datetime.now().isoformat(timespec="seconds")
    canonical_fid = fam["family_id"]
    source_fid = (modelo or {}).get("source_family_id") or canonical_fid

    pre_dec = audit_db.get_decision(conn, sku) or {}
    was_published = bool(pre_dec.get("final_verified"))
    existing_notes = (pre_dec.get("notes") or "").strip()

    modelos = fam.get("modelos") or []
    was_only_modelo = bool(modelo and len(modelos) == 1)

    if modelo:
        gallery = modelo.get("gallery") or []
    else:
        gallery = fam.get("gallery") or []
    photo_count = len(gallery)

    actions = audit_db.get_photo_actions(conn, source_fid)
    actions_count = len(actions)

    # 1. audit_decisions
    new_notes = f"[BORRADO {now}] {motivo.strip()}"
    if existing_notes:
        new_notes += f"\n---\nPrev: {existing_notes}"
    audit_db.upsert_decision(
        conn, sku,
        status="deleted",
        notes=new_notes,
        decided_at=now,
    )

    # 2. catalog mutation
    remove_result = _remove_modelo_from_catalog(canonical_fid, sku)
    family_deleted = remove_result.get("family_deleted", False)

    # 3. append log
    audit_db.log_delete(
        conn, sku, canonical_fid, source_fid, motivo,
        photo_count=photo_count, actions_count=actions_count,
        was_only_modelo=was_only_modelo,
        family_deleted=family_deleted,
        was_published=was_published,
    )

    # 4. commit+push sólo si estaba publicado (SKU visible en vault)
    committed = False
    if was_published and remove_result.get("ok"):
        committed = _commit_catalog_delete(sku, canonical_fid, motivo, family_deleted)

    return {
        "ok": remove_result.get("ok", False),
        "family_deleted": family_deleted,
        "was_published": was_published,
        "committed": committed,
        "error": remove_result.get("error"),
    }


# ═══════════════════════════════════════
# ROUTER
# ═══════════════════════════════════════

def render_page(conn):
    _ensure_init()

    # Sub-navigation
    view = st.session_state.get("audit_view", "queue")

    # Header con tabs + stats
    _render_stats_header(conn)
    st.markdown("")

    tc1, tc2, tc3 = st.columns(3)
    with tc1:
        if st.button("📋 Queue", use_container_width=True, type="primary" if view == "queue" else "secondary"):
            st.session_state.audit_view = "queue"
            st.rerun()
    with tc2:
        if st.button("🔍 Audit Detail", use_container_width=True, type="primary" if view == "detail" else "secondary",
                     disabled=not st.session_state.get("current_family")):
            st.session_state.audit_view = "detail"
            st.rerun()
    with tc3:
        if st.button("🤖 Pending Review", use_container_width=True, type="primary" if view == "pending" else "secondary"):
            st.session_state.audit_view = "pending"
            st.rerun()

    # Status messages from seed
    seed_result = st.session_state.get("audit_seed_result")
    if seed_result:
        st.info(
            f"**Audit queue inicializada:** {seed_result.get('seeded', 0)} families "
            f"(skipped sin foto: {seed_result.get('skipped_no_hero', 0)} · "
            f"skipped category=other: {seed_result.get('skipped_excluded_other', 0)})"
        )
        del st.session_state.audit_seed_result

    # Diagnostics — usamos el `conn` que ya recibe render_page (no abrir uno nuevo:
    # reasignar la variable sombrea el parámetro y cerrarlo rompe render_queue).
    deleted_week = audit_db.deleted_count_since(conn, days=7)
    with st.sidebar:
        st.markdown("---")
        st.markdown("**🔍 Audit Status**")
        st.caption(f"Claude: {'✅' if audit_enrich.claude_available() else '❌ set ANTHROPIC_API_KEY'}")
        # Watermark inpaint backend status — LaMa local (preferido, free, GPU)
        # vs Gemini API (fallback). Sidebar muestra cuál va a usar.
        try:
            import local_inpaint as _li
            _lama_ok = _li.local_inpaint_available()
        except Exception:
            _lama_ok = False
        if _lama_ok:
            st.caption(f"Watermark inpaint: ✅ LaMa local (GPU, $0)")
        elif audit_enrich.gemini_available():
            st.caption(f"Watermark inpaint: ⚠️ Gemini fallback (LaMa no disponible)")
        else:
            st.caption(f"Watermark inpaint: ❌ ningún backend")
        st.caption(f"Gemini (quality regen): {'✅' if audit_enrich.gemini_available() else '❌'}")
        st.caption(f"🗑 {deleted_week} SKU{'s' if deleted_week != 1 else ''} borrado{'s' if deleted_week != 1 else ''} esta semana")
        st.markdown("---")

    # Ops s14 — toast post-delete (set en _borrar_sku_dialog, cleared aquí)
    toast_msg = st.session_state.pop("audit_delete_toast", None)
    if toast_msg:
        st.success(toast_msg)

    st.markdown("")

    catalog = audit_db.load_catalog()
    if not catalog:
        st.error(f"catalog.json no encontrado en {audit_db.CATALOG_PATH}")
        st.info("El audit tool necesita el catalog.json del repo privado `elclub-catalogo-priv`. "
                "Verificá que el directorio existe.")
        return

    if view == "queue":
        render_queue(conn, catalog)
    elif view == "detail":
        render_detail(conn, catalog)
    elif view == "pending":
        render_pending_review(conn, catalog)
    else:
        render_queue(conn, catalog)
