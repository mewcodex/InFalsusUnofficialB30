"""Offline In Falsus B30 generator. Runtime needs only Pillow and bundled assets.

Save parsing is read-only and version-checked. No game files or Unity libraries
are loaded. The B30 rating is a community convention, not a game statistic.
"""
from pathlib import Path
from datetime import datetime
import argparse
import csv
import io
import json
import math
import os
import re
import struct
import sys
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter

APP_VERSION = '1.08'

BASE = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
ASSETS = BASE / 'assets'
DIFFS = {1: ('MIN', '#68d5c4'), 2: ('EVO', '#86bef3'), 4: ('ULT', '#f0bc74'), 8: ('FBD', '#e899b7')}
CLEARS = {0: '—', 1: 'DIVE FAILED', 2: 'DIVE CLEARED', 3: 'FULL LINK', 4: 'PERFECT DIVE'}
CHARACTERS = ('Nia', 'Mei', 'Ayame', 'Iris', 'Story')
BACKGROUND = 'seiko_amphitheatre_clip'
# Representative solid text colors sampled from the game's judgement textures.
JUDGEMENT_COLORS = {'exact': '#DEB6FF', 'shiny': '#F7AEF7', 'near': '#A5D3DE', 'break': '#FF7D94'}
EXPORT_SIZE = (2700, 3450)
FONT_COVERAGE = {k: set(v) for k, v in json.loads((ASSETS/'fonts/game-font-coverage.json').read_text(encoding='utf8')).items()}

class ScaledDraw:
    """Draw the design at native 1.5x resolution, including fonts and artwork."""
    def __init__(self,image,scale=1.5):
        self.draw=ImageDraw.Draw(image);self.scale=scale
    def xy(self,coords):return tuple(v*self.scale for v in coords)
    def scaled_font(self,f):return f.font_variant(size=round(f.size*self.scale))
    def text(self,xy,text,font,**kw):self.draw.text(self.xy(xy),text,font=self.scaled_font(font),**kw)
    def textlength(self,text,font):return self.draw.textlength(text,font=self.scaled_font(font))/self.scale
    def rectangle(self,xy,**kw):
        if 'width' in kw:kw['width']=max(1,round(kw['width']*self.scale))
        self.draw.rectangle(self.xy(xy),**kw)
    def rounded_rectangle(self,xy,radius=0,**kw):
        if 'width' in kw:kw['width']=max(1,round(kw['width']*self.scale))
        self.draw.rounded_rectangle(self.xy(xy),radius=radius*self.scale,**kw)
    def line(self,xy,**kw):
        if 'width' in kw:kw['width']=max(1,round(kw['width']*self.scale))
        self.draw.line(self.xy(xy),**kw)

class SaveRecords(list):
    selected_character = None
    profile_warning = None

class InputError(ValueError):
    pass

class Reader:
    def __init__(self, data):
        self.data = data
        self.pos = 0

    def take(self, n):
        if n < 0 or self.pos + n > len(self.data):
            raise InputError('存档被截断或不是支持的 V3 格式。')
        result = self.data[self.pos:self.pos+n]
        self.pos += n
        return result

    def integer(self):
        return struct.unpack('<i', self.take(4))[0]

    def count(self, limit=1_000_000, nullable=False):
        n = self.integer()
        if not (-1 if nullable else 0) <= n <= limit:
            raise InputError('存档集合长度异常。')
        return n

    def header(self, n):
        if self.take(1) != bytes([n]):
            raise InputError('不支持的存档版本：仅支持已验证的正式版 savestate_V3.sav。')

    def unordered(self, size):
        self.header(2)
        capacity = self.count()
        data = self.take(capacity * size)
        length = self.count()
        if length > capacity:
            raise InputError('存档列表数量超出容量。')
        return [data[i*size:(i+1)*size] for i in range(length)]

    def string(self):
        n = self.integer()
        if n == -1:
            return None
        if abs(n) > 4096:
            raise InputError('存档曲目名长度异常。')
        if n >= 0:
            return self.take(n * 2).decode('utf-16le')
        chars = self.count(4096)
        result = self.take(~n).decode('utf8')
        if len(result.encode('utf-16le')) // 2 != chars:
            raise InputError('存档字符串长度不匹配。')
        return result

def judgement_counts(result):
    parts = [struct.unpack_from('<7H', result, pos) for pos in (10,26,42,58)]
    counts = [sum(part[i] for part in parts) for i in range(7)]
    return dict(exact=sum(counts[4:7]), shiny=counts[6], near=counts[2]+counts[3], breaks=counts[1])

def counts_match_score(counts, score):
    n = counts['exact'] + counts['near'] + counts['breaks']
    if n <= 0:return False
    reconstructed = math.ceil(100_000_000 * (counts['exact'] + counts['near']/2)/n + counts['shiny'])
    return abs(reconstructed-score) <= 2

def parse_save(data):
    r = Reader(data)
    r.header(9)                         # SingleFileSaveDataV2
    r.header(3)                         # CardInventory
    r.unordered(64)                     # CardInstance array
    r.take(r.count(10000) * 24)         # CardDeck array
    r.integer()                        # LastUsedDeckIndex
    r.header(2)                         # IotaInventory
    r.unordered(16)                     # IotaInstance array
    old = r.count(nullable=True)
    if old >= 0:
        r.take(old * 16)                # obsolete dictionary
    r.header(4)                         # GameResultsV4
    count = r.count(10000, nullable=True)
    rows = SaveRecords()
    for _ in range(max(0, count)):
        r.header(3)                     # GameResultKey
        name = r.string()
        song_id, difficulty = struct.unpack('<HB', r.take(3))
        result = r.take(96)             # unmanaged GameResultV4, sizeof = 0x60
        sid, diff, lamp, clear = struct.unpack_from('<HBBB', result)
        score, timestamp = struct.unpack_from('<QQ', result, 80)
        if (song_id, difficulty) != (sid, diff) or diff not in DIFFS or lamp > 2 or clear > 4:
            raise InputError('成绩键与数据不匹配，停止解析。')
        if score > 100_500_000:
            raise InputError('成绩超出当前版本合理范围。')
        if not name:
            raise InputError('成绩缺少曲目内部名。')
        counts=judgement_counts(result)
        rows.append(dict(base_name=name, song_id=sid, difficulty=diff, score=score, clear=clear, lamp=lamp,
                         judgements=counts if counts_match_score(counts,score) else None,
                         judgement_source='verified-highscore' if counts_match_score(counts,score) else None))
    # Validate the boundary after the dictionary instead of scanning for names.
    history = r.unordered(96)
    mappings=[]
    try:
        if r.pos < len(data):
            r.header(2)                 # UnorderedListRef<GameResultsSongInfoMapping>
            capacity=r.count(10000)
            for _ in range(capacity):
                h=r.take(1)[0]
                if h==255:
                    mappings.append(None);continue
                if h!=3:raise InputError('历史曲目映射格式不匹配。')
                mapping={}
                for _ in range(max(0,r.count(10000,nullable=True))):
                    r.header(2)
                    base_name=r.string(); sid=struct.unpack('<H',r.take(2))[0]
                    mapping[sid]=base_name
                start,length=struct.unpack('<ii',r.take(8))
                mappings.append((mapping,start,length))
            active=r.count(10000)
            if active>capacity:raise InputError('历史映射数量异常。')
            mappings=mappings[:active]
            r.take(8)                   # GameResults updateId
            r.header(2)                 # EncounterResults
            r.unordered(72);r.take(8)
            r.header(2)                 # StoryStateV5
            r.take(r.count(10000)*20);r.take(8)
            r.header(17)                # GeneralSaveStateV5
            char=r.take(1)[0]
            if char>=len(CHARACTERS):raise InputError('当前角色编号不受支持。')
            rows.selected_character=CHARACTERS[char]
    except (InputError,UnicodeError) as e:
        rows.profile_warning=str(e)
    # Highest-score aggregate fields may come from different plays. Prefer the
    # actual matching run, never simply the latest play or combined counters.
    runs={}
    for index, result in enumerate(history):
        sid,diff=struct.unpack_from('<HB',result)
        score=struct.unpack_from('<Q',result,80)[0]
        mapped=None
        for entry in mappings:
            if entry:
                mapping,start,length=entry
                if start<=index<start+length:mapped=mapping.get(sid)
        key=(mapped if mapped is not None else sid,diff,score)
        runs[key]=judgement_counts(result)
    for row in rows:
        key=(row['base_name'],row['difficulty'],row['score'])
        numeric=(row['song_id'],row['difficulty'],row['score'])
        counts=runs.get(key,runs.get(numeric))
        if counts is not None:
            row['judgements']=counts;row['judgement_source']='matching-history'
    return rows

def steam_name(source=None):
    """Read only PersonaName from Steam's local loginusers.vdf; no network/auth."""
    roots=[]
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Valve\Steam') as key:
            roots.append(Path(winreg.QueryValueEx(key,'SteamPath')[0]))
    except (ImportError,OSError):pass
    roots.extend([Path(os.environ.get('ProgramFiles(x86)','C:/Program Files (x86)'))/'Steam'])
    wanted=next((p for p in Path(source).parts if re.fullmatch(r'\d{17}',p)),None) if source else None
    for root in roots:
        try:
            text=(root/'config/loginusers.vdf').read_text(encoding='utf-8-sig')
            profiles=[]
            for sid,body in re.findall(r'"(\d{17})"\s*\{([^{}]*)\}',text):
                fields={k.lower():v.replace(r'\"','"').replace('\\\\','\\') for k,v in re.findall(r'"([^"\n]+)"\s*"((?:\\.|[^"\\])*)"',body)}
                if fields.get('personaname'):
                    if sid==wanted:return fields['personaname']
                    profiles.append((fields.get('mostrecent')=='1',fields['personaname']))
            if wanted:return None
            if profiles:return max(profiles,key=lambda x:x[0])[1]
        except (OSError,UnicodeError):continue
    return None

def load_catalog():
    return json.loads((ASSETS / 'catalog.json').read_text(encoding='utf8'))

def play_rating(constant, score):
    if score < 0 or not math.isfinite(float(score)):
        raise InputError('分数必须是非负有限整数。')
    if score >= 100_000_000:
        bonus = 2.0
    elif score >= 98_000_000:
        bonus = 1.0 + (score - 98_000_000) / 2_000_000
    else:
        bonus = (score - 95_000_000) / 3_000_000
    return max(0.0, constant + bonus)

def load_records(path):
    p = Path(path)
    if p.suffix.lower() != '.sav':
        raise InputError('请选择 .sav 格式的游戏存档。')
    if p.stat().st_size > 100_000_000:
        raise InputError('文件过大，请选择游戏存档。')
    return parse_save(p.read_bytes())

CONSTANT_COLUMNS = ('谱面ID','曲名','难度','定数')

def constants_template(catalog):
    stream=io.StringIO(newline='')
    writer=csv.writer(stream);writer.writerow(CONSTANT_COLUMNS)
    for song in catalog['songs']:
        for chart in song['charts']:
            writer.writerow((chart['id'],song['title'],DIFFS[chart['difficulty']][0],f"{chart['level']:.1f}"))
    return stream.getvalue()

def parse_constants(text,catalog):
    charts={c['id']:(s['base_name'],c['difficulty']) for s in catalog['songs'] for c in s['charts']}
    reader=csv.DictReader(io.StringIO(text.lstrip('\ufeff'),newline=''),strict=True)
    if reader.fieldnames is None or len(reader.fieldnames)!=len(CONSTANT_COLUMNS) or set(reader.fieldnames)!=set(CONSTANT_COLUMNS):
        raise InputError('定数表列名不正确，请使用生成的模板。')
    result={}
    try:
        for row in reader:
            line=reader.line_num
            if None in row or any(row.get(k) is None for k in CONSTANT_COLUMNS):
                raise InputError(f'第 {line} 行列数不正确。')
            chart_id=row['谱面ID'].strip()
            if chart_id not in charts:raise InputError(f'第 {line} 行谱面ID无法识别：{chart_id}')
            key=charts[chart_id]
            if key in result:raise InputError(f'第 {line} 行谱面重复：{chart_id}')
            if row['难度'].strip().upper()!=DIFFS[key[1]][0]:
                raise InputError(f'第 {line} 行难度与谱面ID不匹配。')
            value=row['定数'].strip()
            if not re.fullmatch(r'[0-9]+(?:\.[0-9])?',value):
                raise InputError(f'第 {line} 行定数必须为非负数，最多一位小数，例如 12.3。')
            constant=float(value)
            if not math.isfinite(constant):raise InputError(f'第 {line} 行定数超出可用范围。')
            result[key]=constant
    except csv.Error as e:raise InputError(f'定数表CSV格式错误：{e}') from e
    if len(result)!=len(charts):
        raise InputError(f'定数表缺少 {len(charts)-len(result)} 张谱面，请保留模板的全部行。')
    return result

def load_constants(path,catalog):
    path=Path(path)
    if path.suffix.lower()!='.csv':raise InputError('请选择 CSV 定数表。')
    if path.stat().st_size>1_000_000:raise InputError('定数表文件过大。')
    data=path.read_bytes()
    try:text=data.decode('utf-8-sig')
    except UnicodeDecodeError:text=data.decode('gb18030')
    return parse_constants(text,catalog)

def rank_records(records, catalog, constants=None):
    charts = {(s['base_name'], c['difficulty']): (s, c) for s in catalog['songs'] for c in s['charts']}
    best = {}
    skipped = set()
    for record in records:
        key = record['base_name'], record['difficulty']
        if key not in charts:
            skipped.add(key)
            continue
        s, c = charts[key]
        if 'song_id' in record and record['song_id'] != s['id']:
            raise InputError(f"曲目 ID 与内置曲库不匹配：{s['base_name']}。请更新曲库。")
        if record['score'] <= 0:
            continue
        if key in best and best[key]['score'] >= record['score']:
            continue
        constant=constants[key] if constants is not None else float(c['level'])
        best[key] = dict(record, title=s['title'], artist=s['artist'], jacket=s['jacket'],
                         level=c['level'], constant=constant, rating=play_rating(constant, record['score']))
    ranked = sorted(best.values(), key=lambda r: (-r['rating'], -r['score'], -r['constant'], r['base_name'], r['difficulty']))
    return ranked, sorted(skipped)

def b30_value(ranked):
    return sum(r['rating'] for r in ranked[:30]) / 30

def validate_output(path, source=None, extension='.png'):
    path=Path(path)
    if path.suffix.lower()!=extension:
        raise InputError(f'输出文件必须使用 {extension} 扩展名。')
    if source and path.resolve()==Path(source).resolve():
        raise InputError('输出不能覆盖输入文件。')

def find_saves():
    root = Path.home() / 'AppData/LocalLow/lowiro/infalsus'
    return sorted(root.glob('*/release/savestate_V3.sav'), key=lambda p: p.stat().st_mtime, reverse=True)

def font(size, bold=False, numeric=False, family=None):
    bundled={"heading":"Cinzel-SemiBold.ttf", "title":"Supreme-Bold.otf", "cjk":"ChironHeiHK-SB.otf", "score":"Supreme-Bold.otf"}
    if family in bundled:
        return ImageFont.truetype(str(ASSETS/"fonts"/bundled[family]), size)
    if numeric:
        return ImageFont.truetype(str(ASSETS/"fonts"/("Supreme-Bold.otf" if bold else "Supreme-Regular.otf")), size)
    windir = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
    names = (['bahnschrift.ttf', 'arialbd.ttf'] if numeric else ['msyhbd.ttc', 'arialbd.ttf']) if bold else ['msyh.ttc', 'arial.ttf']
    for name in names:
        p = windir / name
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.truetype(str(ASSETS/'fonts'/('Supreme-Regular.otf' if numeric else 'ChironHeiHK-SB.otf')), size)

def fit_text(draw, text, width, size=24, bold=False, minimum=15, family=None):
    if family == "title" and any(ord(c) not in FONT_COVERAGE["Supreme-Bold.otf"] for c in text):
        family = "cjk" if all(ord(c) in FONT_COVERAGE["ChironHeiHK-SB.otf"] for c in text) else None
    for n in range(size, minimum-1, -1):
        f = font(n, bold, family=family)
        if draw.textlength(text, font=f) <= width:
            return text, f
    f = font(minimum, bold, family=family)
    while text and draw.textlength(text+'…', font=f) > width:
        text = text[:-1]
    return text+'…', f

# Native GameResultV4.CalculatedRank thresholds; palette from GameResultAssets.
SCORE_RANK_THRESHOLDS = (80_000_000,85_000_000,90_000_000,95_000_000,98_000_000,99_000_000)
SCORE_RANK_COLORS = ((154, 238, 250), (154, 238, 250), (154, 238, 250), (154, 238, 250), (154, 238, 250), (154, 238, 250), (206, 161, 255), (255, 161, 255))

def score_tint(score):
    rank=1+sum(score>=threshold for threshold in SCORE_RANK_THRESHOLDS)
    return tuple(round(c*0.55+255*0.45) for c in SCORE_RANK_COLORS[rank])

def draw_score(image,draw,x,top,bottom,score,width):
    text=f'{score:011,}'
    size=40
    while size>20 and draw.textlength(text,font=font(size,family='score'))>width:size-=1
    face=draw.scaled_font(font(size,family='score'))
    box=face.getbbox(text,anchor='lt')
    mask=Image.new('L',(box[2]-box[0],box[3]-box[1]))
    ImageDraw.Draw(mask).text((-box[0],-box[1]),text,font=face,fill=255,anchor='lt')
    # Split the actual visible glyph height, rather than the font's line box.
    bounds=mask.getbbox()
    if not bounds:return
    mask=mask.crop(bounds)
    ink=Image.new('RGBA',mask.size,'white')
    ImageDraw.Draw(ink).rectangle((0,round(mask.height*0.4),mask.width,mask.height),fill=score_tint(score))
    ink.putalpha(mask)
    y=round((top+bottom)*draw.scale/2-mask.height/2)
    px=round(x*draw.scale)
    if score>=98_000_000:
        pink=score>=99_000_000
        radius=(9 if pink else 4)*draw.scale
        padding=math.ceil(radius*3)
        halo_mask=Image.new('L',(mask.width+2*padding,mask.height+2*padding))
        halo_mask.paste(mask,(padding,padding))
        color=SCORE_RANK_COLORS[7 if pink else 6]
        # Pink gets a much broader halo plus a restrained inner glow.
        passes=[(radius,1.0),(4*draw.scale,0.4)] if pink else [(radius,1.0)]
        for blur,strength in passes:
            alpha=halo_mask.filter(ImageFilter.GaussianBlur(blur)).point(lambda a:min(255,round(a*strength)))
            glow=Image.new('RGBA',halo_mask.size,color)
            glow.putalpha(alpha)
            image.alpha_composite(glow,(px-padding,y-padding))
    image.alpha_composite(ink,(px,y))

def draw_judgements(draw, xy, counts, width):
    if counts:
        segments = [(f"E: {counts['exact']} ", 'exact'), (f"(+{counts['shiny']})  ", 'shiny'),
                    (f"N: {counts['near']}  ", 'near'), (f"B: {counts['breaks']}", 'break')]
    else:
        segments = [('E: — (+—)  ', 'exact'), ('N: —  ', 'near'), ('B: —', 'break')]
    size=18
    while size>12 and sum(draw.textlength(text,font=font(size,numeric=True)) for text,_ in segments)>width:size-=1
    f=font(size,numeric=True);x,y=xy
    for text,key in segments:
        draw.text((x,y),text,font=f,fill=JUDGEMENT_COLORS[key]);x+=draw.textlength(text,font=f)
    return y+min(draw.scaled_font(f).getbbox(text)[1] for text,_ in segments)/draw.scale

def filter_scores(ranked, difficulties=None, min_level=None, max_level=None):
    if min_level is not None and max_level is not None and min_level > max_level:
        raise InputError('最低等级不能高于最高等级。')
    return sorted((r for r in ranked
        if (difficulties is None or r['difficulty'] in difficulties)
        and (min_level is None or r['level'] >= min_level)
        and (max_level is None or r['level'] <= max_level)),
        key=lambda r: (-r['level'], -r['score'], r['base_name'], r['difficulty']))


def score_progress(selected, catalog, difficulties, min_level, max_level):
    total=sum(1 for song in catalog['songs'] for c in song['charts']
              if c['difficulty'] in difficulties and min_level <= c['level'] <= max_level)
    return (sum(r['score'] >= 98_000_000 for r in selected),
            sum(r['score'] >= 99_000_000 for r in selected), total)


def score_pages(records):
    # Keep all matching records, with a fresh level heading on continuation pages.
    pages=[]; page={'records':[], 'positions':[], 'headings':[]}; y=292
    levels=sorted({r['level'] for r in records}, reverse=True)
    for level in levels:
        group=[r for r in records if r['level']==level]; offset=0
        while offset < len(group):
            if y+54+182 > 2100:
                pages.append(page); page={'records':[], 'positions':[], 'headings':[]}; y=292
            page['headings'].append((y,level)); y+=54
            while offset < len(group) and y+182 <= 2100:
                row=group[offset:offset+3]
                for col,r in enumerate(row):
                    page['records'].append(r); page['positions'].append((56+col*570,y))
                offset+=len(row); y+=182
            if offset < len(group):
                pages.append(page); page={'records':[], 'positions':[], 'headings':[]}; y=292
    if page['records']:pages.append(page)
    return pages


def export_images(ranked,catalog,output,name,character,score_mode=False,difficulties=None,min_level=None,max_level=None):
    if not score_mode:
        render(ranked,catalog,name,character).save(output,format='PNG'); return [Path(output)]
    selected=filter_scores(ranked,difficulties,min_level,max_level)
    if not selected:raise InputError('筛选范围内没有成绩。')
    pages=score_pages(selected); paths=[]; output=Path(output)
    for index,page in enumerate(pages):
        dest=output if len(pages)==1 else output.with_name(f'{output.stem}-{index+1:02}{output.suffix}')
        paths.append(dest)
    # Ask about the exact generated paths before replacing existing pages in the GUI.
    label=' / '.join(DIFFS[d][0] for d in DIFFS if difficulties is None or d in difficulties)
    bounds=f"Lv.{min_level if min_level is not None else 'ALL'}-{max_level if max_level is not None else 'ALL'}"
    for index,(page,dest) in enumerate(zip(pages,paths)):
        image=render(page['records'],catalog,name,character,score_page=page,
            page_label=f'{index+1} / {len(pages)}',filter_label=f'{label}  ·  {bounds}')
        image.save(dest,format='PNG');image.close()
    return paths


def render(ranked, catalog, name='PLAYER', character='Nia', score_page=None, page_label='', filter_label=''):
    W,H=EXPORT_SIZE
    footer_y=2150 if score_page is None else max(y for x,y in score_page['positions'])+222
    if score_page is not None: H=round((footer_y+150)*1.5)
    scale=1.5
    def pixel(n):return round(n*scale)
    if character not in CHARACTERS:raise InputError('请选择支持的角色。')
    bg=ASSETS/'backgrounds'/f'{BACKGROUND}.jpg'
    im=ImageOps.fit(Image.open(bg).convert('RGB'),(W,H),centering=(0.70,0.50)).convert('RGBA')
    im=Image.alpha_composite(im,Image.new('RGBA',(W,H),(7,14,24,180)))
    d=ScaledDraw(im)
    avatar=Image.open(ASSETS/'avatars'/f'{character.lower()}.png').convert('RGBA')
    avatar=avatar.resize((pixel(184),pixel(184)),Image.Resampling.LANCZOS);im.alpha_composite(avatar,(pixel(54),pixel(52)))
    logo=Image.open(ASSETS/'logo.png').convert('RGBA')
    # Bundled logo is already cropped to its visible bounds at export resolution.
    logo.thumbnail((pixel(200),pixel(48)),Image.Resampling.LANCZOS)
    logo_top=60;header_gap=14
    im.alpha_composite(logo,(pixel(263),pixel(logo_top)))
    username,f=fit_text(d,name.strip() or 'PLAYER',1000,72,True,24,family='title' if any(ord(c)>0x24F or c.isdigit() for c in name) else 'heading')
    name_top=logo_top+logo.height/scale+header_gap
    name_box=d.scaled_font(f).getbbox(username,anchor='lt')
    name_height=(name_box[3]-name_box[1])/scale
    d.text((263,name_top),username,font=f,fill='white',anchor='lt')
    d.text((263,name_top+name_height+header_gap+6),('SCORE RECORDS' if score_page is not None else 'PLAYER BESTS'),font=font(22,family='heading'),fill='#a7c4ce',anchor='lt')
    if score_page is None:
        d.text((1744,70),'UNOFFICIAL POTENTIAL',font=font(24,family='heading'),fill='#9fdacb',anchor='ra')
        d.text((1744,103),f'{b30_value(ranked):.4f}',font=font(80,True,numeric=True),fill='white',anchor='ra')
    else:
        ex,ex_plus,total=score_page.get('progress',(0,0,len(ranked)))
        d.text((1744,70),f'EX   {ex}/{total}',font=font(42,numeric=True),fill='#d7bcff',anchor='ra')
        d.text((1744,132),f'EX+   {ex_plus}/{total}',font=font(42,numeric=True),fill='#ffbddc',anchor='ra')
        d.text((1744,222),filter_label+'  |  '+page_label,font=font(20,numeric=True),fill='#becdd6',anchor='ra')
    d.line((56,262,1744,262),fill='#91bfbf',width=2)
    y0=292;cw=548;gap=22;step=182
    positions=score_page['positions'] if score_page is not None else [(56+(i%3)*(cw+gap),y0+(i//3)*step) for i in range(30)]
    layer=Image.new('RGBA',(W,H),(0,0,0,0));ld=ScaledDraw(layer)
    for x,y in positions:
        ld.rounded_rectangle((x,y-2,x+cw,y+172),radius=12,fill=(8,21,33,210),outline=(120,154,173,65),width=1)
    im=Image.alpha_composite(im,layer);d=ScaledDraw(im)
    if score_page is not None:
        for hy,level in score_page['headings']:
            d.text((56,hy+5),f'LEVEL {level}',font=font(28,True,numeric=True),fill='#b4e2d7')
            d.line((240,hy+25,1744,hy+25),fill='#688b94',width=1)
    for i,(x,y) in enumerate(positions):
        if i>=len(ranked):
            d.text((x+cw-17,y+155),f'#{i+1:02}',font=font(17,True,numeric=True),fill='#778b99',anchor='rb')
            d.text((x+183,y+70),'NO RECORD',font=font(23),fill='#778b99');continue
        r=ranked[i];diff,color=DIFFS[r['difficulty']]
        jacket=ImageOps.fit(Image.open(ASSETS/r['jacket']).convert('RGB'),(pixel(144),pixel(144)),method=Image.Resampling.LANCZOS)
        im.paste(jacket,(pixel(x+12),pixel(y+13)))
        d.text((x+cw-17,y+155),f'#{i+1:02}',font=font(17,True,numeric=True),fill='#a9bcc8',anchor='rb')
        tx=x+174;maxw=cw-190
        d.text((tx,y+16),f'{diff}  {r["constant"]:.1f}',font=font(18,True,numeric=True),fill=color)
        d.text((x+cw-17,y+12),f'{r["rating"]:.4f}',font=font(26,True,numeric=True),fill=color,anchor='ra')
        title,tf=fit_text(d,r['title'],maxw,25,True,16,family='title')
        d.text((tx,y+72),title,font=tf,fill='white',anchor='ls')
        judgement_top=draw_judgements(d,(tx,y+137),r.get('judgements'),maxw-48)
        title_bottom=y+72+d.scaled_font(tf).getbbox(title,anchor='ls')[3]/scale
        draw_score(im,d,tx,title_bottom,judgement_top,r['score'],maxw)
    d.line((56,footer_y,1744,footer_y),fill='#91bfbf',width=1)
    d.text((56,footer_y+32),'非官方成绩图 · 不代表游戏内评级',font=font(21),fill='#becdd6')
    stamp=datetime.now().strftime('%Y.%m.%d')
    d.text((1744,footer_y+32),stamp,font=font(20,numeric=True),fill='#becdd6',anchor='ra')
    return im.convert('RGB')

def enable_high_dpi():
    # Must run before creating any windows: prevent Windows bitmap scaling.
    if sys.platform != 'win32':return
    import ctypes
    try:
        user32=ctypes.windll.user32
        user32.SetProcessDpiAwarenessContext.argtypes=[ctypes.c_void_p]
        user32.SetProcessDpiAwarenessContext.restype=ctypes.c_bool
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):return
    except (AttributeError,OSError):pass
    try:ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError,OSError):
        try:ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError,OSError):pass


def gui():
    enable_high_dpi()
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    root=tk.Tk();root.title(f'In Falsus B30 v{APP_VERSION}');root.resizable(False,False)
    # Tk renders text at the display DPI instead of stretching a low-resolution UI.
    root.tk.call('tk','scaling',root.winfo_fpixels('1i')/72)
    bg='#111b24';surface='#1c2b36';fg='#ffffff';muted='#e6edf3';accent='#a2d6c7'
    root.configure(background=bg)
    style=ttk.Style(root);style.theme_use('clam')
    style.configure('.',font=('Microsoft YaHei UI',11),background=bg,foreground=fg)
    style.configure('TFrame',background=bg)
    style.configure('TLabel',background=bg,foreground=muted,font=('Microsoft YaHei UI',10))
    style.configure('TEntry',fieldbackground=surface,foreground=fg,bordercolor=surface,lightcolor=surface,darkcolor=surface,insertcolor=fg,padding=(8,8))
    style.map('TEntry',bordercolor=[('focus',accent)],lightcolor=[('focus',accent)],darkcolor=[('focus',accent)])
    style.configure('TCombobox',fieldbackground=surface,background=surface,foreground=fg,arrowcolor=muted,bordercolor=surface,lightcolor=surface,darkcolor=surface,padding=(8,8))
    style.map('TCombobox',fieldbackground=[('readonly',surface)],foreground=[('readonly',fg)],background=[('active','#293e4c')],bordercolor=[('focus',accent)])
    root.option_add('*TCombobox*Listbox.background',surface)
    root.option_add('*TCombobox*Listbox.foreground',fg)
    root.option_add('*TCombobox*Listbox.selectBackground',accent)
    root.option_add('*TCombobox*Listbox.selectForeground',bg)
    style.configure('TButton',background=surface,foreground=fg,borderwidth=0,padding=(8,8),focusthickness=1,focuscolor=accent)
    style.map('TButton',foreground=[('disabled','#91a0aa'),('!disabled',fg)],background=[('pressed','#334b5a'),('active','#293e4c')])
    style.configure('Export.TButton',background=accent,foreground=bg,font=('Microsoft YaHei UI',11,'bold'),padding=(8,10))
    style.map('Export.TButton',foreground=[('!disabled',bg)],background=[('pressed','#83bdad'),('active','#bae6da')])
    frame=ttk.Frame(root,padding=11);frame.pack(fill='both',expand=True)
    frame.columnconfigure(1,weight=1)
    saves=find_saves();path=tk.StringVar(value=str(saves[0]) if saves else '')
    name=tk.StringVar(value=steam_name(path.get()) or 'PLAYER')
    character=tk.StringVar(value='自动（当前角色）')
    constants_state={'values':None}
    catalog=load_catalog()
    def choose():
        current=Path(path.get()) if path.get() else Path.home()
        directory=current if current.is_dir() else current.parent
        while not directory.is_dir() and directory.parent!=directory:directory=directory.parent
        selected=filedialog.askopenfilename(initialdir=str(directory),filetypes=[('In Falsus 存档','*.sav')])
        if selected:
            previous=steam_name(path.get()) or 'PLAYER'
            path.set(selected)
            path_entry.xview_moveto(1)
            if name.get() in (previous,'PLAYER',''):name.set(steam_name(selected) or 'PLAYER')
    ttk.Label(frame,text='存档').grid(row=0,column=0,sticky='w',padx=(0,6))
    path_entry=ttk.Entry(frame,textvariable=path,width=1)
    path_entry.grid(row=0,column=1,sticky='ew',padx=(0,4));path_entry.xview_moveto(1)
    ttk.Button(frame,text='选择文件',command=choose).grid(row=0,column=2,sticky='ew')
    ttk.Label(frame,text='名字').grid(row=1,column=0,sticky='w',pady=9)
    ttk.Entry(frame,textvariable=name,width=1).grid(row=1,column=1,columnspan=2,sticky='ew',pady=9)
    ttk.Label(frame,text='头像').grid(row=2,column=0,sticky='w')
    ttk.Combobox(frame,textvariable=character,width=1,values=['自动（当前角色）',*CHARACTERS],state='readonly').grid(row=2,column=1,columnspan=2,sticky='ew')
    mode=tk.StringVar(value='B30')
    ttk.Label(frame,text='类型').grid(row=3,column=0,sticky='w',pady=(9,0))
    mode_box=ttk.Combobox(frame,textvariable=mode,values=['B30','分数图'],state='readonly',width=1)
    mode_box.grid(row=3,column=1,columnspan=2,sticky='ew',pady=(9,0))
    filter_frame=ttk.Frame(frame);filter_frame.grid(row=4,column=1,columnspan=2,sticky='ew',pady=(9,0))
    difficulty_vars={d:tk.BooleanVar(value=True) for d in DIFFS}
    filter_controls=[]
    for col,(diff,(label,_)) in enumerate(DIFFS.items()):
        control=ttk.Checkbutton(filter_frame,text=label,variable=difficulty_vars[diff])
        control.grid(row=0,column=col,padx=(0,12));filter_controls.append(control)
    levels=sorted({c['level'] for song in catalog['songs'] for c in song['charts']})
    min_level=tk.StringVar(value=str(min(levels)));max_level=tk.StringVar(value=str(max(levels)))
    ttk.Label(filter_frame,text='等级').grid(row=1,column=0,sticky='w',pady=(6,0))
    for col,var in [(1,min_level),(3,max_level)]:
        control=ttk.Combobox(filter_frame,textvariable=var,values=levels,width=5,state='readonly')
        control.grid(row=1,column=col,sticky='ew',pady=(6,0));filter_controls.append(control)
    ttk.Label(filter_frame,text='至').grid(row=1,column=2,pady=(6,0))
    def sync_filters(*_):
        for control in filter_controls:
            control.configure(state=('readonly' if isinstance(control,ttk.Combobox) else 'normal') if mode.get()=='分数图' else 'disabled')
    mode.trace_add('write',sync_filters);sync_filters()
    def make_template():
        output=filedialog.asksaveasfilename(defaultextension='.csv',initialfile='InFalsus-定数表.csv',filetypes=[('CSV 定数表','*.csv')])
        if not output:return
        try:
            validate_output(output,path.get(),'.csv')
            Path(output).write_text(constants_template(catalog),encoding='utf-8-sig',newline='')
            messagebox.showinfo('已生成','定数表模板已保存，修改“定数”列后导入即可。')
        except Exception as e:messagebox.showerror('生成失败',str(e))
    def import_constants():
        selected=filedialog.askopenfilename(filetypes=[('CSV 定数表','*.csv')])
        if not selected:return
        try:
            values=load_constants(selected,catalog)
            constants_state['values']=values
            import_button.configure(text='导入定数表 ✓')
            messagebox.showinfo('已导入',f'已导入 {len(values)} 张谱面定数，本次运行的导出将使用该表。')
        except Exception as e:messagebox.showerror('导入失败',str(e))
    constants_bar=ttk.Frame(frame)
    constants_bar.grid(row=5,column=1,columnspan=2,sticky='ew',pady=(11,0))
    constants_bar.columnconfigure(0,weight=1);constants_bar.columnconfigure(1,weight=1)
    ttk.Button(constants_bar,text='生成定数表模板',command=make_template).grid(row=0,column=0,sticky='ew',padx=(0,4))
    import_button=ttk.Button(constants_bar,text='导入定数表',command=import_constants)
    import_button.grid(row=0,column=1,sticky='ew')
    def export():
        try:
            records=load_records(path.get());ranked,_=rank_records(records,catalog,constants_state['values'])
            if not ranked:raise InputError('没有找到可排名的正式曲目成绩。')
            selected=character.get()
            if selected not in CHARACTERS:selected=getattr(records,'selected_character',None) or 'Nia'
            output=filedialog.asksaveasfilename(defaultextension='.png',initialfile='InFalsus-Player-Bests.png',filetypes=[('PNG 图片','*.png')])
            if not output:return
            validate_output(output,path.get())
            score_mode=mode.get()=='分数图'
            diffs={d for d,v in difficulty_vars.items() if v.get()}
            if score_mode:
                filtered=filter_scores(ranked,diffs,int(min_level.get()),int(max_level.get()))
                if not filtered:raise InputError('筛选范围内没有成绩。')
                count=len(score_pages(filtered))
                existing=[Path(output).with_name(f'{Path(output).stem}-{i+1:02}.png') for i in range(count)] if count>1 else []
                if any(p.exists() for p in existing) and not messagebox.askyesno('覆盖图片','部分分页图片已存在，是否覆盖？'):return
            paths=export_images(ranked,catalog,output,name.get(),selected,score_mode,diffs,int(min_level.get()),int(max_level.get()))
            messagebox.showinfo('已导出',f'已保存 {len(paths)} 张图片。')
        except Exception as e:messagebox.showerror('导出失败',str(e))
    ttk.Button(frame,text='导出 PNG',style='Export.TButton',command=export).grid(row=6,column=1,columnspan=2,sticky='ew',pady=(11,0))
    root.update_idletasks()
    height=frame.winfo_reqheight()
    root.geometry(f'{height*3}x{height}')
    root.mainloop()


def main():
    p=argparse.ArgumentParser(description='In Falsus Player Bests')
    p.add_argument('--input',type=Path)
    p.add_argument('--output',type=Path)
    p.add_argument('--constants',type=Path)
    p.add_argument('--mode',choices=['b30','scores'],default='b30')
    p.add_argument('--difficulty',choices=[v[0] for v in DIFFS.values()],action='append')
    p.add_argument('--min-level',type=int)
    p.add_argument('--max-level',type=int)
    p.add_argument('--name')
    p.add_argument('--character',choices=CHARACTERS)
    args=p.parse_args()
    if not args.input:
        gui();return
    if not args.output:p.error('--output is required')
    try:
        validate_output(args.output,args.input)
        catalog=load_catalog();rows=load_records(args.input)
        constants=load_constants(args.constants,catalog) if args.constants else None
        ranked,_=rank_records(rows,catalog,constants)
        if not ranked:raise InputError('没有有效的正式曲目成绩。')
        selected=args.character or getattr(rows,'selected_character',None) or 'Nia'
        display_name=args.name or steam_name(args.input) or 'PLAYER'
        diffs=None if args.difficulty is None else {d for d,v in DIFFS.items() if v[0] in args.difficulty}
        export_images(ranked,catalog,args.output,display_name,selected,args.mode=='scores',diffs,args.min_level,args.max_level)
    except (InputError,OSError,UnicodeError) as e:p.exit(1,str(e)+'\n')

if __name__=='__main__':
    main()
