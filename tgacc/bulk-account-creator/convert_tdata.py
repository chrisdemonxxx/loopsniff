#!/usr/bin/env python3
"""CLI entry-point for TData → Telethon .session conversion.

Usage examples:
  # Batch-convert all tdata folders in a directory
  python convert_tdata.py --input ./purchased_tdata/ --output ./sessions/telethon/

  # Convert a single tdata folder
  python convert_tdata.py --input ./single_tdata_folder/ --output ./sessions/telethon/ --single

  # Validate existing .session files
  python convert_tdata.py --validate ./sessions/telethon/

  # Dry-run (show what would be converted)
  python convert_tdata.py --input ./purchased_tdata/ --dry-run
"""

import argparse
import asyncio
import sys
from pathlib import Path

from loguru import logger

from core.tdata_converter import TDataConverter


def _setup_logger() -> None:
    """Configure loguru with a clean format for CLI use."""
    logger.remove()
    logger.add(
        sys.stderr,
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<level>{message}</level>"
        ),
        level="INFO",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert Telegram Desktop TData folders to Telethon .session files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--input", "-i",
        type=str,
        help="Path to directory containing TData folders (or a single TData folder with --single).",
    )
    group.add_argument(
        "--validate", "-V",
        type=str,
        help="Validate existing .session files in the given directory.",
    )

    parser.add_argument(
        "--output", "-o",
        type=str,
        default="sessions/telethon",
        help="Directory where .session files are written (default: sessions/telethon/).",
    )
    parser.add_argument(
        "--profiles", "-p",
        type=str,
        default="outreach/data/device_profiles.json",
        help="Path to device_profiles.json (default: outreach/data/device_profiles.json).",
    )
    parser.add_argument(
        "--single", "-s",
        action="store_true",
        help="Treat --input as a single TData folder instead of a batch directory.",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show what would be converted without actually converting.",
    )

    return parser.parse_args()


# ── Validate mode ───────────────────────────────────────────────────────────

def _run_validate(directory: str) -> int:
    """Validate all .session files in *directory*. Returns exit code."""
    converter = TDataConverter()
    session_dir = Path(directory)

    if not session_dir.is_dir():
        logger.error("Not a directory: {}", directory)
        return 1

    session_files = sorted(session_dir.glob("*.session"))
    if not session_files:
        logger.warning("No .session files found in {}", directory)
        return 0

    valid = 0
    invalid = 0
    for sf in session_files:
        ok = converter.validate_session(str(sf))
        if ok:
            logger.info("✓ {}", sf.name)
            valid += 1
        else:
            logger.error("✗ {}", sf.name)
            invalid += 1

    logger.info("Validation complete — {} valid, {} invalid out of {}", valid, invalid, len(session_files))
    return 1 if invalid else 0


# ── Dry-run mode ────────────────────────────────────────────────────────────

def _run_dry_run(input_path: str, single: bool) -> int:
    """List TData candidates without converting."""
    input_dir = Path(input_path).resolve()

    if single:
        logger.info("[dry-run] Would convert single TData: {}", input_dir)
        return 0

    if not input_dir.is_dir():
        logger.error("Not a directory: {}", input_dir)
        return 1

    from core.tdata_converter import _looks_like_tdata

    candidates = []
    for entry in sorted(input_dir.iterdir()):
        if not entry.is_dir():
            continue
        if _looks_like_tdata(entry):
            candidates.append(entry)
        elif (entry / "tdata").is_dir() and _looks_like_tdata(entry / "tdata"):
            candidates.append(entry)

    if not candidates:
        logger.warning("No TData folders found in {}", input_dir)
        return 0

    logger.info("[dry-run] Found {} TData candidate(s):", len(candidates))
    for c in candidates:
        logger.info("  → {}", c)
    return 0


# ── Convert mode ────────────────────────────────────────────────────────────

async def _run_convert(input_path: str, output: str, profiles: str, single: bool) -> int:
    """Perform the actual conversion. Returns exit code."""
    converter = TDataConverter(output_dir=output, profiles_path=profiles)

    if single:
        result = await converter.convert_single(input_path)
        if result.success:
            logger.info("Session: {}", result.session_path)
            return 0
        logger.error("Conversion failed: {}", result.error)
        return 1

    batch = await converter.convert_batch(input_path)
    logger.info(batch.summary)
    return 1 if batch.failed and batch.converted == 0 else 0


# ── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    _setup_logger()
    args = _parse_args()

    if args.validate:
        sys.exit(_run_validate(args.validate))

    if args.dry_run:
        sys.exit(_run_dry_run(args.input, args.single))

    exit_code = asyncio.run(_run_convert(args.input, args.output, args.profiles, args.single))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
