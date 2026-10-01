"""Merge two normalized price files; the second wins overlapping timestamps."""
import argparse
from storage import read_prices, merge_prices, write_parquet

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file1')
    parser.add_argument('file2')
    parser.add_argument('output', help='Destination .parquet file')
    parser.add_argument('--naive-timezone', help='Required for legacy timestamps without offsets')
    args = parser.parse_args()
    result = merge_prices([read_prices(p, args.naive_timezone) for p in (args.file1, args.file2)])
    write_parquet(result, args.output)
    print(f'Saved {len(result)} rows to {args.output}')

if __name__ == '__main__':
    main()
