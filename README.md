# Stem Separator

Personal maximum-stem music separation project built around the Ultimate Vocal Remover ecosystem.

## Target

One song in, as many useful stems as can be separated reliably out.

### Main stems

- vocals
- drums
- bass
- guitar
- piano / keys
- other

### Vocal sub-stems

- lead vocal
- backing vocals
- vocal residual

### Drum sub-stems

- kick
- snare
- toms
- hi-hat
- ride
- crash
- drum residual

### Percussion targets

- percussion
- shaker
- tambourine
- claps
- percussion residual

### Guitar targets

- **lead guitar**
- **rhythm guitar**
- acoustic guitar
- electric guitar
- guitar residual

Lead/rhythm is treated as a specialist separation problem. The pipeline deliberately does not fake it with EQ, panning, or center extraction. A compatible specialist checkpoint can be supplied with `--guitar-specialist-model`; otherwise the isolated guitar stem is preserved as `guitar_residual` and the manifest marks lead/rhythm as needing a specialist model.

### Keys / orchestral / sequences targets

- piano
- organ
- synth
- strings
- brass
- woodwinds
- pads
- electronic loops
- FX
- residuals for material that cannot yet be assigned reliably

### Generated

- click track WAV
- estimated BPM
- beat-time tempo map JSON

## Current automated pipeline

1. `htdemucs_6s.yaml` -> vocals / drums / bass / guitar / piano / other
2. `MDX23C-DrumSep-aufr33-jarredou.ckpt` -> detailed drum sub-stems
3. `UVR-BVE-4B_SN-44100-2.pth` -> backing-vocal specialist pass
4. optional guitar-specialist pass -> lead / rhythm / acoustic / electric when a compatible checkpoint is provided
5. preserve residual audio instead of inventing low-confidence stems
6. beat tracking -> `click_track.wav` + `tempo_map.json`
7. write `manifest.json` with the real status/source of every requested stem

## Install

Python 3.10+ is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell, activate with:

```powershell
.venv\Scripts\Activate.ps1
```

## Run Maximum Stems

```bash
python -m stem_separator.pipeline song.wav -o outputs/song
```

Models are downloaded/kept in `models/` and are ignored by Git.

With a compatible guitar specialist model:

```bash
python -m stem_separator.pipeline song.wav -o outputs/song \
  --guitar-specialist-model YOUR_GUITAR_MODEL.ckpt
```

## Output truthfulness

`manifest.json` is authoritative. A child stem can be `ready`, `residual_only`, `needs_specialist_model`, `verify_outputs`, or `unavailable`.

The project never claims that every studio multitrack can be reconstructed from a stereo master. When separation is ambiguous, the audio is preserved in a residual instead of silently producing a misleading stem.

## Repository policy

Downloaded model weights, user audio, generated stems, caches, local secrets, and other large runtime artifacts are intentionally excluded from Git.

The project references Ultimate Vocal Remover GUI as upstream. UVR and model authors retain their respective credits and licenses.

Upstream UVR: https://github.com/Anjok07/ultimatevocalremovergui
