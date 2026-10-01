"""Migrate legacy downloads to verified Parquet; delete sources only after validation."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import pandas as pd
from storage import ROOT, TICKERS, COLS, read_prices, merge_prices, write_parquet

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def infer_timezone(path, reference):
    # Old yfinance wrote UTC; newer releases used each exchange's timezone.
    # Resolve the change from matching overlapping OHLCV records, never from host timezone.
    try:
        read_prices(path)
        return 'UTC', {'explicit_offset': 1}
    except ValueError as error:
        if 'explicit timezone' not in str(error):
            raise
    scores = {}
    for zone in ('UTC', 'America/New_York', 'America/Chicago', 'Europe/London'):
        candidate = read_prices(path, zone)
        overlap = candidate.merge(reference, on='Datetime', suffixes=('', '_old'))
        equal = pd.Series(True, index=overlap.index)
        for col in COLS[1:]:
            equal &= (overlap[col].round(5) - overlap[col + '_old'].round(5)).abs() < 0.000011
        scores[zone] = int(equal.sum())
    ordered = sorted(scores, key=scores.get, reverse=True)
    if scores[ordered[0]] == 0:
        return None, scores
    if scores[ordered[0]] == scores[ordered[1]]:
        raise ValueError(f'Cannot resolve timezone for {path}: {scores}')
    return ordered[0], scores

def migrate(root, delete=False):
    dates = sorted(p for p in root.iterdir() if p.is_dir() and re.fullmatch(r'\d{4}-\d{2}-\d{2}', p.name))
    old_dirs = dates + [root / d for d in ('2m-data', 'data_5m', 'options_data_yq', 'options_data') if (root / d).exists()]
    sources = sorted({p for d in old_dirs + [root / 'history'] for p in d.rglob('*.csv')})
    sources += sorted(root.glob('output_*.csv'))
    if not sources:
        print('No legacy CSV sources remain.')
        return
    inventory = {str(p.relative_to(root)): digest(p) for p in sources}
    manifest = {'sources': inventory, 'timezone_decisions': {}, 'outputs': {}}
    def save(df, dest):
        write_parquet(df, dest)
        manifest['outputs'][str(dest.relative_to(root))] = {'rows': len(df), 'sha256': digest(dest)}
    for name, ticker in TICKERS.items():
        frames = []
        old = root / 'history' / f'{ticker}.csv'
        if old.exists():
            frames.append(read_prices(old))
        reference = merge_prices(frames) if frames else None
        previous_zone = None
        for folder in dates:
            source = folder / f'{name}.csv'
            if not source.exists():
                continue
            # The first snapshots have no offsets but match UTC history.
            if reference is None:
                zone, scores = 'UTC', {'baseline': 0}
                if folder.name >= '2026-05-30':
                    raise ValueError(f'No timezone reference for {source}')
            else:
                zone, scores = infer_timezone(source, reference)
                if zone is None:
                    if previous_zone is None:
                        raise ValueError(f'No overlap or established timezone for {source}')
                    zone = previous_zone
                    scores['inherited_from_previous_snapshot'] = 1
                else:
                    if max(scores.values()) < 20 and 'explicit_offset' not in scores and zone != previous_zone:
                        raise ValueError(f'Insufficient evidence of timezone change for {source}: {scores}')
                    previous_zone = zone
            df = read_prices(source, zone)
            manifest['timezone_decisions'][str(source.relative_to(root))] = {'zone': zone, 'matching_rows': scores}
            frames.append(df)
            reference = merge_prices(frames)
        if frames:
            save(reference, root / 'history' / '1m' / f'{ticker}.parquet')
            # Keep distinct observations, including conflicting revisions, with provenance.
            observations = []
            origins = ([old] if old.exists() else []) + [d / f'{name}.csv' for d in dates if (d / f'{name}.csv').exists()]
            for frame, source in zip(frames, origins):
                observations.append(frame.assign(source=str(source.relative_to(root))))
            save(pd.concat(observations, ignore_index=True), root / 'history' / 'observations' / '1m' / f'{ticker}.parquet')
        for directory, interval in [('2m-data', '2m'), ('data_5m', '5m')]:
            source = root / directory / f'{name}.csv'
            if source.exists():
                df = read_prices(source)  # These legacy files have explicit UTC offsets.
                dest = root / 'history' / interval / f'{ticker}.parquet'
                if dest.exists():
                    df = merge_prices([read_prices(dest), df])
                save(df, dest)
    for directory in ('options_data_yq', 'options_data'):
        for source in sorted((root / directory).rglob('*.csv')):
            df = pd.read_csv(source)
            # Preserve provider fields and original timestamp strings exactly.
            dest = root / 'history' / 'options' / directory / source.relative_to(root / directory).with_suffix('.parquet')
            save(df, dest)
    for source in sorted(root.glob('output_*.csv')):
        # These derived files were written in Eastern time by fix_timestamps.py.
        save(read_prices(source, 'America/New_York'), root / 'history' / 'legacy_derived' / source.with_suffix('.parquet').name)
    covered = {p for p in sources if str(p.relative_to(root)) in inventory}
    expected_prices = {p for d in dates + [root/'2m-data', root/'data_5m'] for p in d.glob('*.csv')}
    known = {n + '.csv' for n in TICKERS}
    if any(p.name not in known for p in expected_prices):
        raise ValueError('Unknown price file; refusing cleanup')
    if any(p.name.removesuffix('.csv') not in TICKERS.values() for p in (root/'history').glob('*.csv')):
        raise ValueError('Unknown history file; refusing cleanup')
    for d in old_dirs:
        if any(p.is_symlink() or (p.is_file() and p not in covered) for p in d.rglob('*')):
            raise ValueError(f'Unexpected file in {d}; refusing cleanup')
    for source in sources:
        if digest(source) != inventory[str(source.relative_to(root))]:
            raise ValueError(f'Source changed during migration: {source}')
    (root / 'history' / 'migration_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    if delete:
        for source in sources:
            source.unlink()
        for directory in old_dirs:
            shutil.rmtree(directory)
    print(f'Validated {len(sources)} sources into {len(manifest["outputs"])} Parquet files; cleanup={delete}')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--delete-sources', action='store_true')
    args = parser.parse_args()
    migrate(args.root, args.delete_sources)

if __name__ == '__main__':
    main()
