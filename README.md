# dinomaker

Gerador de dinossauros estilo Roblox (blocky + pixel art) com rig, animações e
histórico para nunca repetir um dino. Cada geração sai em dois formatos:

| | Versão A — Parts (`.rbxmx`/`.rbxm`) | Versão B — Mesh (`.fbx` + PBR) |
|---|---|---|
| Uso no Studio | Insert from File / arrastar — **pronto** | Import 3D do `.fbx` (textura embutida) + arrastar a pasta `DinoKit` para dentro |
| Visual | Parts coloridas + placas pixel art (Neon nos brilhos) | Textura pixel art 1024px com normal/roughness |
| Animações | Embutidas (KeyframeSequence) e tocadas por script, sem publicar nada | Mesmas, pelo `DinoKit` (encaixe automático nos Bones importados) + FBX por animação |
| Extras | Humanoid, DinoAnimator (cliente), DinoBrain (servidor), DinoAPI, VFX | Igual à A via `DinoKit` + `.blend`/`.glb` |

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

## Painel (criar / editar / lote / exportar)
```bash
python -m dinomaker painel        # ou dois cliques em DinoMaker.bat (Windows)
```
Abre `http://localhost:8765` no navegador:
- **Editor**: preview 3D ao vivo com textura e animações; barras para tamanho, cabeça, pescoço, cauda,
  pernas, braços, corpo, robustez, focinho e segmentos; olhos, cores, padrão, partes (chifres, vela,
  cristais…), ataque e VFX. **Medidor de originalidade** contra todo o histórico.
  "Salvar como novo" (precisa ser original) ou "Salvar por cima" (edita um dino existente).
- **Biblioteca**: todos os dinos com miniatura; clique para editar.
- **Lote**: N dinos novos e únicos (reais, fantasia ou misto; filtra por corpo e tema).
- **Exportar**: escolha os dinos e baixe o zip pronto (FBX + arquivo único de kits + plugin).

## Importação rápida da versão B (vários dinos)
```bash
python -m dinomaker pack --name Lote1      # output/Lote1_DinoKits.rbxm + output/DinoMaker_Plugin.rbxm
```
1. Uma vez: copie `tools/DinoMaker_Plugin.rbxm` para a Pasta de plugins do Studio.
2. Importar 3D com **todos** os `.fbx` selecionados (textura embutida).
3. Arraste `Lote1_DinoKits.rbxm` e clique **Instalar kits** (ou só dê Play): cada kit acha o seu dino
   pelo encaixe do esqueleto e monta Humanoid, animações, VFX e scripts.

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

## VFX (versão A)
Partículas com texturas nativas do Roblox (sem upload): **aura** no corpo e na cauda (+ luz),
**bafo** saindo da boca no Roar/Attack, **poeira** nos pés ao andar/correr, **faíscas** no Hit e no Death.
Temas: `fire`, `ice`, `electric`, `magic`, `toxic`, `nature`, `water`, `none` — escolhido automaticamente
pela paleta/padrão, ou forçado no spec com `"vfx": {"theme": "ice"}`.
- Atributo `VFX` (bool) no Model liga/desliga tudo; `VFXTheme` mostra o tema.
- Para editar cores/tamanhos: Model > Chest/Head/... > Attachment `FX_*` > ParticleEmitter.
- `python -m dinomaker rebuild [ids] [--vfx tema]` regera dinos existentes com o gerador atual.
