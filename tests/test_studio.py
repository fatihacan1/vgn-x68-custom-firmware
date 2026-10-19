"""UI regression checks with timers cancelled before any HID operation."""
import tempfile,tkinter as tk,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from x68.desktop import Studio
from x68.battery import decode_battery
from x68.settings import PHYSICAL_KEY_INDICES, encode_key, keymap_entries, compile_macro

class StudioTests(unittest.TestCase):
 def test_clock_display_at_midnight_noon_and_evening(self):
  from datetime import datetime
  a=self.app
  for hour,twelve in ((0,'12:05 AM'),(11,'11:05 AM'),(12,'12:05 PM'),(13,'01:05 PM'),(23,'11:05 PM')):
   a.clock_format.set('12-hour (AM/PM)');self.assertEqual(a.format_time(datetime(2026,10,20,hour,5)),twelve)
   a.clock_format.set('24-hour');self.assertEqual(a.format_time(datetime(2026,10,20,hour,5)),f'{hour:02d}:05')
 def test_clock_format_choice_is_saved_without_immediate_device_write(self):
  a=self.app;a.save_preferences=Mock();a.submit=Mock();a.clock_format.set('12-hour (AM/PM)')
  a.clock_format_preference();a.save_preferences.assert_called_once_with(clock_hour_format=12);a.submit.assert_not_called()
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
 def mapping_snapshot(self):
  mapping=bytearray(384)
  for name,index in PHYSICAL_KEY_INDICES.items():mapping[index*3:index*3+3]=encode_key(name)
  # Already customized before this app instance starts: duplicate actions,
  # missing original usages, and a macro whose slot is not the default slot.
  mapping[63*3:64*3]=encode_key('F17')
  mapping[56*3:57*3]=bytes([113,2,1])
  mapping[49*3:50*3]=encode_key('B')
  return {'lighting':None,'keys':keymap_entries(bytes(mapping)),
          'macros':[{'slot':3,'events':8,'block_hex':compile_macro('CTRL+C').hex()}]}
 def test_saved_actions_load_on_cold_start_and_remain_editable_after_refresh(self):
  a=self.app;a.submit=Mock();a.version={'reported_crc':'test'};snapshot=self.mapping_snapshot()
  a.show_settings(snapshot)
  self.assertEqual(a.lookup('PAGEDOWN'),63);self.assertEqual(a.lookup('K'),56)
  self.assertEqual(a.lookup('A'),49);self.assertEqual(a.lookup('B'),70)
  self.assertEqual(a.mapping_label('PAGEDOWN','PgDn'),'F17')
  self.assertEqual(a.mapping_label('K','K'),'M3')
  a.hit=Mock(return_value='PAGEDOWN');a.select_key(None)
  self.assertEqual(a.selected,63);self.assertIn('F17',a.selection.get())
  a.target.set('F18');a.stage_mapping();self.assertEqual(a.pending_mapping,{63:'F18'})
  snapshot['keys'][63].update(name='F18',code=109)
  a.show_settings(snapshot)
  self.assertIn('F18',a.selection.get());self.assertEqual(a.lookup('PAGEDOWN'),63)
  a.submit.assert_not_called()
 def test_selecting_saved_macro_loads_its_actual_slot_for_editing(self):
  a=self.app;a.submit=Mock();a.version={'reported_crc':'test'};a.show_settings(self.mapping_snapshot())
  a.hit=Mock(return_value='K');a.select_key(None)
  self.assertEqual(a.selected,56);self.assertEqual(a.slot.get(),3)
  self.assertIn('Makro 3',a.selection.get());self.assertIn('C',a.editor.get('1.0','end'))
  a.save_macro();operation=a.submit.call_args.args[1]
  with patch.object(a.settings_client,'assign_macro') as assign:
   operation();self.assertEqual(assign.call_args.args[:2],(56,2))
 def test_reserved_selection_clears_previous_target(self):
  a=self.app;a.version={'reported_crc':'test'};a.show_settings(self.mapping_snapshot());a.selected=56
  a.hit=Mock(return_value='FN');a.select_key(None)
  self.assertIsNone(a.selected);a.submit=Mock();a.save_macro();a.stage_mapping()
  a.submit.assert_not_called();self.assertEqual(a.pending_mapping,{})
 def test_media_action_picker_and_saved_media_key_do_not_write_until_send(self):
  a=self.app;a.submit=Mock();a.version={'reported_crc':'test'};snapshot=self.mapping_snapshot()
  snapshot['keys'][56].update(flag=48,code=0xE900,name='Volume Up')
  a.show_settings(snapshot);a.hit=Mock(return_value='K');a.select_key(None)
  self.assertEqual(a.selected,56);self.assertEqual(a.action_type.get(),'Media')
  self.assertEqual(a.target.get(),'Volume Up');self.assertEqual(a.mapping_label('K','K'),'Vol+')
  self.assertIn('Play / Pause',a.target_combo['values'])
  a.target.set('Mute');a.stage_mapping();self.assertEqual(a.pending_mapping,{56:'Mute'})
  a.action_type.set('Keyboard');a.change_action_type()
  self.assertIn('F17',a.target_combo['values']);self.assertNotIn('Mute',a.target_combo['values'])
  a.hit=Mock(return_value='PAGEDOWN');a.select_key(None)
  self.assertEqual(a.action_type.get(),'Keyboard');self.assertEqual(a.target.get(),'F17')
  a.submit.assert_not_called()
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
