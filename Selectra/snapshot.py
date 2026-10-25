# SPDX-License-Identifier: GPL-3.0-only
"""Immutable, serializable snapshot of one body occurrence; no live API objects."""
from dataclasses import asdict, dataclass, field
import json
from math import isfinite
from types import MappingProxyType

from .matching import Descriptor


@dataclass(frozen=True)
class BodySnapshot:
    scope_key: str
    revision: str
    entities: tuple
    links: tuple = ()  # Undirected, same-kind adjacency (edge-edge or face-face).
    by_key: object = field(init=False, repr=False, compare=False)
    adjacency: object = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        if not self.scope_key or not self.revision:
            raise ValueError('Snapshot needs an explicit body scope and revision.')
        entities = tuple(sorted(self.entities, key=lambda d: d.key))
        if len({d.key for d in entities}) != len(entities):
            raise ValueError('Duplicate entity keys.')
        if any(not d.key or d.scope_key != self.scope_key for d in entities):
            raise ValueError('Every entity must belong to this exact body occurrence.')
        if any(d.kind not in ('edge', 'face') or not isfinite(d.measure) or d.measure <= 0 for d in entities):
            raise ValueError('Snapshot entities must have valid kind and positive size.')
        for d in entities:
            for name in ('perimeter', 'radius', 'face_angle'):
                value = getattr(d, name)
                if value is not None and (not isfinite(value) or value < 0):
                    raise ValueError('Optional measurements must be finite and nonnegative.')
            for name in ('sides', 'loops', 'adjacent_faces'):
                value = getattr(d, name)
                if value is not None and (type(value) is not int or value < 0):
                    raise ValueError('Topology counts must be nonnegative integers.')
        if len({d.kind for d in entities}) > 1:
            raise ValueError('A snapshot contains either edges or faces.')
        by_key = {d.key: d for d in entities}
        adjacency = {d.key: set() for d in entities}
        links = set()
        for a, b in self.links:
            if a not in by_key or b not in by_key or a == b:
                raise ValueError('Adjacency must reference distinct entities inside the body.')
            a, b = sorted((a, b))
            links.add((a, b))
            adjacency[a].add(b)
            adjacency[b].add(a)
        object.__setattr__(self, 'entities', entities)
        object.__setattr__(self, 'links', tuple(sorted(links)))
        object.__setattr__(self, 'by_key', MappingProxyType(by_key))
        object.__setattr__(self, 'adjacency', MappingProxyType({k: tuple(sorted(v)) for k, v in adjacency.items()}))

    def require_keys(self, keys):
        keys = tuple(sorted(set(keys)))
        if any(key not in self.by_key for key in keys):
            raise ValueError('Entity is outside the selected body snapshot.')
        return keys

    def to_dict(self):
        return {'schema_version': 1, 'scope_key': self.scope_key, 'revision': self.revision,
                'entities': [asdict(d) for d in self.entities], 'links': [list(link) for link in self.links]}

    @classmethod
    def from_dict(cls, data):
        if data.get('schema_version') != 1:
            raise ValueError('Unsupported snapshot schema.')
        entities = []
        for row in data['entities']:
            row = dict(row)
            for key in ('direction', 'normal', 'position'):
                if row.get(key) is not None:
                    vector = row[key]
                    if len(vector) != 3 or any(not isfinite(v) for v in vector):
                        raise ValueError('Vectors need three finite components.')
                    row[key] = tuple(vector)
            entities.append(Descriptor(**row))
        return cls(data['scope_key'], data['revision'], tuple(entities), tuple(data.get('links', ())))

    def to_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, allow_nan=False)
