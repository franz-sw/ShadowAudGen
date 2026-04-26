import argparse
import sys
from pathlib import Path

from config import BASE_DIR, DEFAULT_JSON
from generator import AudioGenerator
from exporter import Exporter


def main():
    parser = argparse.ArgumentParser(
        description="Shadowing Audio Generator CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--json", "-j", default=DEFAULT_JSON)
    parser.add_argument("--overwrite", "-o", action="store_true")
    parser.add_argument("--export-all", action="store_true")
    parser.add_argument("--export-only", action="store_true")
    parser.add_argument("--export-name", default="shadowing_transcripts.md")

    args = parser.parse_args()

    try:
        if args.export_only:
            exporter = Exporter()
            md_paths = exporter.export_to_markdown(args.export_name)
            for md_path in md_paths:
                print(f"Export completed: {md_path}")
            return 0

        print("Starting full shadowing workflow...")
        generator = AudioGenerator()
        generator.run_full_generation(json_path=args.json, overwrite=args.overwrite, export_all=args.export_all)

        exporter = Exporter()
        md_paths = exporter.export_to_markdown(default_json=args.json, output_name=args.export_name)

        print("All steps completed successfully!")
        for md_path in md_paths:
            print(f"Export: {md_path}")

        return 0
    except FileNotFoundError as e:
        print(f"File not found: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())