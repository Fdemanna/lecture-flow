# 🎓 LectureFlow

> **Turn raw video & audio lectures into structured, interactive Notion study guides — 100% locally powered by Apple Silicon (Metal) and NVIDIA CUDA.**

[![Python Version](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Windows-lightgrey.svg)]()
[![Transcription Engine](https://img.shields.io/badge/Transcription-MLX%20Whisper%20%7C%20Faster--Whisper-orange.svg)]()
[![LLM Engine](https://img.shields.io/badge/LLM-Qwen%202.5%20(Ollama)-green.svg)]()
[![Integration](https://img.shields.io/badge/Integration-Notion%20API-black.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 📌 Architecture Overview

LectureFlow operates in a fully offline, privacy-first 3-stage pipeline before pushing to Notion:

1. **[Audio Extraction]**: Fast extraction to PCM WAV 16kHz using FFmpeg.
2. **[Local Transcription]**: High-speed, high-accuracy transcription using **MLX Metal** on macOS or **Faster-Whisper (CUDA/CPU)** on Windows/Linux.
3. **[Map-Reduce Synthesis & Audit]**: Summarization and Anti-Hallucination Audit powered by **Qwen 2.5 (via Ollama)**.
4. **[Notion API Export]**: Automated assembly of native blocks (TOCs, Callouts, Toggle lists, Code blocks) into your connected Notion database.

## ✨ Key Features

- **100% Private & Local**: Zero cloud fees, zero OpenAI API keys needed. Your lectures stay on your machine.
- **Zero-Terminal Execution**: One-click launch via native scripts (`.command` for macOS, `.vbs` for Windows).
- **Anti-Hallucination Audit**: Integrated technical auditing with confidence scoring to ensure notes accurately reflect the source material.
- **Native Notion Integration**: Generates dynamic Tables of Contents, syntax-highlighted code blocks, context-aware callouts, and interactive `to_do` checklists directly in Notion.
- **Robust Multiplatform Resilience**: 
  - 15-minute anti-zombie timeouts.
  - Path Traversal mitigation using `os.path.realpath`.
  - Notion API batch chunking (100 blocks per request).

## 🚀 Quick Start & Installation

### Prerequisites
- **Python 3.9+** installed.
- **FFmpeg** installed and added to your system PATH.
- **Ollama** installed with the `qwen2.5:7b` model pulled (`ollama run qwen2.5:7b`).

### Setup on macOS
1. Open a terminal in the project directory and run: `bash scripts/setup_mac.sh` (Only required the first time).
2. Configure your Notion variables (see below).
3. **Run:** Double-click `Iniciar_Mac.command` to launch the app.

### Setup on Windows
1. Double-click `scripts\setup_windows.bat` (Only required the first time).
2. Configure your Notion variables (see below).
3. **Run:** Double-click `Iniciar_Windows.vbs` to launch the app silently in the background.

### 🔑 Notion Integration Guide
1. Go to [Notion Integrations](https://www.notion.so/my-integrations) and create a new **Internal Integration**.
2. Copy the **Internal Integration Secret**.
3. Go to the Notion database (full page) where you want the notes to be saved. Click the three dots `...` in the top right > **Connect to** > select your integration.
4. Copy the **Database ID** from the URL (e.g., `https://www.notion.so/workspace/1234567890abcdef?v=...` -> `1234567890abcdef`).
5. Create a `.env` file based on `.env.example`:
   ```env
   NOTION_TOKEN=your_internal_integration_secret
   NOTION_DATABASE_ID=your_database_id
   ```

## 🛠️ Tech Stack

- **UI Framework:** Streamlit
- **Transcription:** MLX Whisper (macOS) / Faster-Whisper (Windows/Linux)
- **Local LLM Engine:** Ollama (Qwen 2.5)
- **Exporting:** Notion API v1
- **Audio Processing:** FFmpeg

---
*Built for Technical Students and Developers.*
