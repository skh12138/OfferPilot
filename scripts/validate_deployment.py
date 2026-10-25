from pathlib import Path
import subprocess
import yaml

config=yaml.safe_load(Path('compose.yaml').read_text())
assert {'web','api','worker','db','migrate'}==set(config['services'])
assert 'ports' not in config['services']['db']
assert ':latest' not in Path('compose.yaml').read_text()
subprocess.run(['docker','compose','config','--quiet'],check=True)
print('Deployment config validated; container image build is checked separately by CI/Compose acceptance.')
