"""Render this project's own Tk windows offline. No device operations."""
from pathlib import Path
import sys,tkinter as tk
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'.venv/Lib/site-packages'))
from PIL import ImageGrab
from x68.desktop import Studio
root=tk.Tk();app=Studio(root,smoke=True)
# Cancel timers before processing events: no inventory, HID, key capture or I/O.
for timer in root.tk.call('after','info'):root.after_cancel(timer)
folder=ROOT/'reports/studio-preview';folder.mkdir(parents=True,exist_ok=True)
for name in app.pages:
 app.show(name);root.update();app.draw_boards(0)
 ImageGrab.grab(window=root.winfo_id()).save(folder/(name.lower()+'.png'))
app.close();print(folder)
