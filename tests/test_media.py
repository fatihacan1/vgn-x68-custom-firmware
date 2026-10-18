import tempfile,unittest
from contextlib import contextmanager
from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path
from PIL import Image
from x68.media import convert_media,rgb565,media_packet,MAX_BYTES,upload_media,PreparedMedia
from x68.protocol import ProtocolError
from x68.firmware import LIVE_CLOCK_CRC

class MemoryMedia:
 def __init__(self,crc=LIVE_CLOCK_CRC,short=False):
  self.client=SimpleNamespace(last_query=-float('inf'),query_version=lambda:{'reported_crc':crc})
  self.data=bytearray(range(64));self.data[33]=4;self.before=bytes(self.data);self.writes=[];self.packets=[];self.short=short
 @contextmanager
 def _device(self, wireless=True):yield self
 @contextmanager
 def _transaction(self,device):yield
 def _read(self,device,command,length):return bytes(self.data)
 def _write(self,device,command,data):self.writes.append(bytes(data));self.data[:]=data
 def _backup(self,kind,data):return 'mock-backup.json'
 def write(self,packet):self.packets.append(packet);return 1 if self.short else 64
 def read(self,length,timeout):return self.packets[-1]

class MediaTests(unittest.TestCase):
 def test_upload_exits_old_player_and_preserves_unrelated_parameters(self):
  client=MemoryMedia();media=PreparedMedia('generated-test',[Image.new('RGB',(160,96),'red')],100,1,100,'Crop')
  with tempfile.TemporaryDirectory() as folder,patch('x68.media.time.sleep'):
   result=upload_media(client,media,folder)
   self.assertEqual(result['phase'],'complete');self.assertFalse(result['flash_readback_verified'])
   self.assertEqual(client.writes[0][33],0);self.assertEqual(client.writes[-1][33:35],bytes([4,1]))
   self.assertEqual(b''.join(p[8:8+p[4]] for p in client.packets),media.data)
   self.assertEqual(int.from_bytes(client.packets[0][5:8],'little'),0)
   for i in set(range(64))-{33,34,42,43}:self.assertEqual(client.data[i],client.before[i])
 def test_short_write_stops_without_retry_or_selecting_partial_media(self):
  client=MemoryMedia(short=True);media=PreparedMedia('generated-test',[Image.new('RGB',(160,96))],100,1,100,'Crop')
  with tempfile.TemporaryDirectory() as folder,patch('x68.media.time.sleep'):
   with self.assertRaises(ProtocolError):upload_media(client,media,folder)
   self.assertEqual(len(client.packets),1);self.assertEqual(client.data[33],0)
 def test_stock_is_refused_before_media_or_parameter_write(self):
  client=MemoryMedia(crc='14961BE6');media=PreparedMedia('generated-test',[Image.new('RGB',(160,96))],100,1,100,'Crop')
  with tempfile.TemporaryDirectory() as folder:
   with self.assertRaises(ProtocolError):upload_media(client,media,folder)
  self.assertEqual(client.writes,[]);self.assertEqual(client.packets,[])
 def test_rgb565_byte_order(self):
  im=Image.new('RGB',(3,1));im.putdata([(255,0,0),(0,255,0),(0,0,255)])
  self.assertEqual(rgb565(im),bytes.fromhex('f80007e0001f'))
 def test_static_transparency_and_letterbox(self):
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'image.png';Image.new('RGBA',(80,80),(255,0,0,0)).save(p)
   media=convert_media(p,'Fit',background='#0000ff')
   self.assertEqual(len(media.data),30720);self.assertEqual(media.frames[0].size,(160,96))
   self.assertEqual(media.frames[0].getpixel((80,48)),(0,0,255))
   self.assertEqual(media.frames[0].getpixel((0,0)),(0,0,255))
 def test_gif_samples_whole_timeline_not_first_eight(self):
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'animation.gif';frames=[Image.new('RGB',(20,20),(i*16,0,0)) for i in range(16)]
   frames[0].save(p,save_all=True,append_images=frames[1:],duration=100,loop=0)
   media=convert_media(p)
   self.assertEqual(media.source_frames,16);self.assertEqual(len(media.frames),8)
   self.assertEqual(media.period_ms,200);self.assertEqual(len(media.data),245760)
   self.assertGreater(media.frames[-1].getpixel((80,48))[0],200)
 def test_packet_bounds_and_checksum(self):
  for offset,data in [(-1,b'x'),(MAX_BYTES,b'x'),(0,b''),(0,b'x'*57)]:
   with self.assertRaises(ProtocolError):media_packet(offset,data)
  p=media_packet(MAX_BYTES-2,b'ab');self.assertEqual(p[3],33)
  self.assertEqual(int.from_bytes(p[5:8],'little'),MAX_BYTES-2)
  self.assertEqual(int.from_bytes(p[1:3],'little'),sum(p[3:])&65535)
 def test_invalid_fitting_mode_rejected(self):
  with self.assertRaises(ValueError):convert_media('unused','invented')
