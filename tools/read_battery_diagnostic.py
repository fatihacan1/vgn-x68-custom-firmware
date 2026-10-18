"""Query cached engineering data. No settings, GPIO, ADC or charge-control writes."""
from pathlib import Path
import sys,json,time,argparse
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from x68.protocol import X68Client
from x68.settings import SettingsClient
from x68.battery import query_battery
from x68.battery_diagnostic import query_snapshot

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--samples',type=int,default=6);p.add_argument('--interval',type=float,default=5);p.add_argument('--output',type=Path,default=ROOT/'reports/battery-engineering-live.json');a=p.parse_args()
 if not 1<=a.samples<=30 or not 2<=a.interval<=30:p.error('Use 1..30 samples and 2..30 second intervals.')
 client=X68Client();settings=SettingsClient(client,ROOT/'reports/backups');report={'inventory':client.inventory(),'version':client.query_version(),'samples':[],'control_writes':False}
 a.output.parent.mkdir(parents=True,exist_ok=True)
 for i in range(a.samples):
  sample=query_snapshot(settings,report['version']);sample['standard_battery_report']=query_battery(settings);report['samples'].append(sample)
  a.output.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
  print(json.dumps({k:sample[k] for k in ['cached_indicator','previous_indicator','adc_samples_cached','scaled_code_units','lower_threshold_code_units','upper_threshold_code_units','unfiltered_firmware_indicator','pe4','pc3','native_ui_state','transport_mode_raw']},ensure_ascii=True),flush=True)
  if i+1<a.samples:time.sleep(a.interval)
 print(str(a.output.resolve()))
if __name__=='__main__':main()
