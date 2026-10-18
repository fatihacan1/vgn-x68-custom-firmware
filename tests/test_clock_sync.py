from contextlib import contextmanager
from datetime import datetime,timezone,timedelta
from pathlib import Path
import unittest
from x68.settings import SettingsClient
from x68.settings import settings_packet
from x68.firmware import LIVE_CLOCK_CRC
from x68.protocol import ProtocolError

class MemoryClock(SettingsClient):
    def __init__(self):
        self.data=bytes(range(64));self.writes=[]
    @contextmanager
    def _device(self):yield object()
    @contextmanager
    def _transaction(self,device):yield
    def _read(self,device,command,length):return self.data
    def _write(self,device,command,data):self.data=data;self.writes.append((command,data))
    def _backup(self,kind,data):return 'mock-backup.json'

class ClockTests(unittest.TestCase):
    def test_live_clock_is_one_ram_command_without_parameter_write(self):
        client=MemoryClock();sent=[];client._exchange=lambda device,command,**kw:sent.append((command,kw))
        result=client.sync_clock_live(LIVE_CLOCK_CRC,datetime(2026,10,18,15,2,9))
        self.assertEqual(sent,[(24,{'data':bytes.fromhex('09 02 15 07 18 10')})])
        self.assertEqual(client.writes,[]);self.assertFalse(result['persistent_flash_write'])
    def test_live_clock_rejects_stock_without_io(self):
        client=MemoryClock()
        with self.assertRaises(ProtocolError):client.sync_clock_live('14961BE6')
        self.assertEqual(client.writes,[])
    def test_live_clock_requires_exact_six_bytes(self):
        for size in (0,5,7,56):
            with self.assertRaises(ProtocolError):settings_packet(24,data=bytes(size))
    def test_sync_changes_only_six_verified_bcd_fields(self):
        client=MemoryClock();before=client.data
        result=client.sync_clock(datetime(2026,10,18,13,48,1,tzinfo=timezone(timedelta(hours=3))))
        self.assertEqual(client.data[35:41],bytes.fromhex('01 48 13 07 18 10'))
        self.assertEqual(client.data[:35],before[:35]);self.assertEqual(client.data[41:],before[41:])
        self.assertEqual(client.writes[0][0],6)
        self.assertTrue(result['rtc_running_requires_physical_confirmation'])
