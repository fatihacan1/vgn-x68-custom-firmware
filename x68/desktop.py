"""Desktop client (English / Turkish). All device I/O shares one worker; OTA is explicit."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import colorsys, json, math, os, queue, sys, time, subprocess, traceback
import tkinter as tk
from tkinter import ttk, filedialog, colorchooser, messagebox
from .protocol import X68Client
from .settings import SettingsClient, HID_KEYS, MODIFIERS, MEDIA_KEYS, PHYSICAL_KEY_INDICES, compile_macro, macro_text
from .battery import query_battery, BatteryHistory
from .battery_health import ASSUMPTION, ChargeTrend, estimate
from .firmware import MULTI_SCREEN_CRC, MULTI_SCREEN_CRCS, LIVE_CLOCK_CRC, LIVE_CLOCK_CRCS, BATTERY_DIAGNOSTIC_CRC, BATTERY_DIAGNOSTIC_CRCS, CLOCK_FORMAT_CRC, CLOCK_FORMAT_CRCS, DEVICE_STATUS_CRC, STATUS_BADGE_CRC, RETRO_BADGE_CRC
from .media import convert_media, upload_media, upload_screens, set_screen, MAX_FRAMES, SCREENS
from . import autostart, firmware_source, safety
from PIL import Image, ImageTk, ImageOps
from . import pixel, i18n, effects, lcd_preview
from .i18n import t
from .pixel import PixelButton, window, BODY, BIG_BODY, LABEL, HEAD, TITLE, HUGE

ASSETS=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))
WORK=(Path.home()/'Library/Application Support' if sys.platform=='darwin' else Path(os.environ.get('LOCALAPPDATA',Path.home())))/'VGN X68 Custom Firmware' if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1]
# Pages sit inside PC-98 windows: BG is the window fill, PANEL the inset field.
BG=pixel.WIN;PANEL=pixel.FIELD;EDGE=pixel.LINE_MID;INK=pixel.TEXT;MUTED=pixel.MUTED;MINT=pixel.MINT;PINK=pixel.PINK;KEY='#b9a6ea';AMBER=pixel.AMBER
PAGES=['Home','Lighting','Keymap','Macros','Screen','Battery','Firmware','Knowledge','Advanced']
# Install targets, newest first. 0.6.0 = 0.5.1 plus the read-only battery snapshot (command 19 hex).
# Builds are produced locally from the official payload; see firmware_source.
BUILDS=list(firmware_source.BUILDS)
CACHE=WORK/'firmware-cache'
# What each Lavender Quest build gives you (cumulative; newest first in the list).
BUILD_NOTES={'lavender-quest-0.10.0':'Experimental. The same screen as 0.9.2, plus screens 1-4 can each show their own image or GIF (Screen page). Built and emulator-tested in this fork; not yet reviewed by the original author.',
             'lavender-quest-0.9.2':'Newest, recommended. Windows logo (four colours) or Apple logo, a WIN/MAC chip and a padlock that shows the Windows-key lock. Includes everything from the older builds.',
             'lavender-quest-0.9.1':'Windows/Apple logo and padlock badges (cyan Windows logo with a coloured rail). Includes everything from the older builds.',
             'lavender-quest-0.9.0':'Header shows WIN/MAC and L:ON/L:OFF as text. Includes everything from the older builds.',
             'lavender-quest-0.8.0':'Adds the 12-hour AM/PM clock. Includes everything from the older builds.',
             'lavender-quest-0.6.0':'Adds the real battery voltage on the Battery page. The screen looks the same as 0.5.1.',
             'lavender-quest-0.5.1':'First stable build: purple pixel scene, clock set from the computer, image/GIF player and a battery badge on the screen.'}
LCD_LEGEND=['Top-left logo and WIN/MAC: the keyboard\'s Windows or Mac mode. Fn + A switches to Windows, Fn + S to Mac (0.9.0 and newer).',
            'Padlock at the top right: the Windows-key lock, so the Windows key cannot interrupt a game. Fn + Windows key turns it on or off. Gold and closed = locked, green and open = unlocked.',
            'Big clock and DD/MM date: set from this computer (Screen page > Clock). They keep running when the app is closed, until the keyboard loses power.',
            'Battery at the bottom: the battery level the keyboard reports.',
            'X68.EXE, CLOCK, DAY-MO, START and READY: decorative pixel-game text. They have no function.',
            'The bunny blinks and the coin spins: animation only.',
            'Fn + PgUp steps through the screen modes 0-4. On 0.10.0 screen 0 is the clock and screens 1-4 each show their own image (an empty one shows the clock). On older builds modes 0-3 all show the clock and mode 4 shows your image. The Screen page buttons switch directly.']
# Ready-made macros for the Macros page (name, script). Every key here is in settings.HID_KEYS/MODIFIERS.
MACRO_EXAMPLES=[('Copy and paste','CTRL+C\nWAIT 150\nCTRL+V'),('Select all and copy','CTRL+A\nWAIT 50\nCTRL+C'),
                ('Screenshot of an area','WIN+SHIFT+S'),('Task Manager','CTRL+SHIFT+ESC'),('Show the desktop','WIN+D'),
                ('Lock the computer','WIN+L'),('Close the window','ALT+F4'),('Undo three times','CTRL+Z\nWAIT 50\nCTRL+Z\nWAIT 50\nCTRL+Z')]
# Firmware the installer accepts as the starting point (device-reported CRC -> build name).
KNOWN_BUILDS={MULTI_SCREEN_CRC:'Lavender Quest 0.10.0','14961BE6':'Original V0113','EF331DCE':'Lavender Quest 0.4.0','4CB077DE':'Lavender Quest 0.4.1','FC2EBCFE':'Lavender Quest 0.4.2','3C866A9B':'Lavender Quest 0.5.0',LIVE_CLOCK_CRC:'Lavender Quest 0.5.1',BATTERY_DIAGNOSTIC_CRC:'Lavender Quest 0.6.0',CLOCK_FORMAT_CRC:'Lavender Quest 0.8.0',DEVICE_STATUS_CRC:'Lavender Quest 0.9.0',STATUS_BADGE_CRC:'Lavender Quest 0.9.1',RETRO_BADGE_CRC:'Lavender Quest 0.9.2'}
EFFECTS=['Wave','Colour cloud','Vortex','Spectrum','Breathing','Solid','Reactive','Ripple','Trail','Stars','Flowers','Scroll','Wings','Build up','Rain','Scan','Spread','Fast wave','Custom table','Off']
ROWS=[
 [('Esc','ESC',1),*[(str(n),str(n),1) for n in range(1,10)],('0','0',1),('-','-',1),('=','=',1),('Back','BACKSPACE',2)],
 [('Tab','TAB',1.5),*[(c,c,1) for c in 'QWERTYUIOP'],('[','[',1),(']',']',1),('\\','\\',1.5)],
 [('Caps','CAPSLOCK',1.75),*[(c,c,1) for c in 'ASDFGHJKL'],(';',';',1),("'","'",1),('Enter','ENTER',2.25)],
 [('Shift','SHIFT',2.25),*[(c,c,1) for c in 'ZXCVBNM'],(',',',',1),('.','.',1),('/','/',1),('Shift','RSHIFT',1.75),('Up','UP',1)],
 [('Ctrl','CTRL',1.25),('Win','WIN',1.25),('Alt','ALT',1.25),('Space','SPACE',6.25),('Alt','RALT',1.25),('Fn','FN',1.25),('Left','LEFT',1),('Down','DOWN',1),('Right','RIGHT',1)],
]
# Main typing block, 2x2 navigation cluster and spaced inverted-T arrows.
MAIN_ROWS=[[(label,key,size) for label,key,size in row if key not in ('UP','LEFT','DOWN','RIGHT')] for row in ROWS]
LAYOUT=[]
for r,row in enumerate(MAIN_ROWS):
 x=0
 for label,key,size in row:
  LAYOUT.append((label,key,x,r,size));x+=size
LAYOUT += [('Ins','INSERT',15.75,0,1),('Del','DELETE',15.75,1,1),
           ('PgUp','PAGEUP',16.75,0,1),('PgDn','PAGEDOWN',16.75,1,1)]
LAYOUT += [('↑','UP',14.5,3,1),('←','LEFT',13.5,4,1),('↓','DOWN',14.5,4,1),('→','RIGHT',15.5,4,1)]
# Key centres in key units for the lighting preview.
PREVIEW_KEYS=[(key,column+size/2,row) for label,key,column,row,size in LAYOUT]

class Studio:
 def __init__(self,root,smoke=False):
  self.root=root;self.smoke=smoke;self.closed=False;self.busy=False;self.flashing=False
  self.client=X68Client();self.settings_client=SettingsClient(self.client,WORK/'reports/backups')
  self.pool=ThreadPoolExecutor(max_workers=1);self.results=queue.Queue();self.keys=queue.Queue()
  self.inventory=None;self.settings=None;self.version=None;self.logs=[];self.monitor=None
  self.awake=False
  self.history=BatteryHistory();self.monitoring=False;self.next_battery=0;self.test_until=0;self.pressed=set();self.counts={}
  self.lcd_backgrounds={};self.lcd_build=None;self.lcd_phase=None
  self.selected=None;self.paint={};self.keyboxes={};self.page_name='Lighting';self.photos=[];self.scrollers={}
  self.pending_mapping={};self.external_firmware=None;self.operation='';self.operation_started=0;self.needs_battery_read=False
  self.prepared=None;self.media_photos=[];self.media_frame=0;self.media_due=0;self.next_clock_sync=0;self.next_reconnect=float('inf')
  try:preferences=json.loads((WORK/'preferences.json').read_text(encoding='utf-8'))
  except (OSError,ValueError):preferences={}
  self.auto_clock=tk.BooleanVar(value=preferences.get('auto_clock',True));self.clock_note=tk.StringVar(value=t('Waiting for a verified 0.5.1+ connection.'))
  self.clock_interval=tk.StringVar(value=str(preferences.get('clock_interval_minutes',5)) if str(preferences.get('clock_interval_minutes',5)) in ('1','2','5','10','15','30','60') else '5')
  self.clock_format=tk.StringVar(value=t('12-hour (AM/PM)') if preferences.get('clock_hour_format')==12 else t('24-hour'))
  self.start_on_login=tk.BooleanVar(value=autostart.enabled())
  root.title('VGN X68 Custom Firmware');root.geometry('1240x860');root.minsize(1180,820);root.configure(bg=pixel.DESK)
  pixel.load_fonts(ASSETS/'assets/fonts')
  self.style=ttk.Style();self.style.theme_use('clam');st=self.style
  st.configure('.',background=BG,foreground=INK,font=BODY,bordercolor=pixel.LINE_DK,lightcolor=pixel.LINE_DK,darkcolor=pixel.LINE_DK,troughcolor=PANEL,focuscolor=MINT)
  st.configure('TFrame',background=BG);st.configure('Card.TFrame',background=PANEL)
  st.configure('TLabel',background=BG,foreground=INK);st.configure('Muted.TLabel',foreground=MUTED);st.configure('Title.TLabel',font=TITLE)
  field=dict(fieldbackground=PANEL,background=pixel.LINE_DK,foreground=INK,bordercolor=EDGE,lightcolor=EDGE,darkcolor=EDGE,arrowcolor=MINT,padding=6,insertcolor=INK)
  for name in ('TCombobox','TEntry','TSpinbox'):st.configure(name,**field)
  st.map('TCombobox',fieldbackground=[('readonly',PANEL),('disabled',PANEL)],foreground=[('disabled',pixel.DIM),('readonly',INK)],background=[('active',pixel.LINE_MID)],arrowcolor=[('disabled',pixel.DIM)],selectbackground=[('!disabled',PANEL)],selectforeground=[('!disabled',MINT)],bordercolor=[('focus',MINT)])
  root.option_add('*TCombobox*Listbox.background',PANEL);root.option_add('*TCombobox*Listbox.foreground',INK);root.option_add('*TCombobox*Listbox.font',BODY)
  root.option_add('*TCombobox*Listbox.selectBackground',pixel.LINE_DK);root.option_add('*TCombobox*Listbox.selectForeground',MINT)
  for control in ('TCheckbutton','TRadiobutton'):
   st.configure(control,background=BG,foreground=INK,indicatorbackground=PANEL,indicatorforeground=MINT,indicatormargin=(0,0,8,0))
   st.map(control,background=[('active',BG)],foreground=[('disabled',pixel.DIM),('active',MINT)],indicatorbackground=[('selected',MINT),('pressed',EDGE)])
  st.configure('Field.TCheckbutton',background=PANEL);st.map('Field.TCheckbutton',background=[('active',PANEL)])
  st.configure('TNotebook',background=BG,borderwidth=0,tabmargins=0);st.configure('TNotebook.Tab',background=PANEL,foreground=MUTED,padding=(14,6),bordercolor=pixel.LINE_DK,lightcolor=PANEL)
  st.map('TNotebook.Tab',background=[('selected',pixel.LINE_DK)],foreground=[('selected',MINT),('active',INK)])
  st.configure('Treeview',background=PANEL,fieldbackground=PANEL,foreground=INK,rowheight=26,borderwidth=0);st.configure('Treeview.Heading',background=pixel.LINE_DK,foreground=INK,font=LABEL,relief='flat')
  st.map('Treeview',background=[('selected',pixel.LINE_DK)],foreground=[('selected',MINT)]);st.map('Treeview.Heading',background=[('active',pixel.LINE_MID)])
  st.configure('TProgressbar',background=MINT,troughcolor=PANEL,bordercolor=EDGE,lightcolor=MINT,darkcolor=MINT,thickness=14)
  st.configure('TScrollbar',background=pixel.LINE_DK,troughcolor=PANEL,arrowcolor=MINT,bordercolor=PANEL);st.configure('TSeparator',background=pixel.LINE_DK)
  st.configure('TScale',background=EDGE,troughcolor=PANEL)
  # Left column: brand, command menu, connection.
  side=tk.Frame(root,bg=pixel.DESK,width=236);side.pack(side='left',fill='y',padx=(10,0),pady=10);side.pack_propagate(False)
  outer,brand=window(side,pad=10);outer.pack(fill='x')
  sprite=ASSETS/'assets/pixel/bunny-sprite.png'
  if sprite.exists():
   self.brand_photo=tk.PhotoImage(file=str(sprite));tk.Label(brand,image=self.brand_photo,bg=BG,bd=0).pack(side='left',padx=(0,10))
  words=tk.Frame(brand,bg=BG);words.pack(side='left')
  tk.Label(words,text='X68',font=TITLE,bg=BG,fg=INK).pack(anchor='w');tk.Label(words,text=t('CUSTOM\nFIRMWARE'),font=LABEL,bg=BG,fg=MINT,justify='left').pack(anchor='w',pady=(6,0))
  outer,menu=window(side,t('COMMAND'),pad=10);outer.pack(fill='both',expand=True,pady=(10,0))
  self.nav={};self.nav_hover=None
  for name in PAGES:
   item=tk.Label(menu,text='  '+i18n.upper(t(name)),font=BODY,bg=BG,fg=MUTED,anchor='w',cursor='hand2',pady=5)
   item.pack(fill='x');item.bind('<Button-1>',lambda e,n=name:self.show(n))
   item.bind('<Enter>',lambda e,n=name:self.hover_nav(n));item.bind('<Leave>',lambda e:self.hover_nav(None));self.nav[name]=item
  self.usb_mode=tk.StringVar(value=t('Not connected'))
  outer,link=window(side,t('LINK'),pad=10);outer.pack(fill='x',pady=(10,0))
  tk.Label(link,textvariable=self.usb_mode,font=BODY,bg=BG,fg=MINT,justify='left',wraplength=180).pack(anchor='w')
  outer,lang=window(side,t('LANGUAGE'),pad=10);outer.pack(fill='x',pady=(10,0))
  self.language=tk.StringVar(value=i18n.LANG)
  pixel.Choice(lang,self.language,list(i18n.LANGUAGES.items()),columns=2,bg=BG).pack(anchor='w')
  self.language.trace_add('write',lambda *args:self.change_language())
  # Right column: title + clock, page window, message window.
  shell=tk.Frame(root,bg=pixel.DESK);shell.pack(side='left',fill='both',expand=True,padx=10,pady=10)
  top=tk.Frame(shell,bg=pixel.DESK);top.pack(fill='x')
  outer,clock=window(top,pad=10);outer.pack(side='right',fill='y')
  self.clock_text=tk.StringVar(value='--:--');self.clock_date=tk.StringVar(value='')
  tk.Label(clock,textvariable=self.clock_text,font=TITLE,bg=BG,fg=INK).pack(anchor='e');tk.Label(clock,textvariable=self.clock_date,font=LABEL,bg=BG,fg=MUTED).pack(anchor='e',pady=(8,0))
  outer,head=window(top,pad=10);outer.pack(side='left',fill='both',expand=True,padx=(0,10))
  self.title=tk.StringVar(value=t('Home'));tk.Label(head,textvariable=self.title,font=TITLE,bg=BG,fg=INK).pack(anchor='w')
  self.device=tk.StringVar(value=t('LOOKING FOR X68'))
  self.subtitle=tk.StringVar(value='');tk.Label(head,textvariable=self.subtitle,font=BODY,bg=BG,fg=MUTED).pack(anchor='w',pady=(8,0))
  outer,msg=window(shell,pad=10);outer.pack(side='bottom',fill='x',pady=(10,0))
  self.status=tk.StringVar(value=t('Connect the X68 over USB or its 2.4 GHz receiver.'));self.typed=tk.StringVar(value='');self.typing=0
  self.connect_button=PixelButton(msg,t('Connect'),self.refresh);self.connect_button.pack(side='right')
  status_label=tk.Label(msg,textvariable=self.typed,font=BODY,bg=BG,fg=INK,anchor='w',justify='left',wraplength=760);status_label.pack(side='left',fill='x',expand=True)
  status_label.bind('<Configure>',lambda e:status_label.configure(wraplength=max(120,e.width)))
  self.status.trace_add('write',lambda *args:self.type_status())
  outer,self.holder=window(shell,pad=16);outer.pack(fill='both',expand=True,pady=(10,0))
  self.page_frames={name:ttk.Frame(self.holder) for name in PAGES}
  # Pages built around one expanding widget fill the window when they fit; the rest keep their natural height.
  self.pages={name:self.scrollable(name,fill=name in ('Keymap','Macros','Knowledge','Advanced'))[1] for name in PAGES}
  self._lighting();self._mapping();self._macros();self._screen();self._battery();self._firmware();self._knowledge();self._advanced();self._home()
  icon=ASSETS/'assets/icon.png'
  if icon.exists():
   photo=tk.PhotoImage(file=str(icon));self.photos.append(photo);root.iconphoto(True,photo)
  self.type_status();self.tick_clock();self.apply_fonts(root);self.fluid_text()
  root.report_callback_exception=self.ui_error
  self.show('Home');root.protocol('WM_DELETE_WINDOW',self.close);root.after(60,self.pump);root.after(200,self.refresh)
  root.after(100,self.animate)

 def label(self,parent,text,muted=False,**kw):
  w=ttk.Label(parent,text=text,style='Muted.TLabel' if muted else 'TLabel',**kw);w.pack(anchor='w',pady=(0,10));return w
 def row(self,parent):
  f=ttk.Frame(parent);f.pack(fill='x',pady=7);return f
 def button(self,parent,text,command,accent=False):
  b=PixelButton(parent,text,command,accent,bg=parent.cget('background') if isinstance(parent,tk.Frame) else BG);b.pack(side='left',padx=(0,10));return b
 def fluid_text(self,widget=None):
  """Long labels follow the space they sit in instead of a fixed wrap length, so text is never cut off."""
  for child in (widget or self.root).winfo_children():
   if isinstance(child,(tk.Label,ttk.Label)):
    try:wrap=int(str(child.cget('wraplength')) or 0)
    except (ValueError,tk.TclError):wrap=0
    if wrap>=800 and not getattr(child,'fluid',False):
     child.fluid=True;margin=70 if child.master.master is getattr(self,'steps',None) else 40
     child.master.bind('<Configure>',lambda e,label=child,m=margin:label.configure(wraplength=max(200,e.width-m)),add='+')
   self.fluid_text(child)
 def apply_fonts(self,widget):
  if isinstance(widget,(ttk.Combobox,ttk.Entry,ttk.Spinbox)):widget.configure(font=BODY)
  for child in widget.winfo_children():self.apply_fonts(child)
 def hover_nav(self,name):
  self.nav_hover=name
  for n,item in self.nav.items():
   cursor='▶ ' if n==self.page_name or n==name else '  '
   item.configure(text=cursor+i18n.upper(t(n)),fg=MINT if n==self.page_name else (INK if n==name else MUTED))
 def type_status(self):
  # Dialogue-box reveal: shows that a new message arrived without moving the layout.
  self.typing=0;self.reveal()
 def reveal(self):
  text=self.status.get()
  if self.closed:return
  self.typing=min(len(text),self.typing+4);done=self.typing>=len(text)
  self.typed.set(text[:self.typing]+(' ▼' if done else ''))
  if not done:self.root.after(16,self.reveal)
 def format_time(self,moment):
  return f'{moment.hour%12 or 12:02d}:{moment.minute:02d} '+('AM' if moment.hour<12 else 'PM') if self.clock_format.get()==t('12-hour (AM/PM)') else moment.strftime('%H:%M')
 def tick_clock(self):
  if self.closed:return
  now=datetime.now();self.clock_text.set(self.format_time(now));self.clock_date.set(now.strftime('%d.%m.%Y'))
  self.root.after(1000*(60-now.second) if now.second else 1000,self.tick_clock)
 def show(self,name):
  if self.flashing:return
  for p in self.page_frames.values():p.pack_forget()
  self.page_frames[name].pack(fill='both',expand=True);self.root.after_idle(self.scrollers[name][2]);self.page_name=name;self.title.set(i18n.pixel_caps(i18n.upper(t(name))))
  descriptions={'Lighting':'Preview an effect, then send it to the keyboard.','Keymap':'Pick a key on the board and give it a new action.','Macros':'Shortcuts stored on the keyboard itself.','Battery':'Measure the pack and watch it charge.','Firmware':'Reviewed X68 builds, installed only when you say so.','Advanced':'Raw data, backups and the key tester.'}
  descriptions.update(Screen='Send an image or GIF to the 160x96 screen.',Knowledge='Verified facts and open questions, ready to copy.',Home='Plug in over USB. Nothing is written until you press Send.')
  self.subtitle.set(t(descriptions[name]));self.hover_nav(self.nav_hover)
  if name in ('Lighting','Keymap'):self.root.after_idle(self.draw_boards)

 def _home(self):
  p=self.pages['Home'];left=ttk.Frame(p);left.pack(side='left',fill='y');right=ttk.Frame(p);right.pack(side='left',fill='both',expand=True,padx=(16,0))
  self.hero_canvas=tk.Canvas(left,width=640,height=360,bg=PANEL,highlightthickness=2,highlightbackground=pixel.LINE_DK);self.hero_canvas.pack();self.hero_sprite=None
  path=ASSETS/'assets/pixel/home-scene.png'
  if path.exists():
   self.hero_photo=tk.PhotoImage(file=str(path));self.hero_sprite=self.hero_canvas.create_image(2,2,anchor='nw',image=self.hero_photo)
  f=ttk.Frame(left);f.pack(fill='x',pady=(14,0))
  for title,page in [('Lighting','Lighting'),('Keymap','Keymap'),('Screen','Screen'),('Battery','Battery')]:self.button(f,t(title),lambda n=page:self.show(n),page=='Lighting')
  for title,var in [('LINK',self.usb_mode),('FIRMWARE',self.installed)]:
   tk.Label(right,text=t(title),font=LABEL,bg=BG,fg=MUTED).pack(anchor='w',pady=(0,6))
   tk.Label(right,textvariable=var,font=BODY,bg=BG,fg=INK,wraplength=230,justify='left').pack(anchor='w',pady=(0,18))
  tk.Label(right,text=t('BATTERY'),font=LABEL,bg=BG,fg=MUTED).pack(anchor='w',pady=(0,6))
  tk.Label(right,textvariable=self.percent,font=HEAD,bg=BG,fg=INK).pack(anchor='w',pady=(0,8))
  self.home_gauge=tk.Canvas(right,width=230,height=22,bg=BG,highlightthickness=0);self.home_gauge.pack(anchor='w')
  self.draw_gauge(None)
  tk.Label(right,text=t('Choosing keys, colours or files never writes the keyboard. Each page has its own Send button.'),font=BODY,bg=BG,fg=MUTED,wraplength=230,justify='left').pack(anchor='w',side='bottom')
 def draw_gauge(self,volts):
  # HP-bar style: ten blocks across the Li-ion window 3.0 to 4.1 V.
  c=self.home_gauge;c.delete('all');c.create_rectangle(0,0,230,22,fill=pixel.LINE_DK,outline='')
  filled=0 if volts is None else max(0,min(10,round((volts-3.0)/0.11)))
  colour=MINT if filled>3 else (AMBER if filled>1 else PINK)
  for i in range(10):
   x=4+i*22.6;c.create_rectangle(x,4,x+19,18,fill=colour if i<filled else PANEL,outline='')
  if volts is not None and filled==0:c.create_rectangle(4,4,8,18,fill=PINK,outline='')

 def board(self,parent):
  c=tk.Canvas(parent,height=252,bg=BG,highlightthickness=0);c.pack(fill='x');c.bind('<Configure>',lambda e:self.draw_boards());return c
 def _lighting(self):
  p=self.pages['Lighting'];self.rgb_canvas=self.board(p);self.rgb_canvas.bind('<Button-1>',self.paint_key)
  self.effect=tk.StringVar(value='Solid');self.brightness=tk.IntVar(value=4);self.speed=tk.IntVar(value=2);self.color=tk.StringVar(value='#b9a6ea');self.rainbow=tk.StringVar(value='Keep device flag')
  self.preview_mode=tk.StringVar(value='Effect preview')
  self.effect_note=tk.StringVar();tk.Label(p,textvariable=self.effect_note,font=BODY,bg=BG,fg=MINT,anchor='w',justify='left',wraplength=880).pack(fill='x',pady=(6,0))
  body=ttk.Frame(p);body.pack(fill='x',pady=(10,0))
  fx=pixel.panel(body,t('EFFECT'));fx.pack(side='left',fill='y')
  pixel.Choice(fx,self.effect,[(e,t(e)) for e in EFFECTS],columns=4,width=13).pack(anchor='w')
  opts=pixel.panel(body,t('LIGHT'),pad=6);opts.pack(side='left',fill='both',expand=True,padx=(12,0))
  def line(title):
   row=tk.Frame(opts,bg=PANEL);row.pack(fill='x',pady=3);tk.Label(row,text=t(title),font=LABEL,bg=PANEL,fg=MUTED,width=10,anchor='w').pack(side='left');return row
  pixel.Meter(line('BRIGHTNESS'),self.brightness).pack(side='left');pixel.Meter(line('SPEED'),self.speed).pack(side='left')
  self.swatches=tk.Canvas(line('COLOUR'),width=8*26,height=26,bg=PANEL,highlightthickness=0,cursor='hand2');self.swatches.pack(side='left')
  self.swatches.bind('<Button-1>',self.pick_swatch);self.color.trace_add('write',lambda *args:self.draw_swatches());self.draw_swatches()
  pixel.Choice(line('MODE'),self.rainbow,[('Keep device flag',t('Keep')),('Single colour',t('Single')),('Rainbow',t('Rainbow'))],columns=2).pack(side='left')
  pixel.Choice(line('PREVIEW'),self.preview_mode,[('Effect preview',t('Effect')),('Per-key design draft',t('Key draft'))],columns=1).pack(side='left')
  actions=ttk.Frame(p);actions.pack(fill='x',pady=(12,0))
  self.lighting_send=self.button(actions,t('Send to keyboard'),self.apply_lighting,True);self.button(actions,t('Read from keyboard'),self.read_settings);self.button(actions,t('Export draft'),self.export_draft)
  self.preview_mode.trace_add('write',lambda *args:self.lighting_send.configure(state='normal' if self.preview_mode.get()=='Effect preview' else 'disabled'))
  self.lighting_summary=tk.StringVar();tk.Label(p,textvariable=self.lighting_summary,font=BODY,bg=BG,fg=INK,anchor='w',justify='left',wraplength=880).pack(fill='x',pady=(10,0))
  for var in (self.effect,self.brightness,self.speed,self.color,self.rainbow,self.preview_mode):var.trace_add('write',lambda *args:self.lighting_changed())
  self.lighting_hint=tk.Label(p,text=t('The board is a preview. In Key draft, click keys to paint them; drafts stay on this computer.')+' '+t('The animation is an approximation; Send shows the real effect on the keyboard.'),wraplength=880,justify='left',font=BODY,bg=BG,fg=MUTED,anchor='w');self.lighting_hint.pack(fill='x',pady=(10,0))
  self.lighting_changed()
 def lighting_changed(self):
  """Any light setting changed: refresh the description, the send summary and the preview at once."""
  effect=self.effect.get()
  self.effect_note.set(t(effect)+' — '+t(effects.DESCRIPTIONS.get(effect,'')))
  self.lighting_summary.set(self.lighting_summary_text())
  if self.page_name=='Lighting':self.draw_boards(time.monotonic(),only=('rgb',))
 def lighting_summary_text(self):
  if self.preview_mode.get()!='Effect preview':return t('Key draft is local only and is never sent to the keyboard.')
  mode={'Keep device flag':t('Keep'),'Single colour':t('Single'),'Rainbow':t('Rainbow')}[self.rainbow.get()]
  text=t('Send will write: {effect} / brightness {brightness}/4 / speed {speed}/4 / colour {colour} / mode {mode}').format(effect=t(self.effect.get()),brightness=self.brightness.get(),speed=self.speed.get(),colour=self.color.get().upper(),mode=mode)
  current=(self.settings or {}).get('lighting')
  if not current:return text+'\n'+t('The keyboard\'s current lighting has not been read yet.')
  changed=[]
  if EFFECTS[current['mode']-1]!=self.effect.get():changed.append(t('effect'))
  if current['brightness']!=self.brightness.get():changed.append(t('brightness'))
  if current['speed']!=self.speed.get():changed.append(t('speed'))
  if current['color'].lower()!=self.color.get().lower():changed.append(t('colour'))
  wanted={'Single colour':0,'Rainbow':1}.get(self.rainbow.get())
  if wanted is not None and current['rainbow_raw']!=wanted:changed.append(t('mode'))
  return text+'\n'+(t('Different from the keyboard now: {fields}.').format(fields=', '.join(changed)) if changed else t('Same as the keyboard now; sending changes nothing.'))
 SWATCHES=['#b9a6ea','#ff6f9c','#7cf2c2','#ffc66b','#8f9cff','#f2f2f2','#3a2f55']
 def draw_swatches(self):
  c=self.swatches;c.delete('all');current=self.color.get().lower()
  for i,colour in enumerate(self.SWATCHES+[current if current not in self.SWATCHES else '#1b1430']):
   x=2+i*26;c.create_rectangle(x,2,x+22,24,fill='#0c0916',outline='')
   c.create_rectangle(x+2,4,x+20,22,fill=colour,outline='')
   if i==7:c.create_text(x+11,13,text='+',font=BODY,fill=INK if current in self.SWATCHES else pixel.shade(colour,0.4))
   if colour==current:c.create_rectangle(x,0,x+22,2,fill=MINT,outline='');c.create_rectangle(x,24,x+22,26,fill=MINT,outline='')
 def pick_swatch(self,event):
  i=(event.x-2)//26
  if 0<=i<7:self.color.set(self.SWATCHES[i])
  elif i==7:self.choose_color()

 def _mapping(self):
  p=self.pages['Keymap'];self.map_canvas=self.board(p);self.map_canvas.bind('<Button-1>',self.select_key)
  body=ttk.Frame(p);body.pack(fill='both',expand=True,pady=(10,0))
  key=pixel.panel(body,t('SELECTED KEY'));key.pack(side='left',fill='both',expand=True)
  self.selection=tk.StringVar(value=t('Click a key on the board.'));tk.Label(key,textvariable=self.selection,font=HEAD,bg=PANEL,fg=INK,wraplength=420,justify='left').pack(anchor='w')
  f=tk.Frame(key,bg=PANEL);f.pack(anchor='w',pady=(16,0));tk.Label(f,text=t('ACTION TYPE'),font=LABEL,bg=PANEL,fg=MUTED).pack(side='left',padx=(0,10))
  self.action_type=tk.StringVar(value=t('Keyboard'));self.action_type_combo=ttk.Combobox(f,textvariable=self.action_type,values=[t('Keyboard'),t('Media')],state='readonly',width=12);self.action_type_combo.pack(side='left');self.action_type_combo.bind('<<ComboboxSelected>>',self.change_action_type)
  f=tk.Frame(key,bg=PANEL);f.pack(anchor='w',pady=(10,0));tk.Label(f,text=t('NEW ACTION'),font=LABEL,bg=PANEL,fg=MUTED).pack(side='left',padx=(0,10))
  self.target=tk.StringVar(value='CTRL');self.target_combo=ttk.Combobox(f,textvariable=self.target,values=list(MODIFIERS)+list(HID_KEYS),state='readonly',width=16);self.target_combo.pack(side='left',padx=(0,10));self.button(f,t('Add to draft'),self.stage_mapping)
  tk.Label(key,text=t('Fn and reserved firmware functions stay protected.'),font=BODY,bg=PANEL,fg=MUTED).pack(anchor='w',side='bottom')
  draft=pixel.panel(body,t('DRAFT'));draft.pack(side='left',fill='both',expand=True,padx=(12,0))
  self.mapping_note=tk.StringVar(value=t('Empty. Picking keys never writes the keyboard.'))
  tk.Label(draft,textvariable=self.mapping_note,font=BODY,bg=PANEL,fg=MINT,wraplength=400,justify='left',anchor='nw').pack(anchor='w',fill='x')
  f=tk.Frame(draft,bg=PANEL);f.pack(anchor='w',side='bottom');self.mapping_send=self.button(f,t('Send draft ({count})').format(count=0),self.remap,True);self.mapping_send.configure(state='disabled');self.button(f,t('Discard'),self.clear_mapping)
  tk.Label(draft,text=t('Made a mistake? Every send is backed up first. Undo it in Advanced > Restore settings backup.'),font=BODY,bg=PANEL,fg=MUTED,wraplength=400,justify='left').pack(anchor='w',side='bottom',pady=(0,10))
  self.source=tk.StringVar()

 def change_action_type(self,event=None):
  values=list(MEDIA_KEYS) if self.action_type.get()==t('Media') else list(MODIFIERS)+list(HID_KEYS)
  self.target_combo.configure(values=values)
  if self.target.get() not in values:self.target.set(values[0])

 def _macros(self):
  p=self.pages['Macros']
  intro=pixel.panel(p,t('WHAT IS A MACRO?'));intro.pack(fill='x')
  tk.Label(intro,text=t('A macro makes one key press several keys for you, in order. For example, one key can copy, wait a moment and paste. Macros are stored inside the keyboard, so they work even when this app is closed.'),font=BODY,bg=PANEL,fg=INK,wraplength=880,justify='left',anchor='w').pack(fill='x')
  row=ttk.Frame(p);row.pack(fill='both',expand=True,pady=(12,0))
  examples=pixel.panel(row,t('1. START FROM AN EXAMPLE'));examples.pack(side='left',fill='y')
  for name,script in MACRO_EXAMPLES:
   b=PixelButton(examples,t(name),lambda s=script:self.use_example(s),bg=PANEL);b.pack(anchor='w',pady=(0,6))
  tk.Label(examples,text=t('Or write your own on the right.'),font=BODY,bg=PANEL,fg=MUTED).pack(anchor='w',pady=(6,0))
  ed=pixel.panel(row,t('2. THE STEPS'));ed.pack(side='left',fill='both',expand=True,padx=(12,0))
  chips=tk.Frame(ed,bg=PANEL);chips.pack(fill='x',pady=(0,10))
  for token in ('CTRL+C','CTRL+V','CTRL+Z','ALT+TAB','ENTER','WAIT 100'):
   chip=tk.Label(chips,text=token,font=BODY,bg=pixel.LINE_DK,fg=INK,padx=8,pady=2,cursor='hand2');chip.pack(side='left',padx=(0,6))
   chip.bind('<Button-1>',lambda e,t=token:self.insert_token(t))
  self.editor=tk.Text(ed,height=7,bg=pixel.DESK,fg=MINT,insertbackground=MINT,insertwidth=8,font=BODY,padx=12,pady=10,relief='flat',bd=0,undo=True,highlightthickness=2,highlightbackground=pixel.LINE_DK,highlightcolor=MINT)
  self.editor.pack(fill='both',expand=True);self.editor.insert('1.0','CTRL+C\nWAIT 150\nCTRL+V')
  self.editor.bind('<KeyRelease>',lambda e:self.check_macro(),add='+')
  self.macro_check=tk.StringVar();self.macro_check_label=tk.Label(ed,textvariable=self.macro_check,font=BODY,bg=PANEL,fg=MINT,anchor='w',justify='left',wraplength=560);self.macro_check_label.pack(fill='x',pady=(8,0))
  tk.Label(ed,text=t('One step per line:\n  CTRL+C  keys pressed together, joined with +\n  ENTER  a single key by its name (A, F5, ESC, SPACE...)\n  WAIT 100  wait 100 milliseconds before the next step\n  Click a card above to add it.'),font=BODY,bg=PANEL,fg=MUTED,justify='left',anchor='w').pack(fill='x',pady=(8,0))
  target=pixel.panel(p,t('3. WHICH KEY RUNS IT?'));target.pack(fill='x',pady=(12,0))
  f=tk.Frame(target,bg=PANEL);f.pack(anchor='w')
  self.macro_key=tk.StringVar();self.macro_key_combo=ttk.Combobox(f,textvariable=self.macro_key,state='disabled',width=18);self.macro_key_combo.pack(side='left')
  self.macro_key_combo.bind('<<ComboboxSelected>>',lambda e:self.pick_macro_key())
  self.macro_key_note=tk.StringVar(value=t('Connect the keyboard to choose a key.'));tk.Label(f,textvariable=self.macro_key_note,font=BODY,bg=PANEL,fg=INK,anchor='w').pack(side='left',padx=(12,0))
  tk.Label(target,text=t('Tip: pick a key you rarely use, such as Ins, PgUp or PgDn. That key will run the macro instead of its normal job. You can give it back its normal job on the Keymap page.'),font=BODY,bg=PANEL,fg=AMBER,wraplength=880,justify='left',anchor='w').pack(fill='x',pady=(10,0))
  slots=tk.Frame(target,bg=PANEL);slots.pack(fill='x',pady=(10,0))
  tk.Label(slots,text=t('Saved in slot'),font=BODY,bg=PANEL,fg=MUTED).pack(side='left',padx=(0,10))
  self.slot=tk.IntVar(value=1)
  self.slot_choice=pixel.Choice(slots,self.slot,[(n,f'{n:02d}') for n in range(1,17)],columns=8,width=4,marks=self.slot_used);self.slot_choice.pack(side='left')
  tk.Label(target,text=t('The keyboard keeps up to 16 macros. White numbers are slots already in use; a free slot is picked for you. To see what a slot holds, click it and press Load slot.'),font=BODY,bg=PANEL,fg=MUTED,wraplength=880,justify='left',anchor='w').pack(fill='x',pady=(6,0))
  f=ttk.Frame(p);f.pack(fill='x',pady=(12,0))
  self.macro_save_button=self.button(f,t('Save macro'),self.save_macro,True);self.button(f,t('Load slot'),self.load_macro);self.button(f,t('Check'),self.check_macro)
  self.macro_note=tk.StringVar(value=t('Choose the key that should run the macro, then press Save macro.'));tk.Label(p,textvariable=self.macro_note,font=BODY,bg=BG,fg=MINT,wraplength=880,justify='left',anchor='w').pack(fill='x',pady=(10,0))
  self.check_macro()
 def macro_keys(self):
  """(label, key) for physical keys that can run a macro; left/right twins get a side in their label."""
  counts={}
  for label,key,*_ in LAYOUT:counts[label]=counts.get(label,0)+1
  found=[]
  for label,key,*_ in LAYOUT:
   if self.lookup(key) is None:continue
   if counts[label]>1:label=label+' ('+t('right' if key.startswith('R') else 'left')+')'
   found.append((label,key))
  return found
 def refresh_macro_keys(self):
  keys=self.macro_keys();self.macro_choices=dict(keys)
  self.macro_key_combo.configure(values=[label for label,_ in keys],state='readonly' if keys else 'disabled')
  self.sync_macro_target()
 def sync_macro_target(self):
  """Mirror the selected key (shared with the Keymap page) in the macro key picker."""
  if not hasattr(self,'macro_choices'):return
  label=next((l for l,k in self.macro_choices.items() if self.selected is not None and self.lookup(k)==self.selected),'')
  self.macro_key.set(label)
  if not label:return self.macro_key_note.set(t('Choose a key from the list.') if self.macro_choices else t('Connect the keyboard to choose a key.'))
  entry=next(k for k in self.settings['keys'] if k['index']==self.selected)
  self.macro_key_note.set(t('Right now this key sends: {action}').format(action=entry['name']))
  self.macro_save_button.configure(text=t('Save macro to {key}').format(key=label))
 def pick_macro_key(self):
  key=self.macro_choices.get(self.macro_key.get())
  index=self.lookup(key) if key else None
  if index is None:return
  self.selected=index;self.update_selection();self.draw_boards(only=('map',))
  entry=next(k for k in self.settings['keys'] if k['index']==index)
  if entry['flag'] in (112,113):self.slot.set((entry['code']>>8)+1);self.load_macro()
  else:
   free=next((n for n in range(1,17) if not self.slot_used(n)),None)
   if free:self.slot.set(free)
  self.slot_choice.refresh();self.sync_macro_target()
 def use_example(self,script):
  self.editor.delete('1.0','end');self.editor.insert('1.0',script);self.editor.edit_separator();self.check_macro()
 def slot_used(self,slot):
  return bool(self.settings and any(m['slot']==slot and m['events'] for m in self.settings.get('macros',[])))
 def insert_token(self,token):
  line=self.editor.get('insert linestart','insert lineend').strip()
  self.editor.insert('insert lineend',('\n' if line else '')+token);self.editor.see('insert');self.editor.focus_set()

 def _battery(self):
  p=self.pages['Battery'];top=ttk.Frame(p);top.pack(fill='x')
  self.doctor_canvas=tk.Canvas(top,width=384,height=216,bg=PANEL,highlightthickness=2,highlightbackground=pixel.LINE_DK);self.doctor_canvas.pack(side='left',anchor='n')
  art=ASSETS/'assets/pixel/battery-scene.png'
  if art.exists():self.doctor_photo=tk.PhotoImage(file=str(art));self.doctor_canvas.create_image(2,2,anchor='nw',image=self.doctor_photo)
  right=ttk.Frame(top);right.pack(side='left',fill='both',expand=True,padx=(20,0))
  tk.Label(right,text=t('PACK VOLTAGE'),font=LABEL,bg=BG,fg=MUTED).pack(anchor='w')
  self.volts=tk.StringVar(value='-.-- V');self.volts_label=tk.Label(right,textvariable=self.volts,font=HUGE,bg=BG,fg=MINT);self.volts_label.pack(anchor='w',pady=(8,8))
  self.percent=tk.StringVar(value='-- %');self.battery_note=tk.StringVar(value=t('No report yet.'))
  tk.Label(right,textvariable=self.battery_note,font=BODY,bg=BG,fg=MUTED,wraplength=420,justify='left').pack(anchor='w')
  self.verdict=tk.StringVar(value=t('Plug in over USB to measure.'))
  tk.Label(right,textvariable=self.verdict,font=HEAD,bg=BG,fg=INK,wraplength=420,justify='left').pack(anchor='w',pady=(12,14))
  self.monitor_note=tk.StringVar(value=t('Monitoring stopped')+t(' / {count} readings').format(count=0));self.trend_note=tk.StringVar(value='')
  f=ttk.Frame(right);f.pack(anchor='w');self.button(f,t('Measure now'),self.read_battery,True);self.start_battery_button=self.button(f,t('Start monitoring'),self.start_monitor);self.stop_battery_button=self.button(f,t('Stop'),self.stop_monitor);self.stop_battery_button.configure(state='disabled')
  self.battery_warning=tk.Label(p,text=t('SAFETY: these steps mean opening the keyboard and powering a lithium battery from outside. Lithium batteries can get hot, swell or catch fire. If you are not comfortable with electronics, take it to a repair shop instead. Never leave it unattended.'),font=BODY,bg=BG,fg=PINK,wraplength=880,justify='left',anchor='w')
  self.steps=ttk.Frame(p);self.steps.pack(fill='x',pady=(12,0))
  self.chart=tk.Canvas(p,height=170,bg=PANEL,highlightthickness=2,highlightbackground=pixel.LINE_DK);self.chart.pack(fill='x',pady=(8,6));self.chart.bind('<Configure>',lambda event:self.draw_chart())
  f=ttk.Frame(p);f.pack(fill='x');tk.Label(f,textvariable=self.monitor_note,font=BODY,bg=BG,fg=MINT).pack(side='left');tk.Label(f,textvariable=self.trend_note,font=BODY,bg=BG,fg=AMBER).pack(side='left',padx=16)
  tk.Label(f,text=t('EXPORT'),font=LABEL,bg=BG,fg=MUTED,cursor='hand2').pack(side='right');f.winfo_children()[-1].bind('<Button-1>',lambda e:self.save_json(self.history.report(),'battery-session.json'))
  self.trend=ChargeTrend();self.health=None
  self.show_steps([t('Connect the keyboard over USB in wired mode.'),t('Voltage needs the Lavender Quest 0.6.0 build (Firmware page).')])
  # Compatibility with the launcher's --monitor-battery option.
  self.battery_panel=self
 def show_battery_warning(self,visible):
  if visible and not self.battery_warning.winfo_ismapped():self.battery_warning.pack(fill='x',pady=(12,0),before=self.steps)
  elif not visible:self.battery_warning.pack_forget()
 def show_steps(self,steps):
  for child in self.steps.winfo_children():child.destroy()
  for number,text in enumerate(steps,1):
   row=ttk.Frame(self.steps);row.pack(fill='x',pady=1)
   tk.Label(row,text=f'{number}.',font=HEAD,bg=BG,fg=MINT,width=3,anchor='w').pack(side='left',anchor='n')
   tk.Label(row,text=text,font=BODY,bg=BG,fg=INK,wraplength=820,justify='left').pack(side='left',anchor='w')
  self.fluid_text(self.steps)
 def start_monitor(self):
  self.monitoring=True;self.next_battery=0;self.trend.clear();self.monitor_state();self.status.set(t('Battery monitoring started / every 5 seconds.'))
 def stop_monitor(self):
  self.monitoring=False;self.monitor_state();self.status.set(t('Monitoring stopped. The last reading is retained.'))
 def monitor_state(self):
  self.monitor_note.set(t('Monitoring / every 5 seconds' if self.monitoring else 'Monitoring stopped')+t(' / {count} readings').format(count=self.history.total_successes))
  self.start_battery_button.configure(state='disabled' if self.monitoring else 'normal');self.stop_battery_button.configure(state='normal' if self.monitoring else 'disabled')

 def _firmware(self):
  p=self.pages['Firmware'];f=self.row(p)
  self.firmware_preview=ttk.Label(f,background=PANEL);self.firmware_preview.pack(side='left',padx=(0,24))
  info=ttk.Frame(f);info.pack(side='left',fill='both',expand=True)
  self.preview_title=tk.StringVar();ttk.Label(info,textvariable=self.preview_title,font=HEAD).pack(anchor='w',pady=10)
  self.preview_note=tk.StringVar();ttk.Label(info,textvariable=self.preview_note,style='Muted.TLabel',wraplength=350).pack(anchor='w')
  self.lcd_caption=tk.StringVar();tk.Label(p,textvariable=self.lcd_caption,font=BODY,bg=BG,fg=MINT,wraplength=880,justify='left',anchor='w').pack(fill='x')
  self.lcd_legend(p,BG)
  self.installed=tk.StringVar(value=t('Installed build: not checked'));ttk.Label(p,textvariable=self.installed,foreground=MINT).pack(anchor='w',pady=(16,8))
  self.build=tk.StringVar(value=BUILDS[0]);self.build_combo=ttk.Combobox(p,textvariable=self.build,values=BUILDS,state='readonly',width=44);self.build_combo.pack(anchor='w',pady=8)
  self.build.trace_add('write',lambda *args:self.update_firmware_preview())
  f=self.row(p);self.button(f,t('Import file'),self.choose_firmware);self.button(f,t('Check installed version'),self.read_version)
  self.allow_unreviewed=tk.BooleanVar(value=False)
  ttk.Checkbutton(p,text=t('Allow my unreviewed binary (hardware recovery may be required)'),variable=self.allow_unreviewed,command=self.unreviewed_toggled).pack(anchor='w',pady=6)
  self.label(p,t('Builds are made on this computer from the official V0113 firmware, downloaded once from VGN\'s own server. Offline? Import the official updater EXE or your own 236,916-byte .bin. Importing never uploads anything.'),True,wraplength=850)
  tk.Label(p,text='⚠ '+t('CAUTION: installing firmware rewrites the keyboard\'s own internal software. If it is interrupted (cable unplugged, power cut, computer goes to sleep) the keyboard may stop working. Lighting, keys and macros do NOT need a firmware install.'),font=BODY,bg=BG,fg=AMBER,wraplength=850,justify='left').pack(anchor='w',pady=(8,0))
  f=self.row(p);self.install_button=self.button(f,t('Install selected firmware'),self.install,True);self.button(f,t('Sync keyboard clock'),self.sync_clock)
  self.progress=ttk.Progressbar(p,maximum=4936);self.progress.pack(fill='x',pady=12)
  self.firmware_note=tk.StringVar(value=t('Select a build or inspect your own file, then explicitly click Install.'));ttk.Label(p,textvariable=self.firmware_note,style='Muted.TLabel',wraplength=880).pack(anchor='w')
  self.update_firmware_preview()
 def update_firmware_preview(self):
  name=self.build.get();original=name=='Original V0113';external=name.startswith(t('Selected file:'))
  self.preview_title.set(t('ORIGINAL V0113' if original else ('YOUR FIRMWARE' if external else 'X68 PIXEL DESKTOP')))
  self.lcd_build=None if original or external else firmware_source.BUILDS.get(name)
  if original or external:
   self.preview_note.set(t('VGN\'s factory firmware, unchanged. Use it to roll back.') if original else t('No trusted visual preview for an imported binary. Inspect its checks before installing.'))
   self.firmware_preview.configure(image='',text=t(' FACTORY FIRMWARE \n\n VGN V0113 ' if original else ' CUSTOM BINARY \n\n NO TRUSTED PREVIEW '),font=HEAD,foreground=MUTED,width=23,padding=30)
   self.lcd_caption.set('')
  else:
   installed=self.lavender_build()==self.lcd_build
   self.preview_note.set(t(BUILD_NOTES.get(self.lcd_build,''))+('\n\n'+t('This build is installed on your keyboard now.') if installed else ''))
   self.lcd_caption.set(t('Live preview of this build: the clock runs, and the Windows/Mac and lock badges change every few seconds to show what they look like.'))
   self.firmware_preview.configure(text='',width=0,padding=0);self.lcd_phase=None;self.draw_lcd_preview()
 def lavender_build(self):
  """Patch name of the Lavender build the keyboard reports, if it is one the preview can draw."""
  name=KNOWN_BUILDS.get((self.version or {}).get('reported_crc'),'')
  build=name.lower().replace(' ','-')
  return build if build in lcd_preview.FEATURES else None
 def lcd_frame(self,build,moment,phase):
  if build not in self.lcd_backgrounds:
   try:stock=firmware_source.stock(CACHE,download=False)
   except (OSError,ValueError):stock=None
   self.lcd_backgrounds[build]=lcd_preview.background(firmware_source.PATCHES/f'{build}.json',stock)
  demo=int(moment.timestamp()//3)%4
  battery=next((s.get('reported_percent') for s in reversed(self.history.samples) if s.get('reported_percent') is not None),80)
  frame=lcd_preview.render(build,self.lcd_backgrounds[build],moment,twelve=self.clock_format.get()==t('12-hour (AM/PM)'),mac=demo in (1,3),locked=demo>=2,battery=min(100,max(0,int(battery))),phase=phase)
  return ImageTk.PhotoImage(Image.frombytes('RGB',(160,96),lcd_preview.to_rgb(frame)).resize((400,240),Image.Resampling.NEAREST))
 def draw_lcd_preview(self):
  if not getattr(self,'lcd_build',None):return
  now=datetime.now();phase=int(time.monotonic()*4)
  if phase==self.lcd_phase:return
  self.lcd_phase=phase;self.firmware_photo=self.lcd_frame(self.lcd_build,now,phase);self.firmware_preview.configure(image=self.firmware_photo)
 def lcd_legend(self,parent,bg):
  """What each part of the Lavender screen means, and how to change it."""
  tk.Label(parent,text=t('ON THE SCREEN'),font=LABEL,bg=bg,fg=MUTED,anchor='w').pack(fill='x',pady=(12,6))
  for item in LCD_LEGEND:
   tk.Label(parent,text='• '+t(item),font=BODY,bg=bg,fg=INK,wraplength=880,justify='left',anchor='w').pack(fill='x',pady=1)
 def choose_firmware(self):
  if self.busy:return
  path=filedialog.askopenfilename(parent=self.root,title=t('Import the official updater or a V0113 .bin'),filetypes=[(t('Firmware or official updater'),'*.bin *.exe')])
  if not path:return
  def inspect():
   from .firmware import inspect_custom_firmware,V0113_SIZE
   try:return 'official',firmware_source.import_file(CACHE,Path(path))
   except ValueError:pass
   if Path(path).stat().st_size!=V0113_SIZE:raise ValueError(t('Not the official updater and not a 236,916-byte V0113 .bin.'))
   data=Path(path).read_bytes();return 'custom',(data,inspect_custom_firmware(data,firmware_source.stock(CACHE)))
  self.submit('Inspecting firmware file',inspect,lambda result:self.firmware_imported(path,*result))
 def firmware_imported(self,path,kind,value):
  if kind=='official':
   self.firmware_note.set(t('Official V0113 recognised by SHA256 and cached. All builds can now be made offline.'));return self.status.set(t('Official firmware imported. Nothing was uploaded.'))
  data,record=value;self.external_firmware=(data,record);self.allow_unreviewed.set(False)
  name=t('Selected file:')+' '+Path(path).name;self.build_combo.configure(values=BUILDS+[name]);self.build.set(name)
  self.firmware_note.set(f'{record["bytes"]:,} '+t('bytes')+f' / CRC {record["crc"]} / '+t('Known reviewed image' if record['reviewed'] else 'Structurally valid; code and hardware behavior are NOT reviewed')+' / SHA256 '+record['sha256'])
  self.status.set(t('File inspected locally. Nothing was uploaded.'))

 def _screen(self):
  self.screen_scroll,p,_=self.scrollers['Screen'];self.screen_content=p
  self.root.bind('<MouseWheel>',self.scroll_screen,add='+')
  self.root.bind('<Button-4>',self.scroll_screen,add='+');self.root.bind('<Button-5>',self.scroll_screen,add='+')
  left=pixel.panel(p,'LCD  160 x 96');left.pack(side='left',fill='y')
  self.screen_preview=tk.Label(left,bg=PANEL,bd=0);self.screen_preview.pack(anchor='w')
  preview=ASSETS/'assets/pixel/lcd-preview.png'
  if preview.exists():
   with Image.open(preview) as source:photo=ImageTk.PhotoImage(source.resize((400,240),Image.Resampling.NEAREST))
   self.photos.append(photo);self.screen_preview.configure(image=photo)
  f=tk.Frame(left,bg=PANEL);f.pack(fill='x',pady=(12,0))
  self.fit=tk.StringVar(value='Crop');pixel.Choice(f,self.fit,[(v,t(v)) for v in ('Crop','Fit','Stretch')],columns=3).pack(side='left')
  self.fit.trace_add('write',lambda *args:self.reconvert())
  f=tk.Frame(left,bg=PANEL);f.pack(fill='x',pady=(10,0));self.button(f,t('Choose image / GIF'),self.choose_media);self.button(f,t('Upload'),self.send_media,True)
  self.media_note=tk.StringVar(value=t('PNG, JPG, GIF, WEBP or BMP. Long GIFs are sampled to 8 frames.'))
  tk.Label(left,textvariable=self.media_note,font=BODY,bg=PANEL,fg=MINT,wraplength=400,justify='left').pack(anchor='w',pady=(10,6))
  self.media_progress=ttk.Progressbar(left,maximum=100);self.media_progress.pack(fill='x')
  self._screens(left)
  right=ttk.Frame(p);right.pack(side='left',fill='both',expand=True,padx=(12,0))
  scene=pixel.panel(right,t('SCENE'));scene.pack(fill='x')
  scene_note=tk.Label(scene,text=t('The keyboard screen shows either the clock scene or the image/GIF you upload. A new upload replaces the previous one. Press the button below to go back to the clock scene.'),font=BODY,bg=PANEL,fg=MUTED,wraplength=340,justify='left',anchor='w');scene_note.pack(fill='x',pady=(0,10))
  scene.bind('<Configure>',lambda e:scene_note.configure(wraplength=max(120,e.width-32)))
  f=tk.Frame(scene,bg=PANEL);f.pack(anchor='w');self.button(f,t('Lavender desktop'),lambda:self.change_screen(0));self.button(f,t('Show my image/GIF'),lambda:self.change_screen(4))
  self.screen_mode_note=tk.StringVar(value=t('Connect the keyboard to see which screen is showing.'))
  tk.Label(scene,textvariable=self.screen_mode_note,font=BODY,bg=PANEL,fg=MINT,wraplength=880,justify='left',anchor='w').pack(fill='x',pady=(8,0))
  tk.Label(scene,text=t('The keyboard has 5 screen modes (0-4); Fn + PgUp / PgDn steps through them. On Lavender, modes 0-3 all show the clock scene and mode 4 shows your uploaded image/GIF.'),font=BODY,bg=PANEL,fg=MUTED,wraplength=880,justify='left',anchor='w').pack(fill='x',pady=(4,0))
  clock=pixel.panel(right,t('CLOCK'));clock.pack(fill='both',expand=True,pady=(12,0))
  ttk.Checkbutton(clock,text=t('Sync time automatically'),variable=self.auto_clock,command=self.clock_preference,style='Field.TCheckbutton').pack(anchor='w',pady=4)
  f=tk.Frame(clock,bg=PANEL);f.pack(anchor='w',pady=6);tk.Label(f,text=t('Every'),font=BODY,bg=PANEL,fg=INK).pack(side='left')
  interval=ttk.Combobox(f,textvariable=self.clock_interval,values=['1','2','5','10','15','30','60'],state='readonly',width=4);interval.pack(side='left',padx=10);interval.bind('<<ComboboxSelected>>',lambda event:self.clock_preference())
  tk.Label(f,text=t('minutes'),font=BODY,bg=PANEL,fg=INK).pack(side='left')
  f=tk.Frame(clock,bg=PANEL);f.pack(anchor='w',pady=6);tk.Label(f,text=t('Time format'),font=BODY,bg=PANEL,fg=INK).pack(side='left')
  self.clock_format_choice=ttk.Combobox(f,textvariable=self.clock_format,values=[t('24-hour'),t('12-hour (AM/PM)')],state='readonly',width=16);self.clock_format_choice.pack(side='left',padx=10)
  self.clock_format_choice.bind('<<ComboboxSelected>>',lambda event:self.clock_format_preference())
  self.startup_control=ttk.Checkbutton(clock,text=t('Open at login on Mac' if sys.platform=='darwin' else 'Launch when I sign in to Windows'),variable=self.start_on_login,command=self.startup_preference,style='Field.TCheckbutton');self.startup_control.pack(anchor='w',pady=4)
  if sys.platform not in ('win32','darwin'):self.startup_control.configure(state='disabled')
  f=tk.Frame(clock,bg=PANEL);f.pack(anchor='w',pady=(8,0));self.clock_sync_button=self.button(f,t('Sync time now'),self.sync_clock)
  self.clock_note_label=tk.Label(clock,textvariable=self.clock_note,font=BODY,bg=PANEL,fg=MINT,wraplength=340,justify='left',anchor='w');self.clock_note_label.pack(fill='x',pady=8)
  help_note=tk.Label(clock,text=t('AM/PM needs Lavender Quest 0.8.0 or newer. On 2.4 GHz, the format is checked after syncing; use wired USB if it cannot be verified.'),font=BODY,bg=PANEL,fg=MUTED,wraplength=340,justify='left',anchor='w');help_note.pack(fill='x')
  ram_note=tk.Label(clock,text=t('Time and format stay in RAM. After a full power loss, reopen the app to sync again.'),font=BODY,bg=PANEL,fg=MUTED,wraplength=340,justify='left',anchor='w');ram_note.pack(fill='x',pady=(10,0))
  clock.bind('<Configure>',lambda e:[label.configure(wraplength=max(120,e.width-32)) for label in (self.clock_note_label,help_note,ram_note)])

 def _screens(self,parent):
  """Screens 1-4, each with its own image/GIF (Lavender Quest 0.10.0)."""
  panel=pixel.panel(parent,t('SEPARATE SCREENS'));panel.pack(fill='x',pady=(14,0))
  tk.Label(panel,text=t('With Lavender Quest 0.10.0, screens 1-4 each show their own image or GIF and Fn + PgUp steps through them. Screen 0 is always the clock. All screens share 8 frames.'),font=BODY,bg=PANEL,fg=MUTED,wraplength=380,justify='left',anchor='w').pack(fill='x')
  self.screen_slots=[None]*SCREENS;self.slot_thumbs=[None]*SCREENS;self.slot_info=[];self.slot_images=[]
  self.slot_fit=[tk.StringVar(value='Crop') for _ in range(SCREENS)]
  for index in range(SCREENS):
   row=tk.Frame(panel,bg=PANEL);row.pack(fill='x',pady=(8,0))
   tk.Label(row,text=t('Screen {n}').format(n=index+1),font=BODY,bg=PANEL,fg=INK,anchor='w',width=8).pack(side='left')
   image=tk.Label(row,bg=pixel.DESK,width=10,height=3);image.pack(side='left',padx=(0,8));self.slot_images.append(image)
   info=tk.StringVar(value=t('empty'));self.slot_info.append(info)
   tk.Label(row,textvariable=info,font=BODY,bg=PANEL,fg=MUTED,anchor='w',width=9).pack(side='left')
   fit=tk.Frame(panel,bg=PANEL);fit.pack(fill='x',pady=(4,0))
   pixel.Choice(fit,self.slot_fit[index],[(v,t(v)) for v in ('Crop','Fit','Stretch')],columns=3).pack(side='left')
   self.slot_fit[index].trace_add('write',lambda *args,n=index:self.refit_screen_media(n))
   buttons=tk.Frame(panel,bg=PANEL);buttons.pack(fill='x',pady=(4,0))
   self.button(buttons,t('Choose'),lambda n=index:self.choose_screen_media(n))
   self.button(buttons,t('Clear'),lambda n=index:self.clear_screen_media(n))
   self.button(buttons,t('Show'),lambda n=index:self.change_screen(n+1))
  self.frame_budget=tk.StringVar();tk.Label(panel,textvariable=self.frame_budget,font=BODY,bg=PANEL,fg=MINT,anchor='w').pack(fill='x',pady=(10,0))
  f=tk.Frame(panel,bg=PANEL);f.pack(anchor='w',pady=(8,0));self.screens_button=self.button(f,t('Upload all screens'),self.send_screens,True)
  self.screens_note=tk.StringVar(value='');tk.Label(panel,textvariable=self.screens_note,font=BODY,bg=PANEL,fg=AMBER,wraplength=380,justify='left',anchor='w').pack(fill='x',pady=(6,0))
  self.load_screen_choices()
 def screen_frames_used(self,skip=None):
  return sum(len(m.frames) for i,m in enumerate(self.screen_slots) if m is not None and i!=skip)
 def refresh_screen_rows(self):
  for index,media in enumerate(self.screen_slots):
   if media is None:
    self.slot_info[index].set(t('empty'));self.slot_images[index].configure(image='',width=10,height=3);self.slot_thumbs[index]=None
   else:
    self.slot_info[index].set(t('{count} frames').format(count=len(media.frames)))
    self.slot_thumbs[index]=ImageTk.PhotoImage(media.frames[0].resize((80,48),Image.Resampling.NEAREST))
    self.slot_images[index].configure(image=self.slot_thumbs[index],width=80,height=48)
  self.frame_budget.set(t('Frames used: {used} / {total}').format(used=self.screen_frames_used(),total=MAX_FRAMES))
  multi=(self.version or {}).get('reported_crc') in MULTI_SCREEN_CRCS
  self.screens_note.set('' if multi else t('Needs Lavender Quest 0.10.0 (experimental) from the Firmware page. On other builds screens 1-3 show the clock.'))
 def save_screen_choices(self):
  self.save_preferences(screens=[None if m is None else {'path':m.source,'fit':m.fit,'frames':len(m.frames)} for m in self.screen_slots])
 def load_screen_choices(self):
  try:preferences=json.loads((WORK/'preferences.json').read_text(encoding='utf-8'))
  except (OSError,ValueError):preferences={}
  for index,entry in enumerate((preferences.get('screens') or [])[:SCREENS]):
   if not entry:continue
   if entry.get('fit') in ('Crop','Fit','Stretch'):self.slot_fit[index].set(entry['fit'])
   try:self.screen_slots[index]=convert_media(entry['path'],entry.get('fit','Crop'),max_frames=max(1,min(MAX_FRAMES,int(entry.get('frames',MAX_FRAMES)))))
   except (OSError,ValueError,KeyError):self.screen_slots[index]=None
  if self.screen_frames_used()>MAX_FRAMES:self.screen_slots=[None]*SCREENS
  self.refresh_screen_rows()
 def choose_screen_media(self,index):
  if self.busy:return
  room=MAX_FRAMES-self.screen_frames_used(skip=index)
  if room<1:return self.status.set(t('No frames left. Clear another screen first.'))
  path=filedialog.askopenfilename(parent=self.root,title=t('Choose an image or animation'),filetypes=[(t('Images and animations'),'*.png *.jpg *.jpeg *.gif *.webp *.bmp'),(t('All files'),'*.*')])
  if not path:return
  fit=self.slot_fit[index].get()
  self.submit('Converting image',lambda:convert_media(path,fit,max_frames=room),lambda media:self.screen_media_ready(index,media))
 def refit_screen_media(self,index):
  """Crop / Fit / Stretch changed for a screen: convert its picture again (nothing is sent)."""
  media=self.screen_slots[index];fit=self.slot_fit[index].get()
  if media is None or media.fit==fit or self.busy:return
  path,frames=media.source,len(media.frames)
  self.submit('Converting image',lambda:convert_media(path,fit,max_frames=frames),lambda result:self.screen_media_ready(index,result))
 def screen_media_ready(self,index,media):
  self.screen_slots[index]=media;self.save_screen_choices();self.refresh_screen_rows()
  self.status.set(t('Screen {n} ready: {count} frames. Nothing has been sent yet.').format(n=index+1,count=len(media.frames)))
 def clear_screen_media(self,index):
  self.screen_slots[index]=None;self.save_screen_choices();self.refresh_screen_rows()
 def send_screens(self):
  if self.busy:return
  if (self.version or {}).get('reported_crc') not in MULTI_SCREEN_CRCS:return self.status.set(t('Needs Lavender Quest 0.10.0 (experimental) from the Firmware page. On other builds screens 1-3 show the clock.'))
  if not any(self.screen_slots):return self.status.set(t('Choose an image for at least one screen.'))
  if not messagebox.askokcancel(t('Upload all screens'),t('Upload all four screens now?\n\nThis replaces every image on the keyboard, including a single image uploaded earlier. Keep USB connected until it finishes.'),icon='warning',default='cancel',parent=self.root):return
  slots=list(self.screen_slots);show=next(i+1 for i,m in enumerate(slots) if m is not None)
  self.flashing=True;self.monitoring=False;self.stop_test();self.media_progress['value']=0
  self.submit('Uploading screens',lambda:upload_screens(self.settings_client,slots,WORK,show=show,progress=lambda n,total:self.results.put(('media_progress',n,total))),lambda result:self.screens_uploaded(show))
 def screens_uploaded(self,show):
  self.flashing=False;self.media_progress['value']=100;self.next_clock_sync=0;self.show_screen_mode(show)
  self.status.set(t('All screens uploaded. Screen {n} is showing; use the Show buttons or Fn + PgUp to switch.').format(n=show))
  self.root.after(100,self.read_settings)
 def scrollable(self,name,fill=False):
  """Wrap a page in a vertical scroller so long text never pushes controls out of reach.

  The content fills the page when it fits (so expanding widgets still expand) and scrolls when it
  does not; the scrollbar is shown only while it is needed.
  """
  page=self.page_frames[name]
  canvas=tk.Canvas(page,bg=BG,highlightthickness=0,width=1,height=1,yscrollincrement=16)
  scrollbar=ttk.Scrollbar(page,orient='vertical',command=canvas.yview)
  canvas.configure(yscrollcommand=scrollbar.set);canvas.pack(side='left',fill='both',expand=True)
  content=ttk.Frame(canvas);item=canvas.create_window(0,0,window=content,anchor='nw')
  def fit(event=None):
   view=canvas.winfo_height();need=content.winfo_reqheight();width=canvas.winfo_width()
   canvas.itemconfigure(item,width=width if width>1 else 0,height=view if fill and 1<view and need<=view else 0)
   canvas.configure(scrollregion=(0,0,max(width,content.winfo_reqwidth()),max(need,view)))
   if view<=1:return
   if need>view+1 and not scrollbar.winfo_manager():scrollbar.pack(side='right',fill='y',padx=(8,0),before=canvas)
   elif need<=view+1 and scrollbar.winfo_manager():scrollbar.pack_forget();canvas.yview_moveto(0)
  canvas.bind('<Configure>',fit);content.bind('<Configure>',fit)
  self.scrollers[name]=(canvas,content,fit);return canvas,content
 def scroll_screen(self,event):
  if self.page_name not in self.scrollers:return
  canvas,content,_=self.scrollers[self.page_name]
  widget=event.widget
  while widget is not None and widget not in (content,canvas):
   if isinstance(widget,(ttk.Combobox,tk.Text,tk.Listbox)):return
   widget=getattr(widget,'master',None)
  if widget is None or canvas.yview()==(0.0,1.0):return
  number=getattr(event,'num',None);delta=getattr(event,'delta',0)
  steps=(-1 if number==4 else 1) if number in (4,5) else (-int(delta) if sys.platform=='darwin' else -int(delta/120))
  if steps:canvas.yview_scroll(steps,'units');return 'break'

 def choose_media(self):
  if self.busy:return
  path=filedialog.askopenfilename(parent=self.root,title=t('Choose an image or animation'),filetypes=[(t('Images and animations'),'*.png *.jpg *.jpeg *.gif *.webp *.bmp'),(t('All files'),'*.*')])
  if path:self.prepare_media(path)
 def reconvert(self):
  if self.prepared and not self.busy:self.prepare_media(self.prepared.source)
 def prepare_media(self,path):
  fit=self.fit.get();self.submit('Converting image',lambda:convert_media(path,fit),self.media_ready)
 def media_ready(self,prepared):
  self.prepared=prepared;self.media_photos=[ImageTk.PhotoImage(frame.resize((400,240),Image.Resampling.NEAREST)) for frame in prepared.frames]
  self.media_frame=0;self.media_due=0;self.media_progress['value']=0
  self.media_note.set(t('{name}  /  {source} → {frames} frames  /  {period} ms per frame  /  {size} bytes').format(name=Path(prepared.source).name,source=prepared.source_frames,frames=len(prepared.frames),period=prepared.period_ms,size=f'{len(prepared.data):,}'))
  self.status.set(t('Preview ready. Nothing has been sent to the keyboard.'))
 def send_media(self):
  if self.busy:return
  if not self.prepared:return self.status.set(t('Choose an image or GIF first.'))
  wireless=bool(self.inventory and self.inventory.get('transport')=='wireless')
  if not wireless and (not self.version or self.version.get('reported_crc') not in LIVE_CLOCK_CRCS):return self.status.set(t('Install Lavender Quest 0.6.0 in Firmware first.'))
  if not messagebox.askokcancel(t('Replace custom animation'),t('Upload the converted preview?\n\nThis replaces the keyboard’s entire custom image/GIF bank. The previous animation cannot be read back.\nKeep USB connected until the transfer completes.'),icon='warning',default='cancel',parent=self.root):return
  prepared=self.prepared;self.flashing=True;self.monitoring=False;self.stop_test();self.media_progress['value']=0
  self.submit('Uploading screen media',lambda:upload_media(self.settings_client,prepared,WORK,lambda n,total:self.results.put(('media_progress',n,total))),self.media_uploaded)
 def media_uploaded(self,result):
  self.flashing=False;self.media_progress['value']=100;self.next_clock_sync=0
  self.media_note.set(t('Transfer acknowledged; display settings read back. Check the physical screen. Converted data and transfer log saved in reports/media.'))
  self.status.set(t('Custom media selected. Use Lavender desktop to return to the clock scene.'))
 def change_screen(self,mode):
  wireless=bool(self.inventory and self.inventory.get('transport')=='wireless')
  if not wireless and (not self.version or self.version.get('reported_crc') not in LIVE_CLOCK_CRCS):return self.status.set(t('Install Lavender Quest 0.6.0 first.'))
  multi=(self.version or {}).get('reported_crc') in MULTI_SCREEN_CRCS
  if multi and 1<=mode<=4 and self.parameter_byte(45)==ord('X') and self.parameter_byte(49+(mode-1)*4) in (0,None):return self.status.set(t('Screen {n} is empty on the keyboard; it shows the clock. Upload screens first.').format(n=mode))
  if mode==4 and not multi and self.parameter_byte(34) in (0,None):return self.status.set(t('Upload an image or GIF first; there is nothing to show yet.'))
  self.submit('Selecting screen',lambda:set_screen(self.settings_client,mode),lambda result:self.screen_changed(mode))
 def screen_changed(self,mode=0):
  self.next_clock_sync=0;self.status.set(t('Lavender desktop selected.') if mode==0 else t('Your image/GIF is now on the keyboard screen.'))
  self.show_screen_mode(mode);self.root.after(100,self.read_settings)
 def parameter_byte(self,index):
  """A byte of the keyboard's parameter block as last read (None before the first read)."""
  raw=((self.settings or {}).get('lighting') or {}).get('raw_hex')
  return bytes.fromhex(raw.replace(' ',''))[index] if raw else None
 def show_screen_mode(self,mode=None):
  mode=self.parameter_byte(33) if mode is None else mode
  if mode is None:return
  multi=(self.version or {}).get('reported_crc') in MULTI_SCREEN_CRCS
  what=t('clock scene') if mode==0 else (t('screen {n} image/GIF').format(n=mode) if multi else (t('your image/GIF') if mode==4 else t('clock scene')))
  self.screen_mode_note.set(t('Showing now: screen {mode} - {what}').format(mode=mode,what=what))
 def clock_preference(self):
  WORK.mkdir(parents=True,exist_ok=True);self.save_preferences(auto_clock=self.auto_clock.get(),clock_interval_minutes=int(self.clock_interval.get()));self.next_clock_sync=0
 def clock_format_preference(self):
  self.save_preferences(clock_hour_format=12 if self.clock_format.get()==t('12-hour (AM/PM)') else 24)
  self.next_clock_sync=0;self.clock_text.set(self.format_time(datetime.now()))
  self.clock_note.set(t('Time format saved. Press Sync time now to apply to the keyboard.'))
 def startup_preference(self):
  try:
   autostart.configure(self.start_on_login.get());self.status.set(t(('The app will open at your next Mac login.' if sys.platform=='darwin' else 'Windows startup enabled.') if self.start_on_login.get() else 'Open at login disabled.'))
  except OSError as error:
   self.start_on_login.set(autostart.enabled());self.status.set(t('Startup setting failed: ')+str(error))
 def sync_clock(self,manual=True):
  def explain(message):
   self.clock_note.set(message)
   if manual:self.status.set(message)
  if not self.inventory or not self.version:
   self.next_clock_sync=time.monotonic()+60;return explain(t('Connect the keyboard and wait for its settings to load before syncing.'))
  wireless=bool(self.inventory and self.inventory.get('transport')=='wireless')
  if not wireless and (not self.version or self.version.get('reported_crc') not in LIVE_CLOCK_CRCS):
   self.next_clock_sync=time.monotonic()+60;return explain(t('Live sync requires Lavender Quest 0.5.1 or newer. Install it in Firmware.'))
  if self.busy:return explain(t('Another operation is running. Try Sync time now when it finishes.'))
  hour_format=12 if self.clock_format.get()==t('12-hour (AM/PM)') else 24
  if hour_format==12 and not wireless and self.version['reported_crc'] not in CLOCK_FORMAT_CRCS:
   self.next_clock_sync=float('inf');return explain(t('AM/PM needs Lavender Quest 0.8.0 or newer. Check the installed build in Firmware.'))
  crc=self.version['reported_crc'];self.next_clock_sync=time.monotonic()+60
  self.clock_note.set(t('Applying {format} time to the keyboard...').format(format=t('12-hour (AM/PM)' if hour_format==12 else '24-hour')))
  self.submit('Syncing keyboard clock',lambda:self.settings_client.sync_clock_live(crc,receiver=wireless,hour_format=hour_format),self.clock_synced)
 def clock_synced(self,result):
  self.next_clock_sync=time.monotonic()+int(self.clock_interval.get())*60
  moment=datetime.fromisoformat(result['local_time']);hour_format=result.get('hour_format',24)
  rendered=moment.strftime('%I:%M:%S %p') if hour_format==12 else moment.strftime('%H:%M:%S')
  message=t('Keyboard synced: {time} / {format}').format(time=rendered,format=t('12-hour (AM/PM)' if hour_format==12 else '24-hour'))
  self.clock_note.set(message);self.status.set(message)

 def _knowledge(self):
  p=self.pages['Knowledge'];self.label(p,t('FACTS YOU CAN TAKE WITH YOU'),font=HEAD)
  self.label(p,t('Copy this context into an AI chat. Verified behavior and open questions are explicitly separated. No private device paths are included.'),True,wraplength=880)
  f=self.row(p);self.button(f,t('Copy AI context'),self.copy_knowledge,True);self.button(f,t('Export Markdown'),self.export_knowledge);self.button(f,t('Export JSON'),lambda:self.save_json(self.knowledge_record(),'x68-knowledge.json'))
  body=ttk.Frame(p);body.pack(fill='both',expand=True,pady=10)
  text=tk.Text(body,height=12,bg=PANEL,fg=INK,font=BODY,wrap='word',relief='flat',padx=16,pady=14)
  scroll=ttk.Scrollbar(body,command=text.yview);scroll.pack(side='right',fill='y');text.configure(yscrollcommand=scroll.set);text.pack(fill='both',expand=True)
  try:self.knowledge=(ASSETS/'docs/AI-KNOWLEDGE.md').read_text(encoding='utf-8')
  except OSError:self.knowledge=t('Knowledge file missing. Use the complete application folder.')
  text.insert('1.0',self.knowledge);text.configure(state='disabled')
 def knowledge_record(self):return {'application':'VGN X68 Custom Firmware','version':'0.9.2','custom_crc':RETRO_BADGE_CRC,'format':'Markdown','context':self.knowledge,'unknowns':['Battery current and charge control (voltage is an estimate via an inferred 1:2 divider)','Early SUBOR splash storage','Physical macOS validation','Custom-media physical validation pending']}
 def copy_knowledge(self):self.root.clipboard_clear();self.root.clipboard_append(self.knowledge);self.status.set(t('AI context copied to clipboard.'))
 def export_knowledge(self):
  path=filedialog.asksaveasfilename(parent=self.root,initialfile='X68-AI-KNOWLEDGE.md',defaultextension='.md',filetypes=[('Markdown','*.md')])
  if path:Path(path).write_text(self.knowledge,encoding='utf-8');self.status.set(t('Knowledge exported.'))

 def _advanced(self):
  p=self.pages['Advanced'];tabs=ttk.Notebook(p);tabs.pack(fill='both',expand=True)
  raw=ttk.Frame(tabs,padding=12);test=ttk.Frame(tabs,padding=12);tools=ttk.Frame(tabs,padding=12)
  tabs.add(raw,text=t('Device & packets'));tabs.add(test,text=t('Key tester'));tabs.add(tools,text=t('Backups & logs'))
  self.raw=tk.Text(raw,height=12,bg=PANEL,fg=MUTED,font=BODY,wrap='word',relief='flat',padx=12,pady=12,state='disabled');self.raw.pack(fill='both',expand=True)
  self.label(test,t('Focused-window Raw Input from the X68 only. Key tester requires Windows.'),True)
  self.test_canvas=tk.Canvas(test,height=245,bg=PANEL,highlightthickness=0);self.test_canvas.pack(fill='x',pady=14)
  f=self.row(test);self.button(f,t('Start 60-second test'),self.start_test,True);self.button(f,t('Stop test'),self.stop_test);self.button(f,t('Clear results'),self.clear_test)
  self.test_note=tk.StringVar(value=t('No key events recorded.'));ttk.Label(test,textvariable=self.test_note,wraplength=850).pack(anchor='w',pady=14)
  self.label(tools,t('Every settings write creates a backup and verifies readback.'),True,wraplength=850)
  f=self.row(tools);self.button(f,t('Restore settings backup'),self.restore);self.button(f,t('Export diagnostics'),lambda:self.save_json(self.report(),'x68-diagnostics.json'));self.button(f,t('Open reports folder'),self.open_reports)
  self.button(self.row(tools),t('Read cached ADC snapshot'),self.read_adc_snapshot)
  self.label(tools,t('Advanced matrix-cell selection (optional):'),True)
  self.source_combo=ttk.Combobox(tools,textvariable=self.source,state='readonly',width=45);self.source_combo.pack(anchor='w',pady=8);self.source_combo.bind('<<ComboboxSelected>>',self.select_matrix)
  self.log_text=tk.Text(tools,height=8,bg=PANEL,fg=MUTED,font=BODY,wrap='word',relief='flat',padx=12,pady=12,state='disabled');self.log_text.pack(fill='both',expand=True,pady=15)

 def submit(self,name,func,done=None):
  if self.closed:return False
  if self.busy:self.status.set(t('{operation} is still running. Please wait.').format(operation=t(self.operation)));return False
  self.busy=True;self.operation=name;self.operation_started=time.monotonic();self.status.set(t(name)+'...')
  future=self.pool.submit(func)
  def completed(f):
   try:self.results.put(('done',name,f.result(),None,done))
   except Exception as error:self.results.put(('done',name,None,str(error),done))
  future.add_done_callback(completed);return True
 def refresh(self):
  if self.busy:return
  self.inventory=None;self.settings=None;self.version=None;self.next_reconnect=time.monotonic()+5
  self.needs_battery_read=True
  self.connect_button.configure(text=t('Connecting...'),state='disabled');self.submit('Finding X68',self.client.inventory,self.found)
 def found(self,result):
  self.inventory=result;usb=result.get('transport')!='wireless';self.device.set('[+]  SUBOR X68 / '+('USB' if usb else '2.4 GHz'));self.usb_mode.set(t('USB / wired mode' if usb else '2.4 GHz receiver (firmware and LCD media need USB)'));self.connect_button.configure(text=t('Refresh'),state='normal');self.status.set(t('Connected. Device protocol verified.'))
  if self.monitor:self.monitor.close()
  try:
   if sys.platform=='win32':
    from .windows_input import RawKeyboard
    self.monitor=RawKeyboard(self.root,[d['path'] for d in result['interfaces']],self.keys)
  except Exception as error:self.logs.append({'key_test_error':str(error)})
  if not self.smoke:self.read_settings()
 def read_settings(self):self.submit('Reading keyboard settings',self.settings_client.read_settings,self.show_settings)
 def show_settings(self,result):
  self.settings=result;lighting=result['lighting']
  if lighting:
   self.effect.set(EFFECTS[lighting['mode']-1]);self.brightness.set(lighting['brightness']);self.speed.set(lighting['speed']);self.color.set(lighting['color'])
   # Show what the keyboard does now. FF (meaning unverified) lights up multicolour on the device, so it stays 'Keep' but previews as rainbow.
   self.device_rainbow=lighting['rainbow_raw']!=0;self.rainbow.set({0:'Single colour',1:'Rainbow'}.get(lighting['rainbow_raw'],'Keep device flag'))
  self.editable=[k for k in result['keys'] if k['editable']]
  self.source_combo.configure(values=[t('Cell')+f" {k['index']:03d}  /  {k['name']}" for k in self.editable])
  self.update_selection()
  self.lighting_changed();self.refresh_macro_keys();self.show_screen_mode()
  self.status.set(t('Settings loaded. Nothing is written until you press Send.'));self.next_clock_sync=0;self.draw_boards();self.slot_choice.refresh()
  if not self.version:self.read_version()
 def read_version(self):self.submit('Checking installed build',self.client.query_version,self.show_version)
 def save_preferences(self,**values):
  try:preferences=json.loads((WORK/'preferences.json').read_text(encoding='utf-8'))
  except (OSError,ValueError):preferences={}
  WORK.mkdir(parents=True,exist_ok=True);(WORK/'preferences.json').write_text(json.dumps({**preferences,**values}),encoding='utf-8')
 def show_version(self,result):
  self.version=result;self.next_clock_sync=0;crc=result['reported_crc'];known=dict(KNOWN_BUILDS)
  if self.inventory and self.inventory.get('transport')=='wireless':known={}
  self.installed.set(t('Installed: {build}  /  CRC {crc}').format(build=known.get(crc,t('Unrecognized build')),crc=crc) if known else t('Installed build: not reported over 2.4 GHz  /  receiver CRC {crc}').format(crc=crc))
  self.status.set(t('Version read complete / {build} / CRC {crc}').format(build=known.get(crc,t('Unknown build')),crc=crc))
  if known and crc not in known:self.firmware_note.set(self.firmware_block_message(crc))
  self.update_firmware_preview();self.refresh_screen_rows()
 def choose_color(self):
  value=colorchooser.askcolor(color=self.color.get(),parent=self.root)[1]
  if value:self.color.set(value)
 def apply_lighting(self):
  if self.preview_mode.get()!='Effect preview':return self.status.set(t('Per-key draft is local only. Select Effect preview to send global lighting.'))
  if not self.settings:return self.status.set(t('Connect the keyboard and read its settings first.'))
  mode=EFFECTS.index(self.effect.get())+1;rainbow={'Keep device flag':None,'Single colour':False,'Rainbow':True}[self.rainbow.get()]
  args=(mode,self.brightness.get(),self.speed.get(),rainbow,self.color.get())
  self.submit('Saving lighting',lambda:self.settings_client.set_lighting(*args),lambda value:self.root.after(50,self.read_settings))
 def lookup(self,name):
  if not self.settings:return None
  index=PHYSICAL_KEY_INDICES.get(name)
  return next((k['index'] for k in self.settings['keys'] if k['index']==index and k['editable']),None)
 def mapping_label(self,key,label):
  index=self.lookup(key)
  if index is None:return label
  entry=next(k for k in self.settings['keys'] if k['index']==index)
  name=entry['name']
  if name==key:return label
  if entry['flag'] in (112,113):return f"M{(entry['code']>>8)+1}"
  if name in MEDIA_KEYS:
   return t({'Play / Pause':'Play','Previous Track':'Prev','Next Track':'Next',
           'Volume Up':'Vol+','Volume Down':'Vol−','Mute':'Mute'}[name])
  return {'BACKSPACE':'Back','CAPSLOCK':'Caps','PAGEDOWN':'PgDn','PAGEUP':'PgUp',
          'DELETE':'Del','INSERT':'Ins','PRINTSCREEN':'PrtSc','SCROLLLOCK':'ScrLk',
          'RIGHT':'→','LEFT':'←','DOWN':'↓','UP':'↑'}.get(name,name.title() if len(name)>3 and not name.startswith('HID ') else name)
 def draw_boards(self,phase=0,only=None):
  body_font=tk.font.Font(root=self.root,font=BODY)
  for kind in ('rgb','map','test'):
   if only and kind not in only:continue
   canvas=getattr(self,kind+'_canvas')
   colours=self.preview_colours(phase) if kind=='rgb' else {}
   canvas.delete('all');width=max(canvas.winfo_width(),760);unit=int((width-36)/18.0);boxes=[];bg=canvas.cget('bg')
   right=18+int(17.75*unit)+6;cut=8
   canvas.create_polygon(6+cut,4,right-cut,4,right,4+cut,right,244-cut,right-cut,244,6+cut,244,6,244-cut,6,4+cut,fill='#241b3d',outline=pixel.LINE_DK,width=2)
   for label,key,column,row,size in LAYOUT:
    x=16+int(column*unit);y=14+row*45;w=int(unit*size)-4;fill=KEY;ink='#2b1e3e';cursor=pressed=False
    if key in ('ESC','ENTER','SPACE','UP','LEFT','DOWN','RIGHT'):fill='#e2b2d9'
    if kind=='rgb':
     fill=self.paint.get(key,self.color.get()) if self.preview_mode.get()=='Per-key design draft' else colours.get(key,'#3b304b')
     ink=pixel.DESK if sum(int(fill[i:i+2],16) for i in (1,3,5))>370 else INK
    if kind=='map':
     index=self.lookup(key)
     label=self.mapping_label(key,label)
     if index in self.pending_mapping:fill='#ff9cc0'
     if index==self.selected and index is not None:fill=MINT;cursor=True
    if kind=='test':
     fill=MINT if key in self.counts else KEY
     if key in self.pressed:fill=PINK;pressed=True
    legend_font=BODY
    legend_width=body_font.measure(label)
    if kind=='map' and legend_width>w-8:legend_font=(BODY[0],-max(6,int(16*(w-8)/legend_width)))
    pixel.keycap(canvas,x,y,w,40,fill,label,ink,cursor,pressed,font=legend_font)
    boxes.append((x,y,x+w,y+40,key))
   if kind in ('rgb','map'):self.keyboxes[kind]=boxes
 def preview_colours(self,phase):
  rainbow=self.rainbow.get()=='Rainbow' or (self.rainbow.get()=='Keep device flag' and getattr(self,'device_rainbow',False))
  return effects.frame(self.effect.get(),PREVIEW_KEYS,phase,self.color.get(),rainbow,self.speed.get(),self.brightness.get())
 def hit(self,event,kind):return next((b[4] for b in self.keyboxes.get(kind,[]) if b[0]<=event.x<=b[2] and b[1]<=event.y<=b[3]),None)
 def paint_key(self,event):
  if self.preview_mode.get()!='Per-key design draft':return
  key=self.hit(event,'rgb')
  if key:self.paint[key]=self.color.get();self.draw_boards();self.status.set(t('{key} colour staged locally. Per-key device upload is not verified.').format(key=key))
 def export_draft(self):self.save_json({'kind':'local_rgb_design_only','device_write_supported':False,'keys':self.paint},'x68-colour-draft.json')
 def select_key(self,event):
  key=self.hit(event,'map');index=self.lookup(key) if key else None
  self.selected=index
  if index is None:
   self.selection.set(t('This key is reserved, unassigned or not yet mapped.'));self.draw_boards();return
  self.update_selection();self.draw_boards()
  entry=next(k for k in self.settings['keys'] if k['index']==index)
  if entry['flag'] in (112,113):
   self.slot.set((entry['code']>>8)+1);self.slot_choice.refresh();self.load_macro()
 def update_selection(self):
  if self.selected is None:return
  entry=next((k for k in self.settings['keys'] if k['index']==self.selected and k['editable']),None)
  if entry is None:
   self.selected=None;self.selection.set(t('Select an editable source key.'));return
  key=next((name for name,index in PHYSICAL_KEY_INDICES.items() if index==self.selected),t('Matrix cell {index}').format(index=self.selected))
  self.selection.set(t('{key}\nnow sends {action}').format(key=key,action=entry['name']));self.sync_macro_target()
  if entry['name'] in HID_KEYS or entry['name'] in MODIFIERS or entry['name'] in MEDIA_KEYS:
   self.action_type.set(t('Media' if entry['name'] in MEDIA_KEYS else 'Keyboard'))
   self.change_action_type();self.target.set(entry['name'])
 def select_matrix(self,event=None):
  i=self.source_combo.current()
  if i>=0:self.selected=self.editable[i]['index'];self.update_selection();self.draw_boards()
 def stage_mapping(self):
  if self.selected is None:return self.status.set(t('Select an editable source key first.'))
  self.pending_mapping[self.selected]=self.target.get();self.mapping_summary();self.status.set(t('Added to draft. No command was sent.'))
 def clear_mapping(self):self.pending_mapping.clear();self.mapping_summary();self.status.set(t('Draft discarded. No command was sent.'))
 def mapping_summary(self):
  labels={self.lookup(key):label for label,key,*_ in LAYOUT if self.lookup(key) is not None}
  self.mapping_note.set('\n'.join('▶ '+t('{source}  to  {target}').format(source=labels.get(i,t('Cell')+' '+str(i)),target=target) for i,target in self.pending_mapping.items()) if self.pending_mapping else t('Empty. Picking keys never writes the keyboard.'))
  self.mapping_send.configure(text=t('Send draft ({count})').format(count=len(self.pending_mapping)),state='normal' if self.pending_mapping else 'disabled');self.draw_boards()
 def remap(self):
  if not self.pending_mapping:return self.status.set(t('Add a change to the draft first.'))
  changes=dict(self.pending_mapping)
  self.submit('Sending keymap draft',lambda:self.settings_client.remap_batch(changes),lambda result:self.mapping_sent(changes))
 def mapping_sent(self,sent):
  for index,target in sent.items():
   if self.pending_mapping.get(index)==target:self.pending_mapping.pop(index)
  self.mapping_summary();self.status.set(t('Keymap sent and verified.'));self.root.after(100,self.read_settings)
 def check_macro(self):
  text=self.editor.get('1.0','end')
  if not text.strip():self.macro_check_label.configure(fg=AMBER);return self.macro_check.set(t('The macro is empty. Add at least one step.'))
  try:
   block=compile_macro(text);self.macro_check_label.configure(fg=MINT);self.macro_check.set('✓ '+t('This macro is valid: {count} key events. It is not saved yet.').format(count=int.from_bytes(block[:2],'little')))
  except Exception as error:
   self.macro_check_label.configure(fg=PINK);self.macro_check.set('✗ '+self.explain_macro_error(str(error)))
 def explain_macro_error(self,message):
  import re
  found=re.match(r"Line (\d+): unknown key '(.*)'\.",message)
  if found:return t('Line {line}: "{name}" is not a key name this keyboard knows.').format(line=found.group(1),name=found.group(2))
  found=re.match(r'Line (\d+): WAIT expects milliseconds\.',message)
  if found:return t('Line {line}: WAIT needs a number of milliseconds, for example WAIT 100.').format(line=found.group(1))
  return t('There is a mistake in the macro. Use one step per line, keys joined with + and WAIT followed by a number.')
 def load_macro(self):
  if not self.settings:return
  macro=next((m for m in self.settings['macros'] if m['slot']==self.slot.get()),None)
  try:text=macro_text(bytes.fromhex(macro['block_hex'])) if macro else ''
  except Exception:return self.macro_note.set(t('This slot contains events the text editor cannot represent.'))
  self.editor.delete('1.0','end');self.editor.insert('1.0',text);self.macro_note.set(t('Slot loaded from the keyboard.' if macro else 'Empty slot. Write a new macro.'))
 def save_macro(self):
  if not self.settings:return self.macro_note.set(t('Connect the keyboard first.'))
  if self.selected is None:return self.macro_note.set(t('Choose the key that should run the macro first (step 3).'))
  text=self.editor.get('1.0','end');slot=self.slot.get()-1
  try:compile_macro(text)
  except Exception as error:return self.macro_note.set(self.explain_macro_error(str(error)))
  key=self.macro_key.get() or next((name for name,index in PHYSICAL_KEY_INDICES.items() if index==self.selected),str(self.selected))
  if not self.smoke and not messagebox.askokcancel(t('Save macro'),t('Save this macro to {key}?\n\nFrom now on, pressing {key} runs the macro instead of its normal job. You can undo this on the Keymap page or in Advanced > Restore settings backup.').format(key=key),icon='warning',default='cancel',parent=self.root):return
  self.submit('Saving macro',lambda:self.settings_client.assign_macro(self.selected,slot,text),lambda value:self.root.after(50,self.read_settings))
 def read_battery(self):
  version=dict(self.version or {})
  def read():
   result={'report':query_battery(self.settings_client)}
   if version.get('reported_crc') in BATTERY_DIAGNOSTIC_CRCS:
    from .battery_diagnostic import query_snapshot
    result['snapshot']=query_snapshot(self.settings_client,version)
   return result
  self.submit('Reading battery',read,self.show_battery)
 def toggle_battery(self):self.stop_monitor() if self.monitoring else self.start_monitor()
 def show_battery(self,result):
  report=result.get('report',result);snapshot=result.get('snapshot')
  self.history.record(sample=report);value=report.get('reported_percent');stamp=report['observed_at'][11:19]
  self.percent.set(f'{value} %' if value is not None else '-- %')
  if snapshot:
   health=estimate(snapshot);self.health=health;self.history.samples[-1]['health']=health;self.trend.add(health['pack_volts_estimate'])
   colour={'no_voltage':PINK,'dead':PINK,'over_discharged':AMBER,'low':AMBER,'ok':MINT}.get(health['state'],MUTED)
   self.volts.set(f"{health['pack_volts_estimate']:.2f} V");self.volts_label.configure(fg=colour);self.draw_gauge(health['pack_volts_estimate']);self.verdict.set(t(health['headline']));self.show_steps([t(step) for step in health['steps']])
   self.show_battery_warning(health['state'] in ('no_voltage','dead','over_discharged'))
   self.percent.set(f"{health['pack_volts_estimate']:.2f} V")
   self.battery_note.set(t('Read at {stamp}. USB power {power}. Estimate via an inferred 1:2 divider.').format(stamp=stamp,power=t('present' if health['external_power'] else 'absent')))
   self.trend_note.set(self.trend.verdict(health['external_power'])[1] if self.monitoring else '')
  else:
   self.volts.set(f'{value} %' if value is not None else '-- %');self.verdict.set(t('Device-reported level only.'))
   self.show_battery_warning(False)
   self.battery_note.set(t('Read {stamp} / raw level {level}, status {status}. Voltage is measured only by the 0.6.0 build.').format(stamp=stamp,level=report["level_raw"],status=report["status_raw"]))
  self.next_battery=time.monotonic()+5;self.draw_chart();self.monitor_state()
  self.status.set(t('Battery read complete at {stamp} / {value}.').format(stamp=stamp,value=self.percent.get()))
 def draw_chart(self):
  """Line chart of recent readings: pack voltage (0.6.0 builds) or the device-reported level."""
  c=self.chart;c.delete('all');width=max(c.winfo_width(),600);height=max(c.winfo_height(),120)
  data=[item for item in self.history.samples[-200:] if item.get('transport')=='available']
  volts=any(item.get('health') for item in data)
  points=[]
  for item in data:
   value=item['health']['pack_volts_estimate'] if item.get('health') else (None if volts else (item.get('reported_percent') if item.get('reported_percent') is not None else item.get('level_raw')))
   if value is not None:points.append((item.get('observed_at','')[11:19],value))
  left,right,top,bottom=56,width-70,28,height-24
  low,high=(2.8,4.4) if volts else (0,100)
  y=lambda v:bottom-(min(max(v,low),high)-low)/(high-low)*(bottom-top)
  c.create_text(10,8,text=t('PACK VOLTAGE' if volts else 'DEVICE LEVEL'),fill=MUTED,anchor='nw',font=LABEL)
  grid=((3.0,'3.0 V'),(3.5,'3.5 V'),(4.07,t('FULL'))) if volts else ((0,'0 %'),(50,'50 %'),(100,'100 %'))
  for level,name in grid:
   for x in range(left,right,8):c.create_rectangle(x,y(level),x+3,y(level)+1,fill=pixel.LINE_DK,outline='')
   c.create_text(left-8,y(level),text=name,fill=MUTED,anchor='e',font=LABEL)
  if not points:
   c.create_text((left+right)/2,(top+bottom)/2,text=t('No readings yet. Press Measure now or Start monitoring.'),fill=MUTED,font=BODY);return
  step=(right-left)/max(1,len(points)-1)
  xy=[(left+i*step if len(points)>1 else right,y(v)) for i,(_,v) in enumerate(points)]
  if len(xy)>1:c.create_line(*[n for p in xy for n in p],fill=MINT,width=2)
  if len(xy)<=60:
   for x,yy in xy:c.create_rectangle(x-2,yy-2,x+2,yy+2,fill=MINT,outline='')
  last=points[-1][1];x,yy=xy[-1]
  c.create_text(x+8,yy,text=f'{last:.2f} V' if volts else f'{last} %',fill=INK,anchor='w',font=BODY)
  c.create_text(left,bottom+6,text=points[0][0],fill=MUTED,anchor='nw',font=LABEL)
  if len(points)>1:c.create_text(right,bottom+6,text=points[-1][0],fill=MUTED,anchor='ne',font=LABEL)
  c.create_text((left+right)/2,bottom+6,text=t('{count} readings').format(count=len(points)),fill=MUTED,anchor='n',font=LABEL)

 def install(self):
  if self.busy:return self.status.set(t('{operation} is still running. Please wait.').format(operation=t(self.operation)))
  name=self.build.get();external=name.startswith(t('Selected file:'))
  if external and not self.external_firmware:return self.status.set(t('Choose a valid firmware file first.'))
  unreviewed=external and not self.external_firmware[1]['reviewed']
  if unreviewed and not self.allow_unreviewed.get():return self.status.set(t('This binary is unreviewed. Enable the explicit unreviewed-file option before installing.'))
  if not self.inventory:return self.status.set(t('Connect the X68 with a USB cable before installing firmware.'))
  if self.inventory.get('transport')=='wireless':return self.status.set(t('Firmware can only be installed over a USB cable. Set the keyboard switch to wired and plug in the cable.'))
  if not self.version:return self.status.set(t('Check the installed version first.'))
  if self.version.get('reported_crc') not in KNOWN_BUILDS:
   message=self.firmware_block_message(self.version.get('reported_crc'))
   if not self.smoke:messagebox.showwarning(t('Unrecognised firmware'),message+'\n\n'+t('The builds here were made only for VGN\'s original V0113 firmware. Writing them over a different version could leave the keyboard unusable.'),parent=self.root)
   return self.status.set(message)
  danger=[t('This is YOUR UNREVIEWED CODE. Structural checks do not establish hardware compatibility; recovery may require a programmer.')] if unreviewed else []
  if safety.on_battery_power():danger.append(t('This computer is running on battery. Plug in the charger before you continue.'))
  intro=t('Install {name}?').format(name=name)+'\n\n'+t('Firmware is the keyboard\'s own internal software; installing replaces it and takes a few minutes.')+t('\n\nThe official V0113 firmware is downloaded from VGN once if it is not cached yet.\nKeep USB connected in wired mode until verification completes.\nSettings are backed up before writing.')
  checks=[t('The keyboard is connected with a USB cable and its switch is set to wired.'),t('The computer is plugged into power (a laptop is on its charger).'),t('I will not unplug the cable, close this app, or shut down or sleep the computer until it says the installation is complete.'),t('I understand that if the installation is interrupted, the keyboard may stop working and need special hardware to recover.')]
  if not self.confirm_checklist(t('Install firmware'),intro,checks,t('Install'),'\n'.join(danger)):return
  self.stop_monitor();self.stop_test();self.version=None;self.flashing=True;self.progress['value']=0;self.install_button.configure(state='disabled')
  current_reference=self.external_firmware[0] if self.external_firmware else None
  def flash():
   from tools import reflash_v0113 as ota
   self.results.put(('firmware_note',t('Preparing the official V0113 base and applying the patch...')))
   stock=firmware_source.stock(CACHE);payload=self.external_firmware[0] if external else firmware_source.build(CACHE,name)
   ota.ROOT=WORK
   return ota.reflash(payload,stock,firmware_source.apply_patch(stock,'lavender-quest-0.5.1'),progress=lambda n,total:self.results.put(('progress',n,total)),allow_unreviewed=unreviewed,current_user_reference=current_reference)
  self.submit('Installing firmware',flash,self.installed_build)
 def installed_build(self,result):
  self.firmware_note.set(t('Installation complete. Device-reported CRC matches the selected build.'));self.progress['value']=4936;self.flashing=False;self.install_button.configure(state='normal');self.root.after(200,self.read_version)
 def start_test(self):
  if not self.monitor:return self.status.set(t('Connect the X68 in wired mode first.'))
  self.monitor.active=True;self.test_until=time.monotonic()+60;self.test_note.set(t('Testing. Keep this window focused.'))
 def stop_test(self):
  self.test_until=0
  if self.monitor:self.monitor.active=False
  self.pressed.clear()
 def clear_test(self):self.counts.clear();self.pressed.clear();self.draw_boards()
 def restore(self):
  if self.busy:return
  path=filedialog.askopenfilename(parent=self.root,title=t('Restore X68 settings backup'),filetypes=[(t('JSON backup'),'*.json')])
  if path and messagebox.askokcancel(t('Restore settings backup'),t('Restore this backup?\n\nThe keyboard\'s current lighting, keymap and macros will be replaced with the ones in the backup.'),icon='warning',default='cancel',parent=self.root):self.submit('Restoring settings backup',lambda:self.settings_client.restore(path),lambda value:self.root.after(100,self.read_settings))
 def read_adc_snapshot(self):
  if not self.version:return self.status.set(t('Check the installed version first.'))
  version=dict(self.version)
  def read():
   from .battery_diagnostic import query_snapshot
   return query_snapshot(self.settings_client,version)
  self.submit('Reading cached ADC snapshot',read,self.show_adc_snapshot)
 def show_adc_snapshot(self,result):
  self.logs.append({'battery_engineering_snapshot':result});folder=WORK/'reports';folder.mkdir(parents=True,exist_ok=True)
  (folder/'battery-engineering-latest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
  self.status.set(t('ADC snapshot read. Raw counts and calculation are in Advanced; physical voltage/current remain unknown.'))
 def open_reports(self):
  p=WORK/'reports';p.mkdir(parents=True,exist_ok=True)
  if sys.platform=='win32':os.startfile(p)
  else:subprocess.Popen(['open' if sys.platform=='darwin' else 'xdg-open',str(p)])
 def save_json(self,data,name):
  path=filedialog.asksaveasfilename(parent=self.root,initialfile=name,defaultextension='.json',filetypes=[('JSON','*.json')])
  if path:Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');self.status.set(t('File saved.'))
 def report(self):return {'app':'VGN X68 Custom Firmware 0.9.2','inventory':self.inventory,'version':self.version,'settings':self.settings,'packets':self.settings_client.trace,'battery':self.history.report(),'logs':self.logs}
 def details(self):
  self.raw.configure(state='normal');self.raw.delete('1.0','end');self.raw.insert('1.0',json.dumps(self.report(),ensure_ascii=False,indent=2));self.raw.configure(state='disabled')
  self.log_text.configure(state='normal');self.log_text.delete('1.0','end');self.log_text.insert('1.0',json.dumps(self.logs,ensure_ascii=False,indent=2));self.log_text.configure(state='disabled')
 def ui_error(self,kind,error,tb):
  detail=''.join(traceback.format_exception(kind,error,tb));self.logs.append({'ui_error':detail});self.status.set(t('Interface error recorded in Advanced. Other actions remain available.'))
  try:
   folder=WORK/'reports';folder.mkdir(parents=True,exist_ok=True);(folder/'ui-error.txt').write_text(detail,encoding='utf-8')
  except OSError:pass
 def pump(self):
  if self.closed:return
  try:self._pump_once()
  except Exception:self.ui_error(*sys.exc_info())
  finally:
   if not self.closed:self.root.after(60,self.pump)
 def _pump_once(self):
  if self.closed:return
  if self.flashing!=self.awake:self.awake=self.flashing;safety.keep_awake(self.flashing)
  while not self.results.empty():
   item=self.results.get_nowait()
   if item[0]=='firmware_note':self.firmware_note.set(item[1]);continue
   if item[0]=='progress':self.progress['value']=item[1];self.firmware_note.set(t('Writing packet {done} / {total}. Do not unplug the keyboard.').format(done=item[1],total=item[2]));continue
   if item[0]=='media_progress':self.media_progress['value']=100*item[1]/item[2];self.media_note.set(t('Uploading {done} / {total} bytes. Keep USB connected.').format(done=f'{item[1]:,}',total=f'{item[2]:,}'));continue
   _,name,result,error,done=item;self.busy=False
   self.logs.append({'time':datetime.now().astimezone().isoformat(),'operation':name,'error':error})
   if error:
    try:
     (WORK/'reports').mkdir(parents=True,exist_ok=True)
     with open(WORK/'reports/errors.log','a',encoding='utf-8') as log:log.write(datetime.now().astimezone().isoformat(timespec='seconds')+'  '+name+': '+error+'\n')
    except OSError:pass
    self.status.set(error if name=='Finding X68' and 'Input Monitoring' in error else t('Operation failed. Check the connection; details are in Advanced.'))
    if name=='Finding X68':self.inventory=None;self.device.set(t('[ ]  X68 NOT CONNECTED'));self.usb_mode.set(t('Not connected'));self.connect_button.configure(text=t('Connect'),state='normal');self.next_reconnect=time.monotonic()+5
    if name=='Reading battery':self.history.record(error=error);self.next_battery=time.monotonic()+5
    if name=='Syncing keyboard clock':self.next_clock_sync=time.monotonic()+60;self.clock_note.set(t('Sync failed: ')+error);self.status.set(t('Sync failed: ')+error)
    if self.flashing:self.flashing=False;self.install_button.configure(state='normal');self.firmware_note.set(t('Update stopped. Check Advanced logs before retrying; no automatic retry was sent.'));self.media_note.set(t('Transfer stopped. Check Advanced logs. No automatic retry was sent.'))
   elif done:
    self.status.set(t('{operation} complete.').format(operation=t(name)));done(result)
   else:self.status.set(t('{operation} complete.').format(operation=t(name)))
   self.logs=self.logs[-200:]
   if name=='Reading battery':
    folder=WORK/'reports/battery-sessions';folder.mkdir(parents=True,exist_ok=True)
    (folder/'studio-latest.json').write_text(json.dumps(self.history.report(),ensure_ascii=False,indent=2),encoding='utf-8')
   self.details()
   if self.smoke:self.root.after(200,self.smoke_done)
  if not self.smoke and not self.inventory and not self.busy and not self.flashing and time.monotonic()>=self.next_reconnect:self.refresh()
  if not self.smoke and self.auto_clock.get() and self.inventory and self.settings and self.version and not self.busy and not self.flashing and time.monotonic()>=self.next_clock_sync:self.sync_clock(manual=False)
  if not self.smoke and self.needs_battery_read and self.inventory and self.settings and self.version and not self.busy and not self.flashing:
   self.needs_battery_read=False;self.read_battery()
  if self.monitoring and self.inventory and self.settings and self.version and not self.busy and not self.flashing and time.monotonic()>=self.next_battery:self.read_battery()
  while not self.keys.empty():
   e=self.keys.get_nowait()
   if 'error' in e or not self.test_until:continue
   from app import KEY_NAMES,key_id
   code=key_id(e['scan'],e['extended']);name=KEY_NAMES.get(code,code)
   names={'Sol Alt':'ALT','Sağ Alt':'RALT','Sol Ctrl':'CTRL','Sağ Ctrl':'RCTRL','Sol Win':'WIN','Boşluk':'SPACE','Sil':'BACKSPACE','↑':'UP','↓':'DOWN','←':'LEFT','→':'RIGHT','Esc':'ESC'}
   name=names.get(name,name.upper())
   if e['released']:self.pressed.discard(name)
   else:self.pressed.add(name);self.counts[name]=self.counts.get(name,0)+1
   self.test_note.set(t('{key} / {count} press events / {keys} distinct keys').format(key=name,count=self.counts.get(name,0),keys=len(self.counts)))
  if self.test_until:
   if time.monotonic()>=self.test_until:self.stop_test()
   elif self.monitor:
    focused,modifiers=self.monitor.visual_state()
    if not focused:self.pressed.clear()
    for raw,key in {'38':'ALT','E0:38':'RALT','1D':'CTRL','E0:1D':'RCTRL','2A':'SHIFT','36':'RSHIFT','E0:5B':'WIN'}.items():
     if modifiers.get(raw) is False:self.pressed.discard(key)
 def animate(self):
  if self.closed:return
  if self.page_name=='Lighting':self.draw_boards(time.monotonic(),only=('rgb',))
  elif self.page_name in ('Keymap','Advanced'):self.draw_boards(time.monotonic())
  if self.page_name in self.scrollers:self.scrollers[self.page_name][2]()
  if self.page_name=='Firmware':self.draw_lcd_preview()
  if self.page_name=='Screen' and not self.media_photos and self.lavender_build():
   phase=int(time.monotonic()*4)
   if phase!=getattr(self,'screen_phase',None):self.screen_phase=phase;self.screen_photo=self.lcd_frame(self.lavender_build(),datetime.now(),phase);self.screen_preview.configure(image=self.screen_photo)
  if self.page_name=='Screen' and self.media_photos and time.monotonic()>=self.media_due:
   self.screen_preview.configure(image=self.media_photos[self.media_frame]);self.media_frame=(self.media_frame+1)%len(self.media_photos);self.media_due=time.monotonic()+self.prepared.period_ms/1000
  self.root.after(50 if self.page_name in ('Screen','Lighting','Firmware') else 130,self.animate)
 def smoke_done(self):
  result={'inventory_loaded':bool(self.inventory),'window_size':[self.root.winfo_width(),self.root.winfo_height()],'pages':list(self.pages),'english_ui':True,'no_automatic_settings_write':True,'firmware_install_requires_click':True}
  (WORK/'reports').mkdir(parents=True,exist_ok=True);(WORK/'reports/gui-smoke.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result));self.close()
 def firmware_block_message(self,crc):
  """Why installing is blocked, and what to do. V0112 (the factory release before V0113) gets its own steps."""
  if (self.inventory or {}).get('usb_release_hex')=='0112':
   return t('Your keyboard has VGN\'s older factory firmware, V0112 (CRC {crc}). The builds here can only be installed on V0113, so installing is blocked to protect the keyboard. To use them: 1) on VGN\'s official page download.vgnlab.com.cn/firmware open VGN X68 and download the middle item, X68 键盘固件 (X68-V0113固件升级.exe, 2,580,992 bytes); 2) close this app, connect the keyboard by USB cable in wired mode with the computer on mains power, run the updater and wait for OTA Success; 3) reopen this app: it should show Original V0113 and allow the install. Lighting, keys and macros already work on V0112.').format(crc=crc)
  return t('This keyboard runs firmware this app does not recognise (CRC {crc}). Installing firmware is blocked to protect it. Lighting, keys and macros still work.').format(crc=crc)
 def unreviewed_toggled(self):
  if self.allow_unreviewed.get() and not messagebox.askyesno(t('Unreviewed firmware'),t('This lets you install a firmware file that nobody has checked. A wrong or broken file can make the keyboard stop working for good, and fixing it needs a hardware programmer.\n\nOnly continue if you know exactly what this file is. Turn this option on?'),icon='warning',default='no',parent=self.root):self.allow_unreviewed.set(False)
 def confirm_checklist(self,title,intro,checks,confirm,danger=''):
  """Modal confirmation: the confirm button stays disabled until every statement is ticked. Cancel is the default."""
  dialog=tk.Toplevel(self.root,bg=BG);dialog.title(title);dialog.transient(self.root);dialog.resizable(False,False)
  body=tk.Frame(dialog,bg=BG,padx=22,pady=18);body.pack(fill='both',expand=True)
  tk.Label(body,text='⚠  '+title,font=BIG_BODY,bg=BG,fg=AMBER,anchor='w').pack(anchor='w',pady=(0,10))
  tk.Label(body,text=intro,font=BODY,bg=BG,fg=INK,wraplength=560,justify='left').pack(anchor='w')
  if danger:tk.Label(body,text=danger,font=BODY,bg=BG,fg=PINK,wraplength=560,justify='left').pack(anchor='w',pady=(12,0))
  tk.Label(body,text=t('Tick every box to continue:'),font=BODY,bg=BG,fg=MUTED).pack(anchor='w',pady=(16,6))
  answer={'ok':False};ticks=[tk.BooleanVar(value=False) for _ in checks]
  buttons=tk.Frame(body,bg=BG)
  def update(*args):go.configure(state='normal' if all(v.get() for v in ticks) else 'disabled')
  for text,var in zip(checks,ticks):tk.Checkbutton(body,text=text,variable=var,command=update,font=BODY,bg=BG,fg=INK,selectcolor=PANEL,activebackground=BG,activeforeground=MINT,wraplength=530,justify='left',anchor='w').pack(anchor='w',fill='x',pady=2)
  buttons.pack(anchor='e',pady=(18,0))
  def finish(ok):answer['ok']=ok;dialog.grab_release();dialog.destroy()
  cancel=PixelButton(buttons,t('Cancel'),lambda:finish(False),bg=BG);cancel.pack(side='left',padx=(0,10))
  go=PixelButton(buttons,confirm,lambda:finish(True),True,bg=BG);go.pack(side='left');go.configure(state='disabled')
  dialog.protocol('WM_DELETE_WINDOW',lambda:finish(False));dialog.bind('<Escape>',lambda e:finish(False))
  dialog.update_idletasks();x=self.root.winfo_rootx()+(self.root.winfo_width()-dialog.winfo_width())//2;y=self.root.winfo_rooty()+(self.root.winfo_height()-dialog.winfo_height())//3
  dialog.geometry(f'+{max(0,x)}+{max(0,y)}');dialog.grab_set();cancel.focus_set();self.root.wait_window(dialog)
  return answer['ok']
 def change_language(self):
  chosen=self.language.get()
  if chosen==i18n.LANG:return
  self.save_preferences(language=chosen)
  saved=t('Language saved. It applies the next time the app opens.',chosen)
  if self.smoke or self.busy or self.flashing:return self.status.set(saved)
  if messagebox.askyesno(t('Language',chosen),t('Restart the app now to switch the language?',chosen),parent=self.root):self.restart()
  else:self.status.set(saved)
 def restart(self):
  # Frozen builds relaunch the EXE itself; PyInstaller needs a clean environment for the new process.
  command=[sys.executable,*(sys.argv[1:] if getattr(sys,'frozen',False) else sys.argv)]
  self.close()
  if self.closed:subprocess.Popen(command,cwd=os.getcwd(),env={**os.environ,'PYINSTALLER_RESET_ENVIRONMENT':'1'})
 def close(self):
  if self.flashing:
   self.status.set(t('Wait for the device transfer to finish before closing.'))
   if not self.smoke:messagebox.showwarning(t('Transfer in progress'),t('Do not close the app or unplug the keyboard yet. Closing now could leave the keyboard unusable. Wait until it says the transfer is complete.'),parent=self.root)
   return
  self.closed=True;self.stop_test()
  if self.monitor:self.monitor.close()
  self.pool.shutdown(wait=False,cancel_futures=True);self.root.destroy()
