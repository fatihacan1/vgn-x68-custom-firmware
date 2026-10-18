"""Execute the actual RV32 display replacement in Unicorn, with hardware stubs.

Does not access a keyboard. Checks framebuffer bounds, callee-saved registers,
the RAM-to-flash redirect, busy paths and native/host drawing equivalence.
"""
from pathlib import Path
import argparse,ctypes,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from x68.firmware import validate_native_screen
from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.riscv_const import *

def verify(payload,stock,folder):
 validate_native_screen(payload,stock)
 dll=ctypes.CDLL(str((folder/'screen-host.dll').resolve()))
 (ctypes.c_ubyte*30720).in_dll(dll,'background')[:]=payload[0x31664:0x38e64]
 regs=[UC_RISCV_REG_S0,UC_RISCV_REG_S1,UC_RISCV_REG_S2,UC_RISCV_REG_S3,UC_RISCV_REG_S4,UC_RISCV_REG_S5,UC_RISCV_REG_S6,UC_RISCV_REG_S7,UC_RISCV_REG_S8,UC_RISCV_REG_S9,UC_RISCV_REG_S10,UC_RISCV_REG_S11]
 results=[]
 for case,seconds,blocked in [('draw-even',0x42,False),('draw-odd',0x42,False),('next-frame-mode-zero',0x42,False),('pending-transfer',0x42,True),('battery-42',0x42,False),('battery-100',0x42,False),('battery-invalid',0x42,False)]:
  emu=Uc(UC_ARCH_RISCV,UC_MODE_RISCV32);emu.mem_map(0,0x100000);emu.mem_map(0x20000000,0x40000)
  emu.mem_write(0x20000000,payload);emu.mem_write(0x1200,payload[0x12b0:0xa0b4])
  emu.mem_map(0x80140000,0x1000)
  tick=20000000 if case=='draw-odd' else 16000000
  emu.mem_write(0x80140200,tick.to_bytes(4,'little'))
  emu.mem_write(0x80573,bytes([0x42,0x35,0x03,7,0x18,0x10]))
  level={'battery-42':42,'battery-100':100,'battery-invalid':255}.get(case,0)
  emu.mem_write(0x80b70,bytes([level]));ctypes.c_ubyte.in_dll(dll,'battery_level').value=level
  emu.mem_write(0x819e0,b'\xaa'*30720);emu.mem_write(0x80b6c,(65535).to_bytes(4,'little'))
  emu.mem_write(0x80c9a,bytes([128 if blocked or case=='next-frame-mode-zero' else 0]))
  emu.reg_write(UC_RISCV_REG_GP,0x80800);emu.reg_write(UC_RISCV_REG_SP,0x9ff00);emu.reg_write(UC_RISCV_REG_RA,0x10000)
  saved={r:0x12340000+i for i,r in enumerate(regs)}
  for r,v in saved.items():emu.reg_write(r,v)
  rtc=[0,0,seconds,0x35,0x03,0x18,0,0x10,0x26]
  calls=[];writes=[]
  def hardware(uc,address,size,user):
   if address==0x6eac:
    calls.append('original-lcd-transport')
    # Mode-zero's real service consumes display-request bit 4 before transfer.
    if not blocked and uc.mem_read(0x80d20,1)[0]&16:
     uc.mem_write(0x80d20,bytes([uc.mem_read(0x80d20,1)[0]&~16]))
     uc.mem_write(0x80c9a,bytes([uc.mem_read(0x80c9a,1)[0]&~128]))
    uc.reg_write(UC_RISCV_REG_PC,uc.reg_read(UC_RISCV_REG_RA))
   elif address==0x2000f4f4:
    reg=uc.reg_read(UC_RISCV_REG_A0)
    if reg not in (2,3,4,5,7):raise AssertionError('Unexpected RTC register')
    calls.append('rtc-'+str(reg));uc.reg_write(UC_RISCV_REG_A0,rtc[reg]);uc.reg_write(UC_RISCV_REG_PC,uc.reg_read(UC_RISCV_REG_RA))
  def write(uc,access,address,size,value,user):
   allowed=any(lo<=address and address+size<=hi for lo,hi in [(0x819e0,0x891e0),(0x9f000,0x9ff00),(0x80b80,0x80b87),(0x80d8c,0x80d93),(0x80c9a,0x80c9b),(0x80d20,0x80d21),(0x80d82,0x80d83)])
   if not allowed:raise AssertionError(f'Out-of-scope write {address:08X}')
   writes.append(address)
  emu.hook_add(UC_HOOK_CODE,hardware);emu.hook_add(UC_HOOK_MEM_WRITE,write)
  emu.emu_start(0x7110,0x10000,count=2000000)
  assert emu.reg_read(UC_RISCV_REG_PC)==0x10000,'Renderer did not return'
  assert emu.reg_read(UC_RISCV_REG_SP)==0x9ff00,'Stack was not restored'
  assert all(emu.reg_read(r)==v for r,v in saved.items()),'Callee-saved register changed'
  actual=bytes(emu.mem_read(0x819e0,30720))
  if blocked:assert actual==b'\xaa'*30720,'Busy framebuffer changed'
  else:
   (ctypes.c_ubyte*9).in_dll(dll,'rtc')[:]=rtc;ctypes.c_uint.in_dll(dll,'tick').value=tick;dll.render()
   expected=bytes((ctypes.c_ubyte*30720).in_dll(dll,'framebuffer'))
   assert actual==expected,'RV32 and host framebuffer differ'
   assert emu.mem_read(0x80c9a,1)[0]&128,'New frame not marked pending'
   # A real second call, retaining target RAM state, must advance the clock.
   tick+=16000000;emu.mem_write(0x80140200,tick.to_bytes(4,'little'))
   emu.reg_write(UC_RISCV_REG_RA,0x10000);emu.emu_start(0x7110,0x10000,count=2000000)
   rtc[2]=0x43;(ctypes.c_ubyte*9).in_dll(dll,'rtc')[:]=rtc
   ctypes.c_uint.in_dll(dll,'tick').value=tick;dll.render()
   assert bytes(emu.mem_read(0x819e0,30720))==bytes((ctypes.c_ubyte*30720).in_dll(dll,'framebuffer')),'Second target frame did not advance'
  results.append({'case':case,'passed':True,'writes':len(writes),'hardware_calls':calls})
 # The new command is a register-preserving branch inside the stock dispatcher.
 bridge=int.from_bytes(payload[0x1e78c:0x1e790],'little')
 all_regs=[UC_RISCV_REG_RA,UC_RISCV_REG_T0,UC_RISCV_REG_T1,UC_RISCV_REG_T2,UC_RISCV_REG_T3,UC_RISCV_REG_T4,UC_RISCV_REG_T5,UC_RISCV_REG_T6,UC_RISCV_REG_A0,UC_RISCV_REG_A1,UC_RISCV_REG_A2,UC_RISCV_REG_A3,UC_RISCV_REG_A4,UC_RISCV_REG_A5,UC_RISCV_REG_A6,UC_RISCV_REG_A7]+regs
 for bad in (False,True):
  uc=Uc(UC_ARCH_RISCV,UC_MODE_RISCV32);uc.mem_map(0,0x100000);uc.mem_map(0x20000000,0x40000);uc.mem_write(0x20000000,payload)
  packet=bytearray([4,0,0,24,6,0,0,0,0x42,0x35,0x13,7,0x18,0x10])+bytearray(50)
  if bad:packet[8]=0x6a
  uc.mem_write(0x89400,bytes(packet));uc.mem_write(0x80573,b'\xaa'*6);uc.reg_write(UC_RISCV_REG_SP,0x9ff00)
  original={reg:0x12345600+i for i,reg in enumerate(all_regs)};original[UC_RISCV_REG_S0]=0x89400
  for reg,value in original.items():uc.reg_write(reg,value)
  def bridge_write(machine,access,address,size,value,user):
   assert any(lo<=address and address+size<=hi for lo,hi in [(0x9f000,0x9ff00),(0x80573,0x80579),(0x80d92,0x80d93),(0x89407,0x89408)]),f'Clock bridge wrote {address:08X}'
  uc.hook_add(UC_HOOK_MEM_WRITE,bridge_write);uc.emu_start(bridge,0x2001b8a0,count=100000)
  assert uc.reg_read(UC_RISCV_REG_PC)==0x2001b8a0
  assert all(uc.reg_read(reg)==value for reg,value in original.items()),'Clock bridge clobbered a register'
  assert uc.reg_read(UC_RISCV_REG_SP)==0x9ff00
  assert bytes(uc.mem_read(0x80573,6))==(b'\xaa'*6 if bad else bytes(packet[8:14]))
  results.append({'case':'ram-clock-invalid-bcd' if bad else 'ram-clock-valid','passed':True})
 # Diagnostic command: only output packet/stack may be written; no ADC trigger,
 # GPIO, calibration, cached indicator or scheduler state may be changed.
 if int.from_bytes(payload[0x1e790:0x1e794],'little')!=0x2001be74:
  for bad in (False,True):
   uc=Uc(UC_ARCH_RISCV,UC_MODE_RISCV32);uc.mem_map(0,0x100000);uc.mem_map(0x20000000,0x40000);uc.mem_map(0x80140000,0x1000)
   uc.mem_write(0x20000000,payload)
   packet=bytearray([4,0,0,25,47 if bad else 48,0,0,0])+bytearray(56)
   uc.mem_write(0x89400,bytes(packet));uc.mem_write(0x80b70,b'\x2a');uc.mem_write(0x808d3,b'\x23')
   uc.mem_write(0x80140320,b'\x10');uc.mem_write(0x80140310,b'\x08')
   uc.mem_write(0x80d9c,bytes(range(16)));uc.mem_write(0x1130,bytes(range(10)))
   uc.reg_write(UC_RISCV_REG_SP,0x9ff00)
   original={reg:0x12345600+i for i,reg in enumerate(all_regs)};original[UC_RISCV_REG_S0]=0x89400
   for reg,value in original.items():uc.reg_write(reg,value)
   def diagnostic_writes(machine,access,address,size,value,user):
    assert any(lo<=address and address+size<=hi for lo,hi in [(0x9f000,0x9ff00),(0x89407,0x89438)]),f'Diagnostic wrote {address:08X}'
   uc.hook_add(UC_HOOK_MEM_WRITE,diagnostic_writes)
   entry=int.from_bytes(payload[0x1e790:0x1e794],'little');uc.emu_start(entry,0x2001b8a0,count=100000)
   assert uc.reg_read(UC_RISCV_REG_PC)==0x2001b8a0
   assert all(uc.reg_read(reg)==value for reg,value in original.items())
   assert uc.reg_read(UC_RISCV_REG_SP)==0x9ff00
   assert bytes(uc.mem_read(0x80b70,1))==b'\x2a'
   if bad:assert uc.mem_read(0x89407,1)==b'\xff' and uc.mem_read(0x89408,48)==bytes(48)
   else:
    raw=bytes(uc.mem_read(0x89408,48));assert raw[:8]==b'XBD\x01\x2a\x23\x10\x08'
    assert raw[12:28]==bytes(range(16)) and raw[28:38]==bytes(range(10))
   results.append({'case':'diagnostic-invalid-length' if bad else 'diagnostic-readonly-snapshot','passed':True})
 # Media reader: existing stock physical-flash callback, reads only A2000..DE000.
 uc=Uc(UC_ARCH_RISCV,UC_MODE_RISCV32);uc.mem_map(0,0x100000);uc.mem_map(0x20000000,0x40000);uc.mem_map(0x80140000,0x1000)
 uc.mem_write(0x20000000,payload);uc.mem_write(0x1200,payload[0x12b0:0xa0b4]);uc.mem_write(0xbb4,(0x11000).to_bytes(4,'little'));uc.mem_write(0x11000,bytes.fromhex('67 80 00 00'))
 uc.mem_write(0x80571,bytes([4,2]));uc.mem_write(0x8057a,(125).to_bytes(2,'little'))
 uc.reg_write(UC_RISCV_REG_SP,0x9ff00);uc.reg_write(UC_RISCV_REG_GP,0x80800)
 read_calls=[]
 def media_hardware(machine,address,size,user):
  if address==0x6eac:
   machine.mem_write(0x80c9a,b'\0');machine.reg_write(UC_RISCV_REG_PC,machine.reg_read(UC_RISCV_REG_RA))
  elif address==0x11000:
   src=machine.reg_read(UC_RISCV_REG_A0);length=machine.reg_read(UC_RISCV_REG_A1);dest=machine.reg_read(UC_RISCV_REG_A2)
   assert 0xa2000<=src and src+length<=0xde000 and length==30720 and dest==0x819e0
   index=(src-0xa2000)//30720;machine.mem_write(dest,bytes([index+1])*length);read_calls.append(src)
   machine.reg_write(UC_RISCV_REG_PC,machine.reg_read(UC_RISCV_REG_RA))
 def media_writes(machine,access,address,size,value,user):
  assert any(lo<=address and address+size<=hi for lo,hi in [(0x9f000,0x9ff00),(0x80c9a,0x80c9b),(0x80d20,0x80d21),(0x80d49,0x80d4a),(0x80d82,0x80d83)]),f'Media wrote {address:08X}'
 uc.hook_add(UC_HOOK_CODE,media_hardware);uc.hook_add(UC_HOOK_MEM_WRITE,media_writes)
 for ticks,index in [(0,0),(2000000,1)]:
  uc.mem_write(0x80140200,ticks.to_bytes(4,'little'));uc.reg_write(UC_RISCV_REG_RA,0x10000);uc.emu_start(0x7110,0x10000,count=100000)
  assert bytes(uc.mem_read(0x819e0,30720))==bytes([index+1])*30720
 assert read_calls==[0xa2000,0xa9800]
 results.append({'case':'two-media-frames-bounded-stock-flash-read','passed':True})
 return {'hardware_stubs':True,'device_test':False,'cases':results,'charging_gpio_flash_writes':False}

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('stock',type=Path);p.add_argument('--folder',type=Path,default=ROOT/'reports/native-desktop');a=p.parse_args()
 result=verify((a.folder/'x68-v0113-pixel-desktop.bin').read_bytes(),a.stock.read_bytes(),a.folder)
 (a.folder/'emulation-result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
