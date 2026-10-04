"""Animações procedurais (in-place) com IK planar nas pernas.

Cada clipe é uma função t -> pose (rotações locais por osso + translação da raiz
+ alvos de pé). O solver gera, por frame:
  - local[bone] = (R 3x3, t 3)  -> Pose.CFrame do Roblox (Motor6D.Transform)
  - world[bone] = J 4x4         -> Blender
"""
import math
import numpy as np

from .mathx import rx, ry, rz, rot, mat4, inv4, envelope, smooth

FPS = 30


def ang_x(R):
    return math.atan2(R[2, 1], R[1, 1])


class Rig:
    def __init__(self, model):
        self.m = model
        self.order = list(model.bones)
        self.Jrest = {n: mat4(b["R"], b["pos"]) for n, b in model.bones.items()}
        self.off = {}
        for n, b in model.bones.items():
            p = b["parent"]
            self.off[n] = inv4(self.Jrest[p]) @ self.Jrest[n] if p else self.Jrest[n]
        self.legs = model.legs
        self.leg_bones = {bn for lg in self.legs for bn in lg["bones"]}

    def fk(self, local):
        J = {}
        for n in self.order:
            p = self.m.bones[n]["parent"]
            L = local.get(n)
            Lm = np.eye(4) if L is None else L
            J[n] = (J[p] @ self.off[n] @ Lm) if p else (self.off[n] @ Lm)
        return J

    def solve(self, pose):
        """pose: dict(root=(R,t), rot={bone:R}, feet={i:(target_world, pitch)})."""
        local = {}
        R0, t0 = pose.get("root", (np.eye(3), np.zeros(3)))
        local["Hips"] = mat4(R0, t0)
        for b, R in pose.get("rot", {}).items():
            if b in self.m.bones:
                local[b] = mat4(R)
        J = self.fk(local)
        for i, lg in enumerate(self.legs):
            ft = pose.get("feet", {}).get(i)
            if ft is None:
                continue
            target, pitch = ft
            t1, t2, t3 = lg["bones"]
            Jp = J[lg["parent"]]
            T = (inv4(Jp) @ np.append(target, 1.0))[:3]
            hip = self.off[t1][:3, 3]
            dy, dz = T[1] - hip[1], T[2] - hip[2]
            L1, L2 = lg["L1"], lg["L2"]
            D = math.hypot(dy, dz)
            Dc = min(max(D, abs(L1 - L2) + 0.05), L1 + L2 - 0.05)
            if D > 1e-6:
                dy, dz = dy * Dc / D, dz * Dc / D
            base = math.atan2(-dz, -dy)
            ca = (L1 * L1 + Dc * Dc - L2 * L2) / (2 * L1 * Dc)
            alpha = math.acos(min(1.0, max(-1.0, ca)))
            phi1 = base + lg["knee_sign"] * alpha
            ky, kz = -L1 * math.cos(phi1), -L1 * math.sin(phi1)
            phi2 = math.atan2(-(dz - kz), -(dy - ky))
            a1, a2 = lg["a1"], lg["a2"]
            ppitch = ang_x(Jp[:3, :3])
            local[t1] = mat4(rx(phi1 - a1))
            local[t2] = mat4(rx(phi2 - phi1 - a2 + a1))
            local[t3] = mat4(rx((pitch - ppitch) - phi2 + a2))
        J = self.fk(local)
        out = {}
        for n in self.order:
            L = local.get(n, np.eye(4))
            out[n] = (L[:3, :3].copy(), L[:3, 3].copy())
        return out, J


# ================================================================ helpers
def gait(phase, duty, stride, lift):
    phase %= 1.0
    if phase < duty:
        u = phase / duty
        return -stride / 2 + stride * u, 0.0, 0.0
    u = (phase - duty) / (1 - duty)
    dz = stride / 2 - stride * smooth(u)
    return dz, lift * math.sin(math.pi * u), -0.35 * math.sin(2 * math.pi * u)


class Ctx:
    def __init__(self, model, genome):
        self.m = model
        self.g = genome
        P = model.P
        self.P = P
        self.biped = P["stance"] == "biped"
        self.winged = "wings" in model.features
        hind = [lg for lg in model.legs if lg["group"] == "hind"]
        self.leg_len = hind[0]["L1"] + hind[0]["L2"]
        self.hip_y = model.bones["Hips"]["pos"][1]
        self.necks = [b for b in model.bones if b.startswith("Neck")]
        self.tails = [b for b in model.bones if b.startswith("Tail")]
        self.arms = [a for a in model.arms]
        heavy = P["body_w"] * P["body_h"] > 250
        self.T_walk = round(0.75 + self.leg_len * 0.012 + (0.15 if heavy else 0.0), 2)
        self.T_run = round(self.T_walk * 0.6, 2)
        self.stride_walk = self.leg_len * (0.75 if self.biped else 0.6)
        self.stride_run = self.stride_walk * 1.5
        self.duty_walk, self.duty_run = 0.6, 0.4
        self.walk_speed = self.stride_walk / (self.duty_walk * self.T_walk)
        self.run_speed = self.stride_run / (self.duty_run * self.T_run)

    def planted(self, i, dz=0.0, dy=0.0, pitch=0.0):
        a = self.m.legs[i]["ankle"]
        return (np.array([a[0], a[1] + dy, a[2] + dz]), pitch)

    def all_planted(self):
        return {i: self.planted(i) for i in range(len(self.m.legs))}

    def spread(self, chain, total_deg, axis="x"):
        n = max(len(chain), 1)
        return {b: rot(**{axis: total_deg / n}) for b in chain}

    def tail_wave(self, t, period, yaw_amp, pitch=0.0, delay=0.7, pitch_amp=0.0):
        out = {}
        for k, b in enumerate(self.tails):
            ph = 2 * math.pi * t / period - k * delay
            out[b] = rot(x=pitch + pitch_amp * math.sin(ph), y=yaw_amp * (1 + 0.25 * k) * math.sin(ph))
        return out


def merge(*dicts):
    out = {}
    for d in dicts:
        for k, R in d.items():
            out[k] = out[k] @ R if k in out else R
    return out


# ================================================================ clipes
def clip_idle(c, t, T):
    w = 2 * math.pi * t / T
    rots = merge(
        {"Chest": rot(x=1.5 * math.sin(w))},
        c.spread(c.necks, 3 * math.sin(w + 0.6)),
        {"Head": rot(x=2 * math.sin(w + 1.0), y=10 * math.sin(w * 0.5))},
        {"Jaw": rot(x=-3 * max(0.0, math.sin(w)))},
        c.tail_wave(t, T, 5, pitch_amp=2),
    )
    for a in c.arms:
        rots[a["bones"][0]] = rot(x=4 * math.sin(w + 0.4))
        rots[a["bones"][1]] = rot(x=3 * math.sin(w + 0.9))
    root = (rot(x=0.6 * math.sin(w)), np.array([0, -0.25 * c.leg_len * 0.02 * (1 - math.cos(w)), 0]))
    if c.winged:
        for i, lg in enumerate(c.m.legs):
            if lg["group"] == "front":
                rots[lg["bones"][0]] = rot(z=lg["side"] * 2 * math.sin(w))
    return dict(root=root, rot=rots, feet=c.all_planted())


def _locomotion(c, t, T, stride, duty, lift, run):
    ph = t / T
    feet = {}
    for i, lg in enumerate(c.m.legs):
        if c.biped:
            off = 0.0 if lg["side"] > 0 else 0.5
        elif run:
            off = {("hind", -1): 0.0, ("hind", 1): 0.1, ("front", -1): 0.5, ("front", 1): 0.6}[(lg["group"], lg["side"])]
        else:
            off = {("hind", -1): 0.0, ("front", -1): 0.25, ("hind", 1): 0.5, ("front", 1): 0.75}[(lg["group"], lg["side"])]
        dz, dy, pitch = gait(ph + off, duty, stride, lift)
        feet[i] = c.planted(i, dz, dy, pitch)
    w = 2 * math.pi * ph
    bob = c.leg_len * (0.05 if run else 0.03)
    lean = (8 if c.biped else 3) if run else 0
    if c.biped:
        root = (rot(x=-lean + 1.5 * math.sin(2 * w), y=3 * math.sin(w), z=3 * math.sin(w)),
                np.array([0, -bob * (0.5 + 0.5 * math.cos(2 * w)), 0]))
    else:
        root = (rot(x=-lean + 2 * math.sin(2 * w + 0.5), z=2 * math.sin(w)),
                np.array([0, -bob * (0.5 + 0.5 * math.cos(2 * w)), 0]))
    rots = merge(
        {"Chest": rot(x=-1.5 * math.sin(2 * w), y=-2 * math.sin(w))},
        c.spread(c.necks, (lean * 0.6) + 3 * math.sin(2 * w + 1)),
        {"Head": rot(x=-2 * math.sin(2 * w + 1.4), y=-2 * math.sin(w))},
        {"Jaw": rot(x=(-8 if run else 0) * (0.5 + 0.5 * math.sin(2 * w)))},
        c.tail_wave(t, T, 7 if run else 5, pitch=lean * 0.5, pitch_amp=2),
    )
    for a in c.arms:
        sgn = a["side"]
        rots[a["bones"][0]] = rot(x=(15 if run else 8) * math.sin(w + (math.pi if sgn > 0 else 0)) + (20 if run else 0))
        rots[a["bones"][1]] = rot(x=10 * math.sin(w + 1 + (math.pi if sgn > 0 else 0)))
    return dict(root=root, rot=rots, feet=feet)


def clip_walk(c, t, T):
    return _locomotion(c, t, T, c.stride_walk, c.duty_walk, c.leg_len * 0.16, False)


def clip_run(c, t, T):
    return _locomotion(c, t, T, c.stride_run, c.duty_run, c.leg_len * 0.25, True)


def clip_attack(c, t, T):
    style = c.g["attack"]
    u = t / T
    wind = envelope(u, 0.0, 0.32, 0.36, 0.5)
    hit = envelope(u, 0.36, 0.48, 0.58, 1.0)
    rots, root_t, root_r = {}, np.zeros(3), np.eye(3)
    feet = c.all_planted()
    L = c.leg_len
    if style in ("bite", "peck", "claw"):
        k = 0.6 if style == "peck" else 1.0
        rots = merge(
            {"Chest": rot(x=6 * wind - 8 * hit * k)},
            c.spread(c.necks, 16 * wind - 18 * hit * k),
            {"Head": rot(x=14 * wind - 12 * hit)},
            {"Jaw": rot(x=-40 * envelope(u, 0.1, 0.35, 0.42, 0.52))},
            c.tail_wave(t, T, 6),
        )
        root_t = np.array([0, 0, L * 0.05 * wind - L * 0.14 * hit * k])
        root_r = rot(x=3 * wind - 5 * hit)
        if style == "claw":
            for a in c.arms:
                rots[a["bones"][0]] = rot(x=70 * wind - 30 * hit)
                rots[a["bones"][1]] = rot(x=-30 * wind + 20 * hit)
    elif style == "headbutt":
        rots = merge(
            {"Chest": rot(x=5 * wind - 6 * hit)},
            c.spread(c.necks, 12 * wind - 22 * hit),
            {"Head": rot(x=10 * wind - 25 * hit)},
            c.tail_wave(t, T, 8),
        )
        root_t = np.array([0, 0, L * 0.12 * wind - L * 0.22 * hit])
    elif style == "tailswipe":
        sw = 25 * wind - 45 * hit
        root_r = rot(y=-sw * 0.4)
        rots = merge({"Chest": rot(y=sw * 0.3)}, c.spread(c.necks, 0, "y"), {"Head": rot(y=sw * 0.3)})
        for k, b in enumerate(c.tails):
            rots[b] = rot(y=sw * (0.6 + 0.25 * k))
    elif style == "stomp":
        rear = envelope(u, 0.0, 0.4, 0.45, 0.62)
        root_r = rot(x=22 * rear)
        root_t = np.array([0, L * 0.12 * rear, 0])
        rots = merge(c.spread(c.necks, 10 * rear), {"Head": rot(x=10 * rear)}, c.tail_wave(t, T, 4, pitch=-10 * rear))
        for i, lg in enumerate(c.m.legs):
            if lg["group"] == "front" and rear > 0.01:
                feet.pop(i, None)
                rots[lg["bones"][0]] = rot(x=35 * rear)
                rots[lg["bones"][1]] = rot(x=-50 * rear)
    return dict(root=(root_r, root_t), rot=rots, feet=feet)


def clip_roar(c, t, T):
    u = t / T
    inh = envelope(u, 0.0, 0.15, 0.18, 0.3)
    roar = envelope(u, 0.2, 0.32, 0.75, 1.0)
    shake = math.sin(t * 38) * roar
    rots = merge(
        {"Chest": rot(x=-4 * inh + 7 * roar)},
        c.spread(c.necks, -8 * inh + 16 * roar),
        {"Head": rot(x=-6 * inh + 16 * roar, y=5 * shake, z=3 * shake)},
        {"Jaw": rot(x=-42 * roar - 4 * inh)},
        c.tail_wave(t, T * 0.5, 4 * roar + 1, pitch=6 * roar),
    )
    for a in c.arms:
        rots[a["bones"][0]] = rot(x=30 * roar, z=a["side"] * 15 * roar)
    root = (rot(x=-2 * inh + 5 * roar), np.array([0, 0, c.leg_len * 0.04 * roar]))
    if c.winged:
        for lg in c.m.legs:
            if lg["group"] == "front":
                pass
    return dict(root=root, rot=rots, feet=c.all_planted())


def clip_hit(c, t, T):
    u = t / T
    k = envelope(u, 0.0, 0.15, 0.25, 1.0)
    rots = merge(
        {"Chest": rot(x=8 * k, y=6 * k)},
        c.spread(c.necks, 10 * k, "x"),
        {"Head": rot(x=8 * k, y=18 * k)},
        {"Jaw": rot(x=-20 * k)},
        c.tail_wave(t, T, 10 * k),
    )
    root = (rot(x=4 * k, z=3 * k), np.array([0, 0, c.leg_len * 0.08 * k]))
    return dict(root=root, rot=rots, feet=c.all_planted())


def clip_death(c, t, T):
    u = t / T
    stag = envelope(u, 0.0, 0.25, 0.3, 0.45)
    fall = smooth((u - 0.3) / 0.45)
    bw = c.P["body_w"]
    drop = (bw / 2 + 0.5 - c.hip_y) * fall
    root = (rot(x=6 * stag, z=86 * fall), np.array([0, drop, c.leg_len * 0.05 * stag]))
    rots = merge(
        {"Chest": rot(x=6 * stag, y=-6 * fall)},
        c.spread(c.necks, 14 * stag - 10 * fall, "x"),
        c.spread(c.necks, -12 * fall, "y"),
        {"Head": rot(x=12 * stag - 8 * fall, y=-10 * fall)},
        {"Jaw": rot(x=-30 * stag - 18 * fall)},
        {b: rot(y=8 * fall, x=-3 * fall) for b in c.tails},
    )
    feet = {}
    if fall < 0.01:
        feet = c.all_planted()
    else:
        for lg in c.m.legs:
            a, b, f = lg["bones"]
            k = fall
            if lg["group"] == "hind":
                rots[a] = rot(x=35 * k)
                rots[b] = rot(x=-45 * k)
            else:
                rots[a] = rot(x=-30 * k)
                rots[b] = rot(x=40 * k)
            rots[f] = rot(x=-20 * k)
    for a in c.arms:
        rots[a["bones"][0]] = rot(x=25 * fall)
    return dict(root=root, rot=rots, feet=feet)


def clip_eat(c, t, T):
    u = t / T
    down = envelope(u, 0.0, 0.2, 0.8, 1.0)
    chomp = abs(math.sin(t * 2 * math.pi * 2.0)) * down
    reach = 40 if len(c.necks) <= 2 else 30
    rots = merge(
        {"Chest": rot(x=-8 * down)},
        c.spread(c.necks, -reach * down),
        {"Head": rot(x=-20 * down)},
        {"Jaw": rot(x=-18 * chomp)},
        c.tail_wave(t, T, 4, pitch=4 * down),
    )
    root = (rot(x=-6 * down if c.biped else -3 * down), np.zeros(3))
    return dict(root=root, rot=rots, feet=c.all_planted())


def clip_fly(c, t, T):
    w = 2 * math.pi * t / T
    rots = merge(
        {"Chest": rot(x=3 * math.sin(w))},
        c.spread(c.necks, -10),
        {"Head": rot(x=5)},
        c.tail_wave(t, T, 3),
    )
    for lg in c.m.legs:
        a, b, f = lg["bones"]
        if lg["group"] == "front":
            s = lg["side"]
            rots[a] = rot(x=-lg["a1"] * 57.3, z=s * (80 + 28 * math.sin(w)))
            rots[b] = rot(x=-(lg["a2"] - lg["a1"]) * 57.3, z=s * (6 * math.sin(w - 0.6)))
        else:
            rots[a] = rot(x=-55)
            rots[b] = rot(x=30)
            rots[f] = rot(x=-40)
    root = (rot(x=-12), np.array([0, c.leg_len * (0.9 + 0.08 * math.sin(w)), 0]))
    return dict(root=root, rot=rots, feet={})


# nome -> (função, duração(s) ou None p/ calculada, loop, prioridade Roblox)
CLIPS = {
    "Idle": (clip_idle, 3.0, True, "Idle"),
    "Walk": (clip_walk, None, True, "Movement"),
    "Run": (clip_run, None, True, "Movement"),
    "Attack": (clip_attack, 1.1, False, "Action"),
    "Roar": (clip_roar, 1.8, False, "Action"),
    "Hit": (clip_hit, 0.5, False, "Action"),
    "Eat": (clip_eat, 2.4, True, "Action"),
    "Death": (clip_death, 1.8, False, "Action"),
    "Fly": (clip_fly, 0.9, True, "Movement"),
}


def bake(model, genome):
    rig = Rig(model)
    c = Ctx(model, genome)
    clips = {}
    for name, (fn, dur, loop, prio) in CLIPS.items():
        if name == "Fly" and not c.winged:
            continue
        if dur is None:
            dur = c.T_walk if name == "Walk" else c.T_run
        n = int(round(dur * FPS))
        frames = n if loop else n + 1
        local_frames, world = [], {b: [] for b in rig.order}
        for fi in range(frames + (1 if loop else 0)):
            t = fi / FPS
            loc, J = rig.solve(fn(c, t % dur if loop else t, dur))
            local_frames.append(loc)
            if fi < frames:
                for b in rig.order:
                    world[b].append(J[b])
        clips[name] = dict(name=name, duration=dur, loop=loop, priority=prio,
                           frames=frames, local=local_frames, world=world)
    meta = dict(walk_speed=c.walk_speed, run_speed=c.run_speed, T_walk=c.T_walk, T_run=c.T_run)
    return clips, rig, meta
