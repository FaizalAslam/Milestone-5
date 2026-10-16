"""Encode a captioned walkthrough of actual CUA-captured app screens; no remote actions."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SCENES = [
    ('01_upload_new.png',14,'Upload one CSV. Analysis starts automatically.',
     'Choose an 8–12 week period. Validation preserves the original CSV.\nThe app prepares insights and both outputs before any external action.'),
    ('02_themes_new.png',16,'Five ranked themes, with the top three highlighted.',
     'Original completed example: 13,034 valid reviews; 2,001 useful; 11,033 nonspecific.\nTop themes: support 550, app experience 470, missing features 457.'),
    ('03_evidence_new.png',16,'A specific fee issue supported by real reviews.',
     'Five distinct original review texts support recurring brokerage confusion.\nCustomer reports and official fee facts are shown separately.'),
    ('04_pulse_new.png',18,'Weekly product pulse: 149 words and three actions.',
     'The original example includes three exact customer quotes and a key observation.\nPulse edits must retain evidence and pass the same output checks.'),
    ('05_fee_new.png',18,'Explain the fee using official sources.',
     'Four neutral bullets, two official Groww links, and Last checked: 2026-10-16.\nThe explanation directly addresses the identified brokerage confusion.'),
    ('06_email_new.png',14,'A reusable support message, ready for review.',
     'The email preview combines the weekly pulse and full fee explanation.\nThe recipient is blank. The workflow never sends an email.'),
    ('07_approval_new.png',16,'Approve the current outputs before saving.',
     'Live 53-review sample: the approval panel shows both destinations.\nOnly explicit approval can append to Google Docs and create an unsent draft.'),
    ('08_audit_new.png',12,'Inspect data quality and original evidence.',
     'The original example has 234 out-of-window rows; generic reviews are separate.\nSearch, inspect and download exclusions without rerunning analysis.'),
]


def main():
    try:
        import imageio_ffmpeg
    except ImportError:
        raise SystemExit('Install requirements-demo.txt to rebuild the walkthrough.')
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    out = ROOT / 'outputs/demo'
    work = ROOT / '.cache/demo_build'
    work.mkdir(parents=True, exist_ok=True)
    candidates = [Path('C:/Windows/Fonts/arial.ttf'), Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
    font = next((p for p in candidates if p.exists()), None)
    if not font:
        raise SystemExit('A readable Arial or DejaVu Sans font is required for captions.')
    shutil.copyfile(font, work / 'font.ttf')
    clips, timeline = [], []
    start = 0
    for index, (frame, seconds, title, body) in enumerate(SCENES, 1):
        image = out / 'frames' / frame
        if not image.is_file():
            raise SystemExit(f'Capture the actual app screen first: {frame}')
        # FFmpeg treats CR and LF separately; use LF captions on Windows as well.
        (work / 'title.txt').write_text(title, encoding='utf-8', newline='\n')
        (work / 'body.txt').write_text(body, encoding='utf-8', newline='\n')
        (work / 'brand.txt').write_text('GROWW / REVIEW INTELLIGENCE', encoding='utf-8', newline='\n')
        (work / 'step.txt').write_text(f'{index:02d} / {len(SCENES):02d}   LOCAL WORKFLOW WALKTHROUGH', encoding='utf-8', newline='\n')
        (work / 'footer.txt').write_text('Updated wireframe UI | Original review evidence | No auto-send', encoding='utf-8', newline='\n')
        filters = (f'[0:v]scale=1792:770:force_original_aspect_ratio=decrease,pad=1792:770:(ow-iw)/2:(oh-ih)/2:color=white[screen];'
                   f'color=c=0x102d26:s=1920x1080:r=24:d={seconds}[bg];[bg][screen]overlay=64:90,'
                   'drawtext=fontfile=font.ttf:textfile=brand.txt:fontsize=22:fontcolor=0x8bd6b5:x=64:y=25,'
                   'drawtext=fontfile=font.ttf:textfile=step.txt:fontsize=18:fontcolor=0xb2c8bc:x=1200:y=30,'
                   'drawtext=fontfile=font.ttf:textfile=title.txt:fontsize=34:fontcolor=white:x=64:y=895,'
                   'drawtext=fontfile=font.ttf:textfile=body.txt:fontsize=23:fontcolor=0xe0ece5:line_spacing=9:x=64:y=950')
        for marker in range(len(SCENES)):
            color = '0x8bd6b5' if marker < index else '0x355047'
            filters += f',drawbox=x={64 + 224 * marker}:y=1053:w=204:h=5:color={color}:t=fill'
        clip = work / f'scene_{index:02d}.mp4'
        result = subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-loop', '1', '-framerate', '24',
                                 '-i', str(image), '-filter_complex', filters, '-t', str(seconds), '-an',
                                 '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', '-pix_fmt', 'yuv420p',
                                 str(clip)], cwd=work, capture_output=True, text=True)
        if result.returncode:
            raise SystemExit(result.stderr[-2500:])
        clips.append(clip)
        timeline.append(dict(start_seconds=start, duration_seconds=seconds, screenshot=frame, title=title, caption=body,
                             screenshot_sha256=hashlib.sha256(image.read_bytes()).hexdigest()))
        start += seconds
        print(f'Encoded scene {index}/{len(SCENES)}', flush=True)
    (work / 'concat.txt').write_text(''.join(f"file '{p.name}'\n" for p in clips), encoding='utf-8')
    video = out / 'groww_workflow_demo.mp4'
    subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', 'concat.txt',
                    '-c', 'copy', '-movflags', '+faststart', str(video)], cwd=work, check=True)
    decoded = subprocess.run([ffmpeg, '-hide_banner', '-i', str(video), '-f', 'null', '-'], capture_output=True, text=True)
    if decoded.returncode:
        raise SystemExit('The complete video failed decoding: ' + decoded.stderr[-1000:])
    match = re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)', decoded.stderr)
    if not match:
        raise SystemExit('Could not verify the encoded video duration.')
    duration = int(match[1]) * 3600 + int(match[2]) * 60 + float(match[3])
    if not 0 < duration <= 180:
        raise SystemExit('The video must be no longer than three minutes.')
    subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-ss', '2', '-i', str(video),
                    '-frames:v', '1', '-q:v', '3', str(out / 'poster.jpg')], check=True)
    metadata = dict(kind='captioned_screenshot_walkthrough', created_at=datetime.now(timezone.utc).isoformat(),
                    duration_seconds=duration, width=1920, height=1080, fps=24, full_decode_passed=True,
                    audio=False, remote_actions_performed=False, screenshots_are_actual_app=True,
                    sha256=hashlib.sha256(video.read_bytes()).hexdigest(),
                    poster_sha256=hashlib.sha256((out / 'poster.jpg').read_bytes()).hexdigest(), scenes=timeline)
    (out / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    story = '# Captioned local workflow walkthrough\n\nThis video uses actual app screenshots with captions. It is a screen walkthrough, not a continuous recording of live model calls or remote writes. The screenshots show the updated wireframe UI; the original example and the separate live sample approval panel are labelled. The video does not record a new external write.\n\n'
    for scene in timeline:
        story += f"## {scene['start_seconds']}s — {scene['title'].replace(chr(10), ' ')}\n\n{scene['caption']}\n\n"
    (out / 'STORYBOARD.md').write_text(story, encoding='utf-8')
    print(f'PASS: {duration:g}-second 1080p walkthrough; complete video decoded successfully.')


if __name__ == '__main__':
    main()
