"""Offline candidate frames, not automatic action recognition. Python 3.9+."""
import argparse
import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def run(args, timeout=120):
    result = subprocess.run(args, capture_output=True, timeout=timeout, check=False)
    if result.returncode:
        # Decoder messages can echo private paths or metadata; don't print them.
        raise ValueError(Path(args[0]).name + ' failed; verify local format and decoding support')
    return result.stdout


def executable(name):
    path = shutil.which(name)
    if not path:
        raise ValueError('Missing executable: ' + name)
    return path


def probe(video):
    video = Path(video).resolve(strict=True)
    if not video.is_file() or video.suffix.lower() not in {'.mp4', '.mov', '.mkv', '.webm', '.avi', '.m4v'}:
        raise ValueError('Use a local MP4/MOV/MKV/WebM/AVI/M4V file, not a URL or playlist')
    payload = json.loads(run([executable('ffprobe'), '-v', 'error', '-protocol_whitelist', 'file,pipe',
                              '-show_format', '-show_streams', '-of', 'json', str(video)], 60))
    streams = payload.get('streams', [])
    videos = [s for s in streams if s.get('codec_type') == 'video' and not s.get('disposition', {}).get('attached_pic')]
    if not videos:
        raise ValueError('No video stream')
    stream = videos[0]
    duration = float(stream.get('duration') or payload.get('format', {}).get('duration', 0))
    if not finite(duration) or duration <= 0:
        raise ValueError('No finite duration')
    return video, {'duration': duration, 'width': stream['width'], 'height': stream['height'],
                   'video_stream': stream['index'], 'has_audio': any(s.get('codec_type') == 'audio' for s in streams)}


def sample_times(duration, start=0, end=None, interval=3, max_frames=80, times=None):
    end = duration if end is None else end
    if not all(finite(v) for v in (duration, start, end, interval)) or not 0 <= start < end <= duration or interval <= 0:
        raise ValueError('Invalid sampling range or interval')
    if not isinstance(max_frames, int) or isinstance(max_frames, bool) or not 2 <= max_frames <= 500:
        raise ValueError('max_frames must be between 2 and 500')
    if times is not None:
        if not times or len(times) > max_frames or any(not finite(t) or not start <= t < end for t in times):
            raise ValueError('Explicit times out of range or above cap')
        return sorted(set(times)), False
    # Include a near-end sample; never silently truncate coverage at the cap.
    last = max(start, end - min(0.1, (end - start) / 2))
    count = int(math.ceil((last - start) / interval)) + 1
    if count > max_frames:
        return [start + (last - start) * i / (max_frames - 1) for i in range(max_frames)], True
    result = [start + i * interval for i in range(max(1, count)) if start + i * interval < last]
    return result + [last], False


def contact_sheets(output, frames):
    from PIL import Image, ImageDraw
    for offset in range(0, len(frames), 20):
        group = frames[offset:offset + 20]
        sheet = Image.new('RGB', (1200, math.ceil(len(group) / 4) * 200), 'white')
        draw = ImageDraw.Draw(sheet)
        for n, frame in enumerate(group):
            x, y = n % 4 * 300, n // 4 * 200
            with Image.open(output / frame['file']) as original:
                thumb = original.convert('RGB')
            thumb.thumbnail((288, 166))
            sheet.paste(thumb, (x + 6, y + 6))
            draw.text((x + 6, y + 175), f"{frame['id']}  t={frame['at']:.3f}s", fill='black')
        sheet.save(output / f'contact-{offset // 20 + 1:03}.jpg', quality=90)


def capture(video, output, start=0, end=None, interval=3, max_frames=80, times=None, audio=False):
    from PIL import Image
    video, info = probe(video)
    ffmpeg = executable('ffmpeg')
    chosen, adjusted = sample_times(info['duration'], start, end, interval, max_frames, times)
    source_hash = digest(video)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'frames').mkdir()
    frames = []
    for number, at in enumerate(chosen, 1):
        ident = f'f{number:04}'
        relative = 'frames/' + ident + '.png'
        target = output / relative
        run([ffmpeg, '-v', 'error', '-nostdin', '-n', '-protocol_whitelist', 'file,pipe',
             '-ss', f'{at:.6f}', '-i', str(video), '-map', f"0:{info['video_stream']}",
             '-frames:v', '1', '-an', '-sn', '-dn', '-update', '1', str(target)])
        if not target.is_file():
            raise ValueError('No frame at requested time; use an earlier timestamp')
        with Image.open(target) as im:
            width, height = im.size
        frames.append({'id': ident, 'at': at, 'file': relative, 'width': width, 'height': height, 'sha256': digest(target)})
    audio_file = None
    if audio and info['has_audio']:
        audio_file = 'audio.wav'
        run([ffmpeg, '-v', 'error', '-nostdin', '-n', '-protocol_whitelist', 'file,pipe',
             '-ss', str(start), '-i', str(video), '-t', str((end or info['duration']) - start),
             '-map', '0:a:0', '-vn', '-sn', '-dn', '-ac', '1', '-ar', '16000', str(output / audio_file)], 300)
    if digest(video) != source_hash:
        raise ValueError('Video changed during extraction; do not use these frames')
    index = {'schema': 'screen-frames/1', 'source': {'name': video.name, 'sha256': source_hash, **info},
             'sampling': {'start': start, 'end': end or info['duration'], 'requested_interval': interval,
                          'cap_adjusted': adjusted, 'explicit_times': times is not None,
                          'time_basis': 'requested seek seconds relative to playback start, not click timestamps'},
             'audio': {'requested': audio, 'file': audio_file, 'offset_seconds': start}, 'frames': frames}
    contact_sheets(output, frames)
    (output / 'index.json').write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'frames': len(frames), 'cap_adjusted': adjusted, 'has_audio': info['has_audio'], 'audio_extracted': audio_file is not None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--start', type=float, default=0)
    parser.add_argument('--end', type=float)
    parser.add_argument('--interval', type=float, default=3)
    parser.add_argument('--max-frames', type=int, default=80)
    parser.add_argument('--times', help='Comma-separated seconds within the selected range')
    parser.add_argument('--audio', action='store_true')
    args = parser.parse_args()
    try:
        times = [float(x) for x in args.times.split(',')] if args.times else None
        result = capture(args.video, args.output, args.start, args.end, args.interval, args.max_frames, times, args.audio)
        print(json.dumps({'ok': True, **result}, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, subprocess.TimeoutExpired, ImportError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
