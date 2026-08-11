# Contributing

1. Open an issue describing the user problem and affected workflow mode.
2. Keep changes focused and do not add model files, generated media, personal paths, credentials, or telemetry.
3. Update `compatibility.json` when changing a required model, node, plugin, or tested runtime.
4. Add or update deterministic unit tests.
5. Run:

```powershell
py -3 -X utf8 -m unittest -v test_workflow_engine.py
node --check app.js
.\scripts\privacy-check.ps1
```

Pull requests must state whether GPU generation was actually run. Schema validation, workflow export, and a completed render are different evidence levels and must not be presented as equivalent.
