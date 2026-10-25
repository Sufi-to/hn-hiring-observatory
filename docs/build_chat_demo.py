"""Build the focused Ask & Inspect GIF from actual captured chat states.

Run .venv/bin/python docs/build_chat_demo.py. Requires Pillow and DejaVu Sans.
No Databricks/model calls. Input states, submitted question, processing state,
answer, expanded SQL and result views were captured through the browser UI.
"""
import hashlib
import json
from pathlib import Path
import re

from PIL import Image, ImageDraw, ImageOps

from build_demo import BG, INK, MUTED, ORANGE, TEAL, font, text

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/assets'
CAPTURES = OUT / 'chat-captures'
W, H, FPS = 1160, 900, 10
QUESTION = 'Which skills grew fastest in Q3 2026 versus Q2 2026?'
CHAPTERS = ['Ask a question', 'Run on Databricks', 'Read the answer', 'Inspect the SQL', 'Explore results']
# Durations are edited for readability; they do not represent model latency.
SHOTS = [
    ('01-ready.jpg', 10, 0, 'Start with a question about the hiring data.'),
    ('02-typing.jpg', 8, 0, 'Enter a question directly in the chat.'),
    ('03-question.jpg', 22, 0, 'Specify the comparison you want, then send.'),
    ('04-running.jpg', 20, 1, 'The app sends your question to Databricks.'),
    ('05-answer.jpg', 40, 2, 'Read the method and the returned counts.'),
    ('06-sql.jpg', 45, 3, 'Open Generated SQL to inspect the query.'),
    ('07-results.jpg', 45, 4, 'Verify skill mentions and total-ad denominators.'),
    ('08-chart.jpg', 60, 4, 'Explore the returned result as a chart.'),
]


def verify_results():
    evidence = (CAPTURES/'result-ax.txt').read_text()
    assert QUESTION in evidence and 'SELECT * FROM' in evidence
    # Parse the actual accessible table captured from this browser session.
    pattern = r'row \(selectable\) (.+?) (\d+) (\d+) (\d+) (\d+) ([\d.]+) ([\d.]+) ([\d.]+)\n'
    rows = re.findall(pattern, evidence)
    reference = json.loads((ROOT/'quality/skill-growth-results.json').read_text())['results'][:5]
    assert len(rows) == len(reference) == 5, 'Expected five captured result rows'
    for actual, expected in zip(rows, reference):
        skill, q2, q3, total2, total3, share2, share3, growth = actual
        assert skill == expected['skill']
        for value, key in [(q2,'previous_mentions'), (q3,'recent_mentions'),
                           (total2,'previous_total'), (total3,'recent_total')]:
            assert int(value) == int(expected[key]), (skill, key)
        for value, key in [(share2,'previous_share_pct'), (share3,'recent_share_pct'),
                           (growth,'growth_percentage_points')]:
            assert round(float(value),2) == round(float(expected[key]),2), (skill,key)
    return 'five skills, counts, denominators, shares and growth matched saved reference'


def slide(filename, chapter, caption):
    im = Image.new('RGB',(W,H),BG)
    d = ImageDraw.Draw(im)
    text(d,(35,20),'HN HIRING OBSERVATORY  /  ASK & INSPECT',19,INK,True)
    text(d,(35,54),caption,23,TEAL,True)
    d.rounded_rectangle((35,100,W-35,838),radius=12,fill='#F6F8FA')
    source = Image.open(CAPTURES/filename).convert('RGB')
    assert source.size == (1280,720), (filename,source.size)
    # Remove sidebar chrome; retain both the conversation and real chat input.
    source = source.crop((320,0,1260,680))
    source = ImageOps.contain(source,(W-86,726),Image.Resampling.LANCZOS)
    im.paste(source,((W-source.width)//2,106+(726-source.height)//2))
    text(d,(36,847),'ACTUAL APP CAPTURES · Edited pauses; waiting time shortened · AI-generated SQL needs review',13,MUTED)
    for i,label in enumerate(CHAPTERS):
        x = 35+i*220
        d.rounded_rectangle((x,875,x+208,878),radius=1,fill=TEAL if i<chapter else '#2C4250')
        text(d,(x,882),label,12,INK if i==chapter else MUTED,i==chapter)
    return im


def build():
    parity = verify_results()
    slides = [slide(name,chapter,caption) for name,_,chapter,caption in SHOTS]
    contact = Image.new('RGB',(W,H*len(slides)))
    for i,im in enumerate(slides): contact.paste(im,(0,H*i))
    palette = contact.resize((580,3600)).quantize(colors=256)
    frames = []
    for i,(_,ticks,chapter,_) in enumerate(SHOTS):
        for tick in range(ticks):
            im = slides[i].copy()
            # Cuts preserve actual input states; short dissolves separate the later views.
            if i>=4 and tick<3:
                im = Image.blend(slides[i-1],im,(tick+1)/3)
            d = ImageDraw.Draw(im)
            x = 35+chapter*220
            d.rounded_rectangle((x,875,x+max(3,208*(tick+1)/ticks),878),radius=1,fill=ORANGE)
            frames.append(im.quantize(palette=palette,dither=Image.Dither.NONE))
    frames[0].save(OUT/'ask-inspect.gif',save_all=True,append_images=frames[1:],
        duration=100,loop=0,optimize=True,disposal=1)
    slides[2].save(OUT/'ask-inspect-preview.png',optimize=True)
    used = [name for name,*_ in SHOTS]+['result-ax.txt']
    manifest = {
        'kind':'edited screenshot sequence of a complete live chat interaction',
        'actual_ui_captures':True,'screen_recording':False,'snapshot_date':'2026-10-25',
        'question':QUESTION,'dimensions':[W,H],'seconds':sum(s[1] for s in SHOTS)/FPS,
        'fps':FPS,'result_reference_parity':parity,
        'editing':'Real partial/full input states and processing capture; pauses and wait shortened. No fabricated results or cursor actions.',
        'scenes':[{'capture':name,'seconds':ticks/FPS,'caption':caption} for name,ticks,_,caption in SHOTS],
        'capture_sha256':{name:hashlib.sha256((CAPTURES/name).read_bytes()).hexdigest() for name in used},
        'reference_sha256':hashlib.sha256((ROOT/'quality/skill-growth-results.json').read_bytes()).hexdigest(),
    }
    (OUT/'ask-inspect-provenance.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'seconds':manifest['seconds'],'frames':len(frames),
        'gif_bytes':(OUT/'ask-inspect.gif').stat().st_size,'reference_parity':parity},indent=2))


if __name__ == '__main__':
    build()
