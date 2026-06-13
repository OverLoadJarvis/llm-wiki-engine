#!/usr/bin/env python3
"""
Convert all files in a directory to Markdown format.

Usage:
    python tools/file_to_md.py --input_dir raw/documents
    python tools/file_to_md.py --input_dir raw/documents --output_dir wiki/sources
    python tools/file_to_md.py --input_dir raw/documents --delete_source

Features:
    - Recursively processes all files in subdirectories
    - Preserves directory structure relative to input_dir
    - Skips hidden files and existing .md files
    - Optional: delete source files after conversion
"""

import argparse
from tqdm import tqdm
from pathlib import Path
from markitdown import MarkItDown
from tools.logger import get_logger, setup_logging

logger = get_logger(__name__)


def convert_directory_to_md(
    input_dir: Path,
    output_dir: Path | None = None,
    delete_source: bool = False
):
    """
    Converts all files in a directory to Markdown format.
    
    :param input_dir: The Path object pointing to the directory to process.
    :param output_dir: Optional. Target directory for converted files.
                       If None, files are saved alongside originals.
                       Directory structure is preserved relative to input_dir.
    :param delete_source: Whether to delete the original source files. Defaults to False.
    """
    md = MarkItDown(enable_plugins=False)

    # get list of files to convert
    files_to_process = [f for f in input_dir.rglob('*') if f.is_file()]

    if not files_to_process:
        logger.error("No files found in %s!", input_dir)
        return

    # Track statistics
    stats = {"converted": 0, "skipped": 0, "failed": 0}

    for file_path in tqdm(files_to_process, desc="Converting Files"):
        # skip hidden files and existing markdown files
        if file_path.name.startswith('.') or file_path.suffix.lower() == '.md':
            tqdm.write(f"Skipping: {file_path.name}")
            stats["skipped"] += 1
            continue

        # Determine output path
        if output_dir is None:
            # Save alongside original file
            output_path = file_path.with_suffix(".md")
        else:
            # Preserve directory structure relative to input_dir
            relative_path = file_path.relative_to(input_dir)
            output_path = output_dir / relative_path.with_suffix(".md")

        try:
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # convert
            result = md.convert(str(file_path))
            # save to .md
            output_path.write_text(result.text_content, encoding="utf-8")
            # optional remove original file
            if delete_source:
                file_path.unlink()
            
            stats["converted"] += 1
            if output_dir is None:
                tqdm.write(f"Converted: {file_path.name} → {output_path.name}")
            else:
                tqdm.write(f"Converted: {file_path.relative_to(input_dir)} → {output_path.relative_to(output_dir)}")
        except Exception as e:
            stats["failed"] += 1
            logger.error("FAILED: Could not convert '%s'. Reason: %s", file_path.name, e)

    # Print summary
    logger.info("\n%s", "=" * 60)
    logger.info("Conversion Summary:")
    logger.info("  ✓ Converted: %d files", stats['converted'])
    logger.info("  ⊘ Skipped:   %d files", stats['skipped'])
    logger.info("  ✗ Failed:    %d files", stats['failed'])
    if output_dir:
        logger.info("\nOutput directory: %s", output_dir)
    logger.info("%s", "=" * 60)


def main(args):
    setup_logging(level="INFO")

    # set Paths
    input_path = Path(args.input_dir).resolve()
    
    if args.output_dir:
        output_path = Path(args.output_dir).resolve()
    else:
        output_path = None

    logger.info("-" * 60)
    logger.info("Input Directory:  %s", input_path)
    logger.info("Output Directory: %s", output_path if output_path else "(same as input)")
    logger.info("Delete Source:    %s", args.delete_source)
    logger.info("-" * 60)

    # validate input directory
    if not input_path.exists():
        logger.error("\nError: Input directory not found at %s", input_path)
        return

    if not input_path.is_dir():
        logger.error("\nError: Input path is not a directory: %s", input_path)
        return

    # execute
    try:
        convert_directory_to_md(input_path, output_path, args.delete_source)
        logger.info("\nConversion process complete.")
    except Exception as e:
        logger.error("\nAn unexpected error occurred during execution: %s", e)
        raise


if __name__ == "__main__":
    """Command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Convert all files in a directory to Markdown and delete originals.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert files, save alongside originals
  python tools/file_to_md.py --input_dir raw/documents

  # Convert files to a specific output directory (preserves structure)
  python tools/file_to_md.py --input_dir raw/documents --output_dir wiki/sources

  # Convert and delete original files
  python tools/file_to_md.py --input_dir raw/documents --delete_source
        """
    )
    parser.add_argument(
        "--input_dir",
        type=str,
        required=True,
        help="The path to the directory containing files to convert."
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default=None,
        help="Optional. Target directory for converted files. "
             "Directory structure will be preserved relative to input_dir. "
             "If not specified, files are saved alongside originals."
    )
    parser.add_argument(
        "--delete_source",
        action="store_true",
        help="Whether to delete the original source files after conversion."
    )
    args = parser.parse_args()

    main(args)
