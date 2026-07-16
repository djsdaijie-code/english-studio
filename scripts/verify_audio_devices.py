from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import wave

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer
from PySide6.QtMultimedia import QMediaDevices

from english_typing_trainer.services.audio_playback import AudioPlaybackService
from english_typing_trainer.services.recording_service import RecordingService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify local audio devices without retaining recordings."
    )
    parser.add_argument("--playback", action="store_true")
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args(argv)
    app = QCoreApplication.instance() or QCoreApplication([])
    temporary_root = Path(tempfile.mkdtemp(prefix="english-studio-audio-check-"))
    report: dict[str, object] = {
        "audio_input_count": len(QMediaDevices.audioInputs()),
        "audio_output_count": len(QMediaDevices.audioOutputs()),
        "playback_requested": args.playback,
        "recording_requested": args.record,
    }
    try:
        if args.playback:
            tone_path = temporary_root / "device-check.wav"
            _write_quiet_tone(tone_path)
            playback = AudioPlaybackService()
            states: list[str] = []
            failures: list[str] = []
            playback.state_changed.connect(states.append)
            playback.playback_failed.connect(failures.append)
            playback.toggle(tone_path)
            _wait(app, 1800)
            playback.stop()
            report["playback_started"] = "playing" in states
            report["playback_error"] = failures[-1] if failures else None

        if args.record:
            recording = RecordingService(temporary_root / "recordings")
            failures: list[str] = []
            recording.failed.connect(failures.append)
            started_path = recording.start()
            _wait(app, 800)
            completed_path = recording.stop() if started_path else None
            _wait(app, 600)
            report["recording_created"] = bool(
                completed_path
                and completed_path.is_file()
                and completed_path.stat().st_size > 0
            )
            report["recording_error"] = failures[-1] if failures else None
            if completed_path:
                completed_path.unlink(missing_ok=True)

        requested_results = []
        if args.playback:
            requested_results.append(bool(report.get("playback_started")))
        if args.record:
            requested_results.append(bool(report.get("recording_created")))
        report["passed"] = all(requested_results) if requested_results else True
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["passed"] else 1
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)


def _wait(_app: QCoreApplication, milliseconds: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


def _write_quiet_tone(path: Path) -> None:
    sample_rate = 16_000
    duration_seconds = 0.25
    amplitude = 0.08 * 32767
    frames = b"".join(
        struct.pack(
            "<h",
            int(amplitude * math.sin(2 * math.pi * 440 * index / sample_rate)),
        )
        for index in range(int(sample_rate * duration_seconds))
    )
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(sample_rate)
        stream.writeframes(frames)


if __name__ == "__main__":
    raise SystemExit(main())
