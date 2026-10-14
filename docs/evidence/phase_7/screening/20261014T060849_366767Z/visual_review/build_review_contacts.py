"""Render DEV-only retained images; no transform, decoder, detector or hold-out run.

Run from this folder: python build_review_contacts.py
Every tile copies native RGB pixels from [0, 360, 1280, 700), with no resampling.
The road and glare areas therefore have exactly the same native frame mapping.
"""
from pathlib import Path
import hashlib
import json
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent
VARIANTS = ['raw', 'gamma_070', 'exposure_125', 'contrast_125', 'unsharp_s1_a05']
FRAMES = [0, 7, 14, 29, 239, 2277, 2337, 2397, 2457, 2516, 7072, 7132, 7192, 7252, 7311]
CROP = (0, 360, 1280, 700)
FONT = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 18)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    report = json.loads((SOURCE / 'report.json').read_text())
    assert report['sample_indices'] == FRAMES
    assert not report['heldout_evaluation_executed']
    index = {'contract': 'phase7_dev_pixel_review_v1', 'source_run_id': report['run_id'],
             'source_report_sha256': sha(SOURCE/'report.json'),
             'native_crop_xyxy': list(CROP), 'resampling': 'NONE_NATIVE_PIXEL_COPY',
             'holdout_reviewed_by_this_method': False, 'sheets': [], 'checks': []}
    for frame in FRAMES:
        raw = SOURCE / 'source_frames' / f'frame_{frame:09d}.png'
        for kind in ('transformed', 'annotated'):
            canvas = Image.new('RGB', (1280, 5*368+34), '#121820')
            draw = ImageDraw.Draw(canvas)
            draw.text((8, 4), f'DEV frame {frame} | {kind} | native crop x=0..1279, y=360..699', font=FONT, fill='white')
            row = {'frame_index': frame, 'kind': kind, 'raw_source': str(raw.relative_to(SOURCE)),
                   'raw_source_sha256': sha(raw), 'tiles': []}
            for i, variant in enumerate(VARIANTS):
                original = SOURCE / variant / f'frame_{frame:09d}_{kind}.png'
                with Image.open(original) as im:
                    assert im.size == (1280,720)
                    tile = im.convert('RGB').crop(CROP)
                y = 34+i*368
                draw.text((8,y+2), variant, font=FONT, fill='white')
                canvas.paste(tile, (0,y+28))
                assert canvas.crop((0,y+28,1280,y+368)).tobytes() == tile.tobytes()
                row['tiles'].append({'variant':variant,'source':str(original.relative_to(SOURCE)),
                    'source_sha256':sha(original), 'source_crop_xyxy':list(CROP),
                    'sheet_tile_xyxy':[0,y+28,1280,y+368], 'pixel_sha256_rgb_crop':hashlib.sha256(tile.tobytes()).hexdigest()})
                index['checks'].append({'frame':frame,'variant':variant,'kind':kind,'native_crop_pixel_equal':True})
            dest = HERE/f'frame_{frame:09d}_{kind}_comparison.png'
            canvas.save(dest)
            row['path']=dest.name
            row['sha256']=sha(dest)
            index['sheets'].append(row)
    index['check_count']=len(index['checks'])
    index['all_passed']=all(x['native_crop_pixel_equal'] for x in index['checks'])
    index['builder_sha256']=sha(Path(__file__))
    (HERE/'contact_index.json').write_text(json.dumps(index,indent=2)+'\n')
    print(json.dumps({'sheets':len(index['sheets']),'native_pixel_checks':index['check_count'],'all_passed':index['all_passed']}))

if __name__ == '__main__':
    main()
