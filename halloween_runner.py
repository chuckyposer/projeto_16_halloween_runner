#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CORRIDA ASSOMBRADA - Endless runner de Halloween feito com Panda3D
------------------------------------------------------------------
Instalação:   pip install panda3d
Executar:     python halloween_runner.py

Controles:
    ← / A ........ pista para a esquerda
    → / D ........ pista para a direita
    ESPAÇO / ↑ / W  pular
    ↓ / S ........ cair rápido (no ar)
    R ............ reiniciar
    ESC .......... sair

Objetivo: correr o máximo possível! O jogo só termina quando você cair
num buraco de gosma verde ou tropeçar numa lápide / cerca.
Pegue os doces para ganhar pontos extras.

Obs.: o texto dentro do jogo não usa acentos porque a fonte padrão do
Panda3D não tem todos os caracteres acentuados.
"""

import math
import os
import random
import sys

from direct.gui.OnscreenText import OnscreenText
from direct.showbase.ShowBase import ShowBase
from panda3d.core import (
    AmbientLight, ClockObject, DirectionalLight, Fog, Geom, GeomNode,
    GeomTriangles, GeomVertexData, GeomVertexFormat, GeomVertexWriter,
    NodePath, Point3, TextNode, loadPrcFileData,
)

loadPrcFileData("", "window-title Corrida Assombrada\nwin-size 1280 720\nsync-video 1\n")

# ----------------------------------------------------------------------------
# CONFIGURAÇÕES (mexa à vontade!)
# ----------------------------------------------------------------------------
LANE_W = 3.2          # distância entre as pistas
ROW_LEN = 5.0         # comprimento de cada "fatia" da estrada
NROWS = 18            # quantas fatias existem ao mesmo tempo
GRAVITY = 36.0
JUMP_V = 16.0         # força do pulo
START_SPEED = 12.0
MAX_SPEED = 30.0
ACCEL = 0.28          # quanto a velocidade aumenta por segundo

BEST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "melhor_pontuacao.txt")

# Cores
ORANGE = (1.0, 0.45, 0.05, 1)
PURPLE = (0.30, 0.10, 0.42, 1)
DARK = (0.08, 0.07, 0.10, 1)
STONE = (0.46, 0.48, 0.52, 1)
WOOD = (0.22, 0.13, 0.07, 1)
BONE = (0.85, 0.80, 0.65, 1)
GLOW_YELLOW = (1.0, 0.85, 0.2, 1)
GLOW_GREEN = (0.2, 1.0, 0.35, 1)
BG = (0.07, 0.03, 0.11)


# ----------------------------------------------------------------------------
# GEOMETRIA PROCEDURAL (caixas e esferas coloridas, sem arquivos externos)
# ----------------------------------------------------------------------------
def _geom_node(name, verts, norms, tris, color):
    vdata = GeomVertexData(name, GeomVertexFormat.getV3n3c4(), Geom.UHStatic)
    vdata.setNumRows(len(verts))
    vw = GeomVertexWriter(vdata, "vertex")
    nw = GeomVertexWriter(vdata, "normal")
    cw = GeomVertexWriter(vdata, "color")
    for v, n in zip(verts, norms):
        vw.addData3f(*v)
        nw.addData3f(*n)
        cw.addData4f(*color)
    prim = GeomTriangles(Geom.UHStatic)
    for a, b, c in tris:
        prim.addVertices(a, b, c)
    prim.closePrimitive()
    geom = Geom(vdata)
    geom.addPrimitive(prim)
    node = GeomNode(name)
    node.addGeom(geom)
    np = NodePath(node)
    np.setTwoSided(True)
    return np


def make_box(sx, sy, sz, color):
    hx, hy, hz = sx / 2, sy / 2, sz / 2
    faces = [
        ((1, 0, 0), [(hx, -hy, -hz), (hx, hy, -hz), (hx, hy, hz), (hx, -hy, hz)]),
        ((-1, 0, 0), [(-hx, hy, -hz), (-hx, -hy, -hz), (-hx, -hy, hz), (-hx, hy, hz)]),
        ((0, 1, 0), [(hx, hy, -hz), (-hx, hy, -hz), (-hx, hy, hz), (hx, hy, hz)]),
        ((0, -1, 0), [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, -hy, hz), (-hx, -hy, hz)]),
        ((0, 0, 1), [(-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]),
        ((0, 0, -1), [(-hx, hy, -hz), (hx, hy, -hz), (hx, -hy, -hz), (-hx, -hy, -hz)]),
    ]
    verts, norms, tris = [], [], []
    for n, corners in faces:
        base = len(verts)
        for c in corners:
            verts.append(c)
            norms.append(n)
        tris.append((base, base + 1, base + 2))
        tris.append((base, base + 2, base + 3))
    return _geom_node("box", verts, norms, tris, color)


def make_sphere(radius, color, rings=10, segs=14):
    verts, norms, tris = [], [], []
    for i in range(rings + 1):
        phi = math.pi * i / rings
        for j in range(segs + 1):
            th = 2 * math.pi * j / segs
            nx = math.sin(phi) * math.cos(th)
            ny = math.sin(phi) * math.sin(th)
            nz = math.cos(phi)
            verts.append((nx * radius, ny * radius, nz * radius))
            norms.append((nx, ny, nz))
    for i in range(rings):
        for j in range(segs):
            a = i * (segs + 1) + j
            b = a + 1
            c = a + segs + 1
            d = c + 1
            tris.append((a, c, b))
            tris.append((b, c, d))
    return _geom_node("sphere", verts, norms, tris, color)


def box(parent, size, pos, color, glow=False, hpr=None):
    np = make_box(*size, color)
    np.reparentTo(parent)
    np.setPos(*pos)
    if hpr:
        np.setHpr(*hpr)
    if glow:
        np.setLightOff()
    return np


def ball(parent, radius, pos, color, scale=(1, 1, 1), glow=False, segs=14):
    np = make_sphere(radius, color, rings=max(6, segs // 2), segs=segs)
    np.reparentTo(parent)
    np.setPos(*pos)
    np.setScale(*scale)
    if glow:
        np.setLightOff()
    return np


def inst(template, parent, pos=(0, 0, 0), h=0.0, scale=1.0):
    np = parent.attachNewNode("inst")
    template.instanceTo(np)
    np.setPos(*pos)
    np.setH(h)
    np.setScale(scale)
    return np


class Row:
    """Uma fatia da estrada (3 pistas + laterais + decoração)."""

    def __init__(self, parent):
        self.node = parent.attachNewNode("row")
        self.y = 0.0
        self.holes = set()
        self.obstacles = []   # (pista ou None, y_local, altura, meia_profundidade)
        self.candies = []


# ----------------------------------------------------------------------------
# JOGO
# ----------------------------------------------------------------------------
class HalloweenRunner(ShowBase):
    def __init__(self):
        ShowBase.__init__(self)
        self.disableMouse()
        self.setBackgroundColor(*BG)
        self.camLens.setFov(68)

        self.build_lights_and_fog()
        self.build_templates()
        self.build_sky()
        self.build_player()
        self.build_bats()
        self.build_hud()

        self.world = self.render.attachNewNode("world")
        self.rows = [Row(self.world) for _ in range(NROWS)]

        self.best = self.load_best()
        self.t = 0.0
        self.state = "menu"
        self.over_time = 0.0
        self.setup_input()
        self.reset_world()
        self.show_menu()

        self.taskMgr.add(self.update, "update")

    # ------------------------------------------------------------------ setup
    def build_lights_and_fog(self):
        amb = AmbientLight("amb")
        amb.setColor((0.42, 0.32, 0.55, 1))
        self.render.setLight(self.render.attachNewNode(amb))

        moon = DirectionalLight("moonlight")
        moon.setColor((0.95, 0.75, 0.55, 1))
        moon_np = self.render.attachNewNode(moon)
        moon_np.setHpr(-25, -50, 0)
        self.render.setLight(moon_np)

        fog = Fog("fog")
        fog.setColor(*BG)
        fog.setExpDensity(0.028)
        self.render.setFog(fog)

    def build_templates(self):
        """Cria os 'moldes' que serão instanciados (barato e rápido)."""
        # Tiles da estrada (2 tons alternados) com tracinho de osso no meio
        self.tpl_tile = []
        for col in [(0.20, 0.17, 0.25, 1), (0.25, 0.21, 0.30, 1)]:
            t = NodePath("tile")
            box(t, (3.1, ROW_LEN, 0.5), (0, ROW_LEN / 2, -0.25), col)
            box(t, (0.15, 1.6, 0.03), (0, ROW_LEN / 2, 0.01), BONE)
            self.tpl_tile.append(t)

        # Gosma verde que brilha no fundo dos buracos
        self.tpl_glow = NodePath("glow")
        box(self.tpl_glow, (3.1, ROW_LEN, 0.1), (0, ROW_LEN / 2, -4), GLOW_GREEN, glow=True)

        # Chão lateral
        self.tpl_side = []
        for col in [(0.10, 0.09, 0.11, 1), (0.13, 0.10, 0.14, 1)]:
            s = NodePath("side")
            box(s, (15.5, ROW_LEN, 0.6), (0, ROW_LEN / 2, -0.7), col)
            self.tpl_side.append(s)

        # Lápide (obstáculo e decoração)
        self.tpl_tomb = NodePath("tomb")
        box(self.tpl_tomb, (2.0, 0.6, 1.5), (0, 0, 0.75), STONE)
        ball(self.tpl_tomb, 1.0, (0, 0, 1.5), STONE, scale=(1.0, 0.3, 0.55))
        box(self.tpl_tomb, (0.15, 0.05, 0.8), (0, -0.31, 1.1), DARK)
        box(self.tpl_tomb, (0.6, 0.05, 0.14), (0, -0.31, 1.3), DARK)

        # Cerca baixa (precisa pular!)
        self.tpl_fence = NodePath("fence")
        for x in (-4.6, -1.6, 1.6, 4.6):
            box(self.tpl_fence, (0.25, 0.25, 1.1), (x, 0, 0.55), WOOD)
        box(self.tpl_fence, (9.6, 0.18, 0.18), (0, 0, 0.85), BONE)
        box(self.tpl_fence, (9.6, 0.18, 0.18), (0, 0, 0.45), BONE)
        for x in (-3.1, 0.0, 3.1):
            ball(self.tpl_fence, 0.28, (x, -0.05, 1.2), ORANGE, glow=True, segs=8)

        # Árvore morta
        self.tpl_tree = NodePath("tree")
        tw = (0.18, 0.11, 0.08, 1)
        box(self.tpl_tree, (0.55, 0.55, 4.2), (0, 0, 2.1), tw)
        box(self.tpl_tree, (0.22, 0.22, 2.0), (0.75, 0, 3.4), tw, hpr=(0, 0, 50))
        box(self.tpl_tree, (0.22, 0.22, 1.7), (-0.65, 0, 2.7), tw, hpr=(0, 0, -50))
        box(self.tpl_tree, (0.18, 0.18, 1.4), (0.0, 0.5, 3.9), tw, hpr=(0, 40, 0))
        box(self.tpl_tree, (0.16, 0.16, 1.1), (0.0, -0.45, 3.5), tw, hpr=(0, -45, 20))

        # Abóbora decorativa (jack-o'-lantern)
        self.tpl_jack = NodePath("jack")
        ball(self.tpl_jack, 0.7, (0, 0, 0.6), ORANGE, scale=(1, 1, 0.85))
        box(self.tpl_jack, (0.14, 0.14, 0.3), (0, 0, 1.2), (0.2, 0.5, 0.15, 1))
        box(self.tpl_jack, (0.18, 0.1, 0.18), (-0.25, -0.66, 0.8), GLOW_YELLOW, glow=True)
        box(self.tpl_jack, (0.18, 0.1, 0.18), (0.25, -0.66, 0.8), GLOW_YELLOW, glow=True)
        box(self.tpl_jack, (0.5, 0.1, 0.12), (0, -0.66, 0.4), GLOW_YELLOW, glow=True)

        # Doce
        self.tpl_candy = NodePath("candy")
        ball(self.tpl_candy, 0.32, (0, 0, 0), (1.0, 0.2, 0.7, 1), scale=(1.2, 0.9, 0.9),
             glow=True, segs=10)
        box(self.tpl_candy, (0.14, 0.34, 0.34), (0.48, 0, 0), GLOW_YELLOW, glow=True)
        box(self.tpl_candy, (0.14, 0.34, 0.34), (-0.48, 0, 0), GLOW_YELLOW, glow=True)

    def build_sky(self):
        moon = ball(self.render, 14, (-35, 250, 36), (1.0, 0.95, 0.7, 1), glow=True, segs=24)
        moon.setFogOff()
        for _ in range(60):
            s = random.uniform(0.3, 0.8)
            star = box(self.render, (s, s, s),
                       (random.uniform(-220, 220), 260, random.uniform(20, 80)),
                       (1, 1, 0.9, 1), glow=True)
            star.setFogOff()

    def build_player(self):
        self.player = self.render.attachNewNode("player")
        self.vis = self.player.attachNewNode("vis")
        self.vis.setZ(1.0)
        self.model = self.vis.attachNewNode("model")
        self.model.setZ(-1.0)
        m = self.model

        # Cabeça de abóbora
        ball(m, 0.58, (0, 0, 1.65), ORANGE, scale=(1.15, 1.0, 0.95))
        # Chapéu de bruxa (caixas empilhadas)
        ball(m, 0.85, (0, 0, 2.12), PURPLE, scale=(1, 1, 0.12))
        box(m, (0.62, 0.62, 0.35), (0, 0, 2.3), PURPLE)
        box(m, (0.64, 0.64, 0.08), (0, 0, 2.2), ORANGE)
        box(m, (0.42, 0.42, 0.35), (0, 0, 2.62), PURPLE)
        box(m, (0.22, 0.22, 0.3), (0.05, 0, 2.92), PURPLE, hpr=(0, 0, -15))
        # Corpo
        box(m, (0.8, 0.5, 0.9), (0, 0, 0.95), (0.18, 0.06, 0.25, 1))
        # Braços e pernas (com pivôs para balançar)
        self.armL = m.attachNewNode("armL")
        self.armL.setPos(-0.55, 0, 1.3)
        box(self.armL, (0.2, 0.22, 0.7), (0, 0, -0.3), PURPLE)
        self.armR = m.attachNewNode("armR")
        self.armR.setPos(0.55, 0, 1.3)
        box(self.armR, (0.2, 0.22, 0.7), (0, 0, -0.3), PURPLE)
        self.legL = m.attachNewNode("legL")
        self.legL.setPos(-0.2, 0, 0.5)
        box(self.legL, (0.28, 0.3, 0.5), (0, 0, -0.25), DARK)
        self.legR = m.attachNewNode("legR")
        self.legR.setPos(0.2, 0, 0.5)
        box(self.legR, (0.28, 0.3, 0.5), (0, 0, -0.25), DARK)

    def build_bats(self):
        self.bats = []
        wing_col = (0.25, 0.12, 0.30, 1)
        for _ in range(6):
            root = self.render.attachNewNode("bat")
            box(root, (0.5, 0.35, 0.3), (0, 0, 0), wing_col, glow=True)
            box(root, (0.08, 0.05, 0.08), (-0.1, -0.19, 0.05), (1, 0.1, 0.1, 1), glow=True)
            box(root, (0.08, 0.05, 0.08), (0.1, -0.19, 0.05), (1, 0.1, 0.1, 1), glow=True)
            wl = root.attachNewNode("wl")
            wl.setPos(0.25, 0, 0)
            box(wl, (1.1, 0.4, 0.05), (0.55, 0, 0), wing_col, glow=True)
            wr = root.attachNewNode("wr")
            wr.setPos(-0.25, 0, 0)
            box(wr, (1.1, 0.4, 0.05), (-0.55, 0, 0), wing_col, glow=True)
            root.setScale(1.6)
            root.setFogOff()
            self.bats.append(dict(
                np=root, wl=wl, wr=wr,
                ph=random.uniform(0, 6.28), bx=random.uniform(-14, 14),
                by=random.uniform(18, 45), bz=random.uniform(7, 13),
                sp=random.uniform(0.4, 0.9), amp=random.uniform(4, 9),
            ))

    def build_hud(self):
        orange = (1, 0.55, 0.1, 1)
        shadow = (0, 0, 0, 1)
        self.score_text = OnscreenText(
            text="", parent=self.a2dTopLeft, pos=(0.06, -0.12), scale=0.08,
            fg=orange, shadow=shadow, align=TextNode.ALeft, mayChange=True)
        self.candy_text = OnscreenText(
            text="", parent=self.a2dTopLeft, pos=(0.06, -0.22), scale=0.055,
            fg=(1, 0.4, 0.8, 1), shadow=shadow, align=TextNode.ALeft, mayChange=True)
        self.best_text = OnscreenText(
            text="", parent=self.a2dTopRight, pos=(-0.06, -0.12), scale=0.06,
            fg=(0.9, 0.9, 0.9, 1), shadow=shadow, align=TextNode.ARight, mayChange=True)
        self.msg_title = OnscreenText(
            text="", pos=(0, 0.3), scale=0.16, fg=orange, shadow=shadow, mayChange=True)
        self.msg_sub = OnscreenText(
            text="", pos=(0, 0.12), scale=0.065, fg=(0.95, 0.9, 0.8, 1), shadow=shadow,
            mayChange=True)
        self.msg_hint = OnscreenText(
            text="", pos=(0, -0.05), scale=0.05, fg=(0.7, 0.8, 0.7, 1), shadow=shadow,
            mayChange=True)

    def setup_input(self):
        self.accept("escape", sys.exit)
        for k in ("arrow_left", "a"):
            self.accept(k, self.change_lane, [-1])
        for k in ("arrow_right", "d"):
            self.accept(k, self.change_lane, [1])
        for k in ("space", "arrow_up", "w"):
            self.accept(k, self.on_jump)
        for k in ("arrow_down", "s"):
            self.accept(k, self.fast_fall)
        self.accept("r", self.start_game)

    # ------------------------------------------------------------ mensagens
    def show_menu(self):
        self.msg_title.setText("CORRIDA ASSOMBRADA")
        self.msg_sub.setText("Aperte ESPACO para comecar")
        self.msg_hint.setText("Setas / A D = trocar de pista    ESPACO = pular")

    def hide_msgs(self):
        self.msg_title.setText("")
        self.msg_sub.setText("")
        self.msg_hint.setText("")

    # --------------------------------------------------------- melhor score
    def load_best(self):
        try:
            with open(BEST_FILE) as f:
                return int(f.read().strip())
        except Exception:
            return 0

    def save_best(self):
        try:
            with open(BEST_FILE, "w") as f:
                f.write(str(self.best))
        except Exception:
            pass

    # ------------------------------------------------------------- estado
    def reset_world(self):
        self.prev_safe = 0
        self.prev_holes = set()
        self.prev_kind = "plain"
        self.serial = 0
        self.elapsed = 0.0
        self.speed = START_SPEED
        self.dist = 0.0
        self.candies = 0
        self.lane = 0
        self.jump_z = 0.0
        self.vz = 0.0
        self.fall_kind = None
        self.fall_t = 0.0
        for i, row in enumerate(self.rows):
            row.y = -17 + i * ROW_LEN
            row.node.setY(row.y)
            self.fill_row(row, safe=(row.y < 30))
        self.player.setPos(0, 0, 0)
        self.vis.setHpr(0, 0, 0)
        self.update_hud()

    def start_game(self):
        self.reset_world()
        self.state = "play"
        self.hide_msgs()

    def on_jump(self):
        if self.state == "menu":
            self.start_game()
        elif self.state == "over":
            if self.over_time > 0.6:
                self.start_game()
        elif self.state == "play" and self.jump_z <= 0.001:
            self.vz = JUMP_V

    def fast_fall(self):
        if self.state == "play" and self.jump_z > 0.05:
            self.vz = -22.0

    def change_lane(self, d):
        if self.state == "play":
            self.lane = max(-1, min(1, self.lane + d))

    def score(self):
        return int(self.dist / 3) + self.candies * 25

    def update_hud(self):
        self.score_text.setText("Pontos: %d" % self.score())
        self.candy_text.setText("Doces: %d" % self.candies)
        self.best_text.setText("Melhor: %d" % max(self.best, self.score()))

    # ------------------------------------------------- geração da estrada
    def fill_row(self, row, safe=False):
        row.node.node().removeAllChildren()
        row.holes = set()
        row.obstacles = []
        row.candies = []
        self.serial += 1
        node = row.node
        diff = min(1.0, self.elapsed / 120.0)

        # Sempre existe uma pista livre, e ela muda no máximo 1 pista por fatia
        safe_lane = max(-1, min(1, self.prev_safe + random.choice((-1, 0, 0, 1))))

        kind = "plain"
        if not safe:
            r = random.random()
            p_hole = 0.22 + 0.18 * diff
            p_tomb = 0.22 + 0.10 * diff
            p_fence = 0.10 + 0.05 * diff
            if r < p_hole:
                kind = "holes"
            elif r < p_hole + p_tomb:
                kind = "tombs"
            elif r < p_hole + p_tomb + p_fence and self.prev_kind == "plain":
                kind = "fence"

        if kind == "holes":
            for lane in (-1, 0, 1):
                if lane != safe_lane and lane not in self.prev_holes and random.random() < 0.7:
                    row.holes.add(lane)
            if not row.holes:
                kind = "plain"

        # Estrada e laterais
        parity = self.serial % 2
        for lane in (-1, 0, 1):
            x = lane * LANE_W
            if lane in row.holes:
                inst(self.tpl_glow, node, (x, 0, 0))
            else:
                inst(self.tpl_tile[parity], node, (x, 0, 0))
        inst(self.tpl_side[parity], node, (-12.5, 0, 0))
        inst(self.tpl_side[parity], node, (12.5, 0, 0))

        # Obstáculos
        if kind == "tombs":
            for lane in (-1, 0, 1):
                if lane != safe_lane and random.random() < 0.65:
                    inst(self.tpl_tomb, node, (lane * LANE_W, 2.5, 0))
                    row.obstacles.append((lane, 2.5, 2.0, 0.45))
            if not row.obstacles:
                kind = "plain"
        elif kind == "fence":
            inst(self.tpl_fence, node, (0, 2.5, 0))
            row.obstacles.append((None, 2.5, 1.1, 0.4))

        # Doces
        if kind == "fence" or (row.holes and random.random() < 0.6):
            lane = random.choice(list(row.holes)) if row.holes else random.choice((-1, 0, 1))
            cz = 2.6
        elif random.random() < 0.45:
            lane, cz = safe_lane, 1.0
        else:
            lane, cz = None, 0
        if lane is not None:
            cn = node.attachNewNode("candy")
            self.tpl_candy.instanceTo(cn)
            cn.setPos(lane * LANE_W, 2.5, cz)
            row.candies.append(dict(np=cn, x=lane * LANE_W, ly=2.5, z=cz, alive=True))

        # Decoração nas laterais
        for side in (-1, 1):
            if random.random() < 0.6:
                r = random.random()
                x = side * random.uniform(6.5, 13)
                y = random.uniform(0, ROW_LEN)
                if r < 0.55:
                    inst(self.tpl_tree, node, (x, y, -0.4), h=random.uniform(0, 360),
                         scale=random.uniform(0.8, 1.5))
                elif r < 0.8:
                    inst(self.tpl_tomb, node, (x, y, -0.4), h=random.uniform(-25, 25),
                         scale=random.uniform(0.6, 1.0))
                else:
                    inst(self.tpl_jack, node, (x, y, -0.4), h=random.uniform(-25, 25),
                         scale=random.uniform(0.9, 1.5))

        self.prev_safe = safe_lane
        self.prev_holes = set(row.holes)
        self.prev_kind = kind

    def scroll(self, dist):
        for row in self.rows:
            row.y -= dist
            row.node.setY(row.y)
        while self.rows[0].y < -17:
            row = self.rows.pop(0)
            row.y = self.rows[-1].y + ROW_LEN
            row.node.setY(row.y)
            self.fill_row(row)
            self.rows.append(row)

    # ------------------------------------------------------------ colisões
    def check_collisions(self):
        px = self.player.getX()
        jz = self.jump_z
        on_ground = jz <= 0.001
        for row in self.rows:
            if row.y > 4 or row.y + ROW_LEN < -4:
                continue
            # Buraco
            if on_ground and row.y + 0.5 < 0 < row.y + ROW_LEN - 0.5:
                for lane in row.holes:
                    if abs(px - lane * LANE_W) < 1.0:
                        self.start_fall("hole")
                        return
            # Obstáculos
            for lane, ly, h, hl in row.obstacles:
                if abs(row.y + ly) < hl + 0.5:
                    if lane is None or abs(px - lane * LANE_W) < 1.2:
                        if jz < h - 0.2:
                            self.start_fall("hit")
                            return
            # Doces
            for c in row.candies:
                if c["alive"] and abs(row.y + c["ly"]) < 0.9 \
                        and abs(px - c["x"]) < 1.3 and abs(1.0 + jz - c["z"]) < 1.4:
                    c["alive"] = False
                    c["np"].hide()
                    self.candies += 1

    def start_fall(self, kind):
        self.state = "falling"
        self.fall_kind = kind
        self.fall_t = 0.0
        self.vz = 7.0 if kind == "hit" else 1.0

    def game_over(self):
        self.state = "over"
        self.over_time = 0.0
        sc = self.score()
        new_record = sc > self.best
        if new_record:
            self.best = sc
            self.save_best()
        self.update_hud()
        self.msg_title.setText("FIM DE JOGO")
        self.msg_sub.setText("Pontos: %d    Melhor: %d" % (sc, self.best))
        self.msg_hint.setText(("NOVO RECORDE!   " if new_record else "") +
                              "ESPACO para tentar de novo")

    # ------------------------------------------------------------ animações
    def animate_runner(self, airborne):
        if airborne:
            self.legL.setP(35)
            self.legR.setP(-20)
            self.armL.setP(-110)
            self.armR.setP(-110)
            self.model.setZ(-1.0)
        else:
            s = math.sin(self.t * 16)
            self.legL.setP(s * 50)
            self.legR.setP(-s * 50)
            self.armL.setP(-s * 40)
            self.armR.setP(s * 40)
            self.model.setZ(-1.0 + abs(s) * 0.1)

    def animate_bats(self):
        for b in self.bats:
            t = self.t * b["sp"] + b["ph"]
            b["np"].setPos(b["bx"] + math.sin(t) * b["amp"],
                           b["by"] + math.cos(t * 0.7) * 5,
                           b["bz"] + math.sin(t * 2) * 1.5)
            flap = math.sin(self.t * 14 + b["ph"]) * 35
            b["wl"].setR(flap)
            b["wr"].setR(-flap)

    def update_candies(self, dt):
        for row in self.rows:
            for c in row.candies:
                if c["alive"]:
                    c["np"].setH(c["np"].getH() + 200 * dt)

    def update_camera(self):
        px = self.player.getX()
        self.camera.setPos(px * 0.4, -9, 5.8)
        self.camera.lookAt(Point3(px * 0.2, 12, 1.4))
        self.camLens.setFov(68 + (self.speed - START_SPEED) * 0.35)

    # ------------------------------------------------------------ loop
    def update(self, task):
        dt = min(ClockObject.getGlobalClock().getDt(), 0.05)
        self.t += dt
        self.animate_bats()
        self.update_candies(dt)

        if self.state == "menu":
            self.scroll(5.0 * dt)
            self.animate_runner(False)

        elif self.state == "play":
            self.elapsed += dt
            self.speed = min(MAX_SPEED, START_SPEED + self.elapsed * ACCEL)

            # Movimento lateral suave
            target_x = self.lane * LANE_W
            x = self.player.getX()
            x += (target_x - x) * min(1.0, dt * 14)
            self.vis.setR((x - target_x) * 4)

            # Pulo
            if self.jump_z > 0 or self.vz != 0:
                self.vz -= GRAVITY * dt
                self.jump_z += self.vz * dt
                if self.jump_z <= 0:
                    self.jump_z = 0.0
                    self.vz = 0.0
            self.player.setPos(x, 0, self.jump_z)
            self.animate_runner(self.jump_z > 0.05)

            self.scroll(self.speed * dt)
            self.dist += self.speed * dt
            self.check_collisions()
            self.update_hud()

        elif self.state == "falling":
            self.fall_t += dt
            decel = 45.0 if self.fall_kind == "hit" else 6.0
            self.speed = max(0.0, self.speed - decel * dt)
            self.scroll(self.speed * dt)

            self.vz -= GRAVITY * dt
            self.jump_z += self.vz * dt
            if self.fall_kind == "hit" and self.jump_z < 0:
                self.jump_z = 0.0
                self.vz = abs(self.vz) * 0.4 if abs(self.vz) > 2 else 0.0
            self.player.setZ(self.jump_z)
            self.vis.setP(self.vis.getP() - 420 * dt)
            if self.fall_kind == "hole":
                self.vis.setR(self.vis.getR() + 200 * dt)
            if self.fall_t > 1.6:
                self.game_over()

        elif self.state == "over":
            self.over_time += dt

        self.update_camera()
        return task.cont


if __name__ == "__main__":
    HalloweenRunner().run()