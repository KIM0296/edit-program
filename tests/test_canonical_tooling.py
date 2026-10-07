import json
from dataclasses import FrozenInstanceError
from hashlib import sha256
from pathlib import Path

import pytest

from tools.canonical_assets.checksums import (
    canonical_json,
    checksum_bytes,
    file_hash,
    parse_checksums,
    parse_json,
    safe_relative,
    staging_path,
)
from tools.canonical_assets.ffmpeg import ToolchainProfile, encode_tokens, mux_tokens, preflight
from tools.canonical_assets.model import AssetRole, BuildError, FailureStatus
from tools.canonical_assets.validate import parse_streams, validate_audio, validate_frame_records


def test_canonical_json_literal_and_invalid_numbers():
    assert (
        canonical_json({"z": [1, {"b": True, "a": "한"}], "a": None})
        == '{"a":null,"z":[1,{"a":"한","b":true}]}\n'.encode()
    )
    for value in (float("nan"), float("inf")):
        with pytest.raises(ValueError):
            canonical_json({"x": value})
    for raw in (b'{"a":1,"a":2}\n', b'{"x":NaN}\n', b"\xef\xbb\xbf{}\n"):
        with pytest.raises(ValueError):
            parse_json(raw)


def test_checksums_exact_format_and_real_bytes(tmp_path):
    one, two = sha256(b"one").hexdigest(), sha256(b"two").hexdigest()
    result = checksum_bytes((("z\\a", one), ("b", two)))
    assert result == f"{two}  b\n{one}  z/a\n".encode()
    assert parse_checksums(result) == (("b", two), ("z/a", one))
    assert sha256(result).digest() != sha256(checksum_bytes((("z/a", two), ("b", two)))).digest()
    path = tmp_path / "file"
    path.write_bytes(b"one")
    assert file_hash(path) == one
    for bad in (
        result.replace(b"  ", b" "),
        result.replace(b"\n", b"\r\n"),
        result + result,
        result[:-1],
    ):
        with pytest.raises(ValueError):
            parse_checksums(bad)


@pytest.mark.parametrize(
    "path",
    ["../escape", "/absolute", "C:/absolute", "a/../b", "a//b", "a/./b", "a:stream", "x\nname", ""],
)
def test_unsafe_paths_rejected(path, tmp_path):
    with pytest.raises(ValueError):
        safe_relative(path)
    with pytest.raises(ValueError):
        staging_path(tmp_path, path)


def profile(tmp_path):
    return ToolchainProfile(
        tmp_path / "ffmpeg.exe",
        tmp_path / "ffprobe.exe",
        "3.11.16",
        "2.3.5",
        "ffmpeg version test\nconfiguration: test",
        "ffprobe version test",
        "a" * 64,
        "b" * 64,
        "c" * 64,
        ("dnxhd", "dnxhr_lb", "yuv422p", "mov", "wav", "pcm_s24le", "bitexact"),
    )


def test_typed_commands_fixed_tokens_and_frozen_profile(tmp_path):
    tool = profile(tmp_path)
    with pytest.raises(FrozenInstanceError):
        tool.python_version = "3.14"
    command = encode_tokens(tool, tmp_path, "work/alpha.mov")
    assert isinstance(command, tuple)
    assert command[command.index("-profile:v") + 1] == "dnxhr_lb"
    assert command[command.index("-frames:v") + 1] == "720"
    assert command[command.index("-pix_fmt") + 1] == "yuv422p"
    assert "1280x720" in command and "pipe:0" in command and "-n" in command
    mux = mux_tokens(
        tool, tmp_path, "work/alpha.mov", "work/alpha.wav", "package/assets/alpha_v1.mov"
    )
    assert mux.count("copy") == 2 and mux[mux.index("-map") + 1] == "0:v:0"
    with pytest.raises(TypeError):
        encode_tokens(tool, tmp_path, "x", extra_args=("-c:v", "h264"))
    with pytest.raises(ValueError):
        encode_tokens(tool, tmp_path, "../outside.mov")
    with pytest.raises(TypeError):
        encode_tokens(tool, str(tmp_path), "x")


def test_missing_toolchain_fails_before_writing_media(tmp_path):
    with pytest.raises(BuildError) as caught:
        preflight(tmp_path / "ffmpeg.exe", tmp_path / "ffprobe.exe")
    assert caught.value.status == FailureStatus.TOOLCHAIN_UNSUPPORTED
    assert list(tmp_path.iterdir()) == []


def video():
    return {
        "index": 0,
        "codec_type": "video",
        "codec_name": "dnxhd",
        "profile": "DNXHR LB",
        "width": 1280,
        "height": 720,
        "pix_fmt": "yuv422p",
        "r_frame_rate": "24/1",
        "avg_frame_rate": "24/1",
        "field_order": "progressive",
        "sample_aspect_ratio": "1:1",
    }


def audio():
    return {
        "index": 1,
        "codec_type": "audio",
        "codec_name": "pcm_s24le",
        "sample_rate": "48000",
        "channels": 2,
        "bits_per_sample": 24,
        "bits_per_raw_sample": "24",
        "channel_layout": "stereo",
    }


def test_stream_parser_uses_observed_facts():
    facts = parse_streams(json.dumps({"streams": [video(), audio()]}).encode(), AssetRole.ALPHA)
    assert facts.video.width == 1280 and facts.audio.channels == 2
    with pytest.raises(FrozenInstanceError):
        facts.video.width = 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("profile", "DNXHR HQ"),
        ("codec_name", "h264"),
        ("width", 1920),
        ("height", 1080),
        ("pix_fmt", "yuv420p"),
        ("r_frame_rate", "30/1"),
        ("avg_frame_rate", "0/0"),
        ("field_order", "unknown"),
        ("sample_aspect_ratio", "2:1"),
    ],
)
def test_wrong_video_structure_rejected(field, value):
    v = video()
    v[field] = value
    with pytest.raises(BuildError):
        parse_streams(json.dumps({"streams": [v, audio()]}).encode(), AssetRole.ALPHA)


@pytest.mark.parametrize(
    "field,value",
    [
        ("codec_name", "aac"),
        ("sample_rate", "44100"),
        ("channels", 1),
        ("bits_per_sample", 16),
        ("channel_layout", "mono"),
    ],
)
def test_wrong_audio_structure_rejected(field, value):
    a = audio()
    a[field] = value
    with pytest.raises(BuildError):
        parse_streams(json.dumps({"streams": [video(), a]}).encode(), AssetRole.ALPHA)


@pytest.mark.parametrize(
    "streams",
    [
        [video()],
        [video(), audio(), {"codec_type": "subtitle"}],
        [video(), audio(), {"codec_type": "data"}],
        [],
    ],
)
def test_unexpected_stream_count_rejected(streams):
    with pytest.raises(BuildError):
        parse_streams(json.dumps({"streams": streams}).encode(), AssetRole.ALPHA)


def test_full_frame_observation_count_and_raster():
    records = {
        "frames": [
            {"width": 1280, "height": 720, "media_type": "video", "interlaced_frame": 0}
            for _ in range(720)
        ]
    }
    validate_frame_records(json.dumps(records).encode())
    records["frames"].pop()
    with pytest.raises(BuildError):
        validate_frame_records(json.dumps(records).encode())
    records["frames"].append(
        {"width": 1280, "height": 721, "media_type": "video", "interlaced_frame": 0}
    )
    with pytest.raises(BuildError):
        validate_frame_records(json.dumps(records).encode())


def test_audio_validation_exact_equality_not_just_duration():
    source = b"\0" * 8640000
    validate_audio(source, source)
    with pytest.raises(BuildError) as caught:
        validate_audio(source, source[:-6])
    assert caught.value.status == FailureStatus.SAMPLE_COUNT_MISMATCH
    with pytest.raises(BuildError) as caught:
        validate_audio(source, b"\1" + source[1:])
    assert caught.value.status == FailureStatus.AUDIO_DECODE_MISMATCH


def test_toolchain_capability_absence_and_exact_evidence(tmp_path, monkeypatch):
    import platform

    from tools.canonical_assets import ffmpeg as f

    monkeypatch.setattr(platform, "python_version_tuple", lambda: ("3", "11", "16"))
    monkeypatch.setattr(platform, "python_version", lambda: "3.11.16")
    encoder = tmp_path / "ffmpeg.exe"
    probe = tmp_path / "ffprobe.exe"
    encoder.write_bytes(b"fake encoder for unit test")
    probe.write_bytes(b"fake probe for unit test")
    responses = {
        "-version": b"ffmpeg version test\nconfiguration: test",
        "encoder=dnxhd": b"dnxhd dnxhr_lb yuv422p",
        "-muxers": b"mov wav",
        "encoder=pcm_s24le": b"pcm_s24le",
        "full": b"bitexact",
    }

    def capture(tokens, failure):
        if tokens[0] == str(probe.resolve()):
            return b"ffprobe version test"
        return responses[tokens[-1]]

    monkeypatch.setattr(f, "_capture", capture)
    actual = preflight(encoder, probe)
    assert actual.ffmpeg_sha256 == sha256(encoder.read_bytes()).hexdigest()
    for key, bad in [
        ("encoder=dnxhd", b"dnxhd yuv422p"),
        ("-muxers", b"mov"),
        ("encoder=pcm_s24le", b"aac"),
        ("full", b"no-options"),
    ]:
        original = responses[key]
        responses[key] = bad
        with pytest.raises(BuildError) as caught:
            preflight(encoder, probe)
        assert caught.value.status == FailureStatus.TOOLCHAIN_UNSUPPORTED
        responses[key] = original


def test_subprocess_failure_and_error_diagnostics_never_fallback(monkeypatch):
    import subprocess

    from tools.canonical_assets import ffmpeg as f

    called = []

    def run(tokens, **kwargs):
        called.append((tokens, kwargs))
        return subprocess.CompletedProcess(tokens, 1, b"", b"encoder rejected profile")

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(BuildError) as caught:
        f._capture(("ffmpeg", "-version"), FailureStatus.ENCODE_FAILURE)
    assert caught.value.status == FailureStatus.ENCODE_FAILURE and len(called) == 1
    assert called[0][1]["shell"] is False
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda tokens, **kwargs: subprocess.CompletedProcess(tokens, 0, b"", b"decode error"),
    )
    with pytest.raises(BuildError):
        f._capture(("ffmpeg",), FailureStatus.FRAME_COUNT_MISMATCH)


def test_new_tools_have_no_network_resolve_or_shell_surface():
    import ast

    directory = Path(__file__).parents[1] / "tools" / "canonical_assets"
    for path in directory.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not any(
                    n.name.split(".")[0] in {"requests", "urllib", "socket", "DaVinciResolveScript"}
                    for n in node.names
                )
            if isinstance(node, ast.Call):
                assert not any(
                    k.arg == "shell" and isinstance(k.value, ast.Constant) and k.value.value is True
                    for k in node.keywords
                )


def test_contradictory_audio_bit_depth_and_boolean_stream_index_rejected():
    a = audio()
    a["bits_per_raw_sample"] = "16"
    with pytest.raises(BuildError):
        parse_streams(json.dumps({"streams": [video(), a]}).encode(), AssetRole.ALPHA)
    a = audio()
    a["index"] = True
    with pytest.raises(BuildError):
        parse_streams(json.dumps({"streams": [video(), a]}).encode(), AssetRole.ALPHA)


def test_missing_stream_scan_requires_complete_decoded_frame_proof():
    from tools.canonical_assets.validate import validate_frame_records

    v = video()
    v.pop("field_order")
    blob = json.dumps({"streams": [v, audio()]}).encode()
    with pytest.raises(BuildError):
        parse_streams(blob, AssetRole.ALPHA)
    proof = validate_frame_records(
        json.dumps(
            {
                "frames": [
                    {"media_type": "video", "width": 1280, "height": 720, "interlaced_frame": 0}
                    for _ in range(720)
                ]
            }
        ).encode()
    )
    assert (
        parse_streams(blob, AssetRole.ALPHA, decoded_video=proof).video.field_order == "progressive"
    )


def test_decode_uses_explicit_passthrough_frame_mode(tmp_path):
    from tools.canonical_assets.ffmpeg import decode_tokens

    tokens = decode_tokens(profile(tmp_path), tmp_path, "video.mov", audio=False)
    assert "-vsync" not in tokens
    assert tokens[tokens.index("-fps_mode") + 1] == "passthrough"


def test_audio_only_layout_requires_actual_canonical_stereo_wav():
    from tools.canonical_assets.wav import wav_bytes

    a = audio()
    a["index"] = 0
    a.pop("channel_layout")
    blob = json.dumps({"streams": [a]}).encode()
    with pytest.raises(BuildError):
        parse_streams(blob, AssetRole.AUDIO_ONLY)
    wav = wav_bytes(bytes(8640000))
    assert (
        parse_streams(blob, AssetRole.AUDIO_ONLY, canonical_wav=wav).audio.channel_layout
        == "stereo"
    )
    with pytest.raises(BuildError):
        parse_streams(blob, AssetRole.AUDIO_ONLY, canonical_wav=b"invalid")
    a["channel_layout"] = "mono"
    with pytest.raises(BuildError):
        parse_streams(
            json.dumps({"streams": [a]}).encode(), AssetRole.AUDIO_ONLY, canonical_wav=wav
        )
