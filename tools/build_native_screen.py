"""Build one native pixel desktop, replacing the original screen dispatcher.

Uses the owner's exact V0113 payload; never accesses USB. LLVM and Pillow are
build-time dependencies. The source C renderer is also run as a host DLL to
produce previews from the identical drawing code.
"""
from pathlib import Path
import argparse, ctypes, hashlib, json, subprocess, sys, zlib
from datetime import datetime
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from x68.firmware import validate_v0113
from PIL import Image, ImageDraw

PIXEL_FONT={
 'A':[14,17,17,31,17,17,17],'B':[30,17,17,30,17,17,30],
 'C':[15,16,16,16,16,16,15],'D':[30,17,17,17,17,17,30],
 'E':[31,16,16,30,16,16,31],'F':[31,16,16,30,16,16,16],
 'G':[15,16,16,23,17,17,15],'H':[17,17,17,31,17,17,17],
 'I':[14,4,4,4,4,4,14],'K':[17,18,20,24,20,18,17],
 'L':[16,16,16,16,16,16,31],'M':[17,27,21,21,17,17,17],
 'N':[17,25,21,19,17,17,17],'O':[14,17,17,17,17,17,14],
 'P':[30,17,17,30,16,16,16],'R':[30,17,17,30,20,18,17],
 'S':[15,16,16,14,1,1,30],'T':[31,4,4,4,4,4,4],
 'U':[17,17,17,17,17,17,14],'V':[17,17,17,17,17,10,4],
 'W':[17,17,17,21,21,27,17],'X':[17,17,10,4,10,17,17],
 'Y':[17,17,10,4,4,4,4],'0':[14,17,19,21,25,17,14],
 '1':[4,12,4,4,4,4,14],'6':[14,16,16,30,17,17,14],
 '8':[14,17,17,14,17,17,14],'.':[0,0,0,0,0,0,4],
 '-':[0,0,0,31,0,0,0],' ': [0]*7,
}
def label(draw,text,xy,color):
 x,y=xy
 for char in text:
  for row,bits in enumerate(PIXEL_FONT[char]):
   for col in range(5):
    if bits&(16>>col):draw.point((x+col,y+row),fill=color)
  x+=6

def desktop():
 im=Image.new('RGB',(160,96),'#211631');d=ImageDraw.Draw(im)
 d.rectangle((0,0,159,12),fill='#68518f')
 d.line((0,0,159,0),fill='#d9c4ff');d.line((0,12,159,12),fill='#100b1e')
 # Mini four-colour desktop icon.
 for x,y,c in [(4,3,'#eda6e8'),(8,3,'#b6f1d6'),(4,7,'#a999ef'),(8,7,'#f4d28e')]:d.rectangle((x,y,x+2,y+2),fill=c)
 label(d,'X68.EXE',(16,3),'#fff1fc')
 for x in (132,141,150):
  d.rectangle((x,3,x+6,9),fill='#a78bc2',outline='#ddc6f4')
 d.line((152,5,154,7),fill='#332045');d.line((154,5,152,7),fill='#332045')
 d.rectangle((4,17,155,79),fill='#171229',outline='#a88bd1')
 d.line((5,18,154,18),fill='#4e3c70')
 label(d,'CLOCK',(10,43),'#8d7ba7');label(d,'DAY-MO',(108,35),'#8d7ba7')
 # Pixel skyline and floating platforms, intentionally clear of live text.
 d.polygon([(5,72),(24,53),(35,64),(48,50),(69,72)],fill='#41315e')
 d.polygon([(29,72),(49,57),(68,73),(87,57),(102,72)],fill='#5d457f')
 for x,y in [(11,53),(89,48),(104,55),(132,58),(144,67)]:d.point((x,y),fill='#d2b1ec')
 d.rectangle((6,74,153,78),fill='#a18bc3');d.line((6,74,153,74),fill='#e2ccf6')
 for x in range(8,152,8):d.rectangle((x,77,x+3,78),fill='#67527f')
 d.rectangle((87,65,116,68),fill='#d8b3e4');d.line((87,65,116,65),fill='#f7d7f5')
 # Little mint pixel adventurer with lavender ears and a magenta scarf.
 d.rectangle((104,54,113,62),fill='#b7f1db');d.rectangle((104,51,106,55),fill='#b7f1db')
 d.rectangle((111,51,113,55),fill='#b7f1db');d.rectangle((107,62,113,64),fill='#a296dd')
 d.point((107,57),fill='#211631');d.point((112,57),fill='#211631')
 d.rectangle((104,60,114,61),fill='#e8a2d9');d.rectangle((114,61,118,62),fill='#e8a2d9')
 # Small d-pad / coin details.
 d.rectangle((17,64,20,72),fill='#e6b7ed');d.rectangle((14,67,23,69),fill='#e6b7ed')
 d.rectangle((132,62,135,68),fill='#f3d58b');d.line((133,63,133,67),fill='#fff3c0')
 d.rectangle((0,83,159,95),fill='#675087');d.line((0,83,159,83),fill='#d7b9ec')
 d.rectangle((3,86,43,93),fill='#a18ab5',outline='#dec9ed');label(d,'START',(8,87),'#291e3b')
 label(d,'PLAYER 1',(55,87),'#f0dff6')
 d.rectangle((116,86,156,93),fill='#332343');label(d,'READY',(121,87),'#b5efd6')
 return im

def rgb565(im):
 return b''.join((((r>>3)<<11)|((g>>2)<<5)|(b>>3)).to_bytes(2,'big') for r,g,b in im.getdata())
def decode(data):
 values=[int.from_bytes(data[i:i+2],'big') for i in range(0,len(data),2)]
 im=Image.new('RGB',(160,96));im.putdata([(((v>>11)&31)*255//31,((v>>5)&63)*255//63,(v&31)*255//31) for v in values]);return im
def redirect():
 # RAM 0x7110 -> flash 0x20027664, through t1, preserving the caller's ra.
 delta=0x20027664-0x7110; upper=(delta+0x800)>>12; low=delta-(upper<<12)
 return ((upper<<12)|(6<<7)|0x17).to_bytes(4,'little')+(((low&4095)<<20)|(6<<15)|0x67).to_bytes(4,'little')

def build(stock,out):
 validate_v0113(stock);out.mkdir(parents=True,exist_ok=True)
 llvm=Path('C:/Program Files/LLVM/bin');source=ROOT/'firmware/native_screen.c'
 subprocess.run([str(llvm/'clang.exe'),'--target=riscv32-unknown-elf','-march=rv32imc','-mabi=ilp32','-Os','-ffreestanding','-fno-builtin','-fno-stack-protector','-msmall-data-limit=0','-mno-relax','-c',str(source),'-o',str(out/'screen.o')],check=True)
 subprocess.run([str(llvm/'ld.lld.exe'),'-m','elf32lriscv','--entry=render','--defsym=stock_ack=0x2001b8a0','--section-start=.text=0x20027664','--section-start=.rodata=0x20028664',str(out/'screen.o'),'-o',str(out/'screen.elf')],check=True)
 subprocess.run([str(llvm/'llvm-objcopy.exe'),'-O','binary',str(out/'screen.elf'),str(out/'screen-code.bin')],check=True)
 dis=subprocess.run([str(llvm/'llvm-objdump.exe'),'-d',str(out/'screen.elf')],check=True,capture_output=True,text=True).stdout
 (out/'screen-disassembly.txt').write_text(dis,encoding='utf-8')
 code=(out/'screen-code.bin').read_bytes()
 if len(code)>0x2000:raise ValueError('Renderer exceeds its retired logo area')
 # render must be first; fail rather than redirect into an assumed symbol.
 symbols=subprocess.run([str(llvm/'llvm-nm.exe'),str(out/'screen.elf')],check=True,capture_output=True,text=True).stdout
 if '20027664 T render' not in symbols:raise ValueError('Renderer entry address differs')
 background=rgb565(desktop());patched=bytearray(stock)
 if patched[0x71c0:0x71c8]!=bytes.fromhex('79 71 06 d6 22 d4 26 d2'):raise ValueError('LCD entry differs')
 patched[0x71c0:0x71c8]=redirect()
 bridge=int(next(line.split()[0] for line in symbols.splitlines() if line.endswith(' T clock_bridge')),16)
 if stock[0x1e78c:0x1e790]!=(0x2001be74).to_bytes(4,'little'):raise ValueError('Clock command slot is not the verified unsupported handler')
 patched[0x1e78c:0x1e790]=bridge.to_bytes(4,'little')
 battery_bridge=int(next(line.split()[0] for line in symbols.splitlines() if line.endswith(' T battery_bridge')),16)
 if stock[0x1e790:0x1e794]!=(0x2001be74).to_bytes(4,'little'):raise ValueError('Battery diagnostic slot differs')
 patched[0x1e790:0x1e794]=battery_bridge.to_bytes(4,'little')
 patched[0x27664:0x2ee64]=bytes(0x7800)
 patched[0x27664:0x27664+len(code)]=code
 patched[0x2ee64:0x31664]=bytes(0x2800)
 patched[0x31664:0x38e64]=background
 patched[-4:]=(zlib.crc32(patched[:-4])^0xffffffff).to_bytes(4,'little')
 target=out/'x68-v0113-pixel-desktop.bin';target.write_bytes(patched)
 # Run the exact C drawing function on Windows with only hardware reads mocked.
 subprocess.run([str(llvm/'clang.exe'),'--target=x86_64-pc-windows-msvc','-DSCREEN_HOST','-Os','-ffreestanding','-fno-builtin','-fno-stack-protector','-c',str(source),'-o',str(out/'screen-host.obj')],check=True)
 subprocess.run([str(llvm/'lld-link.exe'),'/dll','/noentry','/nodefaultlib',str(out/'screen-host.obj'),'/out:'+str(out/'screen-host.dll')],check=True)
 dll=ctypes.CDLL(str((out/'screen-host.dll').resolve()))
 (ctypes.c_ubyte*30720).in_dll(dll,'background')[:]=background
 rtc=(ctypes.c_ubyte*9).in_dll(dll,'rtc');rtc[:]=[0,0,0x42,0x35,0x03,0x18,0,0x10,0x26]
 dll.render();frame=bytes((ctypes.c_ubyte*30720).in_dll(dll,'framebuffer'))
 im=decode(frame);im.save(out/'native-preview.png');im.resize((800,480),Image.Resampling.NEAREST).save(out/'native-preview-large.png')
 frames=[]
 for sec in (0x42,0x43):
  rtc[2]=sec;dll.render();frames.append(decode(bytes((ctypes.c_ubyte*30720).in_dll(dll,'framebuffer'))).resize((640,384),Image.Resampling.NEAREST))
 frames[0].save(out/'native-preview.gif',save_all=True,append_images=frames[1:],duration=1000,loop=0)
 manifest={'name':'Lavender Quest','version':'0.6.0','built_at':datetime.now().astimezone().isoformat(),'kind':'native_display_renderer','payload_sha256':hashlib.sha256(patched).hexdigest(),'payload_crc':patched[-4:][::-1].hex().upper(),'renderer_sha256':hashlib.sha256(code).hexdigest(),'renderer_bytes':len(code),'hook_hex':redirect().hex(),'clock_bridge':f'{bridge:08X}','battery_bridge':f'{battery_bridge:08X}','battery_diagnostic':'Read-only cached ADC/GPIO/threshold snapshot, command 19 hex, 48 bytes','stock_sha256':hashlib.sha256(stock).hexdigest(),'preview_uses_mock_rtc':True,'charge_logic_changed':False,'custom_image_bank_used_by_default':False,'media_optional':True,'ram_clock_command':'18','battery_badge':'Cached indicator at RAM 80B70, 0..100 only; invalid shows --; no charging status'}
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
 print(json.dumps(manifest));return target,manifest

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stock',type=Path);parser.add_argument('--output',type=Path,default=ROOT/'reports/native-desktop');args=parser.parse_args();build(args.stock.read_bytes(),args.output.resolve())
