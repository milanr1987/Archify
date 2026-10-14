"""Čiste izvedene provjere iz bezbjednog inventara; bez pristupa izvorima."""
from collections import defaultdict
from datetime import datetime


def skill_groups(items):
    by_id = {i.id: i for i in items}
    named = defaultdict(list)
    for item in items:
        if item.kind == 'skill':
            named[item.name.lower()].append(item)
    groups = []
    for name, members in sorted(named.items()):
        buckets = defaultdict(list)
        for item in members:
            for loc in item.locations:
                if loc.origin == 'standalone':
                    key = ('own',)
                else:
                    plugin = by_id.get((loc.origin or '')[7:]) if (loc.origin or '').startswith('plugin:') else None
                    if plugin and plugin.metadata.get('version'):
                        key = ('plugin', plugin.name, plugin.metadata.get('marketplace',''), plugin.metadata['version'])
                    else:
                        key = ('unknown', loc.origin or '')
                buckets[key].append({'itemId':item.id, 'path':loc.path, 'profile':loc.profile or '',
                    'hash':loc.contentHash or 'unknown', 'origin':'samostalno' if key[0]=='own' else 'plugin',
                    'plugin':key[1] if key[0]=='plugin' else '', 'version':key[-1] if key[0]=='plugin' else ''})
        statuses = []
        own_drift = False
        variants = []
        for key, locations in sorted(buckets.items()):
            hashes = {v['hash'] for v in locations}
            status = 'nepoznato' if 'unknown' in hashes or key[0]=='unknown' else 'razlikuje se' if len(hashes)>1 else 'isti'
            statuses.append(status)
            if key[0]=='own' and status=='razlikuje se': own_drift=True
            variants.append({'cohort':list(key), 'status':status, 'locations':locations})
        status = 'nepoznato' if 'nepoznato' in statuses else 'razlikuje se' if 'razlikuje se' in statuses else 'isti'
        groups.append({'name':members[0].name, 'status':status, 'ownDrift':own_drift,
                       'itemIds':[m.id for m in members], 'variants':variants,
                       'multiple':sum(len(m.locations) for m in members)>1})
    return groups


def hook_matrix(items, profiles):
    rows = {}
    seen = set()
    for item in sorted(items, key=lambda i:i.id):
        if item.kind != 'hook': continue
        key = (item.metadata.get('event','unknown'),item.metadata.get('matcher',''))
        cells = rows.setdefault(key,{p:[] for p in sorted(profiles)})
        for loc in item.locations:
            if not loc.profile: continue
            identity = (key,loc.profile,loc.path,loc.origin)
            if identity in seen: continue
            seen.add(identity)
            cells.setdefault(loc.profile,[]).append({'hookCount':int(item.metadata.get('hookCount','0')),
                'hookTypes':item.metadata.get('hookTypes',[]),
                'origin':'plugin' if (loc.origin or '').startswith('plugin:') else 'settings'})
    return [{'event':key[0],'matcher':key[1],'cells':cells} for key,cells in sorted(rows.items())]


def activity_key(item):
    dates = []
    for key in ('lastCommitAt','lastSessionAt'):
        try:
            date = datetime.fromisoformat(item.metadata.get(key,'unknown'))
            if date.tzinfo: dates.append(date.timestamp())
        except (ValueError,TypeError,OverflowError): pass
    return max(dates, default=float('-inf'))
