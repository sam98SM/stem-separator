# Stem Separator

Personal music stem-separation project based on the Ultimate Vocal Remover GUI (UVR) codebase.

## Goal

Build a local workflow that can take a mixed song and progressively produce useful live/performance stems such as:

- vocals
- bass
- guitar
- keys / piano
- drums
- percussion
- sequences / synths / FX
- drum sub-stems (kick, snare, hi-hat, toms, cymbals)
- a generated click track aligned to the detected tempo/grid

## Repository policy

This repository tracks source code and text configuration only. Downloaded model weights, user audio, generated stems, caches, local secrets, and other large runtime artifacts are intentionally excluded from Git.

The uploaded source archive was based on Ultimate Vocal Remover GUI v5.6. The original UVR project and its developers remain credited; this repository is a personal derivative/workspace and is not the official UVR repository.

Upstream: https://github.com/Anjok07/ultimatevocalremovergui

## Current state

Initial import: UVR source/configuration prepared for GitHub hygiene. No source-code behavior has been changed yet.

Next development target: automate a multi-pass separation pipeline for drums + percussion + sequences, then generate a synchronized click track.

## License / third-party notice

The upstream UVR README states that the UVR code is MIT-licensed and requests attribution. The uploaded archive did not contain a standalone LICENSE file, so third-party licensing should be verified against upstream before redistribution. Model weights may have their own terms and are intentionally not committed here.
