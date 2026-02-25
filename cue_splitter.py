#!/usr/bin/env python3
"""
CUE Splitter - Split single-file CUE+audio using flacsplit.

Usage:
    python cue_splitter.py <basedir> <outdir> [options]

Example:
    python cue_splitter.py ~/Music/downloads ~/Music/library
"""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, List, Tuple


# Regex patterns
FILE_RE = re.compile(r'^\s*FILE\s+"([^"]+)"\s+(\S+)\s*$', re.IGNORECASE)
TRACK_RE = re.compile(r'^\s*TRACK\s+\d+\s+AUDIO\s*$', re.IGNORECASE)
PERFORMER_RE = re.compile(r'^\s*PERFORMER\s+"([^"]+)"\s*$', re.IGNORECASE)
TITLE_RE = re.compile(r'^\s*TITLE\s+"([^"]+)"\s*$', re.IGNORECASE)

# Audio file extensions
AUDIO_EXTS = {".flac", ".wav"}

# Transliteration map to match flacsplit sanitize() behavior.
LATIN_MAP = [
    # latin-1
    "A", "A", "A", "A", "A", "A",
    "AE",
    "C",
    "E", "E", "E", "E",
    "I", "I", "I", "I",
    "DH",
    "N",
    "O", "O", "O", "O", "O",
    None,
    "O",
    "U", "U", "U", "U",
    "Y",
    "th",
    "ss",
    "a", "a", "a", "a", "a", "a",
    "ae",
    "c",
    "e", "e", "e", "e",
    "i", "i", "i", "i",
    "dh",
    "n",
    "o", "o", "o", "o", "o",
    None,
    "o",
    "u", "u", "u", "u",
    "y",
    "th",
    "y",
    # latin extended-A
    "A", "a", "A", "a", "A", "a",
    "C", "c", "C", "c", "C", "c", "C", "c",
    "D", "d", "D", "d",
    "E", "e", "E", "e", "E", "e", "E", "e", "E", "e",
    "G", "g", "G", "g", "G", "g", "G", "g",
    "H", "h", "H", "h",
    "I", "i", "I", "i", "I", "i", "I", "i", "I", "i",
    "IJ", "ij",
    "J", "j",
    "K", "k", "k",
    "L", "l", "L", "l", "L", "l", "L", "l", "L", "l",
    "N", "n", "N", "n", "N", "n", "n", "N", "n",
    "O", "o", "O", "o", "O", "o",
    "OE", "oe",
    "R", "r", "R", "r", "R", "r",
    "S", "s", "S", "s", "S", "s", "S", "s",
    "T", "t", "T", "t", "T", "t",
    "U", "u", "U", "u", "U", "u", "U", "u", "U", "u", "U", "u",
    "W", "w",
    "Y", "y", "Y",
    "Z", "z", "Z", "z", "Z", "z",
    "s",
]
LATIN_MAP_BEGIN = 0xC0
LATIN_MAP_END = LATIN_MAP_BEGIN + len(LATIN_MAP)


def read_text_guessing(path: Path) -> str:
    """Try common encodings for CUE files to handle various encodings."""
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-16", "utf-16le", "utf-16be", "cp1251", "latin-1"):
        try:
            text = raw.decode(enc, errors="strict")
            if "\uFFFD" not in text:  # No replacement characters
                return text
        except UnicodeDecodeError:
            continue
    # Fallback: decode with replacement
    return raw.decode("utf-8", errors="replace")


def parse_cue_files(cue: Path) -> List[Path]:
    """
    Parse CUE file and return list of referenced audio files.
    Resolves relative paths relative to CUE directory.
    """
    try:
        text = read_text_guessing(cue).splitlines()
    except Exception:
        return []

    refs = []
    seen = set()
    
    for line in text:
        match = FILE_RE.match(line)
        if not match:
            continue
        
        fname = match.group(1).strip()
        ref = Path(fname)
        
        # Resolve relative paths
        if not ref.is_absolute():
            ref = (cue.parent / ref).resolve()
        
        # Deduplicate
        ref_str = str(ref)
        if ref_str not in seen:
            seen.add(ref_str)
            refs.append(ref)
    
    return refs


def sanitize_name(value: str) -> str:
    """Transliterate a Latin-based UTF-8 string to ASCII like flacsplit."""
    if value == "( )":
        return "Untitled"

    result_chars = []
    guessed_indexes = []

    for ch in value:
        code = ord(ch)
        if ("0" <= ch <= "9") or ch == " " or ("A" <= ch <= "Z") or ("a" <= ch <= "z"):
            result_chars.append(ch)
        elif ch == "\t":
            result_chars.append(" ")
        elif LATIN_MAP_BEGIN <= code < LATIN_MAP_END:
            mapped = LATIN_MAP[code - LATIN_MAP_BEGIN]
            if mapped:
                result_chars.extend(mapped)
                if len(mapped) >= 2 and mapped[1].isupper():
                    guessed_indexes.append(len(result_chars) - 1)
        # Ignore all other characters.

    for idx in guessed_indexes:
        if idx != len(result_chars) - 1 and not result_chars[idx + 1].isupper():
            result_chars[idx] = result_chars[idx].lower()

    return "".join(result_chars)


def parse_cue_artist_album(cue: Path) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract album-level PERFORMER and TITLE from CUE before TRACK section.
    Returns (artist, album) or (None, None) when not found.
    """
    try:
        lines = read_text_guessing(cue).splitlines()
    except Exception:
        return None, None

    artist = None
    album = None

    for line in lines:
        if TRACK_RE.match(line):
            break
        if artist is None:
            m = PERFORMER_RE.match(line)
            if m:
                artist = m.group(1).strip()
                continue
        if album is None:
            m = TITLE_RE.match(line)
            if m:
                album = m.group(1).strip()
                continue

    return artist, album


def candidate_artist_album(artist: str, album: str) -> List[Tuple[str, str]]:
    """Return candidate (artist, album) pairs to match output directories."""
    sanitized_artist = sanitize_name(artist)
    sanitized_album = sanitize_name(album) if album else "no album"
    return [(sanitized_artist, sanitized_album)]


def count_cue_tracks(cue: Path) -> int:
    """Count number of TRACK entries in CUE file."""
    try:
        text = read_text_guessing(cue).splitlines()
    except Exception:
        return 0
    
    return sum(1 for line in text if TRACK_RE.match(line))


def count_audio_files(directory: Path) -> int:
    """Count audio files in a directory."""
    if not directory.exists():
        return 0
    
    try:
        return sum(
            1 for p in directory.iterdir()
            if p.is_file() and p.suffix.lower() in AUDIO_EXTS
        )
    except Exception:
        return 0


def find_audio_file(refs: List[Path]) -> Optional[Path]:
    """Return referenced audio file if it exists."""
    if refs and refs[0].exists():
        return refs[0]
    return None


def output_release_dir(cue: Path, basedir: Path, outdir: Path) -> Path:
    """
    Determine output directory as {outdir}/{artist}/{album}.
    Falls back to {outdir}/{relative_parent} when metadata is missing.
    """
    artist, album = parse_cue_artist_album(cue)
    if artist is not None or album is not None:
        artist_value = artist or ""
        album_value = album or ""
        for cand_artist, cand_album in candidate_artist_album(artist_value, album_value):
            cand_dir = outdir / cand_artist / cand_album
            if cand_dir.exists():
                return cand_dir
        sanitized_artist = sanitize_name(artist_value)
        sanitized_album = sanitize_name(album_value) if album_value else "no album"
        return outdir / sanitized_artist / sanitized_album

    try:
        rel_parent = cue.parent.relative_to(basedir)
        return outdir / rel_parent
    except ValueError:
        pass

    return outdir / cue.parent.name


def run_flacsplit(cue: Path, out_root: Path, resample: int, dry_run: bool) -> None:
    """Execute flacsplit command to split audio file."""
    cmd = [
        "flacsplit",
        "-r", str(resample),
        "-O", str(out_root),
        str(cue),
    ]

    if dry_run:
        print(f"  [DRY RUN] Would run: {' '.join(cmd)}")
        return

    # Create output directory
    out_root.mkdir(parents=True, exist_ok=True)

    # Run flacsplit
    proc = subprocess.run(cmd, capture_output=True, text=True)

    if proc.returncode != 0:
        raise RuntimeError(
            f"flacsplit failed with code {proc.returncode}\n"
            f"STDOUT: {proc.stdout}\n"
            f"STDERR: {proc.stderr}"
        )


def ensure_tools() -> None:
    """Check that required tools (flacsplit) are available in PATH."""
    if shutil.which("flacsplit") is None:
        print("ERROR: Missing required tool: flacsplit", file=sys.stderr)
        sys.exit(2)


def should_process(cue: Path, out_dir: Path, force: bool) -> Tuple[bool, str]:
    """
    Determine if CUE file should be processed.
    Returns (should_process, reason).
    """
    # Check if CUE has multiple tracks
    track_count = count_cue_tracks(cue)
    if track_count <= 1:
        return False, "no tracks or only 1 track"
    
    # Check if it's single-file CUE
    refs = parse_cue_files(cue)
    if len(refs) == 0:
        return False, "no audio file referenced"
    elif len(refs) > 1:
        return False, "multi-file CUE (already split)"
    
    # Check if audio file exists
    audio = find_audio_file(refs)
    if not audio:
        return False, "audio file not found"
    
    # Check idempotency: compare track counts
    if not force:
        existing_count = count_audio_files(out_dir)
        if existing_count == track_count:
            return False, f"already processed ({existing_count}/{track_count} tracks)"
    
    return True, f"{track_count} tracks"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Split CUE+single audio files with flacsplit into {outdir}/{artist}/{album}.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ~/Music/downloads ~/Music/library
  %(prog)s ./input ./output --force
        """
    )
    parser.add_argument(
        "basedir",
        help="Base directory to scan for CUE files"
    )
    parser.add_argument(
        "outdir",
        help="Output directory root for flacsplit (-O)"
    )
    parser.add_argument(
        "--resample",
        type=int,
        default=48000,
        help="Resample to specified rate (default: 48000)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually splitting"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-splitting even if output exists"
    )
    
    args = parser.parse_args()
    
    # Resolve paths
    basedir = Path(args.basedir).expanduser().resolve()
    outdir = Path(args.outdir).expanduser().resolve()
    
    # Check required tools
    ensure_tools()
    
    # Validate basedir
    if not basedir.exists():
        print(f"ERROR: Base directory not found: {basedir}", file=sys.stderr)
        return 2
    
    if not basedir.is_dir():
        print(f"ERROR: Base directory is not a directory: {basedir}", file=sys.stderr)
        return 2
    
    # Find all CUE files
    print(f"Scanning {basedir} for CUE files...")
    cues = sorted(basedir.rglob("*.cue")) + sorted(basedir.rglob("*.CUE"))
    
    if not cues:
        print(f"No CUE files found in {basedir}")
        return 0
    
    print(f"Found {len(cues)} CUE file(s)\n")
    
    # Statistics
    stats = {"processed": 0, "skipped": 0, "failed": 0}
    
    # Process each CUE file
    for cue in cues:
        # Determine output directory as {outdir}/{artist}/{album}
        out_release_dir = output_release_dir(cue, basedir, outdir)

        # Get relative path for display
        try:
            rel_path = out_release_dir.relative_to(outdir)
        except ValueError:
            rel_path = out_release_dir.name
        
        # Check if should process
        should_proc, reason = should_process(cue, out_release_dir, args.force)
        
        if not should_proc:
            print(f"SKIP: {rel_path} - {reason}")
            stats["skipped"] += 1
            continue
        
        # Process
        print(f"SPLIT: {rel_path} - {reason}")
        try:
            run_flacsplit(cue, outdir, args.resample, args.dry_run)
            
            # Verify output
            if not args.dry_run:
                result_count = count_audio_files(out_release_dir)
                expected_count = count_cue_tracks(cue)
                if result_count < expected_count:
                    print(f"  WARNING: Expected {expected_count} tracks, got {result_count}")
                else:
                    print(f"  ✓ Created {result_count} tracks")
            
            stats["processed"] += 1
            
        except Exception as e:
            print(f"FAILED: {rel_path} - {e}", file=sys.stderr)
            stats["failed"] += 1
    
    # Summary
    print(f"\n{'='*60}")
    print(f"Summary: {stats['processed']} processed, {stats['skipped']} skipped, {stats['failed']} failed")
    
    if args.dry_run:
        print("\n(This was a dry run - no files were actually split)")
    
    return 1 if stats["failed"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
