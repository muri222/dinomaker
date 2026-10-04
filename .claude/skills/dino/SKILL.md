---
name: dino
description: Cria um dinossauro NOVO (real ou fantasia) para o jogo Roblox usando o gerador dinomaker deste repositório — modelo blocky estilo Roblox com textura pixel art, rig e animações (Idle, Walk, Run, Attack, Roar, Hit, Eat, Death, Fly), exportado como .rbxmx pronto (versão A) e FBX+PBR (versão B), sem repetir nada do histórico. Use quando o usuário pedir "gera um dino", "novo dinossauro", "faz um dino de fogo", "/dino", ou pedir lotes de dinos.
---

# /dino — gerar dinossauro único para Roblox

Você opera o gerador `dinomaker` (Python). Ele cuida da geometria, rig, animações,
textura e exportação. **Seu trabalho é a parte criativa** (conceito que chama atenção
de crianças/jovens no Roblox) + garantir que não repete nada + QA visual.

## 0. Ambiente (uma vez por sessão)
- Python 3.10+ com `numpy` e `pillow` (`pip install -r requirements.txt`).
- Blender 4.2+ no PATH ou `DINOMAKER_BLENDER=<caminho do blender>` (no Windows ele acha
  `C:\Program Files\Blender Foundation\Blender*\blender.exe` sozinho).
  Sem Blender: `pip install bpy` num Python compatível e aponte `DINOMAKER_BLENDER` para esse python.
- Opcional (validação + `.rbxm` binário): Node.js e `npm install` dentro de `tools/`.

## 1. Ler o histórico
```
python -m dinomaker list
python -m dinomaker species      # espécies, arquétipos, paletas, padrões, features
```
`history/history.json` tem tudo que já foi criado (inclui os 8 dinos feitos à mão,
marcados `legacy`). Nunca edite o histórico à mão para "liberar" algo parecido.

## 2. Criar o conceito
Escolha UM dos caminhos e escreva um spec em `specs/<id>.json`:
- **Real**: espécie ainda não usada (ou usada com visual bem diferente).
- **Fantasia**: `"fantasy": true` + `"archetype"` + features chamativas
  (crystals, lava, galaxy, antlers, mane, gem, glow_eyes, tusks...).

Regras de apelo para o público do Roblox:
- Paleta saturada e com contraste (primária x acento). Evite tudo marrom/cinza.
- Um "gancho" visual forte por dino: vela, crista, chifres, cristais, padrão galáxia...
- Nome curto e divertido em PT-BR (ex.: "Rex Magma", "Trici Algodão", "Ptero Trovão").
- `"chibi": true` deixa cabeça/olhos maiores (fofo) — bom para dinos "pet".
- Carnívoros: olhos `fierce`; herbívoros/fofos: `cute`; mágicos: `glow`.

Formato do spec (tudo opcional — o que faltar é sorteado; no arquivo real não use comentários `//`):
```json
{
  "name": "Rex Magma",
  "species": "tyrannosaurus",          // OU "archetype": "theropod" + "fantasy": true
  "size": "large",                      // tiny | small | medium | large | giant
  "palette": "volcano",                 // nome de paleta OU {"primary":"#..","belly":"#..","accent":"#..","pattern":"#.."}
  "pattern": {"type": "lava", "scale": 6, "density": 0.7},
  "eyes": {"style": "glow", "size": 3},
  "features": ["crystals", "-teeth"],  // "-x" remove uma feature padrão
  "params": {"skull_len": 18},          // ajuste fino de proporções (px)
  "variation": {"head": 1.2, "legs": 0.9},
  "chibi": false,
  "studs": false,                       // superfície com studs estilo LEGO
  "attack": "bite",                     // bite | claw | headbutt | tailswipe | stomp | peck
  "description": "T-Rex com rachaduras de lava brilhando"
}
```

## 3. Checar unicidade ANTES de gerar
```
python -m dinomaker check specs/<id>.json
```
Se a similaridade com algo do histórico for ≥ 0.82, mude o conceito (arquétipo,
paleta, features, padrão) — não baixe o threshold sem o usuário pedir.

## 4. Gerar
```
python -m dinomaker new --spec specs/<id>.json
```
(Lote aleatório: `python -m dinomaker new --count 5`; só fantasia: `--fantasy`.)
Saída em `output/<id>/`:
- `A_roblox_parts/<id>.rbxmx` (+ `.rbxm` se o Node estiver disponível) — pronto para o Studio.
- `B_mesh/<id>.fbx`, `B_mesh/anims/*.fbx`, `textures/*_albedo|normal|roughness|metalness.png`, `.blend`, `.glb`.
- `preview/*.png`, `genome.json`, `README.md` (passo a passo de importação).
O histórico é atualizado automaticamente.

## 5. QA (obrigatório)
1. Abra os PNGs de `output/<id>/preview/` com a ferramenta Read e confira: silhueta
   legível, gancho visual aparecendo, cores vivas, boca/olhos no lugar, pernas no chão.
2. Versão A simulada exatamente como o Roblox (Motor6D + KeyframeSequence):
   `python tools/preview_rbx.py output/<id>/A_roblox_parts/<id>.rbxmx /tmp/a.png Attack 0.5`
   (precisa de `bpy`; rode com o Python do Blender: `blender -b -P tools/preview_rbx.py -- ...`).
3. Se algo ficou ruim: `python -m dinomaker forget <id>`, ajuste o spec e gere de novo.

## 6. Entregar
Resuma para o usuário: nome, conceito, arquivos e como importar (está no README do dino).
Faça commit de `specs/<id>.json` e `history/history.json` (os outputs ficam fora do git,
salvo se o usuário pedir).
