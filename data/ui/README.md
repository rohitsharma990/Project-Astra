# Astra desktop companion

This UI is a transparent, frameless Qt WebEngine host around a local Three.js scene. The WebGL layer owns presentation and interaction; `backend_bridge.py` is the only application integration boundary and delegates requests to the existing `BackendRuntime`.

## Start

From the repository root, after placing the supplied model at `ui/models/ai_ohto.glb`:

```text
backend\.venv\Scripts\python.exe ui\main.py
```

The UI persists position, size, scale, topmost preference, and edge preference in `ui/settings.json`. Right-click the character for controls, left-drag it to move the native window, double-click to open chat, and use approval cards for agent plans that require confirmation.

## Asset limitation

The workspace currently does not contain `ai_ohto.glb`, so the model's dimensions, rig, materials, textures, and embedded animation clips could not be inspected here. The renderer does not substitute another model; it reports a load failure until the supplied file is copied into `ui/models/`.

True OS window attachment/snapping and system tray integration are not included in this first UI slice. Native dragging, transparent presentation, topmost mode, asynchronous backend calls, approval gating, and safe shutdown are implemented.
