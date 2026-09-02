import json
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "models" / "ai_ohto.glb"


def read_glb_json(path: Path) -> dict:
    data = path.read_bytes()
    magic, version, _ = struct.unpack_from("<III", data, 0)
    assert magic == 0x46546C67
    assert version == 2
    offset = 12
    while offset < len(data):
        length, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        chunk = data[offset:offset + length]
        offset += length
        if chunk_type == 0x4E4F534A:
            return json.loads(chunk.decode("utf-8"))
    raise AssertionError("GLB JSON chunk missing")


def test_real_glb_exists_and_has_valid_header():
    assert MODEL.is_file()
    assert MODEL.stat().st_size == 7_253_992
    read_glb_json(MODEL)


def test_real_glb_geometry_materials_textures_and_animation_metadata():
    gltf = read_glb_json(MODEL)
    assert len(gltf["meshes"]) == 13
    assert len(gltf["materials"]) == 13
    assert len(gltf["textures"]) == 6
    assert gltf.get("animations", []) == []
    assert gltf.get("skins", []) == []


def test_ui_settings_persist_position_and_size(tmp_path, monkeypatch):
    import ui.config as config

    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(config, "SETTINGS_PATH", settings_file)
    config.save_settings({"x": -120, "y": 88, "width": 420, "height": 600})
    saved = config.load_settings()
    assert saved["x"] == -120
    assert saved["y"] == 88
    assert saved["width"] == 420
    assert saved["height"] == 600


def test_ui_and_backend_bridge_import():
    import pytest

    pytest.importorskip("PySide6")
    import ui.main
    import ui.backend_bridge

    assert ui.main.CompanionWindow
    assert ui.backend_bridge.BackendBridge
