"""Build clearly labeled illustrated demo media from verified saved outputs.

No UI automation, account access, model calls or invented market data.
Requires Pillow and FFmpeg. Run from any directory using the project's venv.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/assets'
W, H = 1280, 800
BG, WHITE, INK, MUTED = '#F5F7FA', '#FFFFFF', '#192A35', '#637480'
TEAL, ORANGE, LINE = '#247B83', '#D65A31', '#E1E7EC'
STEPS = ['Overview', 'Skill growth', 'Ask + inspect SQL', 'Trace the source', 'Architecture']
FONT_DIR = Path('/usr/share/fonts/truetype/dejavu')


def font(size, bold=False, mono=False):
    name = 'DejaVuSansMono.ttf' if mono else 'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'
    path = FONT_DIR / name
    return ImageFont.truetype(str(path), size) if path.is_file() else ImageFont.load_default(size=size)


def text(draw, xy, value, size=24, fill=INK, bold=False, mono=False):
    draw.text(xy, str(value), font=font(size, bold, mono), fill=fill)


def box(draw, xy, fill=WHITE, outline=LINE, radius=18):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=1)


def base(index, title, subtitle, caption):
    image = Image.new('RGB', (W, H), BG)
    draw = ImageDraw.Draw(image)
    text(draw, (55, 30), 'HN / OBSERVATORY', 25, bold=True)
    box(draw, (788, 25, 1225, 67), fill='#E8EFF0', outline='#E8EFF0', radius=9)
    text(draw, (807, 36), 'ILLUSTRATED · VERIFIED SAVED OUTPUTS', 15, TEAL, True)
    draw.line((55, 91, 1225, 91), fill=LINE, width=2)
    text(draw, (55, 115), f'0{index+1}  /  {STEPS[index].upper()}', 17, ORANGE, True)
    text(draw, (55, 154), title, 37, bold=True)
    text(draw, (55, 211), subtitle, 20, MUTED)
    text(draw, (55, 685), caption, 18, MUTED)
    draw.line((55, 729, 1225, 729), fill=LINE, width=2)
    for i, label in enumerate(STEPS):
        x = 55 + i * 238
        draw.ellipse((x, 756, x+9, 765), fill=ORANGE if i == index else '#CAD5DC')
        text(draw, (x+18, 749), label, 15, INK if i == index else MUTED, i == index)
    return image, draw


def read(name):
    return json.loads((ROOT / name).read_text())


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    quality = read('quality/full-extraction-results.json')
    metrics = quality['checks']['coverage'][0]
    classified = quality['checks']['quality'][0]
    growth_report = read('quality/skill-growth-results.json')
    assert growth_report['status'] == 'success'
    growth = growth_report['results'][:5]
    assert growth_report['periods'] == {'previous':['2026-04','2026-06'], 'recent':['2026-07','2026-09']}, 'Update the story dates for a different comparison snapshot'
    lead = growth[0]
    previous_total, recent_total = int(lead['previous_total']), int(lead['recent_total'])
    chat_report = read('quality/app-live-results.json')
    assert chat_report['chat']['reference_sql_parity'] == 'passed'
    sources = read('quality/app-chat-results.json')['checks'][0]['rows'][:5]
    model = read('quality/model-comparison-results.json')
    winner = next(row for row in model['scores'] if row['model'] == model['selected_model'])
    frames = []

    im, d = base(0, 'From hiring posts to hiring signals.',
        'Explore skills, compensation, seniority, work policies and countries.',
        'Saved snapshot: October 25, 2026. Posts and advertisements are not vacancy or hire counts.')
    cards = [(metrics['successful_posts'], 'SOURCE POSTS PROCESSED'),
             (classified['ai_classified_hiring_posts'], 'AI-CLASSIFIED HIRING ADS'),
             (metrics['months'], 'MONTHLY THREADS SINCE 2020')]
    for i, (value, label) in enumerate(cards):
        x = 55 + i * 398
        box(d, (x, 269, x+374, 421))
        text(d, (x+24, 293), f'{int(value):,}', 46, TEAL, True)
        text(d, (x+24, 367), label, 15, MUTED, True)
    box(d, (55, 451, 1225, 647))
    text(d, (82, 475), 'A question is a good starting point.', 26, bold=True)
    for y, line in [(522, 'Which skills are gaining share of hiring advertisements?'),
                    (557, 'What compensation is explicitly stated, and what remains unknown?'),
                    (592, 'Can I inspect the SQL and trace a result to its original source?')]:
        text(d, (83, y), '→  ' + line, 22, MUTED)
    frames.append(im)

    im, d = base(1, 'Compare share, not just raw mentions.',
        'Q3 2026 versus Q2 2026 · at least 20 mentions in each quarter',
        f'Denominators include every hiring ad: {previous_total:,} in Q2 and {recent_total:,} in Q3. Partial October is excluded.')
    box(d, (55, 266, 1225, 655))
    text(d, (81, 287), 'SKILL', 15, MUTED, True)
    text(d, (322, 287), 'SHARE IN Q2 → SHARE IN Q3', 15, MUTED, True)
    text(d, (1010, 287), 'CHANGE', 15, MUTED, True)
    labels = {'rails':'Rails', 'ai':'AI', 'nodejs':'Node.js', 'react native':'React Native', 'llms':'LLMs'}
    for i, row in enumerate(growth):
        y = 330 + i * 62
        text(d, (81, y), labels.get(row['skill'], row['skill']), 23, bold=True)
        width = float(row['growth_percentage_points']) / 2.1 * 610
        d.rounded_rectangle((322, y+30, 322+width, y+44), radius=5, fill=TEAL)
        text(d, (322, y), f"{row['previous_share_pct']}% → {row['recent_share_pct']}%", 19, MUTED)
        text(d, (1010, y), '+' + row['growth_percentage_points'] + ' pp', 23, TEAL, True)
    frames.append(im)

    im, d = base(2, 'Ask a question. Inspect the method.',
        'A Databricks-hosted model proposes SQL; the app checks and executes it.',
        'This saved chat answer matched the reference SQL. AI-generated queries still require review.')
    box(d, (55, 267, 1225, 333), fill='#E8EFF0', outline='#E8EFF0')
    text(d, (78, 288), '“Which skills grew fastest in Q3 2026 versus Q2 2026?”', 24, TEAL, True)
    box(d, (55, 357, 812, 655), fill=INK, outline=INK)
    text(d, (80, 377), 'GENERATED SQL · EXCERPT', 16, '#A8C8CE', True)
    excerpt = ["FROM workspace.hnjob.post_attributes", "WHERE status = 'success' AND is_hiring = TRUE",
        "COUNT_IF(period = 'previous') AS previous_total", "COUNT_IF(period = 'recent') AS recent_total",
        'JOIN workspace.hnjob.post_skills AS s ...', 'ORDER BY growth_pp DESC LIMIT 5']
    for i, line in enumerate(excerpt): text(d, (80, 420+i*31), line, 16, '#ECF2F4', mono=True)
    box(d, (837, 357, 1225, 655))
    text(d, (861, 380), 'VERIFIED RESULT', 16, MUTED, True)
    text(d, (861, 425), labels.get(lead['skill'], lead['skill']) + '  +' + lead['growth_percentage_points'] + ' pp', 27, TEAL, True)
    text(d, (861, 476), f"{lead['previous_mentions']} → {lead['recent_mentions']} mentions", 22)
    text(d, (861, 519), f'{previous_total:,} → {recent_total:,} total ads', 21)
    text(d, (861, 577), 'Counts + SQL stay visible.', 19, MUTED)
    frames.append(im)

    im, d = base(3, 'Follow the result back to the post.',
        'Recorded query: five recent remote/Rust advertisements with original HN links.',
        'Matches describe whole posts. A listed policy or skill may apply to only one advertised role.')
    box(d, (55, 266, 1225, 655))
    for i, row in enumerate(sources):
        y = 286 + i * 70
        text(d, (81, y), row['company'] or 'Company unspecified', 25, bold=True)
        text(d, (380, y+4), f"HN #{row['comment_id']}  ·  {row['month']}", 19, MUTED)
        text(d, (81, y+33), row['source_url'], 17, TEAL)
        if i < len(sources)-1: d.line((81, y+62, 1197, y+62), fill=LINE)
    frames.append(im)

    im, d = base(4, 'One pipeline, from source to application.',
        'Python · Delta tables · AI Functions · Databricks SQL · Streamlit · Plotly',
        'Five-model comparison uses 20 development posts; the scores are not corpus-wide accuracy.')
    stages = [('INGEST', 'Official HN API', 'Raw text + hashes'),
              ('EXTRACT', 'AI Functions', 'Structured attributes'),
              ('CURATE', 'Delta tables', 'Evidence + quality flags'),
              ('SERVE', 'Databricks Apps', 'Charts + SQL assistant')]
    for i, (label, line1, line2) in enumerate(stages):
        x = 55 + i*300
        box(d, (x, 285, x+270, 426))
        text(d, (x+18, 303), label, 16, ORANGE, True)
        text(d, (x+18, 344), line1, 22, bold=True)
        text(d, (x+18, 383), line2, 16, MUTED)
        if i < 3: text(d, (x+276, 342), '→', 22, TEAL, True)
    for i, (title, detail, note) in enumerate([
        ('Resumable processing', 'Reuse successful outputs', 'Hash + model + prompt version'),
        ('Model evaluation', f"{winner['fully_passing_posts']}/20 raw post checks", 'GPT OSS 120B selected'),
        ('Traceable analytics', 'SQL checks + source links', '10 automated tests + live checks')]):
        x = 55+i*398
        box(d, (x, 465, x+374, 647))
        text(d, (x+20, 488), title, 22, bold=True)
        text(d, (x+20, 540), detail, 20, TEAL)
        text(d, (x+20, 585), note, 16, MUTED)
    frames.append(im)

    # These are illustrations generated from structured data, not edited UI screenshots.
    for i, frame in enumerate(frames): frame.save(OUT / f'scene-{i:02}.png', optimize=True)
    frames[0].save(OUT / 'overview.png', optimize=True)
    montage = Image.new('RGB', (W, H*len(frames)))
    for i, frame in enumerate(frames): montage.paste(frame, (0, H*i))
    palette = montage.resize((256, 800)).quantize(colors=192)
    indexed = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
    indexed[0].save(OUT / 'walkthrough.gif', save_all=True, append_images=indexed[1:],
                    duration=[5000]*5, loop=0, optimize=True, disposal=2)
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg: raise RuntimeError('Install FFmpeg to build the captioned MP4.')
    subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
        '-framerate', '1/15', '-i', str(OUT / 'scene-%02d.png'),
        '-vf', 'fps=24,format=yuv420p', '-c:v', 'libx264', '-preset', 'veryfast',
        '-crf', '23', '-movflags', '+faststart', '-t', '75', '-an',
        '-metadata', 'title=HN Hiring Observatory — illustrated walkthrough',
        '-metadata', 'comment=Illustrated from verified saved outputs; explanatory layouts; no audio.',
        str(OUT / 'walkthrough.mp4')], check=True, timeout=180)
    sources_used = ['quality/full-extraction-results.json', 'quality/skill-growth-results.json',
        'quality/app-live-results.json', 'quality/app-chat-results.json', 'quality/model-comparison-results.json']
    manifest = {'kind': 'illustrated walkthrough from verified saved outputs',
        'screen_recording': False, 'audio': False, 'snapshot_date': '2026-10-25',
        'dimensions': [W, H], 'gif_seconds':25, 'video_seconds':75,
        'source_sha256': {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources_used}}
    (OUT/'provenance.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({p.name: p.stat().st_size for p in OUT.iterdir() if p.is_file()}, indent=2))


if __name__ == '__main__': build()
