# unmanic-plugins

Custom Unmanic plugins for my home media server setup.

## Plugins

### add_eac3_track

Adds an E-AC3 (Dolby Digital Plus) 768 kbps audio track to MKV files
containing audio codecs that are not compatible with Fire TV Stick 4K Max
and LG OLED TVs (BX / C9).

**Problematic codecs detected:** TrueHD, DTS, DTS-HD MA, DTS:X, PCM, FLAC

**Behavior:**
- Video stream is copied (no re-encode) — Dolby Vision is preserved
- All original audio tracks are kept
- One new E-AC3 5.1 @ 768 kbps track is added per problematic language
- The German E-AC3 track is set as default (if available),
  otherwise the first new E-AC3 track becomes default
- Subtitles and chapters remain untouched

**Why E-AC3?** It preserves Atmos metadata (unlike plain AC3) and is
natively supported by Fire TV and LG OLED TVs via eARC passthrough.

## Installation

In Unmanic: **Settings → Plugins → Add new repo** and paste this repo's URL.
