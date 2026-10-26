"""Summarize sanitized service-load evidence without model access."""
import argparse
from collections import Counter
import json
from pathlib import Path
from service_load import summarize


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def report(root):
    output={}
    for phase in sorted(p for p in root.iterdir() if p.is_dir()):
        item={}
        summary=phase/'summary.json'
        if summary.exists():item['summary']=json.loads(summary.read_text())
        log=phase/'requestlogs.jsonl'
        if log.exists():
            rows=read_rows(log)
            item['server_logs']={'requests':len(rows),'hits':sum(r.get('hits',0) for r in rows),
                                 'dedup':sum(r.get('dedup',0) for r in rows),
                                 'status':dict(Counter(str(r.get('status')) for r in rows)),
                                 'max_wait_ms':max((r.get('wait_ms',0) for r in rows),default=0)}
        resources=phase/'resources.jsonl'
        if resources.exists():
            rows=read_rows(resources)
            rss=[r['rss_kib'] for r in rows if 'rss_kib' in r]
            item['resources']={'samples':len(rows),'peak_rss_mib':max(rss)/1024 if rss else None,
                               'first_rss_mib':rss[0]/1024 if rss else None,
                               'last_rss_mib':rss[-1]/1024 if rss else None,
                               'first_swap':rows[0].get('swap') if rows else None,
                               'last_swap':rows[-1].get('swap') if rows else None,
                               'first_vm':rows[0].get('vm') if rows else None,
                               'last_vm':rows[-1].get('vm') if rows else None}
        live=phase/'live.jsonl'
        if live.exists():
            rows=read_rows(live)
            windows={}
            for r in rows:windows.setdefault(int(r['end_s']//60),[]).append(r)
            item['minute_windows']={str(k):summarize(v,60) for k,v in windows.items()}
            if rows:
                # Compare identical class/mode cohorts, not aggregate latency mixtures.
                end=max(r['end_s'] for r in rows)
                trend={}
                for sparse in (False,True):
                    for length in (32,512,2048):
                        cohort=[r for r in rows if r['sparse']==sparse and r['length']==length]
                        first=[r for r in cohort if 600<=r['end_s']<1200]
                        last=[r for r in cohort if end-600<=r['end_s']<end]
                        if first and last:
                            trend[f'{sparse}-{length}']={'stable_10_20_min':summarize(first,600),
                                                        'last_10_min':summarize(last,600)}
                item['cohort_trends']=trend
        recovery=phase/'recovery.json'
        if recovery.exists():item['recovery']=json.loads(recovery.read_text())
        if item:output[phase.name]=item
    return output


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.write_text(json.dumps(report(a.root),indent=2))
