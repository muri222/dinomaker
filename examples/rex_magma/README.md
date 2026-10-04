# Rex Magma

- Espécie base: tyrannosaurus (theropod) — fantasia
- Tamanho: large (10.2 studs de altura, 23.6 de comprimento)
- Features: teeth, crystals, horns_brow
- Paleta: volcano | Padrão: lava | Olhos: glow
- Animações: Idle, Walk, Run, Attack, Roar, Hit, Eat, Death
- WalkSpeed 5.3 / RunSpeed 19.6 studs/s (batem com a passada)

## A) Roblox Parts — pronto para usar (`A_roblox_parts/rex_magma.rbxmx`)
Studio > Model > (botão direito no Workspace) **Insert from File...** e escolha o `.rbxmx`
(ou arraste o arquivo para a janela do Studio). Já vem com Humanoid, rig Motor6D,
animações embutidas e scripts. Para testar: marque o atributo `Wander` do Model e dê Play.

## B) Mesh + textura PBR (`B_mesh/`)
1. Studio > Avatar/Model > **Import 3D** > `rex_magma.fbx` (Rig: General, File Dimensions: Studs).
2. No MeshPart importado, adicione **SurfaceAppearance** com `textures/rex_magma_albedo.png` (ColorMap),
   `_normal.png` (NormalMap), `_roughness.png` (RoughnessMap), `_metalness.png` (MetalnessMap).
3. Animações: Animation Editor > ... > **Import > From FBX Animation** com cada arquivo de `anims/`.
   Depois publique (Publish to Roblox) para obter os AnimationIds.
`rex_magma.blend` e `rex_magma.glb` servem para editar/visualizar.
