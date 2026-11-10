"""Bounded image/GIF conversion and the exact X68 custom-media writer.

Stock command 21 hex erases A2000..DE000 on its first packet. This is an
explicit replacement of the entire custom-media bank, never a background job.
The source file and converted payload are saved locally before any write.
"""
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import hashlib, io, json, time
from PIL import Image, ImageOps
from .protocol import ProtocolError
from .firmware import LIVE_CLOCK_CRC, LIVE_CLOCK_CRCS, MULTI_SCREEN_CRCS
# Lavender 0.10.0 screen table in the parameter block: 45..47 magic, then four
# entries (first frame, frame count, period LE16) for screens 1-4 at 48..63.
SCREEN_MAGIC=b'XS\x01'
SCREENS=4

WIDTH,HEIGHT=160,96
FRAME_BYTES=WIDTH*HEIGHT*2
MAX_FRAMES=8
MAX_BYTES=FRAME_BYTES*MAX_FRAMES

@dataclass
class PreparedMedia:
    source:str
    frames:list
    period_ms:int
    source_frames:int
    source_duration_ms:int
    fit:str
    @property
    def data(self):return b''.join(rgb565(frame) for frame in self.frames)
    def metadata(self):
        data=self.data
        return {'source':self.source,'source_frames':self.source_frames,'source_duration_ms':self.source_duration_ms,
                'device_frames':len(self.frames),'period_ms':self.period_ms,'fit':self.fit,'width':WIDTH,'height':HEIGHT,
                'format':'RGB565 big endian, row-major','payload_bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}

def rgb565(image):
    return b''.join((((r>>3)<<11)|((g>>2)<<5)|(b>>3)).to_bytes(2,'big') for r,g,b in image.convert('RGB').get_flattened_data())

def convert_media(path,fit='Crop',background='#211631',max_frames=MAX_FRAMES):
    path=Path(path)
    if not 1<=max_frames<=MAX_FRAMES:raise ValueError('Device supports 1 to 8 frames.')
    if fit not in ('Crop','Fit','Stretch'):raise ValueError('Unknown image fitting mode.')
    if path.stat().st_size>30*1024*1024:raise ValueError('Choose a source file below 30 MB.')
    with Image.open(path) as source:
        if source.width*source.height>16000000:raise ValueError('Source image exceeds 16 megapixels.')
        count=getattr(source,'n_frames',1)
        if count>500:raise ValueError('Choose a GIF with 500 frames or fewer.')
        durations=[]
        for index in range(count):
            source.seek(index);durations.append(max(20,min(5000,int(source.info.get('duration',100) or 100))))
        total=sum(durations);wanted=min(count,max_frames);targets=[i*total/wanted for i in range(wanted)]
        chosen=[];end=0;cursor=0
        for index,duration in enumerate(durations):
            end+=duration
            while cursor<len(targets) and targets[cursor]<end:
                chosen.append(index);cursor+=1
        frames=[]
        for index in chosen:
            source.seek(index)
            rgba=source.convert('RGBA');solid=Image.new('RGBA',rgba.size,background);solid.alpha_composite(rgba);frame=solid.convert('RGB')
            if fit=='Crop':frame=ImageOps.fit(frame,(WIDTH,HEIGHT),Image.Resampling.LANCZOS)
            elif fit=='Fit':frame=ImageOps.pad(frame,(WIDTH,HEIGHT),Image.Resampling.LANCZOS,color=background)
            else:frame=frame.resize((WIDTH,HEIGHT),Image.Resampling.LANCZOS)
            frames.append(frame.copy())
    return PreparedMedia(str(path.resolve()),frames,max(50,min(5000,round(total/wanted))),count,total,fit)

def media_packet(offset,data):
    if type(offset) is not int or offset<0 or not 1<=len(data)<=56 or offset+len(data)>MAX_BYTES:
        raise ProtocolError('Media packet is outside the verified custom-media bank.')
    packet=bytearray(64);packet[0]=4;packet[3]=0x21;packet[4]=len(data);packet[5:8]=offset.to_bytes(3,'little');packet[8:8+len(data)]=data
    packet[1:3]=(sum(packet[3:])&65535).to_bytes(2,'little');return bytes(packet)

def _send_media(device,frame,trace):
    if device.write(frame)!=64:raise ProtocolError('Short media write. No automatic retry sent.')
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        reply=bytes(device.read(64,250))
        if len(reply)==64 and reply[:8]==frame[:8]:
            trace.append({'command':33,'offset':int.from_bytes(frame[5:8],'little'),'size':frame[4],'acknowledged':True});return
    raise ProtocolError('Media packet was not acknowledged. Transfer stopped without a blind retry.')

def set_screen(settings,mode):
    # The same five values Fn+PgUp cycles through (measured: 0,1,2,3,4).
    if mode not in (0,1,2,3,4):raise ProtocolError('Screen mode must be 0-4.')
    with settings._device() as device:
        before=settings._read(device,5,64);desired=bytearray(before);desired[33]=mode
        backup=settings._backup('lighting',before)
        with settings._transaction(device):settings._write(device,6,bytes(desired))
        after=settings._read(device,5,64)
        if after[33]!=mode:raise ProtocolError('Display mode readback differs. Backup: '+backup)
    return {'screen':mode,'backup':backup}

def upload_media(settings,prepared,project_dir,progress=None):
    if not 1<=len(prepared.frames)<=8 or not 50<=prepared.period_ms<=5000:raise ProtocolError('Invalid prepared media.')
    payload=prepared.data
    if len(payload)!=len(prepared.frames)*FRAME_BYTES:raise ProtocolError('Converted frame size differs.')
    # An exact custom CRC is required: stock's timing units are not assumed.
    remaining=2-(time.monotonic()-settings.client.last_query)
    if remaining>0:time.sleep(remaining)
    version=settings.client.query_version()
    if version['reported_crc'] not in LIVE_CLOCK_CRCS:raise ProtocolError('Install Lavender Quest 0.5.1 before uploading media.')
    folder=Path(project_dir)/'reports/media'/datetime.now().strftime('%Y%m%d-%H%M%S-%f');folder.mkdir(parents=True)
    (folder/'converted.rgb565').write_bytes(payload);(folder/'conversion.json').write_text(json.dumps(prepared.metadata(),indent=2),encoding='utf-8')
    prepared.frames[0].save(folder/'preview.png')
    trace=[];result={'phase':'preflight','conversion':prepared.metadata(),'flash_readback_verified':False,'trace':trace}
    try:
        with settings._device(wireless=False) as device:
            before=settings._read(device,5,64);result['parameter_backup']=settings._backup('lighting',before)
            # Exit the media player before erasing its bank. This also clears
            # the renderer's cached frame for single-frame replacements.
            if 1<=before[33]<=4:
                desktop=bytearray(before);desktop[33]=0
                with settings._transaction(device):settings._write(device,6,bytes(desktop))
                if settings._read(device,5,64)[33]!=0:raise ProtocolError('Could not leave custom-media mode.')
                time.sleep(0.3)
            result['phase']='writing_custom_media'
            with settings._transaction(device):
                for offset in range(0,len(payload),56):
                    _send_media(device,media_packet(offset,payload[offset:offset+56]),trace)
                    if progress:progress(min(offset+56,len(payload)),len(payload))
            desired=bytearray(before);desired[33]=4;desired[34]=len(prepared.frames);desired[42:44]=prepared.period_ms.to_bytes(2,'little')
            desired[45:48]=bytes(3)  # one image for screen 4: switch any multi-screen table off
            with settings._transaction(device):settings._write(device,6,bytes(desired))
            after=settings._read(device,5,64)
            if after[33:35]!=desired[33:35] or after[42:48]!=desired[42:48]:raise ProtocolError('Media settings readback differs.')
        result['phase']='complete';return result
    except Exception as error:result['phase']='stopped';result['error']=str(error);raise
    finally:(folder/'upload.json').write_text(json.dumps(result,indent=2),encoding='utf-8')


def screen_table(slots):
    """Bank layout for screens 1-4: [(first, count, period) or None]; frames are packed in screen order."""
    if len(slots)!=SCREENS:raise ValueError('Four screen slots are expected.')
    table=[];first=0
    for prepared in slots:
        if prepared is None:table.append(None);continue
        count=len(prepared.frames)
        if not 1<=count or not 50<=prepared.period_ms<=5000:raise ProtocolError('Invalid prepared media.')
        table.append((first,count,prepared.period_ms));first+=count
    if first>MAX_FRAMES:raise ProtocolError(f'The screens use {first} frames; the keyboard holds {MAX_FRAMES}.')
    if not first:raise ProtocolError('Choose an image for at least one screen.')
    return table


def screen_parameters(before,table,show):
    """The parameter block with the screen table written and screen `show` selected."""
    desired=bytearray(before);desired[33]=show;desired[45:48]=SCREEN_MAGIC
    # Stock Fn+PgUp/PgDn (V0113 20012128..2001214C, 200123D8) only reaches mode 4 while
    # parameter 34 is non-zero; with the table present Lavender itself ignores 34.
    desired[34]=sum(entry[1] for entry in table if entry)
    for index,entry in enumerate(table):
        first,count,period=entry or (0,0,0)
        desired[48+index*4:52+index*4]=bytes([first,count])+period.to_bytes(2,'little')
    return desired


def upload_screens(settings,slots,project_dir,show=1,progress=None):
    """Write every screen's frames as one bank (stock command 21 erases the whole bank), then the table."""
    table=screen_table(slots)
    if not 0<=show<=SCREENS:raise ProtocolError('Screen mode must be 0-4.')
    payload=b''.join(prepared.data for prepared in slots if prepared is not None)
    remaining=2-(time.monotonic()-settings.client.last_query)
    if remaining>0:time.sleep(remaining)
    version=settings.client.query_version()
    if version['reported_crc'] not in MULTI_SCREEN_CRCS:raise ProtocolError('Separate screens need Lavender Quest 0.10.0.')
    folder=Path(project_dir)/'reports/media'/datetime.now().strftime('%Y%m%d-%H%M%S-%f');folder.mkdir(parents=True)
    (folder/'converted.rgb565').write_bytes(payload)
    meta={'screens':[None if s is None else s.metadata() for s in slots],'table':table,'show':show}
    (folder/'conversion.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    trace=[];result={'phase':'preflight','screens':meta,'trace':trace}
    try:
        with settings._device(wireless=False) as device:
            before=settings._read(device,5,64);result['parameter_backup']=settings._backup('lighting',before)
            if 1<=before[33]<=4:
                desktop=bytearray(before);desktop[33]=0
                with settings._transaction(device):settings._write(device,6,bytes(desktop))
                if settings._read(device,5,64)[33]!=0:raise ProtocolError('Could not leave custom-media mode.')
                time.sleep(0.3)
            result['phase']='writing_custom_media'
            with settings._transaction(device):
                for offset in range(0,len(payload),56):
                    _send_media(device,media_packet(offset,payload[offset:offset+56]),trace)
                    if progress:progress(min(offset+56,len(payload)),len(payload))
            desired=screen_parameters(before,table,show)
            with settings._transaction(device):settings._write(device,6,bytes(desired))
            after=settings._read(device,5,64)
            if after[33]!=desired[33] or after[45:64]!=desired[45:64]:raise ProtocolError('Screen table readback differs.')
        result['phase']='complete';return result
    except Exception as error:result['phase']='stopped';result['error']=str(error);raise
    finally:(folder/'upload.json').write_text(json.dumps(result,indent=2,default=str),encoding='utf-8')
