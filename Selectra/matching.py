# SPDX-License-Identifier: GPL-3.0-only
"""Deterministic intent hypotheses over immutable snapshots; no Fusion imports.

Lengths are cm, areas cm², angles radians. Scores are ranking heuristics,
not calibrated probabilities. A missing property never means a match.
"""
from dataclasses import dataclass
from math import acos, isfinite, pi, sqrt
from typing import Optional, Tuple

Vector = Tuple[float, float, float]


@dataclass(frozen=True)
class Descriptor:
    key: str
    kind: str
    geometry: str
    measure: float  # Edge length or face area.
    perimeter: Optional[float] = None
    radius: Optional[float] = None
    direction: Optional[Vector] = None  # Line direction or cylinder axis.
    normal: Optional[Vector] = None  # Oriented normal, planar faces only.
    sides: Optional[int] = None
    loops: Optional[int] = None


@dataclass(frozen=True)
class Tolerance:
    relative: float = 0.01
    angle: float = 2 * pi / 180
    length: float = 1e-6
    area: float = 1e-8

    def __post_init__(self):
        if any(not isfinite(v) or v < 0 for v in
               (self.relative, self.angle, self.length, self.area)):
            raise ValueError('Tolerances must be finite and nonnegative.')
        if self.angle > pi:
            raise ValueError('Angular tolerance must not exceed pi.')


@dataclass(frozen=True)
class Hypothesis:
    intent: str
    label: str
    keys: Tuple[str, ...]
    score: float


@dataclass(frozen=True)
class Inference:
    proposals: Tuple[Hypothesis, ...]
    ambiguous: bool
    explanation: str


def _near(a, b, relative, absolute):
    return (a is not None and b is not None and isfinite(a) and isfinite(b)
            and abs(a - b) <= max(absolute, relative * max(abs(a), abs(b))))


def _angle(a, b, axial=False):
    if a is None or b is None:
        return float('inf')
    if not all(isfinite(v) for v in a + b):
        return float('inf')
    na, nb = sqrt(sum(v*v for v in a)), sqrt(sum(v*v for v in b))
    if not na or not nb:
        return float('inf')
    dot = sum(x*y for x, y in zip(a, b)) / (na * nb)
    return acos(max(-1.0, min(1.0, abs(dot) if axial else dot)))


def _matches(a, b, intent, t):
    if a.kind != b.kind:
        return False
    same_geometry = a.geometry == b.geometry
    size = _near(a.measure, b.measure, t.relative,
                 t.length if a.kind == 'edge' else t.area)
    radius = _near(a.radius, b.radius, t.relative, t.length)
    direction = _angle(a.direction, b.direction, axial=True) <= t.angle
    normal = _angle(a.normal, b.normal) <= t.angle
    shape = (same_geometry and size
             and _near(a.perimeter, b.perimeter, t.relative, t.length)
             and a.sides is not None and a.sides == b.sides
             and a.loops is not None and a.loops == b.loops)
    if intent == 'length':
        return same_geometry and size
    if intent == 'direction':
        return a.geometry == b.geometry == 'line' and direction
    if intent == 'length_direction':
        return a.geometry == b.geometry == 'line' and size and direction
    if intent == 'radius':
        # Full circles and arcs are different families; open arc length is
        # intentionally ignored for the radius-only hypothesis.
        return same_geometry and a.geometry in ('circle', 'arc', 'cylinder') and radius
    if intent == 'radius_size':
        return same_geometry and a.geometry in ('circle', 'arc', 'cylinder') and radius and size
    if intent == 'area':
        return a.kind == 'face' and size
    if intent == 'shape_size':
        return a.kind == 'face' and shape
    if intent == 'normal':
        return a.geometry == b.geometry == 'plane' and normal
    if intent == 'shape_normal':
        return a.geometry == b.geometry == 'plane' and shape and normal
    raise ValueError('Unknown intent: ' + intent)


def infer(seeds, candidates, tolerance=None):
    """Rank explanations that fit *all* examples, with deterministic tie breaks.

    Candidates must be from a scope already checked by the Fusion adapter.
    The pool includes every seed. Distinct intents producing the same set are
    collapsed, so confidence isn't inflated by duplicate explanations.
    """
    t = tolerance or Tolerance()
    seeds, candidates = tuple(seeds), tuple(candidates)
    if not seeds:
        return Inference((), True, 'Select an edge or a face first.')
    if len({s.key for s in seeds}) != len(seeds):
        raise ValueError('Duplicate seed keys.')
    if len({c.key for c in candidates}) != len(candidates):
        raise ValueError('Duplicate candidate keys.')
    if len({s.kind for s in seeds}) != 1:
        return Inference((), True, 'Use only edges or only faces in this prototype.')
    pool = {c.key: c for c in candidates}
    for s in seeds:
        if s.key in pool and pool[s.key] != s:
            raise ValueError('Conflicting descriptor for seed: ' + s.key)
        pool[s.key] = s
    if any(s.kind not in ('edge', 'face') or s.measure <= 0
           or not isfinite(s.measure) for s in seeds):
        return Inference((), True, 'Examples contain unsupported or degenerate geometry.')
    intents = ([('length_direction', 'Same length and direction', .96),
                ('radius_size', 'Same radius and size', .98),
                ('radius', 'Same radius', .94),
                ('length', 'Same length', .82),
                ('direction', 'Parallel edges', .76)] if seeds[0].kind == 'edge' else
               [('radius_size', 'Same cylinder radius and area', .98),
                ('radius', 'Same cylinder radius', .94),
                ('shape_normal', 'Same size, boundary and orientation', .96),
                ('shape_size', 'Same area and boundary signature', .90),
                ('area', 'Same area', .74),
                ('normal', 'Same facing direction', .72)])
    proposals = []
    seed_keys = {s.key for s in seeds}
    for intent, label, prior in intents:
        # Pairwise seed agreement prevents a chain of drifting examples.
        if not all(_matches(a, b, intent, t) for a in seeds for b in seeds):
            continue
        keys = tuple(sorted(c.key for c in pool.values()
                            if all(_matches(s, c, intent, t) for s in seeds)))
        if not set(keys) - seed_keys:
            continue
        # Mild penalty for a hypothesis covering nearly the entire scope.
        score = prior - .12 * len(keys) / len(pool)
        proposals.append(Hypothesis(intent, label, keys, score))
    proposals.sort(key=lambda h: (-h.score, h.intent))
    distinct = []
    seen = set()
    for proposal in proposals:
        if proposal.keys not in seen:
            distinct.append(proposal)
            seen.add(proposal.keys)
    ambiguous = (not distinct or
                 (len(distinct) > 1 and (len(seeds) == 1 or
                  distinct[0].score - distinct[1].score < .15)))
    explanation = ('No additional matches. Try another example or a wider tolerance.'
                   if not distinct else
                   'Several interpretations fit. Check the preview or add another example.'
                   if ambiguous else 'Best geometric interpretation; check the preview.')
    return Inference(tuple(distinct), ambiguous, explanation)
