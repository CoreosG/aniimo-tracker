"""Bound managed screenshot storage without modifying run history or balances."""
import re
from pathlib import Path

_GENERATED=re.compile(r'(?:\d{8}_\d{6}_[0-9a-f]{8}|[0-9a-f]{32})_(?:auto|money|points|balance)\.png',re.I)


def prune_screenshots(ledger,directory,protected=()):
    limit=ledger.settings()['screenshot_runs']
    if type(limit) is not int or limit<0:raise ValueError('Screenshot retention must be a non-negative whole number.')
    root=Path(directory).resolve()
    result=dict(removed=0,failed=[])
    if not root.is_dir():return result
    runs=ledger.runs();kept_ids={row['id'] for row in runs[:limit]}
    keep=set();referenced=set()
    def remember(value,retain=False):
        if not value:return
        try:path=Path(value).resolve()
        except (OSError,ValueError):return
        referenced.add(path)
        if retain:keep.add(path)
    for row in runs:
        for key in ('money_image','points_image'):remember(row[key],row['id'] in kept_ids)
    for start in ledger.starts():
        active=start['run_id'] is None and not start['cancelled']
        remember(start['screenshot'],active or start['run_id'] in kept_ids)
    for value in ledger.draft().get('images',{}).values():remember(value,True)
    for value in protected:remember(value,True)
    for path in root.iterdir():
        try:
            # Never recurse or follow a link out of the managed folder. Ignore
            # arbitrary user files and OCR scratch files that workers may hold.
            if path.is_symlink() or not path.is_file() or path.suffix.lower()!='.png' or path.name.endswith('.ocr.png'):continue
            resolved=path.resolve()
            if resolved.parent!=root or resolved in keep:continue
            if resolved not in referenced and not _GENERATED.fullmatch(path.name):continue
            path.unlink();result['removed']+=1
        except OSError:
            result['failed'].append(str(path))
    return result
