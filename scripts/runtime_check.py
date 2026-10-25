import shutil
import subprocess
import sys

if sys.version_info[:2] != (3,12):raise SystemExit('Python 3.12 is required')
for executable in ['node','pnpm','docker']:
    if not shutil.which(executable):raise SystemExit(f'{executable} is required')
version=subprocess.check_output(['node','--version'],text=True).strip()
if not version.startswith('v24.'):raise SystemExit(f'Node24 is required; found {version}')
print('Python3.12 / Node24 / pnpm / Docker CLI found; Docker daemon checked by make up.')
