# SPDX-License-Identifier: GPL-3.0-only
"""Explicit search domains; body-local topology stays isolated when combined."""
from dataclasses import replace
from .snapshot import BodySnapshot

SCOPES = (('body', 'This Body'), ('component', 'This Component'), ('all', 'All Components'))


def component_contains(component_path, occurrence_path):
    """A root component contains the assembly; an instance contains its subtree."""
    return component_path is None or occurrence_path == component_path or occurrence_path.startswith(component_path+'+')


def merge_snapshots(snapshots, scope_key, revision):
    """Namespace local IDs before ranking an explicitly authorized domain."""
    entities, links, walls, maps = [], [], [], []
    for index, snapshot in enumerate(snapshots):
        mapping = {d.key: '{}:{}'.format(index, d.key) for d in snapshot.entities}
        maps.append(mapping)
        entities.extend(replace(d, key=mapping[d.key], scope_key=scope_key) for d in snapshot.entities)
        links.extend((mapping[a], mapping[b]) for a, b in snapshot.links)
        walls.extend((mapping[a], mapping[b]) for a, b in snapshot.wall_pairs)
    complete = all(s.relations_complete for s in snapshots)
    return BodySnapshot(scope_key, revision, tuple(entities), tuple(links), tuple(walls) if complete else (), complete), tuple(maps)
