import json
from pathlib import Path
from offerpilot.api.app import app
Path("contracts/openapi.json").write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n")
