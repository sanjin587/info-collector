# -*- coding: utf-8 -*-
"""Auto-detect GPU once and persist the choice.

Usage:
    from utils.gpu_config import get_device_config
    device, compute_type = get_device_config()
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

On first run, auto-detects CUDA availability and saves to .gpu_config.json.
Subsequent runs read the cached config — no re-detection overhead.
To force re-detection: delete .gpu_config.json or run with --gpu-detect.
"""
import json
import os
import sys
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / ".gpu_config.json"


def _detect():
    """Probe ctranslate2 for CUDA support."""
    try:
        from ctranslate2 import get_supported_compute_types
        cuda_types = get_supported_compute_types("cuda")
        if cuda_types and "float16" in cuda_types:
            return {"device": "cuda", "compute_type": "float16"}
    except Exception:
        pass
    return {"device": "cpu", "compute_type": "int8"}


def get_device_config(force_detect=False):
    """Return (device, compute_type) from cache or auto-detect.

    Set force_detect=True to re-probe and overwrite cache.
    """
    if not force_detect and CONFIG_PATH.exists():
        try:
            cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return cfg["device"], cfg["compute_type"]
        except Exception:
            pass

    cfg = _detect()
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass  # non-fatal — will re-detect next time

    # Print once so user knows what's being used
    label = "GPU" if cfg["device"] == "cuda" else "CPU"
    print(f"[gpu_config] 检测完成 → {label} (已保存到 {CONFIG_PATH.name})", flush=True)
    return cfg["device"], cfg["compute_type"]
