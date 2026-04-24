import os
import logging
from unmanic.libs.unplugins.settings import PluginSettings

logger = logging.getLogger("Unmanic.Plugin.add_eac3_track")

PROBLEMATIC_CODECS = ["truehd", "dts", "pcm_s16le", "pcm_s24le", "pcm_bluray", "pcm_dvd", "flac"]


class Settings(PluginSettings):
    settings = {
        "bitrate": "768k",
        "preferred_language": "ger",
    }


def get_problematic_audio_streams(probe_streams):
    """Liefert Liste der Audio-Streams, die konvertiert werden mÃ¼ssen."""
    problematic = []
    for stream in probe_streams:
        if stream.get("codec_type") != "audio":
            continue
        codec = stream.get("codec_name", "").lower()
        profile = stream.get("profile", "").lower()
        # DTS-HD MA und DTS:X haben codec_name "dts", unterscheiden sich per profile
        if codec in PROBLEMATIC_CODECS:
            problematic.append(stream)
    return problematic


def already_has_matching_eac3(probe_streams, problematic_streams):
    """PrÃ¼ft, ob fÃ¼r jede problematische Sprache schon eine E-AC3 existiert."""
    existing_eac3_langs = set()
    for s in probe_streams:
        if s.get("codec_type") == "audio" and s.get("codec_name", "").lower() == "eac3":
            lang = s.get("tags", {}).get("language", "und")
            existing_eac3_langs.add(lang)

    needed_langs = set()
    for s in problematic_streams:
        lang = s.get("tags", {}).get("language", "und")
        needed_langs.add(lang)

    return needed_langs.issubset(existing_eac3_langs)


def on_library_management_file_test(data):
    """Entscheidet, ob Datei verarbeitet werden muss."""
    abspath = data.get("path")
    probe_streams = data.get("shared_info", {}).get("ffprobe", {}).get("streams", [])

    if not probe_streams:
        # Kein Probe-Info â†’ Unmanic soll selbst probieren
        data["add_file_to_pending_tasks"] = False
        return data

    problematic = get_problematic_audio_streams(probe_streams)
    if not problematic:
        logger.info(f"{abspath}: Keine problematischen Audio-Codecs gefunden.")
        data["add_file_to_pending_tasks"] = False
        return data

    if already_has_matching_eac3(probe_streams, problematic):
        logger.info(f"{abspath}: E-AC3-Spuren fÃ¼r alle Sprachen bereits vorhanden.")
        data["add_file_to_pending_tasks"] = False
        return data

    logger.info(f"{abspath}: {len(problematic)} problematische Audio-Spur(en) gefunden.")
    data["add_file_to_pending_tasks"] = True
    return data


def on_worker_process(data):
    """Baut den FFmpeg-Befehl."""
    settings = Settings(library_id=data.get("library_id"))
    bitrate = settings.get_setting("bitrate")
    pref_lang = settings.get_setting("preferred_language")

    probe_streams = data.get("shared_info", {}).get("ffprobe", {}).get("streams", [])
    if not probe_streams:
        return data

    problematic = get_problematic_audio_streams(probe_streams)
    if not problematic:
        return data

    # PrÃ¼fen welche Sprachen schon eine E-AC3-Spur haben â†’ die skippen wir
    existing_eac3_langs = set()
    for s in probe_streams:
        if s.get("codec_type") == "audio" and s.get("codec_name", "").lower() == "eac3":
            existing_eac3_langs.add(s.get("tags", {}).get("language", "und"))

    # Input / Output
    input_file = data.get("file_in")
    output_file = data.get("file_out")

    cmd = ["-hide_banner", "-loglevel", "info", "-i", input_file, "-map", "0"]

    # Neue E-AC3-Spuren pro problematischer Sprache (eine pro Sprache)
    seen_langs = set()
    new_streams = []  # (original_stream_index, language)
    for s in problematic:
        lang = s.get("tags", {}).get("language", "und")
        if lang in existing_eac3_langs or lang in seen_langs:
            continue
        seen_langs.add(lang)
        # Audio-Index innerhalb der Audio-Streams finden
        audio_streams = [x for x in probe_streams if x.get("codec_type") == "audio"]
        try:
            audio_idx = audio_streams.index(s)
        except ValueError:
            continue
        new_streams.append((audio_idx, lang))
        cmd += ["-map", f"0:a:{audio_idx}"]

    # Alle Original-Streams kopieren
    cmd += ["-c", "copy"]

    # ZÃ¤hle Original-Audio-Streams, um Index der neuen Spuren zu bestimmen
    orig_audio_count = len([x for x in probe_streams if x.get("codec_type") == "audio"])

    # Kodierung der neu gemappten Spuren
    default_target_idx = None
    for i, (audio_idx, lang) in enumerate(new_streams):
        new_audio_output_idx = orig_audio_count + i
        cmd += [
            f"-c:a:{new_audio_output_idx}", "eac3",
            f"-b:a:{new_audio_output_idx}", bitrate,
            f"-ac:a:{new_audio_output_idx}", "6",
            f"-metadata:s:a:{new_audio_output_idx}", f"language={lang}",
            f"-metadata:s:a:{new_audio_output_idx}", f"title=E-AC3 5.1 {bitrate} ({lang})",
        ]
        if lang == pref_lang and default_target_idx is None:
            default_target_idx = new_audio_output_idx

    # Falls keine bevorzugte Sprache gefunden â†’ erste neue Spur wird Default
    if default_target_idx is None and new_streams:
        default_target_idx = orig_audio_count

    # Disposition: alle Audio-Spuren auf 0 setzen, dann Default-Spur markieren
    total_audio = orig_audio_count + len(new_streams)
    for i in range(total_audio):
        if i == default_target_idx:
            cmd += [f"-disposition:a:{i}", "default"]
        else:
            cmd += [f"-disposition:a:{i}", "0"]

    cmd += ["-y", output_file]

    data["exec_command"] = ["ffmpeg"] + cmd
    data["repeat"] = False
    logger.info(f"FFmpeg-Befehl: {' '.join(data['exec_command'])}")
    return data
