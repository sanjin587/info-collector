from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
COLLECTOR_PATH = ROOT / "scripts" / "collector.py"

spec = importlib.util.spec_from_file_location("info_collector_cli", COLLECTOR_PATH)
collector = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(collector)


def load_collector_with_env(monkeypatch, **values):
    for name in ("OBSIDIAN_OUTPUT_DIR", "OBSIDIAN_VAULT_PATH"):
        monkeypatch.setenv(name, "")
    for name, value in values.items():
        monkeypatch.setenv(name, str(value))

    isolated_spec = importlib.util.spec_from_file_location(
        "info_collector_config_test", COLLECTOR_PATH
    )
    assert isolated_spec is not None
    assert isolated_spec.loader is not None
    isolated_collector = importlib.util.module_from_spec(isolated_spec)
    isolated_spec.loader.exec_module(isolated_collector)
    return isolated_collector


def test_detect_douyin_url():
    platform, target = collector.detect("https://www.douyin.com/video/123456789")
    assert platform == "抖音"
    assert target == "https://www.douyin.com/video/123456789"


def test_detect_youtube_url():
    platform, target = collector.detect("https://youtu.be/abcDEF123")
    assert platform == "YouTube"
    assert target == "https://youtu.be/abcDEF123"


def test_detect_local_media(tmp_path):
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"")
    platform, target = collector.detect(str(media))
    assert platform == "本地文件"
    assert target == str(media)


def test_rejects_short_cdp_text():
    ok, reason = collector._validate_transcript_quality("这是很短的一句话", source="CDP")
    assert not ok
    assert "过少" in reason or "行数" in reason


def test_accepts_reasonable_cdp_transcript():
    text = "\n".join([
        "今天我们讨论一个实际的问题，如何把一段视频稳定地变成可搜索、可归档的逐字稿。",
        "第一步是识别内容来源，第二步是获取媒体，第三步是转录并检查文本质量。",
        "如果主方案失败，系统应该自动进入备用方案，而不是直接结束整个任务。",
    ])
    ok, reason = collector._validate_transcript_quality(text, source="CDP")
    assert ok
    assert reason == "ok"


def test_fallback_chain_uses_second_strategy():
    def fail():
        raise RuntimeError("expected failure")

    result = collector.run_fallback_chain(
        "test-chain",
        [
            {"label": "first", "fn": fail, "timeout": 1},
            {
                "label": "second",
                "fn": lambda: {"transcript": "成功的逐字稿内容", "platform": "test"},
                "timeout": 1,
            },
        ],
    )

    assert result["transcript"] == "成功的逐字稿内容"
    assert result["_strategy"] == "second"
    assert result["_tried"] == ["first", "second"]


def test_default_transcript_output_is_repository_local(monkeypatch):
    isolated_collector = load_collector_with_env(monkeypatch)

    assert isolated_collector.OBSIDIAN_TARGET == (
        ROOT / "outputs" / "transcripts"
    )


def test_obsidian_vault_path_uses_default_transcript_subdirectory(
    monkeypatch, tmp_path
):
    vault = tmp_path / "vault"
    isolated_collector = load_collector_with_env(
        monkeypatch, OBSIDIAN_VAULT_PATH=vault
    )

    assert isolated_collector.OBSIDIAN_TARGET == (
        vault
        / "05_内容生产库"
        / "三金AI实验室_30天万粉作战计划"
        / "逐字稿"
    )


def test_direct_output_path_takes_precedence_over_vault(monkeypatch, tmp_path):
    vault = tmp_path / "vault"
    direct_output = tmp_path / "direct-output"
    isolated_collector = load_collector_with_env(
        monkeypatch,
        OBSIDIAN_VAULT_PATH=vault,
        OBSIDIAN_OUTPUT_DIR=direct_output,
    )

    assert isolated_collector.OBSIDIAN_TARGET == direct_output
