"""UI regression checks with timers cancelled before any HID operation."""
import tempfile,tkinter as tk,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from x68.desktop import Studio
from x68.battery import decode_battery

class StudioTests(unittest.TestCase):
 def setUp(self):
  try:self.root=tk.Tk()
  except tk.TclError as error:self.skipTest(str(error))
  self.root.withdraw();self.app=Studio(self.root,smoke=True)
  for timer in self.root.tk.call('after','info'):self.root.after_cancel(timer)
 def tearDown(self):
  if hasattr(self,'app'):self.app.close()
 def test_key_selection_and_staging_never_submit_device_work(self):
  a=self.app;a.submit=Mock();a.selected=16;a.target.set('A');a.stage_mapping()
  self.assertEqual(a.pending_mapping,{16:'A'});a.submit.assert_not_called()
  self.assertIn('(1)',a.mapping_send['text']);a.clear_mapping();a.submit.assert_not_called()
  self.assertEqual(str(a.mapping_send['state']),'disabled')
 def test_per_key_draft_cannot_accidentally_send_global_lighting(self):
  a=self.app;a.submit=Mock();a.preview_mode.set('Per-key design draft');a.apply_lighting()
  a.submit.assert_not_called();self.assertEqual(str(a.lighting_send['state']),'disabled')
 def test_battery_read_finishes_and_stop_is_explicit(self):
  a=self.app;a.start_monitor()
  a.show_battery({'observed_at':'2026-10-18T14:00:00+03:00','transport':'available',**decode_battery(bytes([0,1,0,0,0,0]))})
  self.assertIn('complete',a.status.get());self.assertEqual(a.percent.get(),'0 %')
  self.assertIn('1 readings',a.monitor_note.get());a.stop_monitor()
  self.assertFalse(a.monitoring);self.assertEqual(str(a.stop_battery_button['state']),'disabled')
 def test_firmware_selection_changes_preview_without_upload(self):
  a=self.app;a.submit=Mock();before=a.firmware_preview['image'];a.build.set('Original V0113')
  self.assertEqual(a.preview_title.get(),'ORIGINAL V0113');self.assertNotEqual(a.firmware_preview['image'],before);a.submit.assert_not_called()
 def test_ui_callback_error_does_not_stop_result_pump(self):
  a=self.app
  def broken(value):raise ValueError('test rendering failure')
  with tempfile.TemporaryDirectory() as folder,patch('x68.desktop.WORK',Path(folder)):
   a.results.put(('done','Mock read',{},None,broken));a.pump()
   self.assertFalse(a.busy);self.assertTrue(self.root.tk.call('after','info'))
   called=[];a.results.put(('done','Next read',{},None,called.append));a.pump();self.assertEqual(called,[{}])
