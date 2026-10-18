"""Read-only engineering snapshot from the exact experimental diagnostic build.

All numbers are native code units/cached counts, not calibrated measurements.
Do not turn GPIO states into charging-current claims.
"""
from datetime import datetime
from .protocol import ProtocolError
from .firmware import BATTERY_DIAGNOSTIC_CRC

def decode_snapshot(data):
    if len(data)!=48 or data[:4]!=b'XBD\x01':raise ProtocolError('Unknown diagnostic snapshot format.')
    u16=lambda offset:int.from_bytes(data[offset:offset+2],'little')
    u32=lambda offset:int.from_bytes(data[offset:offset+4],'little')
    samples=[u16(i) for i in range(12,28,2)]
    upper,lower=u16(32),u16(34)
    offset=int.from_bytes(data[30:31],'little',signed=True)
    # Exact 20010524..20010584 math: each central sample is shifted right
    # by two before summing, then the original integer calibration is used.
    trimmed=sum(value>>2 for value in samples[2:6])&65535
    product=(trimmed*data[10]*data[11]*u16(28))&0xffffffff
    if product&0x80000000:product-=0x100000000
    scaled=((product>>13)+offset)&65535
    if trimmed==0:unfiltered=0 if upper else 100
    elif scaled>=upper:unfiltered=100
    elif scaled<=lower:unfiltered=0
    elif data[8]==2:unfiltered=100
    elif upper>lower:unfiltered=100*(scaled-lower)//(upper-lower)
    else:unfiltered=None
    return {'observed_at':datetime.now().astimezone().isoformat(timespec='seconds'),
            'cached_indicator':data[4],'previous_indicator':data[5],
            'gpio_e_raw':data[6],'gpio_c_raw':data[7],'pe4':bool(data[6]&16),'pc3':bool(data[7]&8),
            'native_ui_state':data[8],'transport_mode_raw':data[9],
            'adc_samples_cached':samples,'adc_samples_sorted':samples==sorted(samples),
            'all_adc_samples_zero':not any(samples),'adc_factors':[data[10],data[11]],
            'calibration_scale':u16(28),'calibration_offset':offset,
            'upper_threshold_code_units':upper,'lower_threshold_code_units':lower,
            'trimmed_sample_code_units':trimmed,'scaled_code_units':scaled,
            'unfiltered_firmware_indicator':unfiltered,
            'low_level_flag_raw':data[46],'filter_counter_raw':data[47],
            'scheduler_timestamp_raw':u32(38),'mcu_timer_raw':u32(42),
            'payload_hex':data.hex(' '),'physical_voltage_mv':None,'charging_current_ma':None,
            'charging_verified':False,'peripheral_control_writes':False,
            'limitation':'Cached ADC counts and native arithmetic only. No new ADC conversion, calibrated voltage/current or physical charge measurement.'}

def query_snapshot(settings,version):
    if version.get('reported_crc')!=BATTERY_DIAGNOSTIC_CRC:raise ProtocolError('Exact experimental battery-diagnostic firmware is required; no diagnostic command sent.')
    with settings._device() as device:data=settings._exchange(device,25,size=48)
    return decode_snapshot(data)
