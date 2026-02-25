# Flacsplit splits FLAC and WAVE files based on a cuesheet.

## Features:
  - Add a 'REM OFFSET <N>' line to a cuesheet to add <N> to all track numbers
   for file naming and tagging purposes. For multi-disk albums.
  - Cuesheets can be UTF-8 or ISO8859-1.
  - Pathnames are sanitized to alphanumeric characters and spaces only. Accents
   are stripped for everything up to and including Latin Extended-A, and ß,
   [Ðð], [Þþ], [Ææ], [Œœ], are translated to ss, Dh/dh, Th/th, Ae/ae, Oe/oe.
   All other characters stripped.
     - This caused a problem with Sigur Ros' album '( )' on FAT32 since it
     sanitizes to just ' '.  I have no better solution than hard-coding that
     case.
  - FLAC files always encoded with --best.
  - Writes Replaygain. Does not produce consistent results for multi-disk
   albums, but it's close enough.
  - Support sample rate up to 192kHz.
  - Support downsampling. If chosen sample rate is higher than source, option will be ignored. 


**Build dependencies:** cmake, flex, yacc, flac, libsndfile, libid3tag, boost, icu, lame, libogg, libvorbis, mpg123, opus.

**Helper scripts:** `cue_splitter.py` is a Python script that takes directory, scans for cuesheets, and runs flacsplit on them. It preserves state in a `cue_splitter.json` files already processed won't be processed again.

Usage:
    python cue_splitter.py <basedir> <outdir> [--resample <rate | default(48000)>] [--dry-run] [--force]

Example:
    python cue_splitter.py ~/Music/downloads ~/Music/library
