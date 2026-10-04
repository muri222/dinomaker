# dinomaker

Gerador de dinossauros estilo Roblox (blocky + pixel art) com rig, animações e
histórico para nunca repetir um dino. Cada geração sai em dois formatos:

| | Versão A — Parts (`.rbxmx`/`.rbxm`) | Versão B — Mesh (`.fbx` + PBR) |
|---|---|---|
| Uso no Studio | Insert from File / arrastar — **pronto** | Import 3D + SurfaceAppearance + importar animações |
| Visual | Parts coloridas + placas pixel art (Neon nos brilhos) | Textura pixel art 1024px com normal/roughness |
| Animações | Embutidas (KeyframeSequence) e tocadas por script, sem publicar nada | FBX por animação para o Animation Editor |
| Extras | Humanoid, DinoAnimator (cliente), DinoBrain (servidor), DinoAPI | `.blend` e `.glb` para editar/visualizar |

Animações: **Idle, Walk, Run, Attack, Roar, Hit, Eat, Death** (+ **Fly** para pterossauros).
Andar/correr usam IK nas pernas e `WalkSpeed`/`RunSpeed` calculados para o pé não escorregar.

## Instalação
```bash
pip install -r requirements.txt          # numpy + pillow
# Blender 4.2+ instalado (Windows: detectado em C:\Program Files\Blender Foundation\)
# ou: set DINOMAKER_BLENDER=C:\caminho\blender.exe
cd tools && npm install                  # opcional: valida o .rbxmx e gera o .rbxm binário
```

## Uso
```bash
python -m dinomaker new                              # 1 dino aleatório e único
python -m dinomaker new --count 5 --fantasy          # 5 criaturas de fantasia
python -m dinomaker new --species triceratops --palette candy --chibi
python -m dinomaker new --spec specs/exemplo_rex_magma.json
python -m dinomaker check specs/meu.json             # similaridade com o histórico
python -m dinomaker list | species | forget <id>
```
Saída em `output/<id>/` com `README.md` explicando a importação daquele dino.

Com o Claude Code, use a skill **`/dino`** (`.claude/skills/dino/SKILL.md`): o Claude cria o
conceito (nome, espécie real ou fantasia, paleta, gancho visual), checa o histórico,
gera, revisa os previews e entrega.

## Como funciona
```
spec (parcial) ─► genome.resolve ─► checagem de similaridade com history/history.json
       │                                   (arquétipo, proporções, features, cores, padrão)
       ▼
 model.build_model  ─ ossos + caixas em "pixels" (1 px = 1 texel), 10 arquétipos, 30+ features
 texture.paint_faces ─ pixel art por face (barriga, padrões no espaço do mundo, olhos, boca...)
 anims.bake          ─ FK + IK planar nas pernas, ciclos de passada sem escorregar
       ├─► export_rbx  → A: .rbxmx (Parts, Motor6D, Humanoid, KeyframeSequences, scripts)
       └─► blender_build (dentro do Blender) → B: .fbx, anims/*.fbx, .glb, .blend, previews
```
- **Arquétipos**: theropod, raptor, spinosaur, sauropod, ceratopsian, stegosaur, ankylosaur,
  hadrosaur, pachycephalosaur, pterosaur. **34 espécies reais** pré-configuradas.
- **Fantasia**: cristais, lava, galáxia, chifres de cervo, juba, gema, presas, olhos brilhantes...
- **Unicidade**: similaridade ≥ 0.82 com qualquer dino do histórico é recusada (ajustável com `--threshold`).
  O histórico já inclui os 8 dinos feitos à mão (`tools/seed_legacy.py`).

## Ferramentas de QA
- `tools/validate_rbx.js` — lê o `.rbxmx` com o rbx-dom (reflexão oficial da API do Roblox),
  falha em propriedade inválida e grava o `.rbxm`.
- `tools/preview_rbx.py` — simula o rig Motor6D + KeyframeSequence como o Roblox faz e renderiza.
- `python -m unittest discover tests`

## Script API (versão A)
```lua
local API = require(workspace.RexMagma.DinoAPI)
API.Play(dino, "Roar")              -- Attack | Roar | Hit | Eat
API.Walk(dino, Vector3.new(20,0,0)) -- usa o WalkSpeed que bate com a animação
API.Run(dino, pos)
API.SetFlying(dino, true)           -- pterossauros
API.Kill(dino)                      -- toca Death
```
Atributo `Wander = true` no Model faz o dino passear sozinho (bom para testar).
