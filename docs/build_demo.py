"""Render an edited, captioned product tour from actual browser captures.

Run with .venv/bin/python docs/build_demo.py. No account or model access.
UI images stay unaltered apart from cropping/resizing; the final architecture
card is an explanatory illustration. Transitions and pauses are edited.
"""
import hashlib
import json
from functools import lru_cache
from pathlib import Path
import shutil
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/assets'
CAPTURES = OUT / 'captures'
W, H, FPS = 1280, 840, 10
BG, PANEL, INK = '#101F2B', '#192E3B', '#F2F6F8'
MUTED, TEAL, ORANGE = '#A5BAC5', '#77D8C7', '#FA936C'
FONT_DIR = Path('/usr/share/fonts/truetype/dejavu')
DURATIONS = [5, 5, 6, 6, 6, 4]
LABELS = ['Explore', 'Track skills', 'Compare growth', 'Ask + inspect', 'Verify source', 'Built on Databricks']


@lru_cache(maxsize=64)
def font(size, bold=False):
    path = FONT_DIR / ('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')
    return ImageFont.truetype(str(path), size)


def text(draw, xy, value, size=20, fill=INK, bold=False):
    draw.text(xy, str(value), font=font(size, bold), fill=fill)


def lines(draw, xy, values, size=34, fill=INK, bold=True, spacing=None):
    x, y = xy
    for line in values:
        text(draw, (x, y), line, size, fill, bold)
        y += spacing or int(size * 1.35)


def screenshot(image, filename, crop):
    source = Image.open(CAPTURES / filename).convert('RGB').crop(crop)
    # Preserve the screenshot's aspect ratio, never redraw chart values or UI.
    shot = ImageOps.contain(source, (826, 570), Image.Resampling.LANCZOS)
    ImageDraw.Draw(image).rounded_rectangle((380, 112, 1232, 722), radius=16, fill='#F6F8FA')
    d = ImageDraw.Draw(image)
    for x, color in [(400, '#FA936C'), (418, '#E8C77B'), (436, '#77D8C7')]:
        d.ellipse((x, 127, x+7, 134), fill=color)
    text(d, (464, 122), 'HN HIRING OBSERVATORY  /  ACTUAL APP CAPTURE', 11, '#60717C', True)
    image.paste(shot, (393 + (826-shot.width)//2, 147 + (570-shot.height)//2))


def scenes():
    report = json.loads((ROOT/'quality/full-extraction-results.json').read_text())
    growth = json.loads((ROOT/'quality/skill-growth-results.json').read_text())
    lead = growth['results'][0]
    assert lead['skill'] == 'rails' and lead['growth_percentage_points'] == '1.91'
    assert int(report['checks']['coverage'][0]['successful_posts']) == 40065
    definitions = [
        (['Hiring signals,', 'from the', 'original posts.'],
         ['40,065 processed posts.', '82 monthly HN threads.', 'One searchable history.'],
         '01-overview.jpg', (245, 0, 1108, 715),
         'LIVE DATA', 'Charts, filters and source links', 'Overview shown: Oct 2025–Sep 2026. Counts describe advertisements, not hires.'),
        (['Follow the', 'changing', 'tech stack.'],
         ['Compare Python,', 'TypeScript and Rust', 'as a share of hiring ads.'],
         '02-skills.jpg', (245, 0, 1108, 760),
         'TRACK PREVALENCE', 'Counts become comparable shares', 'Skills are extracted from whole posts. A single post can advertise several roles.'),
        (['Which skills', 'are gaining', 'ground?'],
         ['Q3 versus Q2 2026.', 'At least 20 mentions', 'in each quarter.'],
         '03-growth.jpg', (245, 0, 1108, 740),
         'RAILS  +1.91 pp', '2.57% → 4.48% of hiring ads', 'Rails: 24/934 ads → 32/714 ads. All hiring ads form the denominator.'),
        (['Ask in plain', 'English.', 'See the SQL.'],
         ['“Which skills grew', 'fastest in Q3 2026', 'versus Q2 2026?”'],
         '05-sql-wide.jpg', (290, 20, 1085, 675),
         'INSPECT THE METHOD', 'Actual returned counts and chart', 'The model proposes SQL. The app checks a read-only query, then executes it.'),
        (['Trust starts', 'with the', 'source.'],
         ['Read the original post.', 'Inspect AI attributes.', 'Follow the HN link.'],
         '06-source.jpg', (250, 135, 1090, 665),
         'SOURCE EVIDENCE', 'Close · September 2026', 'Work policy, country and seniority describe the whole advertisement.'),
        (['From raw text', 'to a working', 'data product.'],
         ['Python · Delta tables', 'AI Functions · SQL', 'Streamlit · Plotly'],
         None, None, 'BUILT END TO END', 'Deployed on Databricks Apps',
         'AI attributes need review. This project measures HN posting activity, not the entire job market.'),
    ]
    results = []
    for i, (title, body, filename, crop, badge, takeaway, caveat) in enumerate(definitions):
        im = Image.new('RGB', (W, H), BG)
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((40, 31, 69, 60), radius=7, fill=ORANGE)
        text(d, (46, 34), 'H', 19, BG, True)
        text(d, (82, 32), 'HN HIRING OBSERVATORY', 21, INK, True)
        text(d, (916, 38), 'PRODUCT TOUR  /  OCT 2026', 14, MUTED, True)
        d.line((40, 84, 1232, 84), fill='#2C4250', width=1)
        text(d, (42, 117), f'0{i+1} / {LABELS[i].upper()}', 14, ORANGE, True)
        lines(d, (40, 170), title, 33)
        lines(d, (42, 339), body, 20, MUTED, False, 33)
        d.rounded_rectangle((40, 490, 348, 650), radius=12, fill=PANEL)
        text(d, (58, 512), badge, 15, TEAL, True)
        # Separate short lines keep the message readable at GitHub README width.
        words, row, wrapped = takeaway.split(), '', []
        for word in words:
            attempt = f'{row} {word}'.strip()
            if d.textlength(attempt, font=font(21, True)) > 270:
                wrapped.append(row); row = word
            else: row = attempt
        wrapped.append(row)
        lines(d, (58, 548), wrapped, 21, INK, True, 30)
        if filename:
            screenshot(im, filename, crop)
        else:
            d.rounded_rectangle((380, 112, 1232, 722), radius=16, fill=PANEL)
            text(d, (415, 142), 'PIPELINE  /  EXPLANATORY DIAGRAM', 13, MUTED, True)
            for j, (name, detail) in enumerate([
                ('01  INGEST', 'Official HN API → raw Delta tables'),
                ('02  EXTRACT', 'AI Functions → skills, salary, level, policy, country'),
                ('03  CURATE', 'Normalized views + evidence + quality flags'),
                ('04  EXPLORE', 'Charts + source explorer + checked SQL assistant'),
            ]):
                y = 194 + j*109
                d.rounded_rectangle((415, y, 1196, y+85), radius=10, fill=BG)
                text(d, (435, y+12), name, 14, TEAL, True)
                text(d, (435, y+40), detail, 21)
            text(d, (415, 667), 'Resumable inference · 5 models compared on 20 development posts', 17, MUTED)
        d = ImageDraw.Draw(im)
        text(d, (41, 743), caveat, 14, MUTED)
        for j, label in enumerate(LABELS):
            x = 40 + j*200
            d.rounded_rectangle((x, 790, x+188, 794), radius=2, fill='#2C4250')
            text(d, (x, 804), label, 13, INK if i==j else MUTED, i==j)
        results.append(im)
    return results


def build():
    slides = scenes()
    # A shared palette keeps text and screenshot colors stable through cuts.
    contact = Image.new('RGB', (W, H*len(slides)))
    for i, slide in enumerate(slides):
        contact.paste(slide, (0, H*i))
        slide.save(OUT/f'scene-{i:02}.png', optimize=True)
    palette = contact.resize((640, 2520)).quantize(colors=256)
    frames, durations = [], []
    total_ticks = sum(DURATIONS)*FPS
    tick = 0
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg: raise RuntimeError('FFmpeg is required.')
    with tempfile.TemporaryDirectory(prefix='hnjob-tour-') as tmp:
        tmp = Path(tmp)
        for scene_i, (slide, seconds) in enumerate(zip(slides, DURATIONS)):
            for local in range(seconds*FPS):
                frame = slide.copy()
                if local < 5 and scene_i > 0:
                    # Keep a useful first-frame poster, then dissolve between scenes.
                    alpha = (local+1)/5
                    frame = Image.blend(slides[scene_i-1], frame, alpha*alpha*(3-2*alpha))
                draw = ImageDraw.Draw(frame)
                for j in range(len(slides)):
                    x = 40 + j*200
                    progress = 1 if j < scene_i else local/max(1, seconds*FPS-1) if j==scene_i else 0
                    if progress:
                        draw.rounded_rectangle((x,790,x+max(4,188*progress),794),radius=2,fill=TEAL)
                frames.append(frame.quantize(palette=palette,dither=Image.Dither.NONE))
                durations.append(100)
                frame.save(tmp/f'{tick:04}.png', compress_level=1)
                tick += 1
        # disposal=1 allows GIF to encode only changed areas during reading pauses.
        frames[0].save(OUT/'walkthrough.gif',save_all=True,append_images=frames[1:],
            duration=durations,loop=0,optimize=True,disposal=1)
        subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-nostdin','-y',
            '-framerate',str(FPS),'-i',str(tmp/'%04d.png'),'-c:v','libx264',
            '-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',
            '-an','-metadata','title=HN Hiring Observatory — real app tour',
            str(OUT/'walkthrough.mp4')],check=True,timeout=180)
    slides[0].save(OUT/'overview.png', optimize=True)
    used = ['01-overview.jpg','02-skills.jpg','03-growth.jpg','05-sql-wide.jpg','06-source.jpg']
    manifest = {
        'kind':'edited product tour from actual browser screenshots, with an illustrated architecture card',
        'screen_recording':False,'actual_ui_captures':True,'audio':False,
        'snapshot_date':'2026-10-25','dimensions':[W,H],'gif_seconds':sum(DURATIONS),
        'video_seconds':sum(DURATIONS),'fps':FPS,'scenes':LABELS,
        'editing':'Cropped/resized captures; editorial captions, reading pauses, dissolves and animated progress. No invented cursor actions.',
        'capture_sha256':{p:hashlib.sha256((CAPTURES/p).read_bytes()).hexdigest() for p in used},
        'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [
            'quality/full-extraction-results.json','quality/skill-growth-results.json']},
    }
    (OUT/'provenance.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'frames':total_ticks,'seconds':sum(DURATIONS),
        'gif_bytes':(OUT/'walkthrough.gif').stat().st_size,
        'mp4_bytes':(OUT/'walkthrough.mp4').stat().st_size},indent=2))


if __name__ == '__main__':
    build()
