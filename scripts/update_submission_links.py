"""Record user-supplied submission links locally; makes no external calls."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from groww.submission import LINK_FIELDS, load_links, validate_links


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in sorted(LINK_FIELDS):
        parser.add_argument('--' + field.replace('_', '-'))
    parser.add_argument('--clear', choices=sorted(LINK_FIELDS), action='append', default=[])
    args = parser.parse_args()
    links = load_links(ROOT)
    for field in LINK_FIELDS:
        if getattr(args, field) is not None:
            links[field] = getattr(args, field)
    for field in args.clear:
        links[field] = None
    validate_links(links)
    (ROOT / 'submission_links.json').write_text(json.dumps(links, indent=2) + '\n', encoding='utf-8')
    print('Submission links saved locally. Rebuild the packet to include changes. Remote evidence remains separately pending.')


if __name__ == '__main__':
    main()
