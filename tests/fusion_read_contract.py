# SPDX-License-Identifier: GPL-3.0-only
"""Read-only contracts on an authorized open body. Not discovered by unittest.

Pass the entry module of the registered running add-in, not a transient MCP
import; this ensures the test uses the source actually loaded by Fusion.
"""
import math
from time import perf_counter

import adsk.fusion


def fingerprint(body):
    properties = body.physicalProperties
    return {'faces': body.faces.count, 'edges': body.edges.count,
            'volume': properties.volume, 'area': properties.area,
            'visible': body.isVisible}


def inspect_body(entry, body, samples=8):
    before, started = fingerprint(body), perf_counter()
    report = {'cases': []}
    for kind, collection in (('edge', body.edges), ('face', body.faces)):
        if not collection.count:
            continue
        seed = collection.item(0)
        if kind == 'edge':
            seed = next(e for e in collection if not e.isDegenerate)
        snapshot, _, references, skipped, _ = entry.adapter.read_snapshot((seed,))
        assert all(entity.body == body for entity in references.values()), 'Body scope escaped.'
        for descriptor in snapshot.entities[:samples]:
            session = entry.SelectionSession(snapshot, (descriptor.key,))
            assert {item.key for item in session.ranking.items} == set(snapshot.by_key)
            session.set_level(0)
            previous = set(session.result)
            for _ in session.ranking.tiers:
                session.adjust_similarity(1)
                assert previous <= set(session.result), 'Ranking ranges must be nested.'
                previous = set(session.result)
            assert set(session.result) == set(snapshot.by_key), 'Full range omitted an entity.'
            session.adjust_similarity(-10000)
            assert session.result == (descriptor.key,), 'Examples must survive contraction.'
        report['cases'].append({'kind': kind, 'entities': len(snapshot.entities),
                                'links': len(snapshot.links), 'samples': min(samples, len(snapshot.entities)),
                                'skipped': skipped, 'complete_ranking': True, 'nested_ranges': True})
    after = fingerprint(body)
    assert before['faces'] == after['faces'] and before['edges'] == after['edges']
    assert before['visible'] == after['visible']
    assert all(math.isclose(before[key], after[key], rel_tol=1e-10) for key in ('volume', 'area'))
    report.update(geometry_unchanged=True, elapsed_seconds=round(perf_counter()-started, 4))
    return report
