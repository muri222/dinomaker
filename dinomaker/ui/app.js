/* DinoMaker — painel de criação/edição (cliente). */
"use strict";

const $ = (s) => document.querySelector(s);
const el = (tag, attrs = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  for (const k of kids) e.append(k);
  return e;
};

const FEAT_PT = {
  teeth: "Dentes", beak: "Bico", horns_brow: "Chifres na testa", horn_nose: "Chifre no nariz",
  horns_long: "Chifres longos", frill: "Babado (frill)", frill_spikes: "Espinhos no babado",
  plates: "Placas nas costas", thagomizer: "Espetos na cauda", back_spikes: "Espinhos nas costas",
  sail: "Vela", hump: "Corcunda", armor: "Armadura", side_spikes: "Espinhos laterais", club: "Clava na cauda",
  crest_tube: "Crista tubo", crest_fan: "Crista leque", crest_double: "Crista dupla", crest_small: "Cristinha",
  crest_head: "Crista de ptero", dome: "Cúpula (cabeça dura)", feathers: "Penas", sickle_claw: "Garra foice",
  big_claws: "Garras grandes", thumb_spike: "Espinho no polegar", neck_spikes: "Espinhos no pescoço",
  wings: "Asas", crystals: "Cristais", antlers: "Galhada", mane: "Juba", gem: "Gema na testa",
  tusks: "Presas", glow_eyes: "Olhos brilhantes",
};
const ARCH_PT = {
  theropod: "Terópode (T-Rex)", raptor: "Raptor", spinosaur: "Espinossauro", sauropod: "Saurópode (pescoço longo)",
  ceratopsian: "Ceratopsídeo (Trici)", stegosaur: "Estegossauro", ankylosaur: "Anquilossauro",
  hadrosaur: "Hadrossauro (bico de pato)", pachycephalosaur: "Paquicefalossauro", pterosaur: "Pterossauro",
};
const CLIP_PT = { Idle: "Parado", Walk: "Andar", Run: "Correr", Attack: "Atacar", Roar: "Rugir", Hit: "Dano",
  Eat: "Comer", Death: "Morrer", Fly: "Voar", Flap: "Asas" };
const GROUP_PT = { head: "Cabeça", neck: "Pescoço", tail: "Cauda", legs: "Pernas", arms: "Braços",
  body: "Corpo (comprimento)", bulk: "Robustez (largura)" };
const COLOR_PT = { primary: "Corpo", belly: "Barriga", accent: "Destaque", pattern: "Padrão", claw: "Garras/chifres", eye: "Olhos" };

let META = null;
let spec = null;          // spec atual (fonte da verdade do editor)
let editingId = null;     // id do dino da biblioteca sendo editado
let lastGenome = null;
let LIB = [];

async function api(path, body) {
  const r = await fetch(path, body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const j = await r.json();
  if (!r.ok) throw Object.assign(new Error(j.erro || r.statusText), { status: r.status });
  return j;
}

function toast(msg, bad = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "on" + (bad ? " bad" : "");
  clearTimeout(toast.h);
  toast.h = setTimeout(() => (t.className = ""), 4500);
}

/* ============================== 3D ============================== */
const V = {};
function initViewer() {
  const host = $("#viewport");
  V.renderer = new THREE.WebGLRenderer({ antialias: true });
  V.renderer.setPixelRatio(window.devicePixelRatio);
  V.renderer.outputEncoding = THREE.sRGBEncoding;
  V.renderer.setClearColor(0x2a2f3a);
  host.append(V.renderer.domElement);
  V.scene = new THREE.Scene();
  V.camera = new THREE.PerspectiveCamera(40, 1, 1, 5000);
  V.controls = new THREE.OrbitControls(V.camera, V.renderer.domElement);
  V.controls.enableDamping = true;
  V.scene.add(new THREE.HemisphereLight(0xffffff, 0x556070, 0.75));
  const sun = new THREE.DirectionalLight(0xffffff, 0.75);
  sun.position.set(-1, 2, -1.5);
  V.scene.add(sun);
  V.grid = new THREE.GridHelper(600, 60, 0x4a5163, 0x363c4a);
  V.scene.add(V.grid);
  V.root = new THREE.Group();
  V.scene.add(V.root);
  V.clip = "Idle"; V.t = 0; V.speed = 1;
  V.clock = new THREE.Clock();
  const resize = () => {
    const w = host.clientWidth, h = host.clientHeight;
    V.renderer.setSize(w, h);
    V.camera.aspect = w / Math.max(h, 1);
    V.camera.updateProjectionMatrix();
  };
  window.addEventListener("resize", resize);
  new ResizeObserver(resize).observe(host);
  resize();
  V.camera.position.set(120, 90, -160);
  const loop = () => {
    requestAnimationFrame(loop);
    animate(V.clock.getDelta());
    V.controls.update();
    V.renderer.render(V.scene, V.camera);
  };
  loop();
}

function buildModel(data, refit) {
  V.root.clear();
  const tex = new THREE.TextureLoader().load(data.atlas);
  tex.magFilter = THREE.NearestFilter;
  tex.minFilter = THREE.NearestFilter;
  tex.encoding = THREE.sRGBEncoding;
  const mat = new THREE.MeshLambertMaterial({ map: tex });
  V.meshes = data.bones.map((b) => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(b.pos, 3));
    g.setAttribute("uv", new THREE.Float32BufferAttribute(b.uv, 2));
    g.computeVertexNormals();
    const m = new THREE.Mesh(g, mat);
    m.matrixAutoUpdate = false;
    V.root.add(m);
    return m;
  });
  // pré-decompõe as poses (posição + quaternion) para interpolar suave
  V.anims = {};
  for (const [name, a] of Object.entries(data.anims)) {
    V.anims[name] = {
      loop: a.loop, fps: a.fps, n: a.frames.length,
      poses: a.frames.map((fr) => fr.map((arr) => {
        const M = new THREE.Matrix4().fromArray(arr);
        const p = new THREE.Vector3(), q = new THREE.Quaternion(), s = new THREE.Vector3();
        M.decompose(p, q, s);
        return [p, q];
      })),
    };
  }
  if (!V.anims[V.clip]) V.clip = "Idle";
  buildClipBar();
  animate(0);
  if (refit) fitCamera();
}

function animate(dt) {
  if (!V.anims || !V.anims[V.clip]) return;
  const a = V.anims[V.clip];
  V.t += dt * V.speed;
  let f = V.t * a.fps;
  if (a.loop) f = f % a.n;
  else if (f >= a.n - 1) { f = a.n - 1; if (V.t * a.fps > a.n + a.fps * 1.2) V.t = 0; }
  const i0 = Math.floor(f), i1 = a.loop ? (i0 + 1) % a.n : Math.min(i0 + 1, a.n - 1), w = f - i0;
  const P = new THREE.Vector3(), Q = new THREE.Quaternion(), S = new THREE.Vector3(1, 1, 1);
  V.meshes.forEach((m, bi) => {
    const [p0, q0] = a.poses[i0][bi], [p1, q1] = a.poses[i1][bi];
    P.copy(p0).lerp(p1, w);
    Q.copy(q0).slerp(q1, w);
    m.matrix.compose(P, Q, S);
  });
}

function fitCamera() {
  const box = new THREE.Box3().setFromObject(V.root);
  const c = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3()).length();
  V.controls.target.copy(c);
  V.camera.position.set(c.x + size * 0.75, c.y + size * 0.45, c.z - size * 0.9);
  V.camera.near = size / 100; V.camera.far = size * 20;
  V.camera.updateProjectionMatrix();
}

function buildClipBar() {
  const bar = $("#clipbar");
  bar.innerHTML = "";
  for (const name of Object.keys(V.anims)) {
    bar.append(el("button", { class: name === V.clip ? "on" : "", onclick: () => { V.clip = name; V.t = 0; buildClipBar(); } },
      CLIP_PT[name] || name));
  }
  bar.append(el("button", { onclick: fitCamera, title: "Centralizar câmera" }, "⟲"));
}

/* ============================== EDITOR ============================== */
const SLIDERS = [];
function buildEditorControls() {
  // base: espécies reais por corpo + fantasia por corpo
  const base = $("#f-base");
  for (const a of META.archetypes) {
    const og = el("optgroup", { label: ARCH_PT[a.key] || a.key });
    for (const sp of META.species[a.key] || []) og.append(el("option", { value: "sp:" + sp.key }, sp.name));
    og.append(el("option", { value: "fa:" + a.key }, "✨ Fantasia (" + (ARCH_PT[a.key] || a.key).split(" (")[0] + ")"));
    base.append(og);
  }
  base.onchange = async () => {
    const [k, v] = base.value.split(":");
    const body = k === "sp" ? { species: v } : { archetype: v, fantasy: true };
    await newDino(body);
  };

  const box = $("#sliders");
  const add = (key, label, min, max, step, get, set, fmt = (x) => (+x).toFixed(2)) => {
    const out = el("b");
    const inp = el("input", { type: "range", min, max, step });
    inp.oninput = () => { out.textContent = fmt(inp.value); set(+inp.value); schedulePreview(); };
    box.append(el("div", { class: "slider" }, el("label", {}, label, out), inp));
    SLIDERS.push({ inp, out, get, fmt });
  };
  add("px", "Tamanho geral", 0.05, 0.4, 0.005, () => spec.px_size, (v) => (spec.px_size = v),
    (x) => (+x).toFixed(3) + " stud/px");
  for (const g of META.groups) {
    add(g, GROUP_PT[g], 0.5, 1.8, 0.01, () => spec.variation[g] ?? 1, (v) => (spec.variation[g] = v), (x) => "×" + (+x).toFixed(2));
  }
  const P = (k) => () => (spec.params[k] ?? (lastGenome ? lastGenome.params[k] : 1));
  add("snout", "Focinho (comprimento)", 2, 24, 1, P("snout_len"), (v) => (spec.params.snout_len = v), (x) => x + " px");
  add("necks", "Segmentos do pescoço", 1, 7, 1, P("neck_segs"), (v) => (spec.params.neck_segs = v), (x) => x);
  add("tails", "Segmentos da cauda", 1, 9, 1, P("tail_segs"), (v) => (spec.params.tail_segs = v), (x) => x);

  $("#f-chibi").onchange = (e) => {
    const on = e.target.checked;
    if (on === !!spec.chibi) return;
    spec.chibi = on;
    spec.variation.head = +(spec.variation.head * (on ? 1.25 : 1 / 1.25)).toFixed(3);
    spec.variation.legs = +(spec.variation.legs * (on ? 0.85 : 1 / 0.85)).toFixed(3);
    syncControls(); schedulePreview();
  };

  for (const s of META.eye_styles) $("#f-eyestyle").append(el("option", { value: s }, { cute: "Fofo", fierce: "Feroz", glow: "Brilhante" }[s] || s));
  $("#f-eyestyle").onchange = (e) => { spec.eyes.style = e.target.value; schedulePreview(); };
  $("#f-eyesize").oninput = (e) => { spec.eyes.size = +e.target.value; $("#v-eyesize").textContent = e.target.value; schedulePreview(); };

  for (const p of Object.keys(META.palettes)) $("#f-palette").append(el("option", { value: p }, p));
  $("#f-palette").onchange = (e) => {
    if (!e.target.value) return;
    Object.assign(spec.palette, META.palettes[e.target.value]);
    e.target.value = "";
    syncControls(); schedulePreview();
  };
  const cbox = $("#colors");
  for (const [k, lbl] of Object.entries(COLOR_PT)) {
    const inp = el("input", { type: "color", id: "c-" + k });
    inp.oninput = () => { spec.palette[k] = inp.value; schedulePreview(); };
    cbox.append(el("label", {}, inp, lbl));
  }

  for (const p of META.patterns) $("#f-pattern").append(el("option", { value: p }, p));
  $("#f-pattern").onchange = (e) => { spec.pattern.type = e.target.value; schedulePreview(); };
  $("#f-pscale").oninput = (e) => { spec.pattern.scale = +e.target.value; $("#v-pscale").textContent = e.target.value; schedulePreview(); };
  $("#f-pdens").oninput = (e) => { spec.pattern.density = +e.target.value; $("#v-pdens").textContent = e.target.value; schedulePreview(); };

  const fb = $("#feats");
  for (const f of META.features) {
    const c = el("input", { type: "checkbox", value: f });
    c.onchange = () => {
      const set = new Set(spec.features_exact);
      c.checked ? set.add(f) : set.delete(f);
      spec.features_exact = [...set];
      schedulePreview();
    };
    fb.append(el("label", {}, c, FEAT_PT[f] || f));
  }

  for (const a of META.attacks) $("#f-attack").append(el("option", { value: a }, a));
  $("#f-attack").onchange = (e) => { spec.attack = e.target.value; schedulePreview(); };
  $("#f-vfx").append(el("option", { value: "" }, "automático"));
  for (const t of META.vfx) $("#f-vfx").append(el("option", { value: t }, t));
  $("#f-vfx").onchange = (e) => { spec.vfx = e.target.value ? { theme: e.target.value } : {}; schedulePreview(); };

  $("#f-name").oninput = (e) => { spec.name = e.target.value; schedulePreview(800); };
  $("#b-random").onclick = () => newDino(Math.random() < 0.5 ? { fantasy: true } : {});
  $("#b-save-new").onclick = () => save("new");
  $("#b-save-replace").onclick = () => save("replace");
}

function syncControls() {
  $("#f-name").value = spec.name || "";
  const base = spec.species ? "sp:" + spec.species : "fa:" + spec.archetype;
  if ([...$("#f-base").options].some((o) => o.value === base)) $("#f-base").value = base;
  for (const s of SLIDERS) { const v = s.get(); s.inp.value = v; s.out.textContent = s.fmt(v); }
  $("#f-chibi").checked = !!spec.chibi;
  $("#f-eyestyle").value = spec.eyes.style;
  $("#f-eyesize").value = spec.eyes.size; $("#v-eyesize").textContent = spec.eyes.size;
  for (const k of Object.keys(COLOR_PT)) { const i = $("#c-" + k); if (spec.palette[k]) i.value = spec.palette[k]; }
  $("#f-pattern").value = spec.pattern.type;
  $("#f-pscale").value = spec.pattern.scale ?? 6; $("#v-pscale").textContent = spec.pattern.scale ?? 6;
  $("#f-pdens").value = spec.pattern.density ?? 0.6; $("#v-pdens").textContent = spec.pattern.density ?? 0.6;
  const fs = new Set(spec.features_exact);
  for (const c of $("#feats").querySelectorAll("input")) c.checked = fs.has(c.value);
  $("#f-attack").value = spec.attack;
  $("#f-vfx").value = (spec.vfx && spec.vfx.theme) || "";
  $("#editing").textContent = editingId ? "Editando: " + editingId + " (Salvar por cima mantém o lugar dele)" : "Novo dino (ainda não salvo)";
  $("#b-save-replace").disabled = !editingId;
}

let previewTimer = null, previewSeq = 0;
function schedulePreview(ms = 350) {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(runPreview, ms);
}

async function runPreview(refit = false) {
  const seq = ++previewSeq;
  $("#busy").classList.add("on");
  try {
    const data = await api("/api/preview", { spec, exclude: editingId });
    if (seq !== previewSeq) return;
    lastGenome = data.genome;
    buildModel(data, refit);
    showStats(data);
    showOriginality(data.originality);
    for (const s of SLIDERS) if (document.activeElement !== s.inp) { const v = s.get(); s.inp.value = v; s.out.textContent = s.fmt(v); }
  } catch (e) {
    toast("Erro no preview: " + e.message, true);
  } finally {
    if (seq === previewSeq) $("#busy").classList.remove("on");
  }
}

function showStats(d) {
  const s = d.stats;
  $("#stats").innerHTML = `Altura <b>${s.altura}</b> studs · Comprimento <b>${s.comprimento}</b> · Andar <b>${s.walk}</b> / Correr <b>${s.run}</b> studs/s · ${s.pecas} peças · ${s.ossos} ossos`;
}

function showOriginality(o) {
  const pct = Math.round(o.score * 100), lim = Math.round(o.threshold * 100);
  const col = o.ok ? (o.score > o.threshold - 0.1 ? "var(--warn)" : "var(--acc)") : "var(--bad)";
  const msg = o.name_taken ? "⚠️ Já existe um dino com esse nome." :
    o.ok ? (o.nearest ? `Original ✓ — mais parecido: <b>${o.nearest}</b> (${pct}%)` : "Original ✓") :
      `⚠️ Parecido demais com <b>${o.nearest}</b> (${pct}% ≥ ${lim}%) — mude cores, partes ou proporções`;
  $("#orig").innerHTML = `${msg}<div class="bar"><i style="width:${pct}%;background:${col}"></i><s style="left:${lim}%"></s></div>`;
}

async function newDino(body) {
  try {
    $("#busy").classList.add("on");
    const r = await api("/api/new", body);
    loadSpec(r.spec, null);
  } catch (e) { toast(e.message, true); $("#busy").classList.remove("on"); }
}

function loadSpec(s, id) {
  spec = JSON.parse(JSON.stringify(s));
  spec.params = spec.params || {};
  spec.vfx = spec.vfx || {};
  editingId = id;
  lastGenome = null;
  syncControls();
  runPreview(true);
}

async function save(mode) {
  try {
    const job = await api("/api/save", { spec, mode, replace_id: editingId, force: $("#f-force").checked });
    toast("Gerando " + spec.name + " (Blender)… acompanhe no topo.");
    watchJob(job, null, (j) => {
      toast("✓ " + j.result.name + " salvo no histórico.");
      editingId = j.result.id;
      syncControls();
      loadLibrary();
    });
  } catch (e) {
    toast(e.status === 409 ? "Não salvei: " + e.message : "Erro: " + e.message, true);
  }
}

/* ============================== JOBS ============================== */
const ACTIVE = new Map();
function watchJob(job, onTick, onDone) {
  ACTIVE.set(job.id, { onTick, onDone });
  updateJobsBar();
}
async function pollJobs() {
  for (const [id, h] of ACTIVE) {
    try {
      const j = await api("/api/job/" + id);
      if (h.onTick) h.onTick(j);
      if (j.status !== "rodando") {
        ACTIVE.delete(id);
        if (j.status === "ok") h.onDone && h.onDone(j);
        else toast("Falhou: " + (j.error || "erro"), true);
      }
    } catch (e) { /* tenta de novo */ }
  }
  updateJobsBar();
}
function updateJobsBar() {
  $("#jobsbar").textContent = ACTIVE.size ? `⏳ ${ACTIVE.size} tarefa(s) rodando…` : "";
}
setInterval(pollJobs, 1000);

/* ============================== BIBLIOTECA ============================== */
async function loadLibrary() {
  LIB = await api("/api/library");
  renderLibrary();
  renderExportList();
}
function matches(d, q) {
  q = q.trim().toLowerCase();
  return !q || [d.name, d.id, d.species, d.archetype, d.palette, d.pattern].join(" ").toLowerCase().includes(q);
}
function renderLibrary() {
  const q = $("#lib-search").value;
  const grid = $("#lib-grid");
  grid.innerHTML = "";
  const list = LIB.filter((d) => matches(d, q));
  $("#lib-count").textContent = `${list.length} de ${LIB.length} dinos`;
  for (const d of list) {
    const img = d.thumb ? el("img", { src: d.thumb, loading: "lazy" }) : el("div", { class: "noimg" }, d.legacy ? "feito à mão" : "sem preview");
    const del = el("button", { class: "del", title: "Remover do histórico", onclick: async (ev) => {
      ev.stopPropagation();
      if (d.legacy) return toast("Dinos feitos à mão ficam no histórico para evitar cópias.");
      if (!confirm(`Remover "${d.name}" do histórico e apagar os arquivos?`)) return;
      await api("/api/forget", { id: d.id, delete_files: true });
      loadLibrary();
    } }, "×");
    const card = el("div", { class: "dcard", onclick: async () => {
      if (!d.editable) return toast("Esse é um dino legado (feito à mão): não dá para editar aqui.");
      const r = await api("/api/dino/" + d.id);
      showTab("editor");
      loadSpec(r.spec, d.id);
    } }, img, el("div", { class: "info" }, del, el("b", {}, d.name), el("small", {}, (ARCH_PT[d.archetype] || d.archetype).split(" (")[0] + " · " + (d.pattern || ""))));
    grid.append(card);
  }
}

/* ============================== LOTE ============================== */
function buildBatch() {
  for (const a of META.archetypes) $("#bt-archs").append(el("label", {}, el("input", { type: "checkbox", value: a.key }), ARCH_PT[a.key] || a.key));
  for (const t of META.themes) $("#bt-themes").append(el("label", {}, el("input", { type: "checkbox", value: t }), t));
  $("#bt-go").onclick = async () => {
    const pick = (sel) => [...document.querySelectorAll(sel + " input:checked")].map((c) => c.value);
    const body = { count: +$("#bt-count").value, name: $("#bt-name").value, kinds: $("#bt-kinds").value,
      archetypes: pick("#bt-archs"), themes: pick("#bt-themes") };
    $("#bt-log").textContent = "escolhendo conceitos únicos…\n";
    $("#bt-bar").style.width = "2%";
    $("#bt-go").disabled = true;
    const job = await api("/api/batch", body);
    watchJob(job, (j) => {
      $("#bt-log").textContent = j.log.join("\n");
      const p = j.progress;
      if (p && p.stage === "gerando") $("#bt-bar").style.width = (100 * p.done / p.total) + "%";
    }, (j) => {
      $("#bt-go").disabled = false;
      $("#bt-bar").style.width = "100%";
      toast(`✓ Lote pronto: ${j.result.ids.length} dinos novos.`);
      loadLibrary();
    });
  };
}

/* ============================== EXPORTAR ============================== */
const EXSEL = new Set();
function renderExportList() {
  const q = $("#ex-search").value;
  const box = $("#ex-list");
  box.innerHTML = "";
  for (const d of LIB.filter((x) => x.editable && matches(x, q))) {
    const c = el("input", { type: "checkbox" });
    c.checked = EXSEL.has(d.id);
    c.onchange = () => { c.checked ? EXSEL.add(d.id) : EXSEL.delete(d.id); countEx(); };
    box.append(el("label", {}, c, d.name));
  }
  countEx();
}
function countEx() { $("#ex-count").textContent = `${EXSEL.size} selecionado(s)`; }
function buildExport() {
  $("#ex-search").oninput = renderExportList;
  $("#ex-all").onclick = () => { LIB.filter((x) => x.editable && matches(x, $("#ex-search").value)).forEach((d) => EXSEL.add(d.id)); renderExportList(); };
  $("#ex-none").onclick = () => { EXSEL.clear(); renderExportList(); };
  $("#ex-go").onclick = async () => {
    if (!EXSEL.size) return toast("Selecione pelo menos um dino.", true);
    $("#ex-go").disabled = true;
    $("#ex-log").textContent = "";
    $("#ex-bar").style.width = "2%";
    const job = await api("/api/export", { ids: [...EXSEL], name: $("#ex-name").value });
    watchJob(job, (j) => {
      $("#ex-log").textContent = j.log.join("\n");
      if (j.progress) $("#ex-bar").style.width = (100 * j.progress.done / j.progress.total) + "%";
    }, (j) => {
      $("#ex-go").disabled = false;
      $("#ex-bar").style.width = "100%";
      $("#ex-log").innerHTML += `\n✓ ${j.result.count} dinos — <a href="${j.result.zip}" style="color:var(--acc)">baixar zip</a>`;
      window.location.href = j.result.zip;
    });
  };
}

/* ============================== TABS / BOOT ============================== */
function showTab(name) {
  document.querySelectorAll("nav button").forEach((b) => b.classList.toggle("on", b.dataset.tab === name));
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("on", t.id === "tab-" + name));
  if (name === "editor") window.dispatchEvent(new Event("resize"));
}

async function boot() {
  document.querySelectorAll("nav button").forEach((b) => (b.onclick = () => showTab(b.dataset.tab)));
  $("#lib-search").oninput = renderLibrary;
  $("#lib-fill").onclick = async () => {
    const falta = LIB.filter((d) => d.editable && !d.thumb).length;
    if (!falta) return toast("Todas as miniaturas já existem.");
    if (!confirm(`Gerar ${falta} dino(s) no Blender? (uns 5–15 s cada, em paralelo)`)) return;
    $("#lib-fill").disabled = true;
    const job = await api("/api/fill", {});
    watchJob(job, (j) => {
      if (j.progress) $("#lib-fill-st").textContent = `${j.progress.done}/${j.progress.total}`;
      if (j.progress && j.progress.done % 5 === 0) loadLibrary();
    }, () => { $("#lib-fill").disabled = false; $("#lib-fill-st").textContent = "✓"; loadLibrary(); });
  };
  META = await api("/api/meta");
  initViewer();
  buildEditorControls();
  buildBatch();
  buildExport();
  await loadLibrary();
  await newDino({});
}
boot().catch((e) => toast("Falha ao iniciar: " + e.message, true));
