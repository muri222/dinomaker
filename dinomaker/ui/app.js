/* DinoMaker — painel de criação/edição (cliente). */
"use strict";

const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const el = (tag, attrs = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const k of kids) if (k !== null && k !== undefined) e.append(k);
  return e;
};
const svg = (d) => {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("class", "i");
  s.innerHTML = d;
  return s;
};
const clone = (o) => JSON.parse(JSON.stringify(o));

const PT = {
  feat: {
    teeth: "Dentes", fangs: "Presas de cima", beak: "Bico", tusks: "Presas de baixo", beard: "Barba",
    horns_brow: "Chifres na testa", horn_nose: "Chifre no nariz", horns_long: "Chifres longos", horn_unicorn: "Chifre de unicórnio",
    horns_ram: "Chifres de carneiro", antlers: "Galhada", ears: "Orelhas", crown: "Coroa", dome: "Cúpula",
    frill: "Babado (frill)", frill_spikes: "Espinhos no babado", cheek_frills: "Abas nas bochechas", gem: "Gema",
    third_eye: "Terceiro olho", halo: "Auréola", crest_small: "Cristinha", crest_fan: "Crista leque",
    crest_tube: "Crista tubo", crest_double: "Crista dupla", crest_head: "Crista de ptero",
    plates: "Placas", sail: "Vela", hump: "Corcunda", back_spikes: "Espinhos", spines_long: "Espinhos longos",
    dorsal_fins: "Nadadeiras", crystals: "Cristais", armor: "Armadura", shell: "Casco", side_spikes: "Espinhos laterais",
    neck_spikes: "Espinhos no pescoço", mane: "Juba", warts: "Verrugas", thagomizer: "Espetos na cauda",
    club: "Clava", tail_fan: "Cauda leque", tail_fork: "Cauda bifurcada", tail_flame: "Cauda de fogo",
    sickle_claw: "Garra foice", big_claws: "Garras grandes", thumb_spike: "Espinho no polegar", feathers: "Penas",
    leg_feathers: "Pernas peludas", arm_wings: "Asas nos braços", wings: "Asas (ptero)", glow_eyes: "Olhos brilhantes",
  },
  arch: {
    theropod: "Terópode", raptor: "Raptor", spinosaur: "Espinossauro", sauropod: "Saurópode",
    ceratopsian: "Ceratopsídeo", stegosaur: "Estegossauro", ankylosaur: "Anquilossauro",
    hadrosaur: "Hadrossauro", pachycephalosaur: "Paquicefalossauro", pterosaur: "Pterossauro",
  },
  clip: { Idle: "Parado", Walk: "Andar", Run: "Correr", Attack: "Atacar", Roar: "Rugir", Hit: "Dano",
    Eat: "Comer", Death: "Morrer", Fly: "Voar", Flap: "Asas" },
  group: { head: "Cabeça", neck: "Pescoço", tail: "Cauda", legs: "Pernas", arms: "Braços",
    body: "Corpo (comprimento)", bulk: "Robustez (largura)" },
  color: { primary: "Corpo", belly: "Barriga", accent: "Destaque", pattern: "Padrão", pattern2: "Padrão 2",
    claw: "Garras", horn: "Chifres", eye: "Íris", pupil: "Pupila", glow: "Brilho", mouth: "Boca", tooth: "Dentes" },
  pattern: { none: "Liso", spots: "Manchas", stripes: "Listras", tiger: "Tigre", dorsal: "Faixa dorsal", bands: "Anéis",
    mottled: "Mesclado", rosettes: "Rosetas", lava: "Lava", zigzag: "Raio", galaxy: "Galáxia", checker: "Xadrez",
    gradient: "Degradê", speckles: "Pintinhas", camo: "Camuflado", hearts: "Corações", stars: "Estrelas",
    scales: "Escamas", split: "Meio a meio" },
  eyes: { cute: "Fofo", fierce: "Feroz", glow: "Brilhante" },
  vfx: { fire: "Fogo", ice: "Gelo", electric: "Elétrico", magic: "Mágico", toxic: "Tóxico", nature: "Natureza",
    water: "Água", none: "Só poeira" },
  attack: { bite: "Mordida", claw: "Garras", headbutt: "Cabeçada", tailswipe: "Rabada", stomp: "Pisão", peck: "Bicada" },
};

let META = null, spec = null, loaded = null, editingId = null, lastData = null, LIB = [];
const UNDO = [], REDO = [];

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
  toast.h = setTimeout(() => (t.className = bad ? "bad" : ""), 4200);
}

/* ================================ 3D ================================ */
const V = { clip: "Idle", t: 0, fx: true };
function initViewer() {
  const host = $("#viewport");
  V.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  V.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  V.renderer.outputEncoding = THREE.sRGBEncoding;
  host.append(V.renderer.domElement);
  V.scene = new THREE.Scene();
  V.camera = new THREE.PerspectiveCamera(38, 1, 1, 5000);
  V.controls = new THREE.OrbitControls(V.camera, V.renderer.domElement);
  V.controls.enableDamping = true;
  V.scene.add(new THREE.HemisphereLight(0xe8f4ff, 0x30363f, 0.8));
  const key = new THREE.DirectionalLight(0xffffff, 0.75);
  key.position.set(-1.2, 2, -1.4);
  V.scene.add(key);
  const rim = new THREE.DirectionalLight(0x4cc4ea, 0.25);
  rim.position.set(1.5, 0.8, 1.6);
  V.scene.add(rim);
  V.grid = new THREE.GridHelper(800, 80, 0x2b3540, 0x1b2129);
  V.scene.add(V.grid);
  V.root = new THREE.Group();
  V.scene.add(V.root);
  initParticles();
  V.clock = new THREE.Clock();
  const resize = () => {
    const w = host.clientWidth, h = host.clientHeight;
    V.renderer.setSize(w, h);
    V.camera.aspect = w / Math.max(h, 1);
    V.camera.updateProjectionMatrix();
  };
  new ResizeObserver(resize).observe(host);
  resize();
  V.camera.position.set(120, 90, -160);
  const loop = () => {
    requestAnimationFrame(loop);
    const dt = Math.min(V.clock.getDelta(), 0.05);
    animate(dt);
    stepParticles(dt);
    V.controls.update();
    if (V.scene.fog && V.size) {  // névoa só no chão distante: acompanha o zoom, o dino nunca escurece
      const d = V.camera.position.distanceTo(V.controls.target);
      V.scene.fog.near = d + V.size * 0.8;
      V.scene.fog.far = d + V.size * 3;
    }
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
  V.vfx = data.vfx;
  if (!V.anims[V.clip]) V.clip = "Idle";
  buildClipBar();
  animate(0);
  if (refit) fitCamera();
}

function animate(dt) {
  if (!V.anims || !V.anims[V.clip]) return;
  const a = V.anims[V.clip];
  V.t += dt;
  let f = V.t * a.fps;
  if (a.loop) f = f % a.n;
  else if (f >= a.n - 1) {
    f = a.n - 1;
    if (V.t * a.fps > a.n + a.fps * 1.2) { V.t = 0; onClipStart(); }
  }
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
  V.camera.position.set(c.x + size * 0.78, c.y + size * 0.42, c.z - size * 0.88);
  V.camera.near = size / 100; V.camera.far = size * 20;
  V.size = size;
  V.scene.fog = V.scene.fog || new THREE.Fog(0x0b0d10, 1, 2);
  V.controls.maxDistance = size * 6;
  V.controls.minDistance = size * 0.15;
  V.camera.updateProjectionMatrix();
}

function buildClipBar() {
  const bar = $("#clipbar");
  bar.innerHTML = "";
  for (const name of Object.keys(V.anims)) {
    bar.append(el("button", { class: "chip", "aria-pressed": String(name === V.clip),
      onclick: () => { V.clip = name; V.t = 0; onClipStart(); buildClipBar(); } }, PT.clip[name] || name));
  }
}

/* ---------- partículas (preview dos VFX) ---------- */
const PMAX = 900;
function initParticles() {
  const g = new THREE.BufferGeometry();
  V.pPos = new Float32Array(PMAX * 3);
  V.pCol = new Float32Array(PMAX * 3);
  g.setAttribute("position", new THREE.BufferAttribute(V.pPos, 3));
  g.setAttribute("color", new THREE.BufferAttribute(V.pCol, 3));
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const x = c.getContext("2d");
  const grd = x.createRadialGradient(32, 32, 0, 32, 32, 32);
  grd.addColorStop(0, "rgba(255,255,255,1)"); grd.addColorStop(0.35, "rgba(255,255,255,.6)"); grd.addColorStop(1, "rgba(255,255,255,0)");
  x.fillStyle = grd; x.fillRect(0, 0, 64, 64);
  V.pMat = new THREE.PointsMaterial({ size: 4, map: new THREE.CanvasTexture(c), vertexColors: true, transparent: true,
    depthWrite: false, blending: THREE.AdditiveBlending, sizeAttenuation: true });
  V.points = new THREE.Points(g, V.pMat);
  V.points.frustumCulled = false;
  V.scene.add(V.points);
  V.parts = [];
  V.emitAcc = 0;
}
const hexRGB = (h) => { const n = parseInt(h.slice(1), 16); return [(n >> 16 & 255) / 255, (n >> 8 & 255) / 255, (n & 255) / 255]; };
function anchorWorld(a) {
  const m = V.meshes && V.meshes[a.bone];
  return m ? new THREE.Vector3(...a.local).applyMatrix4(m.matrix) : null;
}
function spawn(p, origin, dir, spread, count) {
  if (!p || !origin) return;
  const k = V.vfx.scale;
  const cols = p.colors.map((c) => hexRGB(c || "#ffffff"));
  for (let i = 0; i < count && V.parts.length < PMAX; i++) {
    const d = dir ? dir.clone() : new THREE.Vector3(Math.random() - .5, Math.random() - .5, Math.random() - .5).normalize();
    if (dir) d.add(new THREE.Vector3(Math.random() - .5, Math.random() - .5, Math.random() - .5).multiplyScalar(spread)).normalize();
    const sp = (p.speed[0] + Math.random() * (p.speed[1] - p.speed[0])) * k;
    const life = p.life[0] + Math.random() * (p.life[1] - p.life[0]);
    const jitter = new THREE.Vector3(Math.random() - .5, Math.random() - .5, Math.random() - .5).multiplyScalar(6);
    V.parts.push({ p: origin.clone().add(dir ? new THREE.Vector3() : jitter), v: d.multiplyScalar(sp),
      a: new THREE.Vector3(...(p.accel || [0, 0, 0])).multiplyScalar(k), t: 0, life, cols });
  }
}
function onClipStart() {
  if (!V.fx || !V.vfx || !V.vfx.opt.breath) return;
  if (V.clip !== "Roar" && V.clip !== "Attack") return;
  const delay = V.clip === "Roar" ? 450 : 400;
  setTimeout(() => {
    const head = V.meshes[V.vfx.anchors.mouth.bone];
    const o = anchorWorld(V.vfx.anchors.mouth);
    if (!o) return;
    const fwd = new THREE.Vector3(0, 0, -1).transformDirection(head.matrix);
    spawn(V.vfx.breath, o, fwd, 0.35, Math.round((V.clip === "Roar" ? 60 : 25) * V.vfx.opt.intensity));
  }, delay);
}
function stepParticles(dt) {
  const vx = V.vfx;
  if (V.fx && vx && vx.aura && V.meshes) {
    V.emitAcc += dt * vx.aura.rate;
    const n = Math.floor(V.emitAcc);
    V.emitAcc -= n;
    if (n > 0) {
      spawn(vx.aura, anchorWorld(vx.anchors.body), null, 0, n);
      if (vx.anchors.tail && Math.random() < 0.5) spawn(vx.aura, anchorWorld(vx.anchors.tail), null, 0, Math.ceil(n / 2));
    }
    V.pMat.size = Math.max(1.5, (vx.aura.size[0] || 0.4) * vx.scale * 4);
  } else if (vx && vx.breath) {
    V.pMat.size = Math.max(1.5, (vx.breath.size[0] || 0.6) * vx.scale * 3.5);
  }
  const keep = [];
  for (const q of V.parts) {
    q.t += dt;
    if (q.t >= q.life) continue;
    q.v.addScaledVector(q.a, dt).multiplyScalar(1 - dt * 0.8);
    q.p.addScaledVector(q.v, dt);
    keep.push(q);
  }
  V.parts = keep;
  for (let i = 0; i < PMAX; i++) {
    const q = V.parts[i];
    if (!q) { V.pPos[i * 3 + 1] = -99999; continue; }
    V.pPos.set([q.p.x, q.p.y, q.p.z], i * 3);
    const u = q.t / q.life, cs = q.cols, k = Math.min(cs.length - 1, u * (cs.length - 1));
    const a = cs[Math.floor(k)], b = cs[Math.min(cs.length - 1, Math.floor(k) + 1)], w = k - Math.floor(k);
    const fade = 1 - u;
    V.pCol.set([(a[0] + (b[0] - a[0]) * w) * fade, (a[1] + (b[1] - a[1]) * w) * fade, (a[2] + (b[2] - a[2]) * w) * fade], i * 3);
  }
  V.points.geometry.attributes.position.needsUpdate = true;
  V.points.geometry.attributes.color.needsUpdate = true;
}

/* ================================ CONTROLES ================================ */
const CTL = [];   // {sync()} de cada controle
function setRangeFill(inp) {
  const p = ((inp.value - inp.min) / (inp.max - inp.min)) * 100;
  inp.style.setProperty("--p", p + "%");
}
function slider({ label, min, max, step, get, set, fmt = (x) => (+x).toFixed(2), isSet, reset }) {
  const v = el("span", { class: "v" });
  const inp = el("input", { type: "range", min, max, step });
  const rs = el("button", { class: "rs", title: "Voltar ao padrão", onclick: () => change(() => reset()) }, svg('<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>'));
  const box = el("div", { class: "ctl" }, el("div", { class: "top" }, el("span", {}, label), reset ? rs : null, v), inp);
  inp.addEventListener("input", () => { change(() => set(+inp.value), true); v.textContent = fmt(inp.value); setRangeFill(inp); });
  CTL.push({ sync: () => { const x = get(); inp.value = x; v.textContent = fmt(x); setRangeFill(inp); box.classList.toggle("set", !!(isSet && isSet())); } });
  return box;
}
function chipToggle(label, get, set, cls = "chip") {
  const b = el("button", { class: cls, onclick: () => change(() => set(!get())) }, label);
  CTL.push({ sync: () => b.setAttribute("aria-pressed", String(!!get())) });
  return b;
}
function chipChoice(options, get, set, cls = "chip solid") {
  const wrap = el("div", { class: "chips" });
  const btns = options.map(([val, label]) => {
    const b = el("button", { class: cls, onclick: () => change(() => set(val)) }, label);
    wrap.append(b);
    return [val, b];
  });
  CTL.push({ sync: () => btns.forEach(([val, b]) => b.setAttribute("aria-pressed", String(get() === val))) });
  return wrap;
}
function colorSw(key) {
  const inp = el("input", { type: "color" });
  const hex = el("span", { class: "hex" });
  const lab = el("label", { class: "sw" }, inp, el("span", {}, PT.color[key] || key), hex);
  inp.addEventListener("input", () => { change(() => (spec.palette[key] = inp.value), true); hex.textContent = inp.value; });
  CTL.push({ sync: () => {
    const v = spec.palette[key] || (lastData && lastData.colors[key]) || "#888888";
    inp.value = v; hex.textContent = v;
  } });
  return lab;
}
function section(title, open, ...kids) {
  const meta = el("span", { class: "label" });
  const d = el("details", { class: "sec", open }, el("summary", {}, title, meta), el("div", { class: "body" }, ...kids));
  d.meta = meta;
  return d;
}
const sub = (t) => el("div", { class: "sub" }, t);
const fieldrow = (label, ctl) => el("label", { class: "fieldrow" }, el("span", {}, label), ctl);

function buildSections() {
  const host = $("#sections");
  host.innerHTML = "";
  CTL.length = 0;
  const g = () => lastData && lastData.genome;
  const P = (k) => (spec.params[k] !== undefined ? spec.params[k] : (g() ? g().params[k] : 0));

  // ---- base
  const base = el("select", { class: "input" });
  for (const a of META.archetypes) {
    const og = el("optgroup", { label: PT.arch[a.key] || a.key });
    for (const sp of META.species[a.key] || []) og.append(el("option", { value: "sp:" + sp.key }, sp.name));
    og.append(el("option", { value: "fa:" + a.key }, "✦ Fantasia (corpo de " + (PT.arch[a.key] || a.key) + ")"));
    base.append(og);
  }
  base.onchange = () => {
    const [k, v] = base.value.split(":");
    newDino(k === "sp" ? { species: v } : { archetype: v, fantasy: true });
  };
  CTL.push({ sync: () => { const v = spec.species ? "sp:" + spec.species : "fa:" + spec.archetype; base.value = v; } });
  const attack = el("select", { class: "input" }, ...META.attacks.map((a) => el("option", { value: a }, PT.attack[a] || a)));
  attack.onchange = () => change(() => (spec.attack = attack.value));
  CTL.push({ sync: () => (attack.value = spec.attack) });
  host.append(section("Base", true,
    fieldrow("Espécie / corpo", base),
    slider({ label: "Tamanho geral", min: 0.05, max: 0.4, step: 0.005, get: () => spec.px_size, set: (v) => (spec.px_size = v),
      fmt: (x) => (+x).toFixed(3) + " stud/px" }),
    slider({ label: "Personalidade (calmo → agitado)", min: 0.4, max: 1.8, step: 0.05,
      get: () => (spec.anim.energy ?? 1), set: (v) => (spec.anim.energy = v), fmt: (x) => "×" + (+x).toFixed(2),
      isSet: () => spec.anim.energy !== undefined, reset: () => delete spec.anim.energy }),
    el("div", { class: "chips" }, chipToggle("Chibi (cabeça e olhos maiores)", () => spec.chibi, (on) => {
      spec.chibi = on;
      spec.variation.head = +(spec.variation.head * (on ? 1.25 : 1 / 1.25)).toFixed(3);
      spec.variation.legs = +(spec.variation.legs * (on ? 0.85 : 1 / 0.85)).toFixed(3);
    })),
    fieldrow("Ataque", attack),
  ));

  // ---- proporções
  host.append(section("Proporções", true, ...META.groups.map((gk) => slider({
    label: PT.group[gk], min: 0.5, max: 1.8, step: 0.01, get: () => spec.variation[gk] ?? 1,
    set: (v) => (spec.variation[gk] = v), fmt: (x) => "×" + (+x).toFixed(2) }))));

  // ---- medidas avançadas
  const groups = {};
  for (const p of META.params) (groups[p.group] = groups[p.group] || []).push(p);
  const adv = [];
  for (const [gname, list] of Object.entries(groups)) {
    adv.push(sub(gname));
    for (const p of list) {
      adv.push(slider({ label: p.label, min: p.min, max: p.max, step: p.step, get: () => P(p.key),
        set: (v) => (spec.params[p.key] = p.int ? Math.round(v) : v), fmt: (x) => (p.int ? Math.round(x) : (+x).toFixed(p.step < 0.1 ? 2 : 1)),
        isSet: () => spec.params[p.key] !== undefined, reset: () => delete spec.params[p.key] }));
    }
  }
  const advSec = section("Medidas avançadas", false, el("p", { class: "small" }, "Ajuste fino de cada peça. Valores destacados em ciano foram fixados por você; ↺ volta ao automático."), ...adv);
  host.append(advSec);
  CTL.push({ sync: () => (advSec.meta.textContent = Object.keys(spec.params).length + " fixadas") });

  // ---- cores
  const pal = el("select", { class: "input" }, el("option", { value: "" }, "— aplicar paleta pronta —"),
    ...Object.keys(META.palettes).map((p) => el("option", { value: p }, p)));
  pal.onchange = () => { if (pal.value) change(() => Object.assign(spec.palette, META.palettes[pal.value])); pal.value = ""; };
  const adj = (k, label, min, max, step, def, fmt) => slider({ label, min, max, step, get: () => spec.color_adjust[k] ?? def,
    set: (v) => (spec.color_adjust[k] = v), fmt, isSet: () => spec.color_adjust[k] !== undefined && spec.color_adjust[k] !== def,
    reset: () => delete spec.color_adjust[k] });
  const tex = (k, label, min, max, step, def, fmt) => slider({ label, min, max, step, get: () => spec.texture[k] ?? def,
    set: (v) => (spec.texture[k] = v), fmt, isSet: () => spec.texture[k] !== undefined, reset: () => delete spec.texture[k] });
  host.append(section("Cores", true,
    pal,
    el("div", { class: "colors" }, ...["primary", "belly", "accent", "pattern", "pattern2", "horn", "claw", "eye", "pupil", "glow", "mouth", "tooth"].map(colorSw)),
    sub("Ajuste global"),
    adj("hue", "Matiz", -180, 180, 1, 0, (x) => Math.round(x) + "°"),
    adj("sat", "Saturação", 0, 2, 0.01, 1, (x) => "×" + (+x).toFixed(2)),
    adj("val", "Brilho", 0.3, 1.6, 0.01, 1, (x) => "×" + (+x).toFixed(2)),
    adj("contrast", "Contraste", 0.5, 1.6, 0.01, 1, (x) => "×" + (+x).toFixed(2)),
    sub("Textura"),
    tex("belly", "Altura da barriga", 0, 0.5, 0.01, 0.3, (x) => Math.round(x * 100) + "%"),
    tex("grain", "Granulado pixel", 0, 3, 0.05, 1, (x) => "×" + (+x).toFixed(2)),
  ));

  // ---- padrão
  host.append(section("Padrão da pele", true,
    chipChoice(META.patterns.map((p) => [p, PT.pattern[p] || p]), () => spec.pattern.type, (v) => (spec.pattern.type = v)),
    slider({ label: "Escala", min: 3, max: 10, step: 1, get: () => spec.pattern.scale ?? 6, set: (v) => (spec.pattern.scale = v), fmt: (x) => Math.round(x) }),
    slider({ label: "Densidade", min: 0.1, max: 1, step: 0.05, get: () => spec.pattern.density ?? 0.6, set: (v) => (spec.pattern.density = v) }),
    el("div", { class: "chips" }, chipToggle("Padrão também nas pernas", () => spec.texture.pattern_legs, (v) => (spec.texture.pattern_legs = v))),
  ));

  // ---- olhos
  host.append(section("Olhos", false,
    chipChoice(META.eye_styles.map((s) => [s, PT.eyes[s] || s]), () => spec.eyes.style, (v) => (spec.eyes.style = v)),
    slider({ label: "Tamanho", min: 1, max: 6, step: 1, get: () => spec.eyes.size, set: (v) => (spec.eyes.size = v), fmt: (x) => Math.round(x) }),
    el("div", { class: "colors" }, colorSw("eye"), colorSw("pupil")),
  ));

  // ---- partes
  const featSec = section("Partes", true, ...Object.entries(META.feature_groups).flatMap(([gname, list]) => [
    sub(gname),
    el("div", { class: "chips" }, ...list.map((f) => chipToggle(PT.feat[f] || f, () => spec.features_exact.includes(f), (on) => {
      const s = new Set(spec.features_exact);
      on ? s.add(f) : s.delete(f);
      spec.features_exact = [...s];
    }))),
  ]));
  host.append(featSec);
  CTL.push({ sync: () => (featSec.meta.textContent = spec.features_exact.length + " ativas") });

  // ---- vfx
  const vf = (k) => (spec.vfx[k] !== undefined ? spec.vfx[k] : META.vfx_defaults[k]);
  const vset = (k) => (v) => (spec.vfx[k] = v);
  const vcol = el("input", { type: "color" });
  const vhex = el("span", { class: "hex" });
  vcol.addEventListener("input", () => { change(() => (spec.vfx.color = vcol.value), true); vhex.textContent = vcol.value; });
  CTL.push({ sync: () => {
    const c = spec.vfx.color || (lastData && lastData.vfx.glow) || (lastData && lastData.colors.glow) || "#4cc4ea";
    vcol.value = c; vhex.textContent = spec.vfx.color ? c : "do tema";
  } });
  host.append(section("Efeitos (VFX)", false,
    chipChoice([["", "Automático"], ...META.vfx.map((t) => [t, PT.vfx[t] || t])], () => spec.vfx.theme || "", vset("theme")),
    el("div", { class: "colors" }, el("label", { class: "sw" }, vcol, el("span", {}, "Cor dos efeitos"), vhex),
      el("button", { class: "chip", onclick: () => change(() => delete spec.vfx.color) }, "usar cor do tema")),
    slider({ label: "Intensidade", min: 0, max: 3, step: 0.05, get: () => vf("intensity"), set: vset("intensity"), fmt: (x) => "×" + (+x).toFixed(2) }),
    slider({ label: "Tamanho das partículas", min: 0.3, max: 3, step: 0.05, get: () => vf("size"), set: vset("size"), fmt: (x) => "×" + (+x).toFixed(2) }),
    slider({ label: "Brilho da luz", min: 0, max: 5, step: 0.1, get: () => vf("brightness"), set: vset("brightness"), fmt: (x) => (+x).toFixed(1) }),
    el("div", { class: "chips" }, ...[["aura", "Aura"], ["breath", "Bafo"], ["dust", "Poeira"], ["burst", "Faíscas"], ["light", "Luz"]]
      .map(([k, l]) => chipToggle(l, () => vf(k), vset(k)))),
  ));
}

function syncControls() {
  $("#f-name").value = spec.name || "";
  CTL.forEach((c) => c.sync());
  $("#editing").innerHTML = editingId ? `Editando <b>${editingId}</b> · salvar por cima mantém o lugar dele` : "Novo dino (ainda não salvo)";
  $("#b-save-replace").disabled = !editingId;
  $("#t-undo").disabled = !UNDO.length;
  $("#t-redo").disabled = !REDO.length;
}

/* ---------- mudanças, desfazer/refazer ---------- */
let pendingSnap = null, snapTimer = null;
function change(fn, continuous = false) {
  const before = JSON.stringify(spec);
  fn();
  if (continuous) {
    if (!pendingSnap) pendingSnap = before;
    clearTimeout(snapTimer);
    snapTimer = setTimeout(() => { UNDO.push(pendingSnap); pendingSnap = null; REDO.length = 0; syncControls(); }, 500);
  } else {
    UNDO.push(before);
    REDO.length = 0;
  }
  if (UNDO.length > 200) UNDO.shift();
  if (!continuous) syncControls();
  schedulePreview(continuous ? 300 : 120);
}
function undo() {
  if (!UNDO.length) return;
  REDO.push(JSON.stringify(spec));
  spec = JSON.parse(UNDO.pop());
  syncControls(); schedulePreview(60);
}
function redo() {
  if (!REDO.length) return;
  UNDO.push(JSON.stringify(spec));
  spec = JSON.parse(REDO.pop());
  syncControls(); schedulePreview(60);
}
function rnd(a, b) { return a + Math.random() * (b - a); }
function mutateShape() {
  change(() => {
    for (const k of META.groups) spec.variation[k] = +Math.min(1.8, Math.max(0.5, (spec.variation[k] ?? 1) * rnd(0.86, 1.16))).toFixed(3);
    spec.px_size = +Math.min(0.4, Math.max(0.05, spec.px_size * rnd(0.9, 1.1))).toFixed(3);
  });
}
function hsl2hex(h, s, l) {
  const f = (n) => { const k = (n + h / 30) % 12, a = s * Math.min(l, 1 - l); return Math.round(255 * (l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1)))); };
  return "#" + [f(0), f(8), f(4)].map((x) => x.toString(16).padStart(2, "0")).join("");
}
function mutateColor() {
  change(() => {
    const h = rnd(0, 360), sch = Math.random();
    const acc = (h + (sch < 0.5 ? 180 : 120) + rnd(-20, 20)) % 360;
    spec.palette.primary = hsl2hex(h, rnd(0.45, 0.8), rnd(0.38, 0.55));
    spec.palette.belly = hsl2hex((h + rnd(20, 50)) % 360, rnd(0.35, 0.7), rnd(0.72, 0.86));
    spec.palette.accent = hsl2hex(acc, rnd(0.6, 0.9), rnd(0.5, 0.62));
    spec.palette.pattern = hsl2hex(h, rnd(0.5, 0.8), rnd(0.22, 0.34));
    spec.palette.pattern2 = hsl2hex(acc, rnd(0.4, 0.7), rnd(0.3, 0.45));
    spec.color_adjust = {};
  });
}

/* ---------- preview ---------- */
let previewTimer = null, previewSeq = 0;
function schedulePreview(ms = 250) {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(() => runPreview(false), ms);
}
async function runPreview(refit) {
  const seq = ++previewSeq;
  $("#busy").classList.add("on");
  try {
    const data = await api("/api/preview", { spec, exclude: editingId });
    if (seq !== previewSeq) return;
    lastData = data;
    buildModel(data, refit);
    showStats(data);
    showOriginality(data.originality);
    CTL.forEach((c) => { if (!c.focus) c.sync(); });
  } catch (e) {
    toast("Erro no preview: " + e.message, true);
  } finally {
    if (seq === previewSeq) $("#busy").classList.remove("on");
  }
}
function showStats(d) {
  const s = d.stats;
  $("#stats").innerHTML = `<b>${s.altura}</b> altura · <b>${s.comprimento}</b> comp. studs · andar <b>${s.walk}</b> · correr <b>${s.run}</b> · ${s.pecas} peças · ${s.ossos} ossos · ${s.ms} ms`;
}
function showOriginality(o) {
  const pct = Math.round(o.score * 100), lim = Math.round(o.threshold * 100);
  const col = !o.ok ? "var(--neg)" : o.score > o.threshold - 0.1 ? "var(--warn)" : "var(--accent)";
  const msg = o.name_taken ? "Já existe um dino com esse nome." :
    o.ok ? (o.nearest ? `Original · mais parecido: <b>${o.nearest}</b> (${pct}%)` : "Original") :
      `Parecido demais com <b>${o.nearest}</b> (${pct}% ≥ ${lim}%). Mude partes, padrão ou proporções.`;
  $("#orig").innerHTML = `${msg}<div class="bar"><i style="width:${pct}%;background:${col}"></i><s style="left:${lim}%"></s></div>`;
}

async function newDino(body) {
  try {
    $("#busy").classList.add("on");
    const r = await api("/api/new", body);
    loadSpec(r.spec, null);
  } catch (e) { toast(e.message, true); $("#busy").classList.remove("on"); }
}
function normalize(s) {
  s.params = s.params || {}; s.vfx = s.vfx || {}; s.color_adjust = s.color_adjust || {};
  s.texture = s.texture || {}; s.anim = s.anim || {}; s.palette = s.palette || {};
  s.features_exact = s.features_exact || [];
  return s;
}
function loadSpec(s, id) {
  spec = normalize(clone(s));
  loaded = clone(spec);
  editingId = id;
  savedSnap = id ? JSON.stringify(spec) : null;
  UNDO.length = 0; REDO.length = 0;
  syncControls();
  runPreview(true);
}
async function save(mode, then) {
  try {
    const snap = JSON.stringify(spec);
    const job = await api("/api/save", { spec, mode, replace_id: editingId, force: $("#f-force").checked });
    toast("Gerando " + spec.name + " no Blender… acompanhe no topo.");
    watchJob(job, null, (j) => {
      toast("Salvo: " + j.result.name);
      editingId = j.result.id;
      savedSnap = snap;
      syncControls();
      loadLibrary();
      if (then) then(j.result.id);
    });
  } catch (e) {
    toast(e.status === 409 ? "Não salvei: " + e.message + " (marque \"salvar mesmo se parecido\" para forçar)" : "Erro: " + e.message, true);
  }
}
let savedSnap = null;
function exportCurrent() {
  if (editingId && savedSnap === JSON.stringify(spec)) return exportIds([editingId], spec.name);
  save(editingId ? "replace" : "new", (id) => exportIds([id], spec.name));
}

/* exporta ids -> zip (FBX + kits + plugin) e baixa sozinho */
function exportIds(ids, name, bar, log, done) {
  if (!ids.length) return toast("Nenhum dino para exportar.", true);
  return api("/api/export", { ids, name }).then((job) => {
    toast(`Exportando ${ids.length} dino(s)… os que ainda não têm FBX são gerados agora.`);
    watchJob(job, (j) => {
      if (log) log.textContent = j.log.join("\n");
      if (bar && j.progress) bar.style.width = (100 * j.progress.done / j.progress.total) + "%";
    }, (j) => {
      if (bar) bar.style.width = "100%";
      if (log) log.innerHTML += `\n${j.result.count} dinos · <a href="${j.result.zip}">baixar zip de novo</a>`;
      toast(`Pronto: ${j.result.count} dino(s) em exportados/${j.result.name}`);
      api("/api/open", { name: j.result.name }).catch(() => (window.location.href = j.result.zip));
      if (done) done(j);
    });
  }).catch((e) => toast("Erro ao exportar: " + e.message, true));
}

/* ================================ JOBS ================================ */
const ACTIVE = new Map();
function watchJob(job, onTick, onDone) { ACTIVE.set(job.id, { onTick, onDone }); updateJobsBar(); }
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
  const b = $("#jobsbar");
  b.hidden = !ACTIVE.size;
  b.innerHTML = `<span class="spin"></span>${ACTIVE.size} tarefa(s)`;
}
setInterval(pollJobs, 1000);

/* ================================ BIBLIOTECA ================================ */
async function loadLibrary() {
  LIB = await api("/api/library");
  renderLibrary();
  renderExportList();
}
function matches(d, q) {
  q = q.trim().toLowerCase();
  return !q || [d.name, d.id, d.species, d.archetype, d.palette, d.pattern, PT.arch[d.archetype]].join(" ").toLowerCase().includes(q);
}
const PAGE = 120;
let libShown = PAGE;
function renderLibrary(more = false) {
  const q = $("#lib-search").value;
  const grid = $("#lib-grid");
  grid.innerHTML = "";
  libShown = more ? libShown + PAGE : PAGE;
  const list = LIB.filter((d) => matches(d, q));
  $("#lib-count").textContent = `${list.length} de ${LIB.length}`;
  $("#lib-more").hidden = list.length <= libShown;
  for (const d of list.slice(0, libShown)) grid.append(dinoCard(d));
}
function dinoCard(d) {
  const img = d.thumb ? el("img", { src: d.thumb, loading: "lazy", alt: "" }) : el("div", { class: "noimg" }, d.legacy ? "feito à mão" : "sem miniatura");
  const del = el("button", { class: "del", title: "Remover", onclick: async (ev) => {
    ev.stopPropagation();
    if (d.legacy) return toast("Dinos feitos à mão ficam no histórico para evitar cópias.");
    if (!confirm(`Remover "${d.name}" do histórico e apagar os arquivos?`)) return;
    await api("/api/forget", { id: d.id, delete_files: true });
    loadLibrary();
  } }, svg('<path d="M18 6 6 18M6 6l12 12"/>'));
  const exp = d.editable ? el("button", { class: "exp", title: "Exportar para o Roblox", onclick: (ev) => {
    ev.stopPropagation();
    exportIds([d.id], d.name);
  } }, svg('<path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/>')) : null;
  return el("div", { class: "dcard", onclick: async () => {
    if (!d.editable) return toast("Dino feito à mão: não dá para editar aqui.");
    const r = await api("/api/dino/" + d.id);
    showTab("editor");
    loadSpec(r.spec, d.id);
  } }, img, d.fantasy ? el("span", { class: "tagx" }, "fantasia") : null, exp, del,
    el("div", { class: "info" }, el("b", {}, d.name), el("small", {}, (PT.arch[d.archetype] || d.archetype) + " · " + (PT.pattern[d.pattern] || d.pattern || ""))));
}

/* ================================ LOTE ================================ */
function buildBatch() {
  const kinds = { v: "mix" };
  const kb = $("#bt-kinds");
  const kBtns = [["mix", "Misto"], ["real", "Só espécies reais"], ["fantasy", "Só fantasia"]].map(([v, l]) => {
    const b = el("button", { class: "chip solid", onclick: () => { kinds.v = v; kBtns.forEach(([vv, bb]) => bb.setAttribute("aria-pressed", String(vv === v))); } }, l);
    kb.append(b);
    return [v, b];
  });
  kBtns[0][1].setAttribute("aria-pressed", "true");
  const sel = { a: new Set(), t: new Set() };
  const toggles = (host, items, set) => items.forEach(([v, l]) => {
    const b = el("button", { class: "chip", "aria-pressed": "false", onclick: () => { set.has(v) ? set.delete(v) : set.add(v); b.setAttribute("aria-pressed", String(set.has(v))); } }, l);
    host.append(b);
  });
  toggles($("#bt-archs"), META.archetypes.map((a) => [a.key, PT.arch[a.key] || a.key]), sel.a);
  toggles($("#bt-themes"), META.themes.map((t) => [t, t]), sel.t);
  $("#bt-go").onclick = async () => {
    const body = { count: +$("#bt-count").value, name: $("#bt-name").value, kinds: kinds.v, archetypes: [...sel.a], themes: [...sel.t] };
    $("#bt-log").textContent = "escolhendo conceitos únicos…\n";
    $("#bt-bar").style.width = "2%";
    $("#bt-go").disabled = true;
    BATCH.ids = []; BATCH.name = body.name || "Lote";
    renderBatchResults();
    const job = await api("/api/batch", body);
    let seen = 0;
    watchJob(job, (j) => {
      $("#bt-log").textContent = j.log.join("\n");
      const p = j.progress;
      if (p && p.stage === "gerando") {
        $("#bt-bar").style.width = (100 * p.done / p.total) + "%";
        if (p.id && !p.error && !BATCH.ids.includes(p.id)) BATCH.ids.push(p.id);
        if (BATCH.ids.length - seen >= 3 || p.done === p.total) { seen = BATCH.ids.length; loadLibrary().then(renderBatchResults); }
      }
    }, (j) => {
      $("#bt-go").disabled = false;
      $("#bt-bar").style.width = "100%";
      BATCH.ids = j.result.ids;
      toast(`Lote pronto: ${j.result.ids.length} dinos novos.`);
      loadLibrary().then(renderBatchResults);
    });
  };
  $("#bt-export").onclick = () => exportIds(BATCH.ids, BATCH.name, $("#bt-bar"), $("#bt-log"));
}
const BATCH = { ids: [], name: "Lote" };
function renderBatchResults() {
  const by = new Map(LIB.map((d) => [d.id, d]));
  const list = BATCH.ids.map((i) => by.get(i)).filter(Boolean);
  $("#bt-results").hidden = !BATCH.ids.length;
  $("#bt-rcount").textContent = `${list.length} dino(s) neste lote`;
  $("#bt-export").disabled = !list.length;
  const grid = $("#bt-grid");
  const first = !grid.children.length && list.length;
  grid.innerHTML = "";
  list.forEach((d) => grid.append(dinoCard(d)));
  if (first) $("#bt-results").scrollIntoView({ behavior: "smooth", block: "start" });
}

/* ================================ EXPORTAR ================================ */
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
  $("#ex-go").onclick = () => {
    if (!EXSEL.size) return toast("Selecione pelo menos um dino.", true);
    $("#ex-log").textContent = "";
    $("#ex-bar").style.width = "2%";
    exportIds([...EXSEL], $("#ex-name").value, $("#ex-bar"), $("#ex-log"));
  };
}

/* ================================ BOOT ================================ */
function showTab(name) {
  $$(".nav-links a").forEach((a) => (a.dataset.tab === name ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current")));
  $$(".tab").forEach((t) => t.classList.toggle("on", t.id === "tab-" + name));
  if (location.hash !== "#" + name) history.replaceState(null, "", "#" + name);
}
async function boot() {
  $$("[data-tab]").forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); showTab(a.dataset.tab); }));
  $("#lib-search").oninput = () => renderLibrary();
  $("#lib-more").onclick = () => renderLibrary(true);
  $("#f-name").addEventListener("input", (e) => change(() => (spec.name = e.target.value), true));
  $("#b-random").onclick = () => { showTab("editor"); newDino(Math.random() < 0.5 ? { fantasy: true } : {}); };
  $("#b-save-new").onclick = () => save("new");
  $("#b-save-replace").onclick = () => save("replace");
  $("#b-export").onclick = exportCurrent;
  $("#t-undo").onclick = undo;
  $("#t-redo").onclick = redo;
  $("#t-mshape").onclick = mutateShape;
  $("#t-mcolor").onclick = mutateColor;
  $("#t-reset").onclick = () => loaded && change(() => (spec = clone(loaded)));
  $("#t-cam").onclick = fitCamera;
  $("#t-fx").onclick = () => { V.fx = !V.fx; $("#t-fx").setAttribute("aria-pressed", String(V.fx)); if (!V.fx) V.parts = []; };
  document.addEventListener("keydown", (e) => {
    if (e.target.matches("input[type=text],input[type=search],input[type=number]")) return;
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") { e.preventDefault(); e.shiftKey ? redo() : undo(); }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "y") { e.preventDefault(); redo(); }
  });
  META = await api("/api/meta");
  initViewer();
  buildSections();
  buildBatch();
  buildExport();
  const tab = location.hash.slice(1);
  if (["biblioteca", "lote", "exportar"].includes(tab)) showTab(tab);
  await loadLibrary();
  await newDino({});
}
boot().catch((e) => toast("Falha ao iniciar: " + e.message, true));
