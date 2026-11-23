"""Private worker media primitive. Callers supply trusted job-owned local paths."""
import hashlib
import json
import os
import subprocess
from pathlib import Path
from .srt_parser import DJISRTParser

class ExtractionError(RuntimeError):
    pass

def select_subtitle(probe):
    if not isinstance(probe, dict):
        raise ExtractionError('INVALID_PROBE')
    streams = probe.get('streams', [])
    if not isinstance(streams, list) or any(not isinstance(s, dict) for s in streams):
        raise ExtractionError('INVALID_PROBE')
    subtitles = [s for s in streams if s.get('codec_type') == 'subtitle']
    if not subtitles:
        raise ExtractionError('NO_SUBTITLE_STREAM')
    supported = [s for s in subtitles if s.get('codec_name') in {'mov_text', 'subrip', 'srt', 'text', 'ass', 'ssa', 'webvtt'}]
    if not supported:
        raise ExtractionError('UNSUPPORTED_STREAM')
    if len(supported) != 1:
        raise ExtractionError('TELEMETRY_AMBIGUOUS')
    index = supported[0].get('index')
    if type(index) is not int or index < 0:
        raise ExtractionError('INVALID_PROBE')
    return index

def extract_srt(video, output, *, ffmpeg='ffmpeg', ffprobe='ffprobe', timeout=60, max_bytes=10*1024*1024):
    """Extract one text stream; reject overwrites and return validated provenance.

    max_bytes is an output validation limit, not an OS disk quota. The worker
    must also enforce its job-volume quota before invoking this primitive.
    """
    video, output = Path(video), Path(output)
    if not video.is_file():
        raise FileNotFoundError(video)
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    if timeout <= 0 or max_bytes <= 0:
        raise ValueError('Positive extraction limits required')
    temporary = output.with_name(output.name + '.extracting')
    # Exclusive ownership prevents one attempt deleting another attempt's file.
    with temporary.open('xb'):
        pass
    try:
        try:
            probe = subprocess.run([str(ffprobe), '-v', 'error', '-show_entries',
                                    'stream=index,codec_type,codec_name', '-of', 'json', str(video)],
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True, timeout=timeout)
            index = select_subtitle(json.loads(probe.stdout))
            subprocess.run([str(ffmpeg), '-hide_banner', '-loglevel', 'error', '-y', '-i', str(video),
                            '-map', f'0:{index}', '-c:s', 'srt', '-f', 'srt', str(temporary)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise ExtractionError('EXTRACTION_TIMEOUT') from None
        except (subprocess.CalledProcessError, OSError, ValueError):
            raise ExtractionError('EXTRACTION_FAILED') from None
        if temporary.stat().st_size > max_bytes:
            raise ExtractionError('OUTPUT_TOO_LARGE')
        try:
            # The shared parser tolerates decoding errors; extracted evidence must not.
            payload = temporary.read_bytes()
            payload.decode('utf-8', errors='strict')
            rows = DJISRTParser().parse_file(temporary)
        except (ValueError, UnicodeError):
            raise ExtractionError('INVALID_TELEMETRY') from None
        if not rows or not any(r.latitude is not None and r.longitude is not None for r in rows):
            raise ExtractionError('INVALID_TELEMETRY')
        # Hard-link publication is atomic and refuses to overwrite an existing artifact.
        os.link(temporary, output)
        return {'status':'EXTRACTED_VALID', 'stream_index':index, 'cue_count':len(rows),
                'gps_cue_count':sum(r.latitude is not None and r.longitude is not None for r in rows),
                'srt_sha256':hashlib.sha256(payload).hexdigest()}
    finally:
        temporary.unlink(missing_ok=True)
