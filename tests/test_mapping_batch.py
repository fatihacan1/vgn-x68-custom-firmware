from contextlib import contextmanager
import unittest
from x68.settings import SettingsClient,encode_key
from x68.protocol import ProtocolError

class MemoryMapping(SettingsClient):
 def __init__(self):
  self.mapping=bytearray(384);self.mapping[48:51]=encode_key('A');self.mapping[51:54]=encode_key('B');self.writes=[]
 @contextmanager
 def _device(self):yield object()
 def _read(self,device,command,size):return bytes(self.mapping)
 def _set_mapping(self,device,before,after):self.writes.append((before,after));self.mapping[:]=after;return 'mock-backup'

class MappingBatchTests(unittest.TestCase):
 def test_multiple_staged_keys_use_one_write_and_preserve_other_cells(self):
  c=MemoryMapping();before=bytes(c.mapping);result=c.remap_batch({16:'CTRL',17:'C'})
  self.assertEqual(len(c.writes),1);self.assertEqual(result['count'],2)
  self.assertEqual(c.mapping[:48],before[:48]);self.assertEqual(c.mapping[54:],before[54:])
  self.assertEqual(c.mapping[48:54],encode_key('CTRL')+encode_key('C'))
 def test_invalid_cell_rejects_entire_draft_before_any_write(self):
  c=MemoryMapping()
  with self.assertRaises(ProtocolError):c.remap_batch({16:'C',0:'D'})
  self.assertEqual(c.writes,[])
