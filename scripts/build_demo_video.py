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
    ('01_dataset.jpg', 14, 'From raw reviews\nto product action',
     '13,034 reviews in the 12-week window.\nOriginal IDs, dates and URLs retained.\nSaved analysis: 16 October 2026.'),
    ('02_themes.jpg', 16, 'The top themes,\nranked by review count',
     'Support and account operations: 550\nApp stability and UI: 470\nMissing features: 457\nGeneral praise stays in overall sentiment.'),
    ('03_fee_evidence.jpg', 16, 'One fee issue,\nbacked by reviews',
     'Brokerage confusion appears in\nfive distinct original review texts.\nReviewers compare per-order brokerage\nwith larger statement deductions.\nThese are customer reports.'),
    ('04_weekly_pulse.jpg', 18, '149 words.\nThree product actions.',
     'Top themes + three verbatim quotes.\nOne observation + exactly three actions.\nThe pulse is linked to its Phase 2 run.\nEdits must pass the same checks.'),
    ('05_fee_explainer.jpg', 18, 'Explain the fee\nusing official sources.',
     'Four neutral bullets address brokerage.\nTwo official Groww pages support facts.\nOrder types and exceptions stay distinct.\nLast checked: 16 October 2026.'),
    ('06_email_preview.jpg', 14, 'One reusable\nsupport message.',
     'The email combines the weekly pulse\nand the complete brokerage snippet.\nThe subject includes product and date.\nThis is a preview; Gmail is pending.'),
    ('07_approval.jpg', 16, 'Approve the exact\nsnapshot before saving.',
     'Reject leaves both actions unstarted.\nApproval is bound to the content hash.\nMCP supports Doc append + draft create.\nUncertain outcomes need reconciliation.\nLive destinations are not connected yet.'),
    ('07_approval.jpg', 12, 'Ready to review.\nConnect accounts later.',
     'Packet: outputs, sample, sources,\nworkflow imports, guides and source ZIP.\nGitHub, hosted link and live evidence\nwill follow account connection.'),
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
        (work / 'footer.txt').write_text('Saved analysis | Account links and live evidence pending', encoding='utf-8', newline='\n')
        filters = (f'[0:v]scale=760:930:force_original_aspect_ratio=decrease,pad=760:930:(ow-iw)/2:(oh-ih)/2:color=white[screen];'
                   f'color=c=0x102d26:s=1920x1080:r=24:d={seconds}[bg];[bg][screen]overlay=1110:75,'
                   'drawtext=fontfile=font.ttf:textfile=brand.txt:fontsize=22:fontcolor=0x8bd6b5:x=70:y=78,'
                   'drawtext=fontfile=font.ttf:textfile=step.txt:fontsize=21:fontcolor=0xb2c8bc:x=70:y=239,'
                   'drawtext=fontfile=font.ttf:textfile=title.txt:fontsize=57:fontcolor=white:line_spacing=16:x=70:y=296,'
                   'drawtext=fontfile=font.ttf:textfile=body.txt:fontsize=32:fontcolor=0xe0ece5:line_spacing=14:x=70:y=487,'
                   'drawtext=fontfile=font.ttf:textfile=footer.txt:fontsize=22:fontcolor=0xf0c87f:x=70:y=868')
        for marker in range(len(SCENES)):
            color = '0x8bd6b5' if marker < index else '0x355047'
            filters += f',drawbox=x={70 + 112 * marker}:y=974:w=94:h=6:color={color}:t=fill'
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
    story = '# Captioned local workflow walkthrough\n\nThis video uses actual app screenshots with captions. It is a screen walkthrough, not a continuous recording of live model calls or remote writes. Account links and actual Google evidence remain pending.\n\n'
    for scene in timeline:
        story += f"## {scene['start_seconds']}s — {scene['title'].replace(chr(10), ' ')}\n\n{scene['caption']}\n\n"
    (out / 'STORYBOARD.md').write_text(story, encoding='utf-8')
    print(f'PASS: {duration:g}-second 1080p walkthrough; complete video decoded successfully.')


if __name__ == '__main__':
    main()
