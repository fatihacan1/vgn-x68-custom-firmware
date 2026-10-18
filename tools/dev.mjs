// Zero npm dependencies. Bootstraps the native desktop environment on Win/macOS.
import {existsSync, readFileSync, writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {dirname, join, resolve} from 'node:path';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const win=process.platform==='win32';
const envDir=join(root,win?'.venv':'.venv-macos');
const python=join(envDir,win?'Scripts/python.exe':'bin/python');
function run(command,args,options={}) {
  const result=spawnSync(command,args,{cwd:root,stdio:'inherit',...options});
  if(result.error)throw result.error;
  if(result.status!==0)throw new Error(`${command} exited with ${result.status}`);
}
try {
  if(!existsSync(python)) {
    const candidates=win?[['py',['-3']],['python',[]]]:[['python3',[]]];
    const base=candidates.find(([cmd,args])=>spawnSync(cmd,[...args,'-c','import sys; assert sys.version_info >= (3, 10)'],{stdio:'ignore'}).status===0);
    if(!base)throw new Error('Install Python 3.10 or newer with Tk support, then run npm run dev again.');
    run(base[0],[...base[1],'-m','venv',envDir]);
  }
  const hash=createHash('sha256').update(readFileSync(join(root,'requirements.txt'))).digest('hex');
  const marker=join(envDir,'x68-requirements.sha256');
  const imports=spawnSync(python,['-c','import hid; from PIL import Image, ImageTk'],{stdio:'ignore'}).status===0;
  if(!imports || !existsSync(marker) || readFileSync(marker,'utf8')!==hash) {
    run(python,['-m','pip','install','-r','requirements.txt']);writeFileSync(marker,hash);
  }
  if(spawnSync(python,['-c','import tkinter'],{stdio:'ignore'}).status!==0)
    throw new Error('Python Tk is missing. On macOS use a Python installation that includes Tk (python.org), or install the matching python-tk package.');
  const args=process.argv.slice(2);
  if(args.includes('--check'))console.log('X68 desktop environment ready. Run npm run dev to open the app.');
  else if(args.includes('--test'))run(python,['-m','unittest','discover','-s','tests','-q']);
  else run(python,['app.py',...args]);
} catch(error) {console.error('\nX68 launcher: '+error.message);process.exitCode=1;}
