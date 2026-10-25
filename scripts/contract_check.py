import subprocess
from pathlib import Path

paths=[Path('contracts/openapi.json'),Path('apps/web/src/api/schema.d.ts')]
before={p:p.read_bytes() for p in paths}
subprocess.run(['make','contract'],check=True)
changed=[str(p) for p in paths if before[p]!=p.read_bytes()]
if changed:raise SystemExit('Contract drift: '+', '.join(changed))
print('OpenAPI and generated TypeScript are synchronized')
