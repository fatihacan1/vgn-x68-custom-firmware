"""English desktop client. All device I/O shares one worker; OTA is explicit."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import colorsys, json, math, os, queue, sys, time, subprocess, traceback
import tkinter as tk
from tkinter import ttk, filedialog, colorchooser, messagebox
from .protocol import X68Client
from .settings import SettingsClient, HID_KEYS, MODIFIERS, compile_macro, macro_text
from .battery import query_battery, BatteryHistory
from .battery_health import ASSUMPTION, ChargeTrend, estimate
from .firmware import LIVE_CLOCK_CRC, LIVE_CLOCK_CRCS, BATTERY_DIAGNOSTIC_CRC
from .media import convert_media, upload_media, set_screen
from . import autostart, firmware_source
from PIL import Image, ImageTk, ImageOps
from . import pixel
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
EFFECTS=['Wave','Colour cloud','Vortex','Spectrum','Breathing','Solid','Reactive','Ripple','Trail','Stars','Flowers','Scroll','Wings','Build up','Rain','Scan','Spread','Fast wave','Custom table','Off']
ROWS=[
 [('Esc','ESC',1),*[(str(n),str(n),1) for n in range(1,10)],('0','0',1),('-','-',1),('=','=',1),('Back','BACKSPACE',2),('Del','DELETE',1)],
 [('Tab','TAB',1.5),*[(c,c,1) for c in 'QWERTYUIOP'],('[','[',1),(']',']',1),('\\','\\',1.5),('PgUp','PAGEUP',1)],
 [('Caps','CAPSLOCK',1.75),*[(c,c,1) for c in 'ASDFGHJKL'],(';',';',1),("'","'",1),('Enter','ENTER',2.25),('PgDn','PAGEDOWN',1)],
 [('Shift','SHIFT',2.25),*[(c,c,1) for c in 'ZXCVBNM'],(',',',',1),('.','.',1),('/','/',1),('Shift','RSHIFT',1.75),('Up','UP',1),('End','END',1)],
 [('Ctrl','CTRL',1.25),('Win','WIN',1.25),('Alt','ALT',1.25),('Space','SPACE',6.25),('Alt','RALT',1.25),('Fn','FN',1.25),('Left','LEFT',1),('Down','DOWN',1),('Right','RIGHT',1)],
]
# Main typing block, separate navigation column and spaced inverted-T arrows.
MAIN_ROWS=[[(label,key,size) for label,key,size in row if key not in ('DELETE','PAGEUP','PAGEDOWN','END','UP','LEFT','DOWN','RIGHT')] for row in ROWS]
LAYOUT=[]
for r,row in enumerate(MAIN_ROWS):
 x=0
 for label,key,size in row:
  LAYOUT.append((label,key,x,r,size));x+=size
LAYOUT += [(label,key,16.75,r,1) for r,(label,key) in enumerate([('Del','DELETE'),('PgUp','PAGEUP'),('PgDn','PAGEDOWN'),('End','END')])]
LAYOUT += [('↑','UP',14.5,3,1),('←','LEFT',13.5,4,1),('↓','DOWN',14.5,4,1),('→','RIGHT',15.5,4,1)]

class Studio:
 def __init__(self,root,smoke=False):
  self.root=root;self.smoke=smoke;self.closed=False;self.busy=False;self.flashing=False
  self.client=X68Client();self.settings_client=SettingsClient(self.client,WORK/'reports/backups')
  self.pool=ThreadPoolExecutor(max_workers=1);self.results=queue.Queue();self.keys=queue.Queue()
  self.inventory=None;self.settings=None;self.version=None;self.logs=[];self.monitor=None;self.physical_indices={}
  self.history=BatteryHistory();self.monitoring=False;self.next_battery=0;self.test_until=0;self.pressed=set();self.counts={}
  self.selected=None;self.paint={};self.keyboxes={};self.page_name='Lighting';self.photos=[]
  self.pending_mapping={};self.external_firmware=None;self.operation='';self.operation_started=0;self.needs_battery_read=False
  self.prepared=None;self.media_photos=[];self.media_frame=0;self.media_due=0;self.next_clock_sync=0;self.next_reconnect=float('inf')
  try:preferences=json.loads((WORK/'preferences.json').read_text(encoding='utf-8'))
  except (OSError,ValueError):preferences={}
  self.auto_clock=tk.BooleanVar(value=preferences.get('auto_clock',True));self.clock_note=tk.StringVar(value='Waiting for a verified 0.5.1+ connection.')
  self.clock_interval=tk.StringVar(value=str(preferences.get('clock_interval_minutes',5)) if str(preferences.get('clock_interval_minutes',5)) in ('1','2','5','10','15','30','60') else '5')
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
  tk.Label(words,text='X68',font=TITLE,bg=BG,fg=INK).pack(anchor='w');tk.Label(words,text='CUSTOM\nFIRMWARE',font=LABEL,bg=BG,fg=MINT,justify='left').pack(anchor='w',pady=(6,0))
  outer,menu=window(side,'COMMAND',pad=10);outer.pack(fill='both',expand=True,pady=(10,0))
  self.nav={};self.nav_hover=None
  for name in PAGES:
   item=tk.Label(menu,text='  '+name.upper(),font=BODY,bg=BG,fg=MUTED,anchor='w',cursor='hand2',pady=5)
   item.pack(fill='x');item.bind('<Button-1>',lambda e,n=name:self.show(n))
   item.bind('<Enter>',lambda e,n=name:self.hover_nav(n));item.bind('<Leave>',lambda e:self.hover_nav(None));self.nav[name]=item
  self.usb_mode=tk.StringVar(value='Not connected')
  outer,link=window(side,'LINK',pad=10);outer.pack(fill='x',pady=(10,0))
  tk.Label(link,textvariable=self.usb_mode,font=BODY,bg=BG,fg=MINT,justify='left',wraplength=180).pack(anchor='w')
  # Right column: title + clock, page window, message window.
  shell=tk.Frame(root,bg=pixel.DESK);shell.pack(side='left',fill='both',expand=True,padx=10,pady=10)
  top=tk.Frame(shell,bg=pixel.DESK);top.pack(fill='x')
  outer,clock=window(top,pad=10);outer.pack(side='right',fill='y')
  self.clock_text=tk.StringVar(value='--:--');self.clock_date=tk.StringVar(value='')
  tk.Label(clock,textvariable=self.clock_text,font=TITLE,bg=BG,fg=INK).pack(anchor='e');tk.Label(clock,textvariable=self.clock_date,font=LABEL,bg=BG,fg=MUTED).pack(anchor='e',pady=(8,0))
  outer,head=window(top,pad=10);outer.pack(side='left',fill='both',expand=True,padx=(0,10))
  self.title=tk.StringVar(value='Home');tk.Label(head,textvariable=self.title,font=TITLE,bg=BG,fg=INK).pack(anchor='w')
  self.device=tk.StringVar(value='LOOKING FOR X68')
  self.subtitle=tk.StringVar(value='');tk.Label(head,textvariable=self.subtitle,font=BODY,bg=BG,fg=MUTED).pack(anchor='w',pady=(8,0))
  outer,msg=window(shell,pad=10);outer.pack(side='bottom',fill='x',pady=(10,0))
  self.status=tk.StringVar(value='Connect the X68 over USB or its 2.4 GHz receiver.');self.typed=tk.StringVar(value='');self.typing=0
  self.connect_button=PixelButton(msg,'Connect',self.refresh);self.connect_button.pack(side='right')
  tk.Label(msg,textvariable=self.typed,font=BODY,bg=BG,fg=INK,anchor='w',justify='left',wraplength=760).pack(side='left',fill='x',expand=True)
  self.status.trace_add('write',lambda *args:self.type_status())
  outer,self.holder=window(shell,pad=16);outer.pack(fill='both',expand=True,pady=(10,0))
  self.pages={name:ttk.Frame(self.holder) for name in PAGES}
  self._lighting();self._mapping();self._macros();self._screen();self._battery();self._firmware();self._knowledge();self._advanced();self._home()
  icon=ASSETS/'assets/icon.png'
  if icon.exists():
   photo=tk.PhotoImage(file=str(icon));self.photos.append(photo);root.iconphoto(True,photo)
  self.type_status();self.tick_clock();self.apply_fonts(root)
  root.report_callback_exception=self.ui_error
  self.show('Home');root.protocol('WM_DELETE_WINDOW',self.close);root.after(60,self.pump);root.after(200,self.refresh)
  root.after(100,self.animate)

 def label(self,parent,text,muted=False,**kw):
  w=ttk.Label(parent,text=text,style='Muted.TLabel' if muted else 'TLabel',**kw);w.pack(anchor='w',pady=(0,10));return w
 def row(self,parent):
  f=ttk.Frame(parent);f.pack(fill='x',pady=7);return f
 def button(self,parent,text,command,accent=False):
  b=PixelButton(parent,text,command,accent,bg=parent.cget('background') if isinstance(parent,tk.Frame) else BG);b.pack(side='left',padx=(0,10));return b
 def apply_fonts(self,widget):
  if isinstance(widget,(ttk.Combobox,ttk.Entry,ttk.Spinbox)):widget.configure(font=BODY)
  for child in widget.winfo_children():self.apply_fonts(child)
 def hover_nav(self,name):
  self.nav_hover=name
  for n,item in self.nav.items():
   cursor='▶ ' if n==self.page_name or n==name else '  '
   item.configure(text=cursor+n.upper(),fg=MINT if n==self.page_name else (INK if n==name else MUTED))
 def type_status(self):
  # Dialogue-box reveal: shows that a new message arrived without moving the layout.
  self.typing=0;self.reveal()
 def reveal(self):
  text=self.status.get()
  if self.closed:return
  self.typing=min(len(text),self.typing+4);done=self.typing>=len(text)
  self.typed.set(text[:self.typing]+(' ▼' if done else ''))
  if not done:self.root.after(16,self.reveal)
 def tick_clock(self):
  if self.closed:return
  now=datetime.now();self.clock_text.set(now.strftime('%H:%M'));self.clock_date.set(now.strftime('%d.%m.%Y'))
  self.root.after(1000*(60-now.second) if now.second else 1000,self.tick_clock)
 def show(self,name):
  if self.flashing:return
  for p in self.pages.values():p.pack_forget()
  self.pages[name].pack(fill='both',expand=True);self.page_name=name;self.title.set(name.upper())
  descriptions={'Lighting':'Preview an effect, then send it to the keyboard.','Keymap':'Pick a key on the board and give it a new action.','Macros':'Shortcuts stored on the keyboard itself.','Battery':'Measure the pack and watch it charge.','Firmware':'Reviewed X68 builds, installed only when you say so.','Advanced':'Raw data, backups and the key tester.'}
  descriptions.update(Screen='Send an image or GIF to the 160x96 screen.',Knowledge='Verified facts and open questions, ready to copy.',Home='Plug in over USB. Nothing is written until you press Send.')
  self.subtitle.set(descriptions[name]);self.hover_nav(self.nav_hover)
  if name in ('Lighting','Keymap'):self.root.after_idle(self.draw_boards)

 def _home(self):
  p=self.pages['Home'];left=ttk.Frame(p);left.pack(side='left',fill='y');right=ttk.Frame(p);right.pack(side='left',fill='both',expand=True,padx=(16,0))
  self.hero_canvas=tk.Canvas(left,width=640,height=360,bg=PANEL,highlightthickness=2,highlightbackground=pixel.LINE_DK);self.hero_canvas.pack();self.hero_sprite=None
  path=ASSETS/'assets/pixel/home-scene.png'
  if path.exists():
   self.hero_photo=tk.PhotoImage(file=str(path));self.hero_sprite=self.hero_canvas.create_image(2,2,anchor='nw',image=self.hero_photo)
  f=ttk.Frame(left);f.pack(fill='x',pady=(14,0))
  for title,page in [('Lighting','Lighting'),('Keymap','Keymap'),('Screen','Screen'),('Battery','Battery')]:self.button(f,title,lambda n=page:self.show(n),page=='Lighting')
  for title,var in [('LINK',self.usb_mode),('FIRMWARE',self.installed)]:
   tk.Label(right,text=title,font=LABEL,bg=BG,fg=MUTED).pack(anchor='w',pady=(0,6))
   tk.Label(right,textvariable=var,font=BODY,bg=BG,fg=INK,wraplength=230,justify='left').pack(anchor='w',pady=(0,18))
  tk.Label(right,text='BATTERY',font=LABEL,bg=BG,fg=MUTED).pack(anchor='w',pady=(0,6))
  tk.Label(right,textvariable=self.percent,font=HEAD,bg=BG,fg=INK).pack(anchor='w',pady=(0,8))
  self.home_gauge=tk.Canvas(right,width=230,height=22,bg=BG,highlightthickness=0);self.home_gauge.pack(anchor='w')
  self.draw_gauge(None)
  tk.Label(right,text='Choosing keys, colours or files never writes the keyboard. Each page has its own Send button.',font=BODY,bg=BG,fg=MUTED,wraplength=230,justify='left').pack(anchor='w',side='bottom')
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
  body=ttk.Frame(p);body.pack(fill='x',pady=(10,0))
  fx=pixel.panel(body,'EFFECT');fx.pack(side='left',fill='y')
  pixel.Choice(fx,self.effect,EFFECTS,columns=4,width=14).pack(anchor='w')
  opts=pixel.panel(body,'LIGHT',pad=6);opts.pack(side='left',fill='both',expand=True,padx=(12,0))
  def line(title):
   row=tk.Frame(opts,bg=PANEL);row.pack(fill='x',pady=3);tk.Label(row,text=title,font=LABEL,bg=PANEL,fg=MUTED,width=10,anchor='w').pack(side='left');return row
  pixel.Meter(line('BRIGHTNESS'),self.brightness).pack(side='left');pixel.Meter(line('SPEED'),self.speed).pack(side='left')
  self.swatches=tk.Canvas(line('COLOUR'),width=8*26,height=26,bg=PANEL,highlightthickness=0,cursor='hand2');self.swatches.pack(side='left')
  self.swatches.bind('<Button-1>',self.pick_swatch);self.color.trace_add('write',lambda *args:self.draw_swatches());self.draw_swatches()
  pixel.Choice(line('MODE'),self.rainbow,[('Keep device flag','Keep'),('Single colour','Single'),('Rainbow','Rainbow')],columns=2).pack(side='left')
  pixel.Choice(line('PREVIEW'),self.preview_mode,[('Effect preview','Effect'),('Per-key design draft','Key draft')],columns=1).pack(side='left')
  actions=ttk.Frame(p);actions.pack(fill='x',pady=(12,0))
  self.lighting_send=self.button(actions,'Send to keyboard',self.apply_lighting,True);self.button(actions,'Read from keyboard',self.read_settings);self.button(actions,'Export draft',self.export_draft)
  self.preview_mode.trace_add('write',lambda *args:self.lighting_send.configure(state='normal' if self.preview_mode.get()=='Effect preview' else 'disabled'))
  self.lighting_hint=tk.Label(p,text='The board is a preview. In Key draft, click keys to paint them; drafts stay on this computer.',font=BODY,bg=BG,fg=MUTED,anchor='w');self.lighting_hint.pack(fill='x',pady=(10,0))
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
  key=pixel.panel(body,'SELECTED KEY');key.pack(side='left',fill='both',expand=True)
  self.selection=tk.StringVar(value='Click a key on the board.');tk.Label(key,textvariable=self.selection,font=HEAD,bg=PANEL,fg=INK,wraplength=420,justify='left').pack(anchor='w')
  f=tk.Frame(key,bg=PANEL);f.pack(anchor='w',pady=(16,0));tk.Label(f,text='NEW ACTION',font=LABEL,bg=PANEL,fg=MUTED).pack(side='left',padx=(0,10))
  self.target=tk.StringVar(value='CTRL');ttk.Combobox(f,textvariable=self.target,values=list(MODIFIERS)+list(HID_KEYS),state='readonly',width=14).pack(side='left',padx=(0,10));self.button(f,'Add to draft',self.stage_mapping)
  tk.Label(key,text='Fn and reserved firmware functions stay protected.',font=BODY,bg=PANEL,fg=MUTED).pack(anchor='w',side='bottom')
  draft=pixel.panel(body,'DRAFT');draft.pack(side='left',fill='both',expand=True,padx=(12,0))
  self.mapping_note=tk.StringVar(value='Empty. Picking keys never writes the keyboard.')
  tk.Label(draft,textvariable=self.mapping_note,font=BODY,bg=PANEL,fg=MINT,wraplength=400,justify='left',anchor='nw').pack(anchor='w',fill='x')
  f=tk.Frame(draft,bg=PANEL);f.pack(anchor='w',side='bottom');self.mapping_send=self.button(f,'Send draft (0)',self.remap,True);self.mapping_send.configure(state='disabled');self.button(f,'Discard',self.clear_mapping)
  self.source=tk.StringVar()

 def _macros(self):
  p=self.pages['Macros'];left=pixel.panel(p,'SLOT');left.pack(side='left',fill='y')
  self.slot=tk.IntVar(value=1)
  self.slot_choice=pixel.Choice(left,self.slot,[(n,f'{n:02d}') for n in range(1,17)],columns=4,width=4,marks=self.slot_used);self.slot_choice.pack(anchor='w')
  tk.Label(left,text='White: slot holds\na macro.',font=BODY,bg=PANEL,fg=MUTED,justify='left').pack(anchor='w',pady=(12,12))
  f=tk.Frame(left,bg=PANEL);f.pack(anchor='w');self.button(f,'Load slot',self.load_macro)
  right=ttk.Frame(p);right.pack(side='left',fill='both',expand=True,padx=(12,0))
  ed=pixel.panel(right,'SCRIPT');ed.pack(fill='both',expand=True)
  chips=tk.Frame(ed,bg=PANEL);chips.pack(fill='x',pady=(0,10))
  for token in ('CTRL+C','CTRL+V','CTRL+Z','ALT+TAB','ENTER','WAIT 100'):
   chip=tk.Label(chips,text=token,font=BODY,bg=pixel.LINE_DK,fg=INK,padx=8,pady=2,cursor='hand2');chip.pack(side='left',padx=(0,6))
   chip.bind('<Button-1>',lambda e,t=token:self.insert_token(t))
  self.editor=tk.Text(ed,height=10,bg=pixel.DESK,fg=MINT,insertbackground=MINT,insertwidth=8,font=BODY,padx=12,pady=10,relief='flat',bd=0,undo=True,highlightthickness=2,highlightbackground=pixel.LINE_DK,highlightcolor=MINT)
  self.editor.pack(fill='both',expand=True);self.editor.insert('1.0','CTRL+C\nWAIT 150\nCTRL+V')
  tk.Label(ed,text='One shortcut or WAIT per line. Click a card above to add it.',font=BODY,bg=PANEL,fg=MUTED).pack(anchor='w',pady=(8,0))
  f=ttk.Frame(right);f.pack(fill='x',pady=(12,0));self.button(f,'Check',self.check_macro);self.button(f,'Save to selected key',self.save_macro,True)
  self.macro_note=tk.StringVar(value='Pick the target key in Keymap first.');tk.Label(right,textvariable=self.macro_note,font=BODY,bg=BG,fg=MINT,wraplength=560,justify='left').pack(anchor='w',pady=(10,0))
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
  tk.Label(right,text='PACK VOLTAGE',font=LABEL,bg=BG,fg=MUTED).pack(anchor='w')
  self.volts=tk.StringVar(value='-.-- V');self.volts_label=tk.Label(right,textvariable=self.volts,font=HUGE,bg=BG,fg=MINT);self.volts_label.pack(anchor='w',pady=(8,8))
  self.percent=tk.StringVar(value='-- %');self.battery_note=tk.StringVar(value='No report yet.')
  tk.Label(right,textvariable=self.battery_note,font=BODY,bg=BG,fg=MUTED,wraplength=420,justify='left').pack(anchor='w')
  self.verdict=tk.StringVar(value='Plug in over USB to measure.')
  tk.Label(right,textvariable=self.verdict,font=HEAD,bg=BG,fg=INK,wraplength=420,justify='left').pack(anchor='w',pady=(12,14))
  self.monitor_note=tk.StringVar(value='Monitoring stopped / 0 readings');self.trend_note=tk.StringVar(value='')
  f=ttk.Frame(right);f.pack(anchor='w');self.button(f,'Measure now',self.read_battery,True);self.start_battery_button=self.button(f,'Start monitoring',self.start_monitor);self.stop_battery_button=self.button(f,'Stop',self.stop_monitor);self.stop_battery_button.configure(state='disabled')
  self.steps=ttk.Frame(p);self.steps.pack(fill='x',pady=(12,0))
  self.chart=tk.Canvas(p,height=84,bg=PANEL,highlightthickness=2,highlightbackground=pixel.LINE_DK);self.chart.pack(fill='x',pady=(8,6));self.chart.bind('<Configure>',lambda event:self.draw_chart())
  f=ttk.Frame(p);f.pack(fill='x');tk.Label(f,textvariable=self.monitor_note,font=BODY,bg=BG,fg=MINT).pack(side='left');tk.Label(f,textvariable=self.trend_note,font=BODY,bg=BG,fg=AMBER).pack(side='left',padx=16)
  tk.Label(f,text='EXPORT',font=LABEL,bg=BG,fg=MUTED,cursor='hand2').pack(side='right');f.winfo_children()[-1].bind('<Button-1>',lambda e:self.save_json(self.history.report(),'battery-session.json'))
  self.trend=ChargeTrend();self.health=None
  self.show_steps(['Connect the keyboard over USB in wired mode.','Voltage needs the Lavender Quest 0.6.0 build (Firmware page).'])
  # Compatibility with the launcher's --monitor-battery option.
  self.battery_panel=self
 def show_steps(self,steps):
  for child in self.steps.winfo_children():child.destroy()
  for number,text in enumerate(steps,1):
   row=ttk.Frame(self.steps);row.pack(fill='x',pady=1)
   tk.Label(row,text=f'{number}.',font=HEAD,bg=BG,fg=MINT,width=3,anchor='w').pack(side='left',anchor='n')
   tk.Label(row,text=text,font=BODY,bg=BG,fg=INK,wraplength=820,justify='left').pack(side='left',anchor='w')
 def start_monitor(self):
  self.monitoring=True;self.next_battery=0;self.trend.clear();self.monitor_state();self.status.set('Battery monitoring started / every 5 seconds.')
 def stop_monitor(self):
  self.monitoring=False;self.monitor_state();self.status.set('Monitoring stopped. The last reading is retained.')
 def monitor_state(self):
  self.monitor_note.set(('Monitoring / every 5 seconds' if self.monitoring else 'Monitoring stopped')+f' / {self.history.total_successes} readings')
  self.start_battery_button.configure(state='disabled' if self.monitoring else 'normal');self.stop_battery_button.configure(state='normal' if self.monitoring else 'disabled')

 def _firmware(self):
  p=self.pages['Firmware'];f=self.row(p)
  self.firmware_preview=ttk.Label(f,background=PANEL);self.firmware_preview.pack(side='left',padx=(0,24))
  info=ttk.Frame(f);info.pack(side='left',fill='both',expand=True)
  self.preview_title=tk.StringVar();ttk.Label(info,textvariable=self.preview_title,font=HEAD).pack(anchor='w',pady=10)
  self.preview_note=tk.StringVar();ttk.Label(info,textvariable=self.preview_note,style='Muted.TLabel',wraplength=350).pack(anchor='w')
  self.installed=tk.StringVar(value='Installed build: not checked');ttk.Label(p,textvariable=self.installed,foreground=MINT).pack(anchor='w',pady=(16,8))
  self.build=tk.StringVar(value=BUILDS[0]);self.build_combo=ttk.Combobox(p,textvariable=self.build,values=BUILDS,state='readonly',width=44);self.build_combo.pack(anchor='w',pady=8)
  self.build.trace_add('write',lambda *args:self.update_firmware_preview())
  f=self.row(p);self.button(f,'Import file',self.choose_firmware);self.button(f,'Check installed version',self.read_version)
  self.allow_unreviewed=tk.BooleanVar(value=False)
  ttk.Checkbutton(p,text='Allow my unreviewed binary (hardware recovery may be required)',variable=self.allow_unreviewed).pack(anchor='w',pady=6)
  self.label(p,'Builds are made on this computer from the official V0113 firmware, downloaded once from VGN\'s own server. Offline? Import the official updater EXE or your own 236,916-byte .bin. Importing never uploads anything.',True,wraplength=850)
  f=self.row(p);self.install_button=self.button(f,'Install selected firmware',self.install,True);self.button(f,'Sync keyboard clock',self.sync_clock)
  self.progress=ttk.Progressbar(p,maximum=4936);self.progress.pack(fill='x',pady=12)
  self.firmware_note=tk.StringVar(value='Select a build or inspect your own file, then explicitly click Install.');ttk.Label(p,textvariable=self.firmware_note,style='Muted.TLabel',wraplength=880).pack(anchor='w')
  self.update_firmware_preview()
 def update_firmware_preview(self):
  name=self.build.get();original=name=='Original V0113';external=name.startswith('Selected file:')
  self.preview_title.set('ORIGINAL V0113' if original else ('YOUR FIRMWARE' if external else 'X68 PIXEL DESKTOP'))
  self.preview_note.set('VGN\'s factory firmware, unchanged. Use it to roll back.' if original else ('No trusted visual preview for an imported binary. Inspect its checks before installing.' if external else 'Single purple pixel scene.\nRAM clock sync and image/GIF player.'+('\nBattery voltage readout for the Battery page.' if '0.6.0' in name else '')+'\nTheme illustration / sample time.'))
  preview=ASSETS/'assets/pixel/lcd-preview.png'
  if original or external:
   self.firmware_preview.configure(image='',text=' FACTORY FIRMWARE \n\n VGN V0113 ' if original else ' CUSTOM BINARY \n\n NO TRUSTED PREVIEW ',font=HEAD,foreground=MUTED,width=23,padding=30)
  elif preview.exists():
   with Image.open(preview) as source:self.firmware_photo=ImageTk.PhotoImage(source.resize((400,240),Image.Resampling.NEAREST))
   self.firmware_preview.configure(image=self.firmware_photo,text='',width=0,padding=0)
 def choose_firmware(self):
  if self.busy:return
  path=filedialog.askopenfilename(parent=self.root,title='Import the official updater or a V0113 .bin',filetypes=[('Firmware or official updater','*.bin *.exe')])
  if not path:return
  def inspect():
   from .firmware import inspect_custom_firmware,V0113_SIZE
   try:return 'official',firmware_source.import_file(CACHE,Path(path))
   except ValueError:pass
   if Path(path).stat().st_size!=V0113_SIZE:raise ValueError('Not the official updater and not a 236,916-byte V0113 .bin.')
   data=Path(path).read_bytes();return 'custom',(data,inspect_custom_firmware(data,firmware_source.stock(CACHE)))
  self.submit('Inspecting firmware file',inspect,lambda result:self.firmware_imported(path,*result))
 def firmware_imported(self,path,kind,value):
  if kind=='official':
   self.firmware_note.set('Official V0113 recognised by SHA256 and cached. All builds can now be made offline.');return self.status.set('Official firmware imported. Nothing was uploaded.')
  data,record=value;self.external_firmware=(data,record);self.allow_unreviewed.set(False)
  name='Selected file: '+Path(path).name;self.build_combo.configure(values=BUILDS+[name]);self.build.set(name)
  self.firmware_note.set(f'{record["bytes"]:,} bytes / CRC {record["crc"]} / '+('Known reviewed image' if record['reviewed'] else 'Structurally valid; code and hardware behavior are NOT reviewed')+' / SHA256 '+record['sha256'])
  self.status.set('File inspected locally. Nothing was uploaded.')

 def _screen(self):
  p=self.pages['Screen'];left=pixel.panel(p,'LCD  160 x 96');left.pack(side='left',fill='y')
  self.screen_preview=tk.Label(left,bg=PANEL,bd=0);self.screen_preview.pack(anchor='w')
  preview=ASSETS/'assets/pixel/lcd-preview.png'
  if preview.exists():
   with Image.open(preview) as source:photo=ImageTk.PhotoImage(source.resize((400,240),Image.Resampling.NEAREST))
   self.photos.append(photo);self.screen_preview.configure(image=photo)
  f=tk.Frame(left,bg=PANEL);f.pack(fill='x',pady=(12,0))
  self.fit=tk.StringVar(value='Crop');pixel.Choice(f,self.fit,['Crop','Fit','Stretch'],columns=3).pack(side='left')
  self.fit.trace_add('write',lambda *args:self.reconvert())
  f=tk.Frame(left,bg=PANEL);f.pack(fill='x',pady=(10,0));self.button(f,'Choose image / GIF',self.choose_media);self.button(f,'Upload',self.send_media,True)
  self.media_note=tk.StringVar(value='PNG, JPG, GIF, WEBP or BMP. Long GIFs are sampled to 8 frames.')
  tk.Label(left,textvariable=self.media_note,font=BODY,bg=PANEL,fg=MINT,wraplength=400,justify='left').pack(anchor='w',pady=(10,6))
  self.media_progress=ttk.Progressbar(left,maximum=100);self.media_progress.pack(fill='x')
  right=ttk.Frame(p);right.pack(side='left',fill='both',expand=True,padx=(12,0))
  scene=pixel.panel(right,'SCENE');scene.pack(fill='x')
  tk.Label(scene,text='Upload replaces the custom animation bank. Switch back to the clock scene at any time.',font=BODY,bg=PANEL,fg=MUTED,wraplength=380,justify='left').pack(anchor='w',pady=(0,10))
  f=tk.Frame(scene,bg=PANEL);f.pack(anchor='w');self.button(f,'Lavender desktop',lambda:self.change_screen(0))
  clock=pixel.panel(right,'CLOCK');clock.pack(fill='both',expand=True,pady=(12,0))
  ttk.Checkbutton(clock,text='Sync computer time automatically',variable=self.auto_clock,command=self.clock_preference,style='Field.TCheckbutton').pack(anchor='w',pady=4)
  f=tk.Frame(clock,bg=PANEL);f.pack(anchor='w',pady=6);tk.Label(f,text='Every',font=BODY,bg=PANEL,fg=INK).pack(side='left')
  interval=ttk.Combobox(f,textvariable=self.clock_interval,values=['1','2','5','10','15','30','60'],state='readonly',width=4);interval.pack(side='left',padx=10);interval.bind('<<ComboboxSelected>>',lambda event:self.clock_preference())
  tk.Label(f,text='minutes',font=BODY,bg=PANEL,fg=INK).pack(side='left')
  startup=ttk.Checkbutton(clock,text='Launch when I sign in to Windows',variable=self.start_on_login,command=self.startup_preference,style='Field.TCheckbutton');startup.pack(anchor='w',pady=4)
  if sys.platform!='win32':startup.configure(state='disabled')
  tk.Label(clock,textvariable=self.clock_note,font=BODY,bg=PANEL,fg=MINT,wraplength=380,justify='left').pack(anchor='w',pady=8)
  f=tk.Frame(clock,bg=PANEL);f.pack(anchor='w');self.button(f,'Sync time now',self.sync_clock)
  tk.Label(clock,text='Live sync changes RAM only. After a full power loss, open the app again.',font=BODY,bg=PANEL,fg=MUTED,wraplength=380,justify='left').pack(anchor='w',pady=(10,0))

 def choose_media(self):
  if self.busy:return
  path=filedialog.askopenfilename(parent=self.root,title='Choose an image or animation',filetypes=[('Images and animations','*.png *.jpg *.jpeg *.gif *.webp *.bmp'),('All files','*.*')])
  if path:self.prepare_media(path)
 def reconvert(self):
  if self.prepared and not self.busy:self.prepare_media(self.prepared.source)
 def prepare_media(self,path):
  fit=self.fit.get();self.submit('Converting image',lambda:convert_media(path,fit),self.media_ready)
 def media_ready(self,prepared):
  self.prepared=prepared;self.media_photos=[ImageTk.PhotoImage(frame.resize((400,240),Image.Resampling.NEAREST)) for frame in prepared.frames]
  self.media_frame=0;self.media_due=0;self.media_progress['value']=0
  self.media_note.set(f'{Path(prepared.source).name}  /  {prepared.source_frames} → {len(prepared.frames)} frames  /  {prepared.period_ms} ms per frame  /  {len(prepared.data):,} bytes')
  self.status.set('Preview ready. Nothing has been sent to the keyboard.')
 def send_media(self):
  if self.busy:return
  if not self.prepared:return self.status.set('Choose an image or GIF first.')
  wireless=bool(self.inventory and self.inventory.get('transport')=='wireless')
  if not wireless and (not self.version or self.version.get('reported_crc') not in LIVE_CLOCK_CRCS):return self.status.set('Install Lavender Quest 0.6.0 in Firmware first.')
  if not messagebox.askokcancel('Replace custom animation','Upload the converted preview?\n\nThis replaces the keyboard’s entire custom image/GIF bank. The previous animation cannot be read back.\nKeep USB connected until the transfer completes.',parent=self.root):return
  prepared=self.prepared;self.flashing=True;self.monitoring=False;self.stop_test();self.media_progress['value']=0
  self.submit('Uploading screen media',lambda:upload_media(self.settings_client,prepared,WORK,lambda n,total:self.results.put(('media_progress',n,total))),self.media_uploaded)
 def media_uploaded(self,result):
  self.flashing=False;self.media_progress['value']=100;self.next_clock_sync=0
  self.media_note.set('Transfer acknowledged; display settings read back. Check the physical screen. Converted data and transfer log saved in reports/media.')
  self.status.set('Custom media selected. Use Lavender desktop to return to the clock scene.')
 def change_screen(self,mode):
  wireless=bool(self.inventory and self.inventory.get('transport')=='wireless')
  if not wireless and (not self.version or self.version.get('reported_crc') not in LIVE_CLOCK_CRCS):return self.status.set('Install Lavender Quest 0.6.0 first.')
  self.submit('Selecting screen',lambda:set_screen(self.settings_client,mode),lambda result:self.screen_changed())
 def screen_changed(self):self.next_clock_sync=0;self.status.set('Lavender desktop selected.')
 def clock_preference(self):
  WORK.mkdir(parents=True,exist_ok=True);self.save_preferences(auto_clock=self.auto_clock.get(),clock_interval_minutes=int(self.clock_interval.get()));self.next_clock_sync=0
 def startup_preference(self):
  try:
   autostart.configure(self.start_on_login.get());self.status.set('Windows startup enabled.' if self.start_on_login.get() else 'Windows startup disabled.')
  except OSError as error:
   self.start_on_login.set(autostart.enabled());self.status.set('Startup setting failed: '+str(error))
 def sync_clock(self):
  wireless=bool(self.inventory and self.inventory.get('transport')=='wireless')
  if not wireless and (not self.version or self.version.get('reported_crc') not in LIVE_CLOCK_CRCS):
   self.next_clock_sync=time.monotonic()+60;return self.clock_note.set('Live sync requires Lavender Quest 0.5.1 or newer. Install it in Firmware.')
  if self.busy:return
  crc=self.version['reported_crc'];self.next_clock_sync=time.monotonic()+60
  self.submit('Syncing keyboard clock',lambda:self.settings_client.sync_clock_live(crc,receiver=wireless),self.clock_synced)
 def clock_synced(self,result):
  self.next_clock_sync=time.monotonic()+int(self.clock_interval.get())*60;self.clock_note.set('Synced from computer: '+result['local_time'][:19].replace('T',' ')+'  /  RAM only');self.status.set('Keyboard date and time synchronized.')

 def _knowledge(self):
  p=self.pages['Knowledge'];self.label(p,'FACTS YOU CAN TAKE WITH YOU',font=HEAD)
  self.label(p,'Copy this context into an AI chat. Verified behavior and open questions are explicitly separated. No private device paths are included.',True,wraplength=880)
  f=self.row(p);self.button(f,'Copy AI context',self.copy_knowledge,True);self.button(f,'Export Markdown',self.export_knowledge);self.button(f,'Export JSON',lambda:self.save_json(self.knowledge_record(),'x68-knowledge.json'))
  body=ttk.Frame(p);body.pack(fill='both',expand=True,pady=10)
  text=tk.Text(body,bg=PANEL,fg=INK,font=BODY,wrap='word',relief='flat',padx=16,pady=14)
  scroll=ttk.Scrollbar(body,command=text.yview);scroll.pack(side='right',fill='y');text.configure(yscrollcommand=scroll.set);text.pack(fill='both',expand=True)
  try:self.knowledge=(ASSETS/'docs/AI-KNOWLEDGE.md').read_text(encoding='utf-8')
  except OSError:self.knowledge='Knowledge file missing. Use the complete application folder.'
  text.insert('1.0',self.knowledge);text.configure(state='disabled')
 def knowledge_record(self):return {'application':'VGN X68 Custom Firmware','version':'0.6.0','custom_crc':BATTERY_DIAGNOSTIC_CRC,'format':'Markdown','context':self.knowledge,'unknowns':['Battery current and charge control (voltage is an estimate via an inferred 1:2 divider)','Early SUBOR splash storage','Physical macOS validation','Custom-media physical validation pending']}
 def copy_knowledge(self):self.root.clipboard_clear();self.root.clipboard_append(self.knowledge);self.status.set('AI context copied to clipboard.')
 def export_knowledge(self):
  path=filedialog.asksaveasfilename(parent=self.root,initialfile='X68-AI-KNOWLEDGE.md',defaultextension='.md',filetypes=[('Markdown','*.md')])
  if path:Path(path).write_text(self.knowledge,encoding='utf-8');self.status.set('Knowledge exported.')

 def _advanced(self):
  p=self.pages['Advanced'];tabs=ttk.Notebook(p);tabs.pack(fill='both',expand=True)
  raw=ttk.Frame(tabs,padding=12);test=ttk.Frame(tabs,padding=12);tools=ttk.Frame(tabs,padding=12)
  tabs.add(raw,text='Device & packets');tabs.add(test,text='Key tester');tabs.add(tools,text='Backups & logs')
  self.raw=tk.Text(raw,bg=PANEL,fg=MUTED,font=BODY,wrap='word',relief='flat',padx=12,pady=12,state='disabled');self.raw.pack(fill='both',expand=True)
  self.label(test,'Focused-window Raw Input from the X68 only. Key tester requires Windows.',True)
  self.test_canvas=tk.Canvas(test,height=245,bg=PANEL,highlightthickness=0);self.test_canvas.pack(fill='x',pady=14)
  f=self.row(test);self.button(f,'Start 60-second test',self.start_test,True);self.button(f,'Stop test',self.stop_test);self.button(f,'Clear results',self.clear_test)
  self.test_note=tk.StringVar(value='No key events recorded.');ttk.Label(test,textvariable=self.test_note,wraplength=850).pack(anchor='w',pady=14)
  self.label(tools,'Every settings write creates a backup and verifies readback.',True,wraplength=850)
  f=self.row(tools);self.button(f,'Restore settings backup',self.restore);self.button(f,'Export diagnostics',lambda:self.save_json(self.report(),'x68-diagnostics.json'));self.button(f,'Open reports folder',self.open_reports)
  self.button(self.row(tools),'Read cached ADC snapshot',self.read_adc_snapshot)
  self.label(tools,'Advanced matrix-cell selection (optional):',True)
  self.source_combo=ttk.Combobox(tools,textvariable=self.source,state='readonly',width=45);self.source_combo.pack(anchor='w',pady=8);self.source_combo.bind('<<ComboboxSelected>>',self.select_matrix)
  self.log_text=tk.Text(tools,bg=PANEL,fg=MUTED,font=BODY,wrap='word',relief='flat',padx=12,pady=12,state='disabled');self.log_text.pack(fill='both',expand=True,pady=15)

 def submit(self,name,func,done=None):
  if self.closed:return False
  if self.busy:self.status.set(self.operation+' is still running. Please wait.');return False
  self.busy=True;self.operation=name;self.operation_started=time.monotonic();self.status.set(name+'...')
  future=self.pool.submit(func)
  def completed(f):
   try:self.results.put(('done',name,f.result(),None,done))
   except Exception as error:self.results.put(('done',name,None,str(error),done))
  future.add_done_callback(completed);return True
 def refresh(self):
  if self.busy:return
  self.inventory=None;self.settings=None;self.version=None;self.next_reconnect=time.monotonic()+5
  self.needs_battery_read=True
  self.connect_button.configure(text='Connecting...',state='disabled');self.submit('Finding X68',self.client.inventory,self.found)
 def found(self,result):
  self.inventory=result;usb=result.get('transport')!='wireless';self.device.set('[+]  SUBOR X68 / '+('USB' if usb else '2.4 GHz'));self.usb_mode.set('USB / wired mode' if usb else '2.4 GHz receiver (firmware and LCD media need USB)');self.connect_button.configure(text='Refresh',state='normal');self.status.set('Connected. Device protocol verified.')
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
  if not self.physical_indices:
   self.physical_indices={name:self.lookup(name) for row in ROWS for _,name,_ in row}
  self.source_combo.configure(values=[f"Cell {k['index']:03d}  /  {k['name']}" for k in self.editable])
  self.status.set('Settings loaded. Nothing is written until you press Send.');self.next_clock_sync=0;self.draw_boards();self.slot_choice.refresh()
  if not self.version:self.read_version()
 def read_version(self):self.submit('Checking installed build',self.client.query_version,self.show_version)
 def save_preferences(self,**values):
  try:preferences=json.loads((WORK/'preferences.json').read_text(encoding='utf-8'))
  except (OSError,ValueError):preferences={}
  WORK.mkdir(parents=True,exist_ok=True);(WORK/'preferences.json').write_text(json.dumps({**preferences,**values}),encoding='utf-8')
 def show_version(self,result):
  self.version=result;self.next_clock_sync=0;crc=result['reported_crc'];known={'14961BE6':'Original V0113','EF331DCE':'Lavender Quest 0.4.0','4CB077DE':'Lavender Quest 0.4.1','FC2EBCFE':'Lavender Quest 0.4.2','3C866A9B':'Lavender Quest 0.5.0',LIVE_CLOCK_CRC:'Lavender Quest 0.5.1',BATTERY_DIAGNOSTIC_CRC:'Lavender Quest 0.6.0'}
  if self.inventory and self.inventory.get('transport')=='wireless':known={}
  self.installed.set('Installed: '+known.get(crc,'Unrecognized build')+'  /  CRC '+crc if known else 'Installed build: not reported over 2.4 GHz  /  receiver CRC '+crc)
  self.status.set('Version read complete / '+known.get(crc,'Unknown build')+' / CRC '+crc)
 def choose_color(self):
  value=colorchooser.askcolor(color=self.color.get(),parent=self.root)[1]
  if value:self.color.set(value)
 def apply_lighting(self):
  if self.preview_mode.get()!='Effect preview':return self.status.set('Per-key draft is local only. Select Effect preview to send global lighting.')
  if not self.settings:return self.status.set('Connect the keyboard and read its settings first.')
  mode=EFFECTS.index(self.effect.get())+1;rainbow={'Keep device flag':None,'Single colour':False,'Rainbow':True}[self.rainbow.get()]
  args=(mode,self.brightness.get(),self.speed.get(),rainbow,self.color.get())
  self.submit('Saving lighting',lambda:self.settings_client.set_lighting(*args),lambda value:self.root.after(50,self.read_settings))
 def lookup(self,name):
  if name in self.physical_indices:return self.physical_indices[name]
  if not self.settings:return None
  code=(MODIFIERS[name]<<8) if name in MODIFIERS else HID_KEYS.get(name)
  return next((k['index'] for k in self.settings['keys'] if k['editable'] and k['flag']==32 and k['code']==code),None)
 def draw_boards(self,phase=0):
  for canvas,kind in [(self.rgb_canvas,'rgb'),(self.map_canvas,'map'),(self.test_canvas,'test')]:
   canvas.delete('all');width=max(canvas.winfo_width(),760);unit=int((width-36)/18.0);boxes=[];bg=canvas.cget('bg')
   right=18+int(17.75*unit)+6;cut=8
   canvas.create_polygon(6+cut,4,right-cut,4,right,4+cut,right,244-cut,right-cut,244,6+cut,244,6,244-cut,6,4+cut,fill='#241b3d',outline=pixel.LINE_DK,width=2)
   for label,key,column,row,size in LAYOUT:
    x=16+int(column*unit);y=14+row*45;w=int(unit*size)-4;fill=KEY;ink='#2b1e3e';cursor=pressed=False
    if key in ('ESC','ENTER','SPACE','UP','LEFT','DOWN','RIGHT'):fill='#e2b2d9'
    if kind=='rgb':
     fill=self.paint.get(key,self.color.get()) if self.preview_mode.get()=='Per-key design draft' else self.effect_color(self.effect.get(),row,x/width,phase)
     ink=pixel.DESK if sum(int(fill[i:i+2],16) for i in (1,3,5))>370 else INK
    if kind=='map':
     index=self.lookup(key)
     if index in self.pending_mapping:fill='#ff9cc0'
     if index==self.selected and index is not None:fill=MINT;cursor=True
    if kind=='test':
     fill=MINT if key in self.counts else KEY
     if key in self.pressed:fill=PINK;pressed=True
    pixel.keycap(canvas,x,y,w,40,fill,label,ink,cursor,pressed)
    boxes.append((x,y,x+w,y+40,key))
   if kind in ('rgb','map'):self.keyboxes[kind]=boxes
 def effect_color(self,mode,row,x,phase):
  c=self.color.get();rainbow=self.rainbow.get()=='Rainbow' or (self.rainbow.get()=='Keep device flag' and getattr(self,'device_rainbow',False))
  try:base=tuple(int(c[i:i+2],16)/255 for i in (1,3,5))
  except ValueError:base=(.71,.61,.80)
  if mode=='Off':return '#3b304b'
  if rainbow and mode in ('Solid','Breathing'):
   hue=(x+row*.05+phase*.06)%1;level=1 if mode=='Solid' else .3+.7*(math.sin(phase)+1)/2
   return '#'+''.join(f'{int(v*level*255):02x}' for v in colorsys.hsv_to_rgb(hue,.4,.9))
  if mode=='Solid':return '#'+''.join(f'{int(v*255):02x}' for v in base)
  if mode=='Breathing':return '#'+''.join(f'{int(v*(.3+.7*(math.sin(phase)+1)/2)*255):02x}' for v in base)
  hue=(x+row*.05+phase*.06)%1;rgb=colorsys.hsv_to_rgb(hue,.4,.9)
  return '#'+''.join(f'{int(v*255):02x}' for v in rgb)
 def hit(self,event,kind):return next((b[4] for b in self.keyboxes.get(kind,[]) if b[0]<=event.x<=b[2] and b[1]<=event.y<=b[3]),None)
 def paint_key(self,event):
  if self.preview_mode.get()!='Per-key design draft':return
  key=self.hit(event,'rgb')
  if key:self.paint[key]=self.color.get();self.draw_boards();self.status.set(key+' colour staged locally. Per-key device upload is not verified.')
 def export_draft(self):self.save_json({'kind':'local_rgb_design_only','device_write_supported':False,'keys':self.paint},'x68-colour-draft.json')
 def select_key(self,event):
  key=self.hit(event,'map');index=self.lookup(key) if key else None
  if index is None:return self.selection.set('This key is reserved, unassigned or not yet mapped.')
  self.selected=index;current=next(k['name'] for k in self.settings['keys'] if k['index']==index);self.selection.set(f'{key}\nnow sends {current}');self.draw_boards()
 def select_matrix(self,event=None):
  i=self.source_combo.current()
  if i>=0:self.selected=self.editable[i]['index'];self.selection.set(f'Matrix cell {self.selected} selected');self.draw_boards()
 def stage_mapping(self):
  if self.selected is None:return self.status.set('Select an editable source key first.')
  self.pending_mapping[self.selected]=self.target.get();self.mapping_summary();self.status.set('Added to draft. No command was sent.')
 def clear_mapping(self):self.pending_mapping.clear();self.mapping_summary();self.status.set('Draft discarded. No command was sent.')
 def mapping_summary(self):
  labels={self.lookup(key):label for label,key,*_ in LAYOUT if self.lookup(key) is not None}
  self.mapping_note.set('\n'.join(f'▶ {labels.get(i,"Cell "+str(i))}  to  {target}' for i,target in self.pending_mapping.items()) if self.pending_mapping else 'Empty. Picking keys never writes the keyboard.')
  self.mapping_send.configure(text=f'Send draft ({len(self.pending_mapping)})',state='normal' if self.pending_mapping else 'disabled');self.draw_boards()
 def remap(self):
  if not self.pending_mapping:return self.status.set('Add a change to the draft first.')
  changes=dict(self.pending_mapping)
  self.submit('Sending keymap draft',lambda:self.settings_client.remap_batch(changes),lambda result:self.mapping_sent(changes))
 def mapping_sent(self,sent):
  for index,target in sent.items():
   if self.pending_mapping.get(index)==target:self.pending_mapping.pop(index)
  self.mapping_summary();self.status.set('Keymap sent and verified.');self.root.after(100,self.read_settings)
 def check_macro(self):
  try:
   block=compile_macro(self.editor.get('1.0','end'));self.macro_note.set(f'Valid macro / {int.from_bytes(block[:2],"little")} events. Not saved yet.')
  except Exception:self.macro_note.set('Invalid macro. Use balanced DOWN / UP events and valid WAIT values.')
 def load_macro(self):
  if not self.settings:return
  macro=next((m for m in self.settings['macros'] if m['slot']==self.slot.get()),None)
  try:text=macro_text(bytes.fromhex(macro['block_hex'])) if macro else ''
  except Exception:return self.macro_note.set('This slot contains events the text editor cannot represent.')
  self.editor.delete('1.0','end');self.editor.insert('1.0',text);self.macro_note.set('Slot loaded from the keyboard.' if macro else 'Empty slot. Write a new macro.')
 def save_macro(self):
  if self.selected is None:return self.macro_note.set('Pick the target key in Keymap first, then come back here.')
  text=self.editor.get('1.0','end');slot=self.slot.get()-1
  self.submit('Saving macro',lambda:self.settings_client.assign_macro(self.selected,slot,text),lambda value:self.root.after(50,self.read_settings))
 def read_battery(self):
  version=dict(self.version or {})
  def read():
   result={'report':query_battery(self.settings_client)}
   if version.get('reported_crc')==BATTERY_DIAGNOSTIC_CRC:
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
   self.volts.set(f"{health['pack_volts_estimate']:.2f} V");self.volts_label.configure(fg=colour);self.draw_gauge(health['pack_volts_estimate']);self.verdict.set(health['headline']);self.show_steps(health['steps'])
   self.percent.set(f"{health['pack_volts_estimate']:.2f} V")
   self.battery_note.set(f"Read at {stamp}. USB power {'present' if health['external_power'] else 'absent'}. Estimate via an inferred 1:2 divider.")
   self.trend_note.set(self.trend.verdict(health['external_power'])[1] if self.monitoring else '')
  else:
   self.volts.set(f'{value} %' if value is not None else '-- %');self.verdict.set('Device-reported level only.')
   self.battery_note.set(f'Read {stamp} / raw level {report["level_raw"]}, status {report["status_raw"]}. Voltage is measured only by the 0.6.0 build.')
  self.next_battery=time.monotonic()+5;self.draw_chart();self.monitor_state()
  self.status.set(f'Battery read complete at {stamp} / {self.percent.get()}.')
 def draw_chart(self):
  c=self.chart;c.delete('all');width=max(c.winfo_width(),600);height=max(c.winfo_height(),60)-4;data=self.history.samples[-200:]
  volts=any(item.get('health') for item in data);top=4.4 if volts else 100;y=lambda v:int((height-10-(v/top)*(height-24))/4)*4
  if volts:
   for level,name in ((3.0,'3.0 V'),(4.07,'FULL')):
    for x in range(8,width-60,8):c.create_rectangle(x,y(level),x+3,y(level)+1,fill=pixel.LINE_DK,outline='')
    c.create_text(width-10,y(level),text=name,fill=MUTED,anchor='e',font=LABEL)
  step=max(4,(width-80)//max(1,len(data))//4*4)
  for i,item in enumerate(data):
   value=item['health']['pack_volts_estimate'] if item.get('health') else (None if volts else item.get('level_raw'))
   if item.get('transport')!='available' or value is None:continue
   x=8+i*step;c.create_rectangle(x,y(value)-4,x+step-1,y(value),fill=MINT,outline='')
  c.create_text(10,10,text='PACK VOLTAGE' if volts else 'DEVICE LEVEL',fill=MUTED,anchor='nw',font=LABEL)

 def install(self):
  if self.busy:return self.status.set(self.operation+' is still running. Please wait.')
  name=self.build.get();external=name.startswith('Selected file:')
  if external and not self.external_firmware:return self.status.set('Choose a valid firmware file first.')
  unreviewed=external and not self.external_firmware[1]['reviewed']
  if unreviewed and not self.allow_unreviewed.get():return self.status.set('This binary is unreviewed. Enable the explicit unreviewed-file option before installing.')
  notice='\n\nThis is YOUR UNREVIEWED CODE. Structural checks do not establish hardware compatibility; recovery may require a programmer.' if unreviewed else ''
  if not messagebox.askokcancel('Install firmware','Install '+name+'?'+notice+'\n\nThe official V0113 firmware is downloaded from VGN once if it is not cached yet.\nKeep USB connected in wired mode until verification completes.\nSettings are backed up before writing.',parent=self.root):return
  self.stop_monitor();self.stop_test();self.version=None;self.flashing=True;self.progress['value']=0;self.install_button.configure(state='disabled')
  current_reference=self.external_firmware[0] if self.external_firmware else None
  def flash():
   from tools import reflash_v0113 as ota
   self.results.put(('firmware_note','Preparing the official V0113 base and applying the patch...'))
   stock=firmware_source.stock(CACHE);payload=self.external_firmware[0] if external else firmware_source.build(CACHE,name)
   ota.ROOT=WORK
   return ota.reflash(payload,stock,firmware_source.apply_patch(stock,'lavender-quest-0.5.1'),progress=lambda n,total:self.results.put(('progress',n,total)),allow_unreviewed=unreviewed,current_user_reference=current_reference)
  self.submit('Installing firmware',flash,self.installed_build)
 def installed_build(self,result):
  self.firmware_note.set('Installation complete. Device-reported CRC matches the selected build.');self.progress['value']=4936;self.flashing=False;self.install_button.configure(state='normal');self.root.after(200,self.read_version)
 def start_test(self):
  if not self.monitor:return self.status.set('Connect the X68 in wired mode first.')
  self.monitor.active=True;self.test_until=time.monotonic()+60;self.test_note.set('Testing. Keep this window focused.')
 def stop_test(self):
  self.test_until=0
  if self.monitor:self.monitor.active=False
  self.pressed.clear()
 def clear_test(self):self.counts.clear();self.pressed.clear();self.draw_boards()
 def restore(self):
  if self.busy:return
  path=filedialog.askopenfilename(parent=self.root,title='Restore X68 settings backup',filetypes=[('JSON backup','*.json')])
  if path:self.submit('Restoring settings backup',lambda:self.settings_client.restore(path),lambda value:self.root.after(100,self.read_settings))
 def read_adc_snapshot(self):
  if not self.version:return self.status.set('Check the installed version first.')
  version=dict(self.version)
  def read():
   from .battery_diagnostic import query_snapshot
   return query_snapshot(self.settings_client,version)
  self.submit('Reading cached ADC snapshot',read,self.show_adc_snapshot)
 def show_adc_snapshot(self,result):
  self.logs.append({'battery_engineering_snapshot':result});folder=WORK/'reports';folder.mkdir(parents=True,exist_ok=True)
  (folder/'battery-engineering-latest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
  self.status.set('ADC snapshot read. Raw counts and calculation are in Advanced; physical voltage/current remain unknown.')
 def open_reports(self):
  p=WORK/'reports';p.mkdir(parents=True,exist_ok=True)
  if sys.platform=='win32':os.startfile(p)
  else:subprocess.Popen(['open' if sys.platform=='darwin' else 'xdg-open',str(p)])
 def save_json(self,data,name):
  path=filedialog.asksaveasfilename(parent=self.root,initialfile=name,defaultextension='.json',filetypes=[('JSON','*.json')])
  if path:Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');self.status.set('File saved.')
 def report(self):return {'app':'VGN X68 Custom Firmware 0.6.0','inventory':self.inventory,'version':self.version,'settings':self.settings,'packets':self.settings_client.trace,'battery':self.history.report(),'logs':self.logs}
 def details(self):
  self.raw.configure(state='normal');self.raw.delete('1.0','end');self.raw.insert('1.0',json.dumps(self.report(),ensure_ascii=False,indent=2));self.raw.configure(state='disabled')
  self.log_text.configure(state='normal');self.log_text.delete('1.0','end');self.log_text.insert('1.0',json.dumps(self.logs,ensure_ascii=False,indent=2));self.log_text.configure(state='disabled')
 def ui_error(self,kind,error,tb):
  detail=''.join(traceback.format_exception(kind,error,tb));self.logs.append({'ui_error':detail});self.status.set('Interface error recorded in Advanced. Other actions remain available.')
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
  while not self.results.empty():
   item=self.results.get_nowait()
   if item[0]=='firmware_note':self.firmware_note.set(item[1]);continue
   if item[0]=='progress':self.progress['value']=item[1];self.firmware_note.set(f'Writing packet {item[1]} / {item[2]}');continue
   if item[0]=='media_progress':self.media_progress['value']=100*item[1]/item[2];self.media_note.set(f'Uploading {item[1]:,} / {item[2]:,} bytes. Keep USB connected.');continue
   _,name,result,error,done=item;self.busy=False
   self.logs.append({'time':datetime.now().astimezone().isoformat(),'operation':name,'error':error})
   if error:
    try:
     (WORK/'reports').mkdir(parents=True,exist_ok=True)
     with open(WORK/'reports/errors.log','a',encoding='utf-8') as log:log.write(datetime.now().astimezone().isoformat(timespec='seconds')+'  '+name+': '+error+'\n')
    except OSError:pass
    self.status.set(error if name=='Finding X68' and 'Input Monitoring' in error else 'Operation failed. Check the connection; details are in Advanced.')
    if name=='Finding X68':self.inventory=None;self.device.set('[ ]  X68 NOT CONNECTED');self.usb_mode.set('Not connected');self.connect_button.configure(text='Connect',state='normal');self.next_reconnect=time.monotonic()+5
    if name=='Reading battery':self.history.record(error=error);self.next_battery=time.monotonic()+5
    if name=='Syncing keyboard clock':self.next_clock_sync=time.monotonic()+60;self.clock_note.set('Sync failed; reconnecting to verify the device.');self.inventory=None;self.version=None;self.next_reconnect=time.monotonic()+5
    if self.flashing:self.flashing=False;self.install_button.configure(state='normal');self.firmware_note.set('Update stopped. Check Advanced logs before retrying; no automatic retry was sent.');self.media_note.set('Transfer stopped. Check Advanced logs. No automatic retry was sent.')
   elif done:
    self.status.set(name+' complete.');done(result)
   else:self.status.set(name+' complete.')
   self.logs=self.logs[-200:]
   if name=='Reading battery':
    folder=WORK/'reports/battery-sessions';folder.mkdir(parents=True,exist_ok=True)
    (folder/'studio-latest.json').write_text(json.dumps(self.history.report(),ensure_ascii=False,indent=2),encoding='utf-8')
   self.details()
   if self.smoke:self.root.after(200,self.smoke_done)
  if not self.smoke and not self.inventory and not self.busy and not self.flashing and time.monotonic()>=self.next_reconnect:self.refresh()
  if not self.smoke and self.auto_clock.get() and self.inventory and self.settings and self.version and not self.busy and not self.flashing and time.monotonic()>=self.next_clock_sync:self.sync_clock()
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
   self.test_note.set(f"{name} / {self.counts.get(name,0)} press events / {len(self.counts)} distinct keys")
  if self.test_until:
   if time.monotonic()>=self.test_until:self.stop_test()
   elif self.monitor:
    focused,modifiers=self.monitor.visual_state()
    if not focused:self.pressed.clear()
    for raw,key in {'38':'ALT','E0:38':'RALT','1D':'CTRL','E0:1D':'RCTRL','2A':'SHIFT','36':'RSHIFT','E0:5B':'WIN'}.items():
     if modifiers.get(raw) is False:self.pressed.discard(key)
 def animate(self):
  if self.closed:return
  if self.page_name in ('Lighting','Keymap','Advanced'):self.draw_boards(time.monotonic())
  if self.page_name=='Screen' and self.media_photos and time.monotonic()>=self.media_due:
   self.screen_preview.configure(image=self.media_photos[self.media_frame]);self.media_frame=(self.media_frame+1)%len(self.media_photos);self.media_due=time.monotonic()+self.prepared.period_ms/1000
  self.root.after(50 if self.page_name=='Screen' else 130,self.animate)
 def smoke_done(self):
  result={'inventory_loaded':bool(self.inventory),'window_size':[self.root.winfo_width(),self.root.winfo_height()],'pages':list(self.pages),'english_ui':True,'no_automatic_settings_write':True,'firmware_install_requires_click':True}
  (WORK/'reports').mkdir(parents=True,exist_ok=True);(WORK/'reports/gui-smoke.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result));self.close()
 def close(self):
  if self.flashing:
   self.status.set('Wait for the device transfer to finish before closing.');return
  self.closed=True;self.stop_test()
  if self.monitor:self.monitor.close()
  self.pool.shutdown(wait=False,cancel_futures=True);self.root.destroy()
