"""Replace verified native display assets, not the custom-image bank.

Requires Pillow only for building. Does not access a keyboard. All firmware
instructions, pointers and asset dimensions stay unchanged. Original stock
payload is supplied by the owner; it is not distributed with this project.
"""
from pathlib import Path
import argparse
from datetime import datetime
import hashlib
import json
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from x68.firmware import validate_v0113, validate_visual_patch
from PIL import Image, ImageDraw, ImageFont

FONT_DIR = Path('C:/Windows/Fonts')


def font(size, bold=False):
    return ImageFont.truetype(str(FONT_DIR/('tahomabd.ttf' if bold else 'tahoma.ttf')),size)


def glyph(text, width, height, size, bold=False):
    image = Image.new('1',(width,height),0)
    draw = ImageDraw.Draw(image)
    typeface = font(size,bold)
    box = draw.textbbox((0,0),text,font=typeface)
    draw.text(((width-(box[2]-box[0]))//2-box[0],
               (height-(box[3]-box[1]))//2-box[1]),text,font=typeface,fill=1)
    return image


def windows_flag(draw, x, y, unit=9):
    for row, colors in enumerate([('#ed4b23','#66b61e'),('#2488da','#f4c51d')]):
        for col,color in enumerate(colors):
            dx=x+col*(unit+2);dy=y+row*(unit+2)
            draw.polygon([(dx,dy+2-col*2),(dx+unit,dy-col*2),
                          (dx+unit,dy+unit-col*2),(dx,dy+unit+2-col*2)],fill=color)


def boot_image():
    image = Image.new('RGB',(160,96),'#000000')
    draw = ImageDraw.Draw(image)
    windows_flag(draw,67,8,11)
    draw.text((29,40),'Windows',font=font(20),fill='white')
    draw.text((113,39),'xp',font=font(12,True),fill='#f57b23')
    draw.text((49,64),'X68 Keyboard',font=font(9),fill='#c6c6c6')
    draw.rounded_rectangle((48,81,112,90),radius=2,outline='#909090',width=1)
    for x in (70,76,82):
        draw.rectangle((x,83,x+4,88),fill='#2f72d7')
        draw.line((x,83,x+4,83),fill='#91b5f0')
    return image


def brand_strip():
    image=Image.new('RGB',(160,32),'#000000')
    draw=ImageDraw.Draw(image)
    windows_flag(draw,14,6,7)
    draw.text((39,5),'Windows',font=font(17),fill='white')
    draw.text((113,5),'xp',font=font(11,True),fill='#f57b23')
    return image


def rgb565_be(image):
    result=bytearray()
    for r,g,b in image.convert('RGB').getdata():
        value=(r>>3)<<11|(g>>2)<<5|(b>>3)
        result.extend(value.to_bytes(2,'big'))
    return bytes(result)


def build(stock, output):
    validate_v0113(stock)
    output.mkdir(parents=True,exist_ok=True)
    patched=bytearray(stock)
    assets=[]
    def put(name,offset,data):
        patched[offset:offset+len(data)]=data
        assets.append({'name':name,'offset':f'{offset:08X}','bytes':len(data),
                       'sha256':hashlib.sha256(data).hexdigest()})
    for i,text in enumerate('0123456789'):
        put('date_'+text,0x26620+i*16,glyph(text,8,16,12).tobytes())
        put('time_'+text,0x270b8+i*62,glyph(text,16,31,27).tobytes())
        put('seconds_'+text,0x27358+i*16,glyph(text,8,16,12).tobytes())
    for i,text in enumerate(['JAN.','FEB.','MAR.','APR.','MAY','JUN.','JUL.','AUG.','SEP.','OCT.','NOV.','DEC.']):
        put('month_'+text,0x266c0+i*48,glyph(text,24,16,9,True).tobytes())
    for i,text in enumerate(['MON','TUE','WED','THU','FRI','SAT','SUN']):
        put('weekday_'+text,0x27418+i*84,glyph(text,48,14,11,True).tobytes())
    put('colon',0x273f8,glyph(':',8,32,27).tobytes())
    boot=boot_image()
    put('native_vertical_logo',0x27664,rgb565_be(boot))
    put('native_brand_strip',0x2ee64,rgb565_be(brand_strip()))
    put('native_boot_logo',0x31664,rgb565_be(boot))
    patched[-4:] = (zlib.crc32(patched[:-4])^0xffffffff).to_bytes(4,'little')
    validate_visual_patch(bytes(patched),stock)
    destination=output/'x68-v0113-xp-defaults.bin'
    destination.write_bytes(patched)
    boot.save(output/'boot-preview.png')
    # Offline mock of the existing dynamic layout. Values are preview inputs,
    # not values read from the keyboard. The labels are the actual patched masks.
    native=Image.new('RGB',(160,96),'black')
    draw=ImageDraw.Draw(native)
    draw.text((7,5),'USB',font=font(10,True),fill='white')
    draw.text((61,5),'CAPS',font=font(9),fill='#888888')
    draw.rectangle((131,7,152,15),outline='white')
    draw.rectangle((153,9,155,13),fill='white')
    for text,x in [('0',8),('3',24),(':',40),('1',48),('5',64)]:
        mask=glyph(text,8 if text==':' else 16,32 if text==':' else 31,27)
        native.paste('white',(x,44),mask)
    for text,x in [('4',80),('2',88)]:native.paste('white',(x,57),glyph(text,8,16,12))
    native.paste('white',(108,42),glyph('OCT.',24,16,9,True))
    native.paste('white',(132,42),glyph('1',8,16,12))
    native.paste('white',(140,42),glyph('8',8,16,12))
    native.paste('white',(106,62),glyph('SUN',48,14,11,True))
    native.save(output/'native-clock-preview.png')
    sheet=Image.new('RGB',(720,340),'#263044');sd=ImageDraw.Draw(sheet)
    sd.text((20,10),'OFFLINE PREVIEW - native asset replacement',fill='white')
    sheet.paste(boot.resize((320,192),Image.Resampling.NEAREST),(20,50))
    sheet.paste(native.resize((320,192),Image.Resampling.NEAREST),(380,50))
    sd.text((20,260),'Default boot / logo',fill='white')
    sd.text((380,260),'Existing clock layout, English / Tahoma',fill='white')
    sd.text((20,300),'Clock sample values are preview inputs. No charging repair is implied.',fill='white')
    sheet.save(output/'xp-native-preview.png')
    manifest={'built_at':datetime.now().astimezone().isoformat(),
              'stock_sha256':hashlib.sha256(stock).hexdigest(),
              'patched_sha256':hashlib.sha256(patched).hexdigest(),
              'patched_crc':f'{int.from_bytes(patched[-4:],"little"):08X}',
              'payload_bytes':len(patched),'assets':assets,
              'instructions_unchanged':True,'custom_image_bank_used':False,
              'note':'Changes default native assets. Screen layout and charging logic unchanged.'}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return destination,manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stock',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'reports'/'xp-defaults')
    args=parser.parse_args()
    file,manifest=build(args.stock.read_bytes(),args.output)
    print(json.dumps({'payload':str(file),'sha256':manifest['patched_sha256'],'crc':manifest['patched_crc']}))
