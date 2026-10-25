import os
import signal
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT)
processes=[]
try:
    print('Web http://localhost:5173  API http://localhost:8000/docs',flush=True)
    subprocess.run(['.venv/bin/alembic','-c','apps/server/alembic.ini','upgrade','head'],check=True)
    for command in [[sys.executable,'-m','uvicorn','offerpilot.api.app:app','--host','127.0.0.1','--port','8000','--reload'],[sys.executable,'-m','offerpilot.worker.main'],['pnpm','dev']]:
        processes.append(subprocess.Popen(command,cwd=ROOT))
    def stop(signum,frame):raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM,stop)
    while True:
        for child in processes:
            if child.poll() is not None:raise SystemExit(child.returncode)
        import time
        time.sleep(.5)
except KeyboardInterrupt:
    pass
finally:
    for child in processes:child.terminate()
    for child in processes:
        try:child.wait(timeout=5)
        except subprocess.TimeoutExpired:child.kill()
