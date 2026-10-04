"""Arquétipos (planos de corpo), espécies reais/fantasia e paletas.

Todas as medidas estão em "pixels" (1 px = 1 texel da textura). O tamanho final
em studs é px * px_size (definido pela classe de tamanho).
"""

SIZE_CLASSES = {
    # px_size em studs por pixel
    "tiny": 0.07,
    "small": 0.1,
    "medium": 0.14,
    "large": 0.2,
    "giant": 0.28,
}

# ---------------------------------------------------------------- arquétipos
# Parâmetros base. O gerador aplica variações aleatórias por grupo
# (head/neck/tail/legs/body/arms) e o spec pode sobrescrever qualquer chave.
ARCHETYPES = {
    "theropod": dict(
        stance="biped", diet="carnivore", attack="bite", size="large",
        hips_len=16, chest_len=16, body_w=16, body_h=16, chest_h=18, chest_w=16, chest_dy=1,
        thigh=16, thigh_w=8, thigh_d=10, shin=14, shin_w=6, knee_ang=20, shin_ang=-30,
        foot_len=12, foot_h=4, foot_w=8, toes=3,
        arm=7, fore=6, hand=3, arm_w=3, arm_style="tiny",
        neck_segs=1, neck_len=8, neck_w=12, neck_h=12, neck_rise=4, neck_taper=0.1,
        skull_len=14, skull_h=13, skull_w=14, snout_len=11, snout_h=9, snout_w=12, jaw_h=5,
        tail_segs=4, tail_len=12, tail_w=12, tail_h=12, tail_taper=0.78, tail_rise=3,
        eye=3, features=["teeth"],
    ),
    "raptor": dict(
        stance="biped", diet="carnivore", attack="claw", size="small",
        hips_len=11, chest_len=10, body_w=9, body_h=9, chest_h=10, chest_w=9, chest_dy=1,
        thigh=10, thigh_w=5, thigh_d=6, shin=11, shin_w=3, knee_ang=25, shin_ang=-35,
        foot_len=7, foot_h=2, foot_w=5, toes=3,
        arm=6, fore=6, hand=4, arm_w=2, arm_style="long",
        neck_segs=2, neck_len=4, neck_w=5, neck_h=6, neck_rise=3, neck_taper=0.1,
        skull_len=8, skull_h=7, skull_w=7, snout_len=7, snout_h=4, snout_w=5, jaw_h=2,
        tail_segs=4, tail_len=9, tail_w=6, tail_h=5, tail_taper=0.78, tail_rise=1,
        eye=2, features=["teeth", "sickle_claw"],
    ),
    "spinosaur": dict(
        stance="biped", diet="carnivore", attack="bite", size="large",
        hips_len=16, chest_len=16, body_w=14, body_h=14, chest_h=16, chest_w=14, chest_dy=2,
        thigh=13, thigh_w=7, thigh_d=9, shin=11, shin_w=5, knee_ang=20, shin_ang=-28,
        foot_len=10, foot_h=3, foot_w=7, toes=3,
        arm=8, fore=8, hand=4, arm_w=3, arm_style="medium",
        neck_segs=2, neck_len=6, neck_w=9, neck_h=9, neck_rise=4, neck_taper=0.1,
        skull_len=10, skull_h=9, skull_w=10, snout_len=16, snout_h=5, snout_w=7, jaw_h=3,
        tail_segs=5, tail_len=11, tail_w=10, tail_h=12, tail_taper=0.8, tail_rise=1,
        eye=3, features=["teeth", "sail"],
    ),
    "sauropod": dict(
        stance="quad", diet="herbivore", attack="stomp", size="giant",
        hips_len=18, chest_len=20, body_w=18, body_h=18, chest_h=20, chest_w=18, chest_dy=2,
        thigh=13, thigh_w=8, thigh_d=8, shin=12, shin_w=7, knee_ang=0, shin_ang=0,
        foot_len=6, foot_h=3, foot_w=9, toes=3,
        front_w=7, front_ang1=0, front_ang2=0,
        neck_segs=5, neck_len=8, neck_w=9, neck_h=9, neck_rise=6, neck_taper=0.07,
        skull_len=8, skull_h=6, skull_w=7, snout_len=5, snout_h=4, snout_w=6, jaw_h=2,
        tail_segs=6, tail_len=10, tail_w=11, tail_h=11, tail_taper=0.8, tail_rise=-1,
        eye=2, features=[],
    ),
    "ceratopsian": dict(
        stance="quad", diet="herbivore", attack="headbutt", size="large",
        hips_len=16, chest_len=14, body_w=18, body_h=16, chest_h=15, chest_w=17, chest_dy=-1,
        thigh=9, thigh_w=7, thigh_d=8, shin=8, shin_w=6, knee_ang=10, shin_ang=-10,
        foot_len=6, foot_h=3, foot_w=7, toes=3,
        front_w=6, front_ang1=-10, front_ang2=10,
        neck_segs=1, neck_len=4, neck_w=12, neck_h=11, neck_rise=0, neck_taper=0.0,
        skull_len=13, skull_h=12, skull_w=12, snout_len=8, snout_h=8, snout_w=8, jaw_h=3,
        tail_segs=3, tail_len=9, tail_w=10, tail_h=9, tail_taper=0.72, tail_rise=-1,
        eye=3, features=["beak", "frill", "horns_long", "horn_nose"],
    ),
    "stegosaur": dict(
        stance="quad", diet="herbivore", attack="tailswipe", size="large",
        hips_len=18, chest_len=14, body_w=14, body_h=17, chest_h=14, chest_w=13, chest_dy=-3,
        thigh=13, thigh_w=7, thigh_d=8, shin=12, shin_w=6, knee_ang=10, shin_ang=-10,
        foot_len=6, foot_h=3, foot_w=7, toes=3,
        front_w=5, front_ang1=0, front_ang2=0,
        neck_segs=2, neck_len=5, neck_w=7, neck_h=7, neck_rise=-2, neck_taper=0.1,
        skull_len=7, skull_h=6, skull_w=6, snout_len=5, snout_h=4, snout_w=5, jaw_h=2,
        tail_segs=4, tail_len=10, tail_w=9, tail_h=9, tail_taper=0.72, tail_rise=1,
        eye=2, features=["beak", "plates", "thagomizer"],
    ),
    "ankylosaur": dict(
        stance="quad", diet="herbivore", attack="tailswipe", size="large",
        hips_len=16, chest_len=16, body_w=22, body_h=11, chest_h=11, chest_w=21, chest_dy=0,
        thigh=7, thigh_w=7, thigh_d=7, shin=6, shin_w=6, knee_ang=5, shin_ang=-5,
        foot_len=6, foot_h=3, foot_w=7, toes=3,
        front_w=6, front_ang1=0, front_ang2=0,
        neck_segs=1, neck_len=4, neck_w=10, neck_h=8, neck_rise=-1, neck_taper=0.0,
        skull_len=10, skull_h=8, skull_w=12, snout_len=4, snout_h=6, snout_w=10, jaw_h=2,
        tail_segs=4, tail_len=9, tail_w=7, tail_h=5, tail_taper=0.8, tail_rise=0,
        eye=2, features=["beak", "armor", "side_spikes", "club"],
    ),
    "hadrosaur": dict(
        stance="biped", diet="herbivore", attack="tailswipe", size="large",
        hips_len=15, chest_len=14, body_w=13, body_h=14, chest_h=14, chest_w=13, chest_dy=0,
        thigh=13, thigh_w=7, thigh_d=8, shin=12, shin_w=5, knee_ang=18, shin_ang=-25,
        foot_len=9, foot_h=3, foot_w=7, toes=3,
        arm=8, fore=8, hand=3, arm_w=3, arm_style="medium",
        neck_segs=2, neck_len=6, neck_w=8, neck_h=8, neck_rise=4, neck_taper=0.1,
        skull_len=9, skull_h=8, skull_w=8, snout_len=9, snout_h=5, snout_w=8, jaw_h=2,
        tail_segs=4, tail_len=11, tail_w=10, tail_h=11, tail_taper=0.75, tail_rise=1,
        eye=3, features=["beak"],
    ),
    "pachycephalosaur": dict(
        stance="biped", diet="herbivore", attack="headbutt", size="medium",
        hips_len=12, chest_len=11, body_w=11, body_h=11, chest_h=11, chest_w=11, chest_dy=0,
        thigh=11, thigh_w=6, thigh_d=7, shin=10, shin_w=4, knee_ang=20, shin_ang=-28,
        foot_len=7, foot_h=3, foot_w=6, toes=3,
        arm=5, fore=5, hand=2, arm_w=2, arm_style="tiny",
        neck_segs=2, neck_len=4, neck_w=7, neck_h=7, neck_rise=3, neck_taper=0.1,
        skull_len=10, skull_h=9, skull_w=10, snout_len=5, snout_h=5, snout_w=6, jaw_h=2,
        tail_segs=4, tail_len=9, tail_w=8, tail_h=8, tail_taper=0.75, tail_rise=1,
        eye=3, features=["beak", "dome"],
    ),
    "pterosaur": dict(
        stance="quad", diet="carnivore", attack="peck", size="medium",
        hips_len=8, chest_len=10, body_w=8, body_h=8, chest_h=9, chest_w=9, chest_dy=3,
        thigh=7, thigh_w=3, thigh_d=3, shin=7, shin_w=2, knee_ang=15, shin_ang=-15,
        foot_len=4, foot_h=2, foot_w=3, toes=3,
        front_w=3, front_ang1=-15, front_ang2=20,
        neck_segs=2, neck_len=5, neck_w=5, neck_h=5, neck_rise=4, neck_taper=0.1,
        skull_len=7, skull_h=6, skull_w=6, snout_len=14, snout_h=3, snout_w=4, jaw_h=2,
        tail_segs=1, tail_len=5, tail_w=3, tail_h=3, tail_taper=0.7, tail_rise=0,
        eye=2, features=["beak", "wings", "crest_head"],
    ),
}

# ---------------------------------------------------------------- espécies
# key -> (arquétipo, nome exibido, features extras, overrides de parâmetros)
SPECIES = {
    "tyrannosaurus": ("theropod", "T-Rex", [], dict(skull_len=16, skull_h=14, arm=6, fore=5)),
    "giganotosaurus": ("theropod", "Giganotossauro", ["crest_small"], dict(snout_len=13, skull_h=12, size="giant")),
    "allosaurus": ("theropod", "Alossauro", ["crest_small"], dict(arm=8, fore=7, arm_style="medium", body_h=14)),
    "carnotaurus": ("theropod", "Carnotauro", ["horns_brow"], dict(snout_len=7, skull_len=12, arm=4, fore=3)),
    "ceratosaurus": ("theropod", "Ceratossauro", ["horn_nose", "back_spikes"], dict(snout_len=12)),
    "velociraptor": ("raptor", "Velociraptor", ["feathers"], {}),
    "deinonychus": ("raptor", "Deinonico", ["feathers"], dict(size="medium")),
    "utahraptor": ("raptor", "Utahraptor", ["feathers"], dict(size="large", body_h=10)),
    "dilophosaurus": ("raptor", "Dilofossauro", ["crest_double"], dict(size="medium", sickle=False)),
    "compsognathus": ("raptor", "Compsognato", [], dict(size="tiny")),
    "gallimimus": ("raptor", "Galimimo", ["beak", "-teeth", "-sickle_claw"], dict(neck_segs=3, neck_rise=4, skull_len=6, snout_len=6, size="medium")),
    "oviraptor": ("raptor", "Oviraptor", ["beak", "-teeth", "-sickle_claw", "crest_fan", "feathers"], dict(snout_len=4, snout_h=5)),
    "therizinosaurus": ("raptor", "Therizinossauro", ["beak", "-teeth", "-sickle_claw", "big_claws", "feathers"], dict(size="large", body_h=13, body_w=12, neck_segs=3)),
    "spinosaurus": ("spinosaur", "Espinossauro", [], {}),
    "baryonyx": ("spinosaur", "Barionix", ["big_claws", "-sail"], dict(snout_len=14)),
    "concavenator": ("theropod", "Concavenator", ["hump"], dict(size="medium")),
    "brachiosaurus": ("sauropod", "Braquiossauro", [], dict(chest_dy=6, neck_rise=8, tail_segs=4)),
    "diplodocus": ("sauropod", "Diplodoco", [], dict(neck_rise=3, neck_segs=6, tail_segs=8, tail_taper=0.82)),
    "amargasaurus": ("sauropod", "Amargassauro", ["neck_spikes"], dict(size="large", neck_segs=4, neck_rise=4)),
    "triceratops": ("ceratopsian", "Triceratops", [], {}),
    "styracosaurus": ("ceratopsian", "Estiracossauro", ["frill_spikes", "-horns_long"], {}),
    "protoceratops": ("ceratopsian", "Protoceratops", ["-horns_long", "-horn_nose"], dict(size="medium")),
    "sinoceratops": ("ceratopsian", "Sinoceratops", ["frill_spikes", "-horns_long"], {}),
    "stegosaurus": ("stegosaur", "Estegossauro", [], {}),
    "kentrosaurus": ("stegosaur", "Kentrossauro", ["back_spikes"], dict(size="medium")),
    "ankylosaurus": ("ankylosaur", "Anquilossauro", [], {}),
    "parasaurolophus": ("hadrosaur", "Parassaurolofo", ["crest_tube"], {}),
    "corythosaurus": ("hadrosaur", "Coritossauro", ["crest_fan"], {}),
    "edmontosaurus": ("hadrosaur", "Edmontossauro", [], dict(size="large")),
    "iguanodon": ("hadrosaur", "Iguanodonte", ["thumb_spike"], dict(snout_len=7)),
    "pachycephalosaurus": ("pachycephalosaur", "Paquicefalossauro", [], {}),
    "pteranodon": ("pterosaur", "Pteranodonte", [], {}),
    "quetzalcoatlus": ("pterosaur", "Quetzalcoatlo", [], dict(size="large", neck_segs=3, neck_len=6)),
    "dimorphodon": ("pterosaur", "Dimorfodonte", ["teeth", "-beak", "-crest_head"], dict(size="small", snout_len=7, snout_h=4, tail_segs=3)),
}

# Features "fantasia" (para criaturas que não existem mas chamam atenção)
FANTASY_FEATURES = ["crystals", "antlers", "mane", "gem", "tusks", "glow_eyes", "back_spikes", "horns_brow", "feathers", "crest_fan"]

ALL_FEATURES = sorted(set(
    ["teeth", "beak", "horns_brow", "horn_nose", "horns_long", "frill", "frill_spikes", "plates",
     "thagomizer", "back_spikes", "sail", "hump", "armor", "side_spikes", "club", "crest_tube",
     "crest_fan", "crest_double", "crest_small", "crest_head", "dome", "feathers", "sickle_claw",
     "big_claws", "thumb_spike", "neck_spikes", "wings"] + FANTASY_FEATURES))

PATTERNS = ["none", "spots", "stripes", "tiger", "dorsal", "bands", "mottled", "rosettes", "lava", "zigzag", "galaxy"]

EYE_STYLES = ["cute", "fierce", "glow"]

# ---------------------------------------------------------------- paletas
# Paletas pensadas para o público infantil do Roblox: saturadas e legíveis.
PALETTES = {
    "jungle":    dict(primary="#4c9a2a", belly="#c8d86a", accent="#e8a33a", pattern="#2f6b1e"),
    "lime":      dict(primary="#7cc23a", belly="#e4ef9a", accent="#3f7f2a", pattern="#5a9a26"),
    "ocean":     dict(primary="#3a7fc4", belly="#cfe3f2", accent="#f2c94c", pattern="#24578f"),
    "lagoon":    dict(primary="#1fb5c2", belly="#bff0ea", accent="#145e7a", pattern="#127f8c"),
    "desert":    dict(primary="#d9902f", belly="#f3d79a", accent="#8a4b1f", pattern="#a8601e"),
    "volcano":   dict(primary="#c2401f", belly="#f2a541", accent="#2b2b2b", pattern="#ffcf3a"),
    "candy":     dict(primary="#ef7fb8", belly="#ffe0ef", accent="#ffd84a", pattern="#c9529a"),
    "grape":     dict(primary="#7a4fc4", belly="#d9c8f5", accent="#3ee0c8", pattern="#4f2f96"),
    "midnight":  dict(primary="#2c3561", belly="#7a86c2", accent="#5ef2ff", pattern="#151a38"),
    "frost":     dict(primary="#bfe6ff", belly="#ffffff", accent="#4f9cff", pattern="#7fbde8"),
    "toxic":     dict(primary="#9be02a", belly="#efffa0", accent="#7a2ad6", pattern="#2f6b10"),
    "sunset":    dict(primary="#ff7a3d", belly="#ffd29a", accent="#8e3fd1", pattern="#d9482b"),
    "royal":     dict(primary="#2f4fbf", belly="#e9d68a", accent="#ffcc33", pattern="#1d2f7a"),
    "rust":      dict(primary="#9c5a3c", belly="#e6c3a0", accent="#3e6b4a", pattern="#6e3a24"),
    "slate":     dict(primary="#6f7a85", belly="#c9cfd4", accent="#e0533a", pattern="#4a535c"),
    "gold":      dict(primary="#e3b437", belly="#fff1b0", accent="#a5521e", pattern="#b5821c"),
    "bubblegum": dict(primary="#7fd6ff", belly="#fff0fa", accent="#ff6fb1", pattern="#4fb0e0"),
    "forest":    dict(primary="#2f6b3a", belly="#9cc08a", accent="#d64b3a", pattern="#1d4426"),
    "snow":      dict(primary="#f2f2f2", belly="#d9e6f2", accent="#ff5c5c", pattern="#9aa6b2"),
    "shadow":    dict(primary="#2a2a33", belly="#55556a", accent="#ff3355", pattern="#121218"),
}

CLAW_COLORS = ["#efe3c2", "#d9c9a3", "#3a3333", "#f5f0e6"]
MOUTH_COLOR = "#a8323a"
TOOTH_COLOR = "#f5f0e0"

SYLLABLES_A = ["Ra", "Zor", "Ki", "Bru", "Ty", "Lum", "Vex", "Pip", "Gro", "Shi", "Mo", "Dra", "Ko", "Fli", "Zu", "Ny", "Bo", "Ska", "Ter", "Glo"]
SYLLABLES_B = ["rex", "don", "saur", "raptor", "tops", "mimus", "nyx", "zilla", "dactyl", "ceratops", "lophus", "osaurus", "ptor", "mander", "fang"]
