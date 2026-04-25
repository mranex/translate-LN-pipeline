from __future__ import annotations
import argparse
from .config_loader import load_config
from .pipeline import extract_glossary, merge_glossary, approve_glossary, build_segment_glossary, extract_relationships, merge_relationships, approve_relationships, build_segment_pronouns, build_segment_context, label_dialogue, translate, assemble, qa, fix, glossary_prep, relationship_prep, run_translation

def parse_volumes(s: str) -> list[int]:
    if s == "all": return list(range(1, 19))
    out = []
    for part in s.split(','):
        part = part.strip()
        if not part: continue
        if '-' in part:
            a, b = part.split('-', 1); out.extend(range(int(a), int(b)+1))
        else: out.append(int(part))
    return sorted(set(out))

def main():
    parser = argparse.ArgumentParser(description="Final clean Light Novel translation pipeline")
    parser.add_argument("--config", default="config/config.json")
    sub = parser.add_subparsers(dest="cmd", required=True)
    def add_volume(p): p.add_argument("--volume", type=int, required=True)
    def add_volumes(p): p.add_argument("--volumes", required=True, help="all, 1, 1-5, 1,3,7-10")
    p = sub.add_parser("glossary-prep"); add_volumes(p)
    p = sub.add_parser("extract-glossary"); add_volume(p)
    p = sub.add_parser("merge-glossary"); add_volume(p); p.add_argument("--no-previous", action="store_true")
    p = sub.add_parser("approve-glossary"); add_volume(p); p.add_argument("--from-file"); p.add_argument("--overwrite", action="store_true")
    p = sub.add_parser("build-segment-glossary"); add_volume(p)
    p = sub.add_parser("relationship-prep"); add_volume(p)
    p = sub.add_parser("extract-relationships"); add_volume(p)
    p = sub.add_parser("merge-relationships"); add_volume(p); p.add_argument("--no-previous", action="store_true")
    p = sub.add_parser("approve-relationships"); add_volume(p); p.add_argument("--from-file"); p.add_argument("--overwrite", action="store_true")
    p = sub.add_parser("build-segment-pronouns"); add_volume(p)
    p = sub.add_parser("build-context"); add_volume(p)
    p = sub.add_parser("label-dialogue"); add_volume(p)
    p = sub.add_parser("translate"); add_volume(p)
    p = sub.add_parser("assemble"); add_volume(p); p.add_argument("--fixed", action="store_true")
    p = sub.add_parser("qa"); add_volume(p)
    p = sub.add_parser("fix"); add_volume(p)
    p = sub.add_parser("run-translation"); add_volume(p)
    args = parser.parse_args(); config = load_config(args.config)
    if args.cmd == "glossary-prep": glossary_prep(config, parse_volumes(args.volumes))
    elif args.cmd == "extract-glossary": extract_glossary(config, args.volume)
    elif args.cmd == "merge-glossary": merge_glossary(config, args.volume, previous_finalized=not args.no_previous)
    elif args.cmd == "approve-glossary": approve_glossary(config, args.volume, args.from_file, args.overwrite)
    elif args.cmd == "build-segment-glossary": build_segment_glossary(config, args.volume)
    elif args.cmd == "relationship-prep": relationship_prep(config, args.volume)
    elif args.cmd == "extract-relationships": extract_relationships(config, args.volume)
    elif args.cmd == "merge-relationships": merge_relationships(config, args.volume, previous_finalized=not args.no_previous)
    elif args.cmd == "approve-relationships": approve_relationships(config, args.volume, args.from_file, args.overwrite)
    elif args.cmd == "build-segment-pronouns": build_segment_pronouns(config, args.volume)
    elif args.cmd == "build-context": build_segment_context(config, args.volume)
    elif args.cmd == "label-dialogue": label_dialogue(config, args.volume)
    elif args.cmd == "translate": translate(config, args.volume)
    elif args.cmd == "assemble": assemble(config, args.volume, fixed=args.fixed)
    elif args.cmd == "qa": qa(config, args.volume)
    elif args.cmd == "fix": fix(config, args.volume)
    elif args.cmd == "run-translation": run_translation(config, args.volume)
if __name__ == "__main__": main()
