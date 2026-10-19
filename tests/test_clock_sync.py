from contextlib import contextmanager
from datetime import datetime,timezone,timedelta
from pathlib import Path
import unittest
from x68.settings import SettingsClient
from x68.settings import settings_packet
from x68.firmware import LIVE_CLOCK_CRC, CLOCK_FORMAT_CRC, DEVICE_STATUS_CRC
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
    def test_live_status_firmware_keeps_twelve_hour_sync(self):
        client=MemoryClock();sent=[];client._exchange=lambda device,command,**kw:sent.append(kw['data'])
        client.sync_clock_live(DEVICE_STATUS_CRC,datetime(2026,10,20,13,2,9),hour_format=12)
        self.assertEqual(sent,[bytes.fromhex('09 02 93 02 20 10')])
    def test_twelve_hour_flag_keeps_24_hour_time_and_can_be_cleared(self):
        for hour in (0,1,11,12,13,23):
            client=MemoryClock();sent=[];client._exchange=lambda device,command,**kw:sent.append(kw['data'])
            moment=datetime(2026,10,20,hour,2,9)
            client.sync_clock_live(CLOCK_FORMAT_CRC,moment,hour_format=12)
            client.sync_clock_live(CLOCK_FORMAT_CRC,moment,hour_format=24)
            self.assertEqual(sent[0][2],sent[1][2]|128)
            self.assertEqual(sent[1][2],(hour//10)*16+hour%10)
            self.assertEqual(sent[0][:2]+sent[0][3:],sent[1][:2]+sent[1][3:])
            self.assertEqual(client.writes,[])
    def test_unsupported_format_never_reaches_device(self):
        for crc,receiver,fmt in ((LIVE_CLOCK_CRC,False,12),('receiver',True,12),(CLOCK_FORMAT_CRC,False,13)):
            client=MemoryClock();sent=[];client._exchange=lambda *a,**kw:sent.append(kw)
            with self.assertRaises(ProtocolError):client.sync_clock_live(crc,receiver=receiver,hour_format=fmt)
            self.assertEqual(sent,[])
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
