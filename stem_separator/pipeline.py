from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional

import librosa
import numpy as np
import soundfile as sf
from audio_separator.separator import Separator


GENERAL_MODEL = "htdemucs_6s.yaml"
DRUM_MODEL = "MDX23C-DrumSep-aufr33-jarredou.ckpt"
BACKING_VOCAL_MODEL = "UVR-BVE-4B_SN-44100-2.pth"


@dataclass
class StemResult:
    name: str
    path: Optional[str]
    status: str
    source: str
    note: str = ""


class MaximumStemPipeline:
    """Best-effort multi-pass separator.

    The pipeline never invents a specialist stem. When no suitable model is
    configured, ambiguous material is preserved in a residual stem and the
    requested child stem is marked unavailable in manifest.json.
    """

    def __init__(
        self,
        output_dir: Path,
        model_dir: Path,
        output_format: str = "WAV",
        guitar_specialist_model: Optional[str] = None,
    ) -> None:
        self.output_dir = output_dir
        self.model_dir = model_dir
        self.output_format = output_format
        self.guitar_specialist_model = guitar_specialist_model
        self.results: Dict[str, StemResult] = {}

    def _separator(self, model: str, out_dir: Path) -> Separator:
        out_dir.mkdir(parents=True, exist_ok=True)
        separator = Separator(
            output_dir=str(out_dir),
            model_file_dir=str(self.model_dir),
            output_format=self.output_format,
            log_level="info",
        )
        separator.load_model(model_filename=model)
        return separator

    def _record(
        self,
        name: str,
        path: Optional[Path],
        status: str,
        source: str,
        note: str = "",
    ) -> None:
        self.results[name] = StemResult(
            name=name,
            path=str(path) if path else None,
            status=status,
            source=source,
            note=note,
        )

    @staticmethod
    def _find_output(files: Iterable[str], token: str) -> Optional[Path]:
        token = token.lower()
        for file in files:
            path = Path(file)
            if token in path.stem.lower():
                return path
        return None

    def separate_general(self, input_audio: Path) -> Dict[str, Path]:
        out = self.output_dir / "01_general"
        separator = self._separator(GENERAL_MODEL, out)
        output_names = {
            "Vocals": "vocals",
            "Drums": "drums",
            "Bass": "bass",
            "Other": "other",
            "Guitar": "guitar",
            "Piano": "piano",
        }
        files = separator.separate(str(input_audio), output_names)

        found: Dict[str, Path] = {}
        for stem in ("vocals", "drums", "bass", "other", "guitar", "piano"):
            path = self._find_output(files, stem)
            if path:
                found[stem] = path
                self._record(stem, path, "ready", GENERAL_MODEL)
            else:
                self._record(
                    stem,
                    None,
                    "missing",
                    GENERAL_MODEL,
                    "The general model did not return this stem.",
                )
        return found

    def split_drums(self, drums: Optional[Path]) -> None:
        targets = ("kick", "snare", "toms", "hihat", "ride", "crash")
        if drums is None:
            for name in targets:
                self._record(name, None, "unavailable", DRUM_MODEL, "No drums stem was produced.")
            return

        out = self.output_dir / "02_drums"
        separator = self._separator(DRUM_MODEL, out)
        files = separator.separate(str(drums))
        matched: set[Path] = set()

        aliases = {
            "kick": ("kick",),
            "snare": ("snare",),
            "toms": ("toms", "tom"),
            "hihat": ("hihat", "hi_hat", "hi-hat", "hh"),
            "ride": ("ride",),
            "crash": ("crash",),
        }

        for name, tokens in aliases.items():
            path = None
            for token in tokens:
                path = self._find_output(files, token)
                if path:
                    break
            if path:
                matched.add(path)
                self._record(name, path, "ready", DRUM_MODEL)
            else:
                self._record(
                    name,
                    None,
                    "unavailable",
                    DRUM_MODEL,
                    "The configured DrumSep checkpoint may combine ride/crash into cymbals.",
                )

        unmatched = [Path(file) for file in files if Path(file) not in matched]
        if unmatched:
            self._record(
                "drum_residual",
                unmatched[0],
                "ready",
                DRUM_MODEL,
                "Unmatched DrumSep output/residual.",
            )
        else:
            self._record("drum_residual", None, "not_needed", DRUM_MODEL)

    def split_vocals(self, vocals: Optional[Path]) -> None:
        if vocals is None:
            for name in ("lead_vocal", "backing_vocals", "vocal_residual"):
                self._record(
                    name,
                    None,
                    "unavailable",
                    BACKING_VOCAL_MODEL,
                    "No vocals stem was produced.",
                )
            return

        out = self.output_dir / "03_vocals"
        separator = self._separator(BACKING_VOCAL_MODEL, out)
        files = separator.separate(str(vocals))

        backing = self._find_output(files, "back")
        if backing:
            self._record("backing_vocals", backing, "ready", BACKING_VOCAL_MODEL)
        else:
            self._record(
                "backing_vocals",
                None,
                "verify_outputs",
                BACKING_VOCAL_MODEL,
                "BVE output names can vary; inspect generated files before assigning this stem.",
            )

        self._record(
            "lead_vocal",
            None,
            "verify_outputs",
            BACKING_VOCAL_MODEL,
            "Main-vocal assignment is not guessed from an ambiguous filename.",
        )

        residual = out / f"vocal_residual{vocals.suffix}"
        shutil.copy2(vocals, residual)
        self._record(
            "vocal_residual",
            residual,
            "ready",
            "general vocals",
            "Original isolated vocal stem preserved.",
        )

    def split_guitar(self, guitar: Optional[Path]) -> None:
        target_names = (
            "lead_guitar",
            "rhythm_guitar",
            "acoustic_guitar",
            "electric_guitar",
        )
        if guitar is None:
            for name in target_names:
                self._record(name, None, "unavailable", "guitar specialist", "No guitar stem was produced.")
            self._record("guitar_residual", None, "unavailable", "general")
            return

        out = self.output_dir / "04_guitars"
        out.mkdir(parents=True, exist_ok=True)

        if self.guitar_specialist_model:
            separator = self._separator(self.guitar_specialist_model, out)
            files = separator.separate(str(guitar))
            token_map = {
                "lead_guitar": ("lead",),
                "rhythm_guitar": ("rhythm",),
                "acoustic_guitar": ("acoustic",),
                "electric_guitar": ("electric",),
            }
            for name, tokens in token_map.items():
                path = None
                for token in tokens:
                    path = self._find_output(files, token)
                    if path:
                        break
                if path:
                    self._record(name, path, "ready", self.guitar_specialist_model)
                else:
                    self._record(
                        name,
                        None,
                        "unavailable",
                        self.guitar_specialist_model,
                        "The specialist model did not expose this named output.",
                    )
        else:
            for name in target_names:
                self._record(
                    name,
                    None,
                    "needs_specialist_model",
                    "none",
                    "Configure --guitar-specialist-model with a checkpoint trained for this target. "
                    "Lead/rhythm is intentionally not faked with EQ, panning, or center extraction.",
                )

        residual = out / f"guitar_residual{guitar.suffix}"
        shutil.copy2(guitar, residual)
        self._record(
            "guitar_residual",
            residual,
            "ready",
            GENERAL_MODEL,
            "Original isolated guitar stem preserved.",
        )

    def preserve_residual_targets(self, general: Dict[str, Path]) -> None:
        mapping = {
            "percussion": general.get("other"),
            "sequence_residual": general.get("other"),
            "keys_residual": general.get("piano"),
            "orchestral_residual": general.get("other"),
        }
        out = self.output_dir / "05_residuals"
        out.mkdir(parents=True, exist_ok=True)

        for name, source in mapping.items():
            if source:
                target = out / f"{name}{source.suffix}"
                shutil.copy2(source, target)
                self._record(
                    name,
                    target,
                    "residual_only",
                    "general residual",
                    "Preserved for a future specialist pass; not claimed as a clean isolated stem.",
                )
            else:
                self._record(name, None, "unavailable", "general residual")

        for name in (
            "shaker",
            "tambourine",
            "claps",
            "percussion_residual",
            "organ",
            "synth",
            "strings",
            "brass",
            "woodwinds",
            "pads",
            "electronic_loops",
            "fx",
        ):
            if name not in self.results:
                self._record(
                    name,
                    None,
                    "needs_specialist_model",
                    "none",
                    "No reliable generic checkpoint is configured for this child stem yet.",
                )

    def generate_click(self, input_audio: Path) -> None:
        out = self.output_dir / "06_generated"
        out.mkdir(parents=True, exist_ok=True)

        y, sample_rate = librosa.load(str(input_audio), sr=None, mono=True)
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sample_rate)
        bpm = float(np.asarray(tempo).reshape(-1)[0])
        beat_times = librosa.frames_to_time(beat_frames, sr=sample_rate)
        click = librosa.click(times=beat_times, sr=sample_rate, length=len(y))

        click_path = out / "click_track.wav"
        sf.write(click_path, click, sample_rate)

        tempo_map_path = out / "tempo_map.json"
        tempo_map_path.write_text(
            json.dumps(
                {
                    "estimated_bpm": bpm,
                    "sample_rate": sample_rate,
                    "beat_times_seconds": [round(float(value), 6) for value in beat_times],
                    "warning": "Automatic beat tracking can drift on rubato/live recordings; verify before performance.",
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        self._record("click_track", click_path, "ready", "librosa beat tracker")
        self._record("tempo_map", tempo_map_path, "ready", "librosa beat tracker")

    def write_manifest(self) -> Path:
        path = self.output_dir / "manifest.json"
        path.write_text(
            json.dumps(
                {
                    "mode": "maximum_stems",
                    "results": {
                        name: asdict(result)
                        for name, result in sorted(self.results.items())
                    },
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return path

    def run(self, input_audio: Path) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        general = self.separate_general(input_audio)
        self.split_drums(general.get("drums"))
        self.split_vocals(general.get("vocals"))
        self.split_guitar(general.get("guitar"))
        self.preserve_residual_targets(general)
        self.generate_click(input_audio)
        return self.write_manifest()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Maximum-stems personal music separation pipeline"
    )
    parser.add_argument("input", type=Path, help="Input WAV/FLAC/MP3/etc.")
    parser.add_argument("-o", "--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--model-dir", type=Path, default=Path("models"))
    parser.add_argument("--output-format", default="WAV")
    parser.add_argument(
        "--guitar-specialist-model",
        default=None,
        help="Optional audio-separator-compatible model trained for guitar sub-stems.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    pipeline = MaximumStemPipeline(
        output_dir=args.output_dir,
        model_dir=args.model_dir,
        output_format=args.output_format,
        guitar_specialist_model=args.guitar_specialist_model,
    )
    manifest = pipeline.run(args.input)
    print(f"Done. Manifest: {manifest}")


if __name__ == "__main__":
    main()
