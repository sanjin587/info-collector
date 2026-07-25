#!/usr/bin/env python3
"""
本地音视频文件 → 文字（双引擎）

引擎选择:
  1. paraformer（默认）— 阿里百炼在线API，中文极准，需要 DASHSCOPE_API_KEY
  2. whisper — faster-whisper 本地CPU运行，离线可用，模型自动下载

用法:
  python transcribe_local.py 视频.mp4
  python transcribe_local.py 音频.mp3 --engine paraformer
  python transcribe_local.py 演讲.wav --engine whisper --model large-v3
  python transcribe_local.py ./录音目录/ --lang zh --output 全部文稿.txt

支持格式:
  mp3/mp4/wav/m4a/aac/flac/ogg/wmv/mov/avi/mkv/webm/amr/opus
"""

import os, sys, argparse, json, subprocess, time
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

FILE_EXTENSIONS = {'.mp3', '.mp4', '.wav', '.m4a', '.aac', '.flac', '.ogg',
                   '.wmv', '.mov', '.avi', '.mkv', '.webm', '.amr', '.opus'}


def find_media_files(paths):
    """收集所有媒体文件"""
    files = []
    for p in paths:
        p = Path(p)
        if p.is_file():
            if p.suffix.lower() in FILE_EXTENSIONS:
                files.append(p)
            else:
                print(f"⚠️ 跳过不支持的文件: {p.name}")
        elif p.is_dir():
            found = [f for f in p.rglob('*') if f.suffix.lower() in FILE_EXTENSIONS]
            found.sort()
            files.extend(found)
            print(f"📁 从目录找到 {len(found)} 个媒体文件")
        else:
            print(f"⚠️ 路径不存在: {p}")
    return files


def extract_audio(video_path, temp_dir=None):
    """从视频提取16kHz单声道WAV（如果是视频的话）"""
    audio_ext = video_path.suffix.lower()
    if audio_ext in {'.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg', '.opus', '.amr'}:
        return str(video_path)  # 已经是音频

    if temp_dir is None:
        temp_dir = video_path.parent
    temp_audio = Path(temp_dir) / f"~temp_{video_path.stem}.wav"

    print(f"🎬 提取音频: {video_path.name}")
    subprocess.run([
        'ffmpeg', '-i', str(video_path),
        '-vn', '-acodec', 'pcm_s16le',
        '-ar', '16000', '-ac', '1',
        '-y', str(temp_audio)
    ], capture_output=True, check=True)
    return str(temp_audio)


def transcribe_paraformer(audio_path, lang='zh'):
    """使用阿里百炼 Paraformer 语音识别（中文极准）"""
    import dashscope

    api_key = os.environ.get('DASHSCOPE_API_KEY')
    if not api_key:
        print("❌ 未设置 DASHSCOPE_API_KEY")
        print("   请在 .claude/settings.json 的 env 中配置，或 export DASHSCOPE_API_KEY=...")
        sys.exit(1)

    dashscope.api_key = api_key

    api_base = os.environ.get('DASHSCOPE_API_BASE')
    if api_base:
        dashscope.base_http_api_url = api_base
        print(f"🔗 已设置自定义 API: {api_base}")

    # 确定语言参数
    lang_map = {'zh': 'zh-CN', 'en': 'en-US', 'ja': 'ja-JP', 'ko': 'ko-KR',
                'yue': 'zh-CN', 'auto': 'auto'}
    lang_param = lang_map.get(lang, lang)

    print(f"🎯 [Paraformer] 开始识别...")
    start = time.time()

    with open(audio_path, 'rb') as f:
        audio_data = f.read()

    # 文件大小检查（百炼限制 ~10分钟/约50MB）
    file_size_mb = len(audio_data) / (1024 * 1024)
    if file_size_mb > 50:
        print(f"⚠️ 文件较大 ({file_size_mb:.1f}MB)，Paraformer 可能超时，建议截断或用 whisper 引擎")

    # 检测是否为长音频（>4MB 走文件转写异步接口）
    is_long = file_size_mb > 4

    if is_long:
        print(f"📎 长音频模式（{file_size_mb:.1f}MB），使用异步文件转写...")
        from dashscope.audio.asr import Transcription

        # 先上传文件
        print("📤 上传音频文件...")
        upload_start = time.time()
        response = Transcription.async_call(
            model='paraformer-v2',
            file_url=audio_path,  # 需要是URL，本地文件用不上
        )
        # 实际上对于本地文件，需要走不同的路径
        # 改用实时识别+分段方式
        print("⚠️ 大文件建议使用 whisper 引擎（本地处理无大小限制）")
        print("   切换到 whisper:")
        print("   python transcribe_local.py 文件.mp4 --engine whisper")
        sys.exit(1)
    else:
        # 实时识别（小文件）
        from dashscope.audio.asr import Recognition

        recognition = Recognition(
            model='paraformer-v2',
            format='wav',
            sample_rate=16000,
            language='zh-CN'
        )

        # 创建识别任务
        result = recognition.call(audio_data)

    elapsed = time.time() - start
    print(f"⏱ 识别耗时: {elapsed:.1f}s")

    # 解析结果
    if hasattr(result, 'output') and result.output:
        if hasattr(result.output, 'text'):
            full_text = result.output.text
            # 分段
            segments = result.output.get('segments', [])
            if segments:
                lines = []
                for seg in segments:
                    ts = f"[{seg.get('begin_time', 0):.1f}s --> {seg.get('end_time', 0):.1f}s]"
                    lines.append(f"{ts} {seg.get('text', '')}")
                full_text = '\n'.join(lines)
            return full_text
    return str(result)


def transcribe_whisper(audio_path, model_size='base', lang=None):
    """使用 faster-whisper 本地识别（全离线）"""
    from faster_whisper import WhisperModel

    # 确定计算类型 - CPU模式用 int8 加速
    compute_type = 'int8'

    print(f"🧠 [Whisper] 加载模型: {model_size}")
    start = time.time()
    model = WhisperModel(model_size, device='cpu', compute_type=compute_type)
    load_time = time.time() - start
    print(f"  模型加载: {load_time:.1f}s")

    lang_str = f'（指定语言: {lang}）' if lang else '（自动检测）'
    print(f"🎯 开始识别{lang_str}...")

    segments, info = model.transcribe(
        audio_path, language=lang,
        beam_size=5, vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500)
    )

    detected_lang = info.language
    confidence = info.language_probability
    print(f"🌐 检测语言: {detected_lang} (置信度 {confidence:.1%})")

    result_lines = []
    for seg in segments:
        timestamp = f"[{_fmt_time(seg.start)} --> {_fmt_time(seg.end)}]"
        line = f"{timestamp} {seg.text.strip()}"
        result_lines.append(line)

    return '\n'.join(result_lines), detected_lang


def _fmt_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def main():
    parser = argparse.ArgumentParser(
        description='本地文件转文字（Whisper 本地 / Paraformer 在线）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python transcribe_local.py 视频.mp4
  python transcribe_local.py 音频.mp3 --engine whisper
  python transcribe_local.py 会议.m4a --engine paraformer --lang zh
  python transcribe_local.py ./目录/ --engine whisper --model medium -o 文稿.txt
  python transcribe_local.py 演讲.wav --engine whisper --model large-v3 --lang zh
        """)
    parser.add_argument('input', nargs='+', help='媒体文件 或 目录路径')
    parser.add_argument('--engine', '-e', default='paraformer',
                        choices=['paraformer', 'whisper'],
                        help='识别引擎（paraformer=百炼在线/中文准, whisper=本地/离线）')
    parser.add_argument('--model', '-m', default='base',
                        help='Whisper模型大小: tiny/base/small/medium/large-v3（默认 base）')
    parser.add_argument('--lang', '-l', default='zh',
                        help='语言（zh/en/ja/ko，paraformer默认zh，whisper默认自动检测）')
    parser.add_argument('--output', '-o', default=None,
                        help='输出文件路径（不指定则打印到屏幕）')
    parser.add_argument('--json', action='store_true',
                        help='同时输出 JSON 格式')
    parser.add_argument('--keep-temp', action='store_true',
                        help='保留临时音频文件')
    args = parser.parse_args()

    # 找文件
    files = find_media_files(args.input)
    if not files:
        print("❌ 没有找到可识别的媒体文件")
        print(f"支持的格式: {', '.join(sorted(FILE_EXTENSIONS))}")
        sys.exit(1)

    if args.engine == 'paraformer':
        api_key = os.environ.get('DASHSCOPE_API_KEY')
        if not api_key:
            print("❌ 使用 paraformer 引擎需要 DASHSCOPE_API_KEY")
            print("   已写入 settings.json，当前会话可能需要先:")
            print("   export DASHSCOPE_API_KEY=sk-...")
            print("   或使用 whisper 引擎: --engine whisper")
            sys.exit(1)

    all_results = {}
    temp_files = []

    for i, file_path in enumerate(files):
        print(f"\n{'='*60}")
        print(f"📄 [{i+1}/{len(files)}] {file_path.name}")
        print(f"{'='*60}")

        # 提取音频
        try:
            audio_path = extract_audio(file_path)
            if audio_path != str(file_path):
                temp_files.append(audio_path)
        except Exception as e:
            print(f"❌ 提取音频失败: {e}")
            continue

        # 识别
        try:
            if args.engine == 'paraformer':
                text = transcribe_paraformer(audio_path, args.lang)
                all_results[str(file_path)] = {
                    'text': text,
                    'engine': 'paraformer',
                    'segments': [l for l in text.split('\n') if l.strip()]
                }
            else:
                text, detected_lang = transcribe_whisper(audio_path, args.model, args.lang)
                all_results[str(file_path)] = {
                    'text': text,
                    'engine': 'whisper',
                    'model': args.model,
                    'language': detected_lang,
                    'segments': [l for l in text.split('\n') if l.strip()]
                }
        except Exception as e:
            print(f"❌ 识别失败: {e}")
            import traceback
            traceback.print_exc()
            continue

        # 清理临时音频
        if not args.keep_temp and audio_path != str(file_path):
            try:
                os.remove(audio_path)
            except:
                pass

    # 输出汇总
    output_text = []
    for fp, result in all_results.items():
        output_text.append(f"{'='*60}")
        output_text.append(f"文件: {fp}")
        output_text.append(f"引擎: {result.get('engine', '?')}")
        if 'language' in result:
            output_text.append(f"语言: {result['language']}")
        if 'model' in result:
            output_text.append(f"模型: {result['model']}")
        output_text.append(f"{'='*60}")
        output_text.append(result['text'])
        output_text.append('')

    final_text = '\n'.join(output_text)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(final_text)
        print(f"\n✅ 文稿已保存: {args.output}")

    if args.json:
        json_path = (Path(args.output).with_suffix('.json')
                     if args.output else Path.cwd() / 'transcript.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            # segments 只保留纯文本版本
            clean = {}
            for k, v in all_results.items():
                clean[k] = {kk: vv for kk, vv in v.items() if kk != 'segments'}
                clean[k]['text'] = v['text']
            json.dump(clean, f, ensure_ascii=False, indent=2)
        print(f"✅ JSON 已保存: {json_path}")

    # 如果没指定输出文件，显示纯文本摘要
    if not args.output:
        print(f"\n{'='*60}")
        print("📋 文稿内容（完整版）：")
        print(f"{'='*60}")
        # 只显示纯文本，不带时间戳
        for fp, result in all_results.items():
            clean_text = '\n'.join(
                line.split('] ', 1)[-1] if '] ' in line else line
                for line in result['text'].split('\n')
            )
            print(f"\n--- {Path(fp).name} ---")
            print(clean_text[:2000])  # 太长就截断
            if len(clean_text) > 2000:
                print(f"\n...（共 {len(clean_text)} 字，完整内容请指定 --output 保存到文件）")

    print(f"\n{'='*60}")
    print(f"✅ 完成: {len(all_results)}/{len(files)} 个文件转文字成功")
    if args.output:
        print(f"   输出文件: {args.output}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
