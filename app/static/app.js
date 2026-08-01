const $ = (sel) => document.querySelector(sel);

const DAY_NAMES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];
const DAY_SHORT = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

const UPLOADS_KEY = "rol_data_status_v1";
let ministerCount = 0;
let massCount = 0;

function getUploads() {
  try {
    return JSON.parse(localStorage.getItem(UPLOADS_KEY)) || {};
  } catch (e) {
    return {};
  }
}

function formatWhen(ts) {
  return new Date(ts).toLocaleString("es-ES", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function recordUpload(kind, count) {
  const u = getUploads();
  u[kind] = { when: Date.now(), count };
  localStorage.setItem(UPLOADS_KEY, JSON.stringify(u));
  renderFooter();
}

function renderFooter() {
  const u = getUploads();
  $("#footer-ministers").textContent = ministerCount > 0 ? `${ministerCount} registrados` : "0 registrados";
  $("#footer-masses").textContent = massCount > 0 ? `${massCount} activas` : "0 activas";
  const parts = [];
  if (u.ministers) parts.push(`Ministros: ${u.ministers.count} (${formatWhen(u.ministers.when)})`);
  if (u.masses) parts.push(`Misas: ${u.masses.count} (${formatWhen(u.masses.when)})`);
  $("#footer-last-upload").textContent = parts.length
    ? parts.join("  ·  ")
    : "Sin subidas registradas en este navegador";
}

function wrapTable(table) {
  const wrap = document.createElement("div");
  wrap.className = "table-wrap";
  wrap.appendChild(table);
  return wrap;
}

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  let body = null;
  try { body = await res.json(); } catch (e) {}
  if (!res.ok) {
    if (body && typeof body.detail === "string") throw new Error(body.detail);
    throw new Error("Error " + res.status);
  }
  return body;
}

function formatDateInput(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function nextMonday() {
  const d = new Date();
  d.setDate(d.getDate() + ((8 - d.getDay()) % 7 || 7));
  return d;
}

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.toggle("active", b === btn));
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.id === "tab-" + btn.dataset.tab));
  });
});

const daySelectOptions = () => DAY_NAMES.map((n, i) => `<option value="${i + 1}">${n}</option>`).join("");

let locations = [];

async function loadLocations() {
  locations = await api("/api/locations");
  const sel = $("#mass-location");
  sel.innerHTML = "";
  for (const loc of locations) {
    const opt = document.createElement("option");
    opt.value = loc.id;
    opt.textContent = `${loc.name} (${loc.kind === "centro" ? "Centro" : "Filial"}, mín ${loc.default_min})`;
    sel.appendChild(opt);
  }
  renderLocations();
  return locations;
}

function renderLocations() {
  const el = $("#locations");
  el.innerHTML = "<h3>Lugares</h3>";
  if (!locations.length) {
    el.insertAdjacentHTML("beforeend", "<p class='hint'>Todavía no hay lugares. Agrega el centro parroquial y las filiales.</p>");
    return;
  }
  const ul = document.createElement("ul");
  for (const loc of locations) {
    const li = document.createElement("li");
    li.innerHTML = `<span>${escapeHtml(loc.name)} — ${loc.kind === "centro" ? "Centro parroquial" : "Filial"} (mínimo ${loc.default_min})</span> `;
    const del = document.createElement("button");
    del.className = "danger small";
    del.textContent = "Eliminar";
    del.addEventListener("click", async () => {
      if (!confirm(`¿Eliminar "${loc.name}" y todas sus misas?`)) return;
      await fetch("/api/locations/" + loc.id, { method: "DELETE" });
      await Promise.all([loadLocations(), loadMasses()]);
    });
    li.appendChild(del);
    ul.appendChild(li);
  }
  el.appendChild(ul);
}

async function loadMasses() {
  const masses = await api("/api/masses");
  massCount = masses.length;
  const el = $("#masses");
  el.innerHTML = "<h3>Misas</h3>";
  if (!masses.length) {
    el.insertAdjacentHTML("beforeend", "<p class='hint'>No hay misas. Agrega la primera.</p>");
    return;
  }
  const byDay = {};
  masses.forEach((m) => (byDay[m.day] = byDay[m.day] || []).push(m));
  for (let d = 1; d <= 7; d++) {
    if (!byDay[d]) continue;
    const h = document.createElement("h4");
    h.textContent = DAY_NAMES[d - 1];
    el.appendChild(h);
    const grid = document.createElement("div");
    grid.className = "card-grid";
    for (const m of byDay[d]) {
      const card = document.createElement("div");
      card.className = "card nav-card";
      card.innerHTML = `
        <h4>${DAY_NAMES[d - 1]}</h4>
        <p><strong>Hora:</strong> ${escapeHtml(m.time)}</p>
        <p><strong>Lugar:</strong> ${escapeHtml(m.location_name)}</p>
        <p><strong>Mínimo:</strong> ${m.min_ministers}</p>
        <p><strong>Estado:</strong> ${m.active ? "Activa" : "Inactiva"}</p>`;
      const del = document.createElement("button");
      del.className = "danger small";
      del.textContent = "Eliminar";
      del.addEventListener("click", async () => {
        if (!confirm("¿Eliminar esta misa?")) return;
        await fetch("/api/masses/" + m.id, { method: "DELETE" });
        loadMasses();
      });
      const edit = document.createElement("button");
      edit.className = "accent small";
      edit.textContent = "Editar";
      edit.addEventListener("click", () => {
        card.innerHTML = "";
        card.appendChild(createEditForm(m));
      });
      card.appendChild(edit);
      card.appendChild(del);
      grid.appendChild(card);
    }
    el.appendChild(grid);
  }
  renderFooter();

// Helper to create an edit form for a mass entry
function createEditForm(m) {
  const form = document.createElement('form');
  form.className = 'edit-form';

  // Location ID input (numeric; could be enhanced with a selector)
  const locInput = document.createElement('input');
  locInput.type = 'number';
  locInput.name = 'location_id';
  locInput.value = m.location_id || '';
  form.appendChild(document.createTextNode('Lugar ID: '));
  form.appendChild(locInput);
  form.appendChild(document.createElement('br'));

  // Day selector
  const daySelect = document.createElement('select');
  daySelect.name = 'day';
  for (let d = 1; d <= 7; d++) {
    const opt = document.createElement('option');
    opt.value = d;
    opt.textContent = DAY_NAMES[d - 1];
    if (d === m.day) opt.selected = true;
    daySelect.appendChild(opt);
  }
  form.appendChild(document.createTextNode('Día: '));
  form.appendChild(daySelect);
  form.appendChild(document.createElement('br'));

  // Time input
  const timeInput = document.createElement('input');
  timeInput.type = 'time';
  timeInput.name = 'time';
  timeInput.value = m.time || '';
  form.appendChild(document.createTextNode('Hora: '));
  form.appendChild(timeInput);
  form.appendChild(document.createElement('br'));

  // Minimum ministers input
  const minInput = document.createElement('input');
  minInput.type = 'number';
  minInput.name = 'min_ministers';
  minInput.value = m.min_ministers || '';
  form.appendChild(document.createTextNode('Mínimo: '));
  form.appendChild(minInput);
  form.appendChild(document.createElement('br'));

  // Submit and Cancel buttons
  const submitBtn = document.createElement('button');
  submitBtn.type = 'submit';
  submitBtn.textContent = 'Guardar';
  const cancelBtn = document.createElement('button');
  cancelBtn.type = 'button';
  cancelBtn.textContent = 'Cancelar';
  cancelBtn.addEventListener('click', () => {
    // Reload masses to discard changes
    loadMasses();
  });
  form.appendChild(submitBtn);
  form.appendChild(cancelBtn);

  // Handle form submission
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
      await api(`/api/masses/${m.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          location_id: Number(locInput.value),
          day: Number(daySelect.value),
          time: timeInput.value,
          min_ministers: Number(minInput.value) || null,
        }),
      });
      loadMasses();
    } catch (err) {
      alert(err.message);
    }
  });

  return form;
}

}

$("#location-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/api/locations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: $("#location-name").value, kind: $("#location-kind").value }),
    });
    $("#location-name").value = "";
    await Promise.all([loadLocations(), loadMasses()]);
  } catch (err) {
    alert(err.message);
  }
});

$("#mass-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/api/masses", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        location_id: Number($("#mass-location").value),
        day: Number($("#mass-day").value),
        time: $("#mass-time").value,
        min_ministers: Number($("#mass-min").value) || null,
      }),
    });
    await loadMasses();
  } catch (err) {
    alert(err.message);
  }
});

$("#mass-day").innerHTML = daySelectOptions();
$("#mass-day").value = "7";

function renderUploadResult(el, data, label) {
  el.innerHTML = "";
  if (data.imported > 0) {
    el.insertAdjacentHTML("beforeend", `<div class="banner ok">Se importaron ${data.imported} ${label}.</div>`);
  }
  const issues = [];
  data.errors.forEach((e) => issues.push({ ...e, kind: "error" }));
  data.warnings.forEach((e) => issues.push({ ...e, kind: "warning" }));
  if (!issues.length) return;
  const ul = document.createElement("ul");
  for (const i of issues) {
    const li = document.createElement("li");
    li.className = "issue " + i.kind;
    li.textContent = `Fila ${i.row}${i.column ? `, columna "${i.column}"` : ""}: ${i.message}`;
    ul.appendChild(li);
  }
  el.appendChild(ul);
}

$("#upload-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const file = $("#csv-file").files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append("file", file);
  try {
    const res = await api("/api/ministers/upload", { method: "POST", body: fd });
    renderUploadResult($("#upload-result"), res, "ministros");
    recordUpload("ministers", res.imported);
    loadMinisters();
  } catch (err) {
    alert(err.message);
  }
});

$("#masses-upload-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const file = $("#masses-file").files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append("file", file);
  try {
    const res = await api("/api/masses/upload", { method: "POST", body: fd });
    renderUploadResult($("#masses-upload-result"), res, "misas");
    recordUpload("masses", res.imported);
    await Promise.all([loadLocations(), loadMasses()]);
  } catch (err) {
    alert(err.message);
  }
});

$("#clear-ministers").addEventListener("click", async () => {
  if (!confirm("¿Eliminar todos los ministros?")) return;
  await fetch("/api/ministers", { method: "DELETE" });
  loadMinisters();
});

async function loadMinisters() {
  const ministers = await api("/api/ministers");
  ministerCount = ministers.length;
  const el = $("#ministers");
  el.innerHTML = "";
  if (!ministers.length) {
    el.innerHTML = "<p class='hint'>No hay ministros. Sube un CSV o descarga la plantilla.</p>";
    return;
  }
  const table = document.createElement("table");
  table.innerHTML = "<thead><tr><th>Nombre</th><th>Teléfono</th><th>Disponible</th></tr></thead>";
  const tbody = document.createElement("tbody");
  for (const m of ministers) {
    const tr = document.createElement("tr");
    const days = m.days_available.split(",").filter(Boolean).map((d) => DAY_SHORT[Number(d) - 1]).join(", ");
    tr.innerHTML = `<td>${escapeHtml(m.name)}</td><td>${escapeHtml(m.phone || "")}</td><td>${escapeHtml(days)}</td>`;
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  el.appendChild(wrapTable(table));
  renderFooter();
}

function weekParam() {
  const v = $("#roster-week").value;
  return v ? "?week_start=" + v : "";
}

function renderRoster(data) {
  const el = $("#roster-result");
  el.innerHTML = "";
  $("#pdf-btn").hidden = false;
  const banner = document.createElement("div");
  if (data.status === "con_faltantes") {
    banner.className = "banner error";
    banner.innerHTML = "<strong>Rol con faltantes:</strong><ul>" +
      data.warnings.map((w) => `<li>${escapeHtml(w)}</li>`).join("") + "</ul>";
  } else {
    banner.className = "banner ok";
    banner.textContent = "Rol completo generado el " + data.generated_at;
  }
  el.appendChild(banner);
  const info = document.createElement("p");
  info.className = "week-info";
  info.textContent = "Semana del " + data.week_start_display;
  el.appendChild(info);

  for (const day of data.days) {
    if (!day.masses.length) continue;
    const h = document.createElement("h3");
    h.textContent = `${day.label} ${day.date}`;
    el.appendChild(h);
    const table = document.createElement("table");
    table.innerHTML = "<thead><tr><th>Hora</th><th>Lugar</th><th>Ministros</th></tr></thead>";
    const tbody = document.createElement("tbody");
    for (const m of day.masses) {
      const tr = document.createElement("tr");
      const names = m.ministers.map((x) => escapeHtml(x.name)).join(", ") ||
        `<span class="missing">Falta cubrir (${m.assigned}/${m.min_ministers})</span>`;
      tr.innerHTML = `<td>${escapeHtml(m.time)}</td><td>${escapeHtml(m.location)}</td><td>${names}</td>`;
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    el.appendChild(wrapTable(table));
  }
}

async function showRoster() {
  try {
    renderRoster(await api("/api/roster" + weekParam()));
  } catch (err) {
    $("#pdf-btn").hidden = true;
    $("#roster-result").innerHTML = `<p class="hint">${escapeHtml(err.message)}</p>`;
  }
}

$("#roster-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    renderRoster(await api("/api/roster/generate" + weekParam(), { method: "POST" }));
  } catch (err) {
    alert(err.message);
  }
});

$("#reload-btn").addEventListener("click", showRoster);
$("#print-btn").addEventListener("click", () => window.open("/roster/print" + weekParam(), "_blank"));
$("#download-btn").addEventListener("click", () => { window.location = "/api/roster/download.csv" + weekParam(); });
$("#pdf-btn").addEventListener("click", () => { window.location = "/api/roster/pdf" + weekParam(); });

$("#roster-week").value = formatDateInput(nextMonday());

loadLocations();
loadMasses();
loadMinisters();
renderFooter();
