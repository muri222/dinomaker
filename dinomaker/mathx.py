"""Matemática mínima de transformações (espaço Roblox: X direita, Y cima, frente = -Z)."""
import functools
import math
import numpy as np


def rx(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], float)


def ry(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], float)


def rz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], float)


def rot(x=0.0, y=0.0, z=0.0):
    """Rotação local em graus, ordem Y * X * Z (yaw, pitch, roll)."""
    return ry(math.radians(y)) @ rx(math.radians(x)) @ rz(math.radians(z))


def mat4(R=None, t=None):
    M = np.eye(4)
    if R is not None:
        M[:3, :3] = R
    if t is not None:
        M[:3, 3] = t
    return M


def inv4(M):
    R = M[:3, :3]
    t = M[:3, 3]
    out = np.eye(4)
    out[:3, :3] = R.T
    out[:3, 3] = -R.T @ t
    return out


def lerp(a, b, t):
    return a + (b - a) * t


def smooth(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def envelope(t, a, b, c, d):
    """0 antes de a, sobe até 1 em b, fica até c, desce até 0 em d."""
    if t <= a or t >= d:
        return 0.0
    if t < b:
        return smooth((t - a) / max(b - a, 1e-6))
    if t <= c:
        return 1.0
    return 1.0 - smooth((t - c) / max(d - c, 1e-6))


@functools.lru_cache(maxsize=2_000_000)
def hash01(*vals):
    """Hash determinístico -> [0,1)."""
    h = 2166136261
    for v in vals:
        x = int(v * 1000) if isinstance(v, float) else int(v)
        for _ in range(4):
            h ^= x & 0xFF
            h = (h * 16777619) & 0xFFFFFFFF
            x >>= 8
    h ^= h >> 13
    h = (h * 0x5BD1E995) & 0xFFFFFFFF
    h ^= h >> 15
    return (h & 0xFFFFFF) / float(0x1000000)


def vnoise(x, y, z, cell, seed):
    return _vnoise(round(x, 3), round(y, 3), round(z, 3), cell, seed)


@functools.lru_cache(maxsize=1_000_000)
def _vnoise(x, y, z, cell, seed):
    """Value noise 3D trilinear com células de tamanho 'cell'."""
    fx, fy, fz = x / cell, y / cell, z / cell
    ix, iy, iz = math.floor(fx), math.floor(fy), math.floor(fz)
    tx, ty, tz = smooth(fx - ix), smooth(fy - iy), smooth(fz - iz)

    def h(a, b, c):
        return hash01(seed, ix + a, iy + b, iz + c)

    c00 = lerp(h(0, 0, 0), h(1, 0, 0), tx)
    c10 = lerp(h(0, 1, 0), h(1, 1, 0), tx)
    c01 = lerp(h(0, 0, 1), h(1, 0, 1), tx)
    c11 = lerp(h(0, 1, 1), h(1, 1, 1), tx)
    return lerp(lerp(c00, c10, ty), lerp(c01, c11, ty), tz)
