# 🔍 Local Image Matcher & Duplicate Cleaner

A 100% offline, privacy-first local application to detect exact and visual duplicate images, intelligently preserve originals, and safely clean up disk space. Built with **Streamlit**, **SHA-256**, **ImageHash**, and optional **FAISS + CLIP** neural search.

---

## ✨ Features

- **🔒 100% Offline & Private**: Zero external network requests. All images are processed locally on your machine.
- **⚡ Dual Matching Engine**:
  - **Exact Byte Matching**: Uses SHA-256 cryptographic hashing for 100% byte-for-byte identical duplicates.
  - **Perceptual Hash Matching (pHash)**: Catches images that have been resized, re-compressed, or renamed. Adjustable strictness slider.
- **⭐ Smart Original Auto-Detection**:
  - Automatically identifies the true original by favoring clean filenames (excluding `"copy"`, `"(1)"`, etc.), higher resolutions, and earlier creation dates.
  - Flexibility to manually pick which image to keep as the original for any group.
- **🗑️ Safe & Flexible Deletion**:
  - **Safe Mode (Default)**: Moves duplicate files into a `_duplicates_backup/` subfolder so you can restore them anytime.
  - **Permanent Deletion**: Removes duplicates directly from disk when you're confident.
  - **Batch Cleanup**: One-click button to delete all duplicates across all groups while preserving originals.
  - **Per-Group Cleanup**: Review and delete individual duplicate groups at your own pace.
- **📥 Upload Mode with ZIP Export**: Drag-and-drop or upload multiple images directly in your browser and download a clean, deduplicated ZIP archive.
- **🧠 Semantic Neural Search (Optional)**: Includes `build_index.py` using `clip-ViT-B-32` and `FAISS` for semantic vector embeddings.

---

## 📁 Repository Structure

```text
local_image_reco/
├── app.py                  # Main Streamlit web application
├── build_index.py          # CLI script to build FAISS semantic embeddings index
├── images/                 # Sample images dataset for testing duplicate detection
├── requirements.txt        # Python package dependencies
├── .gitignore              # Standard ignore rules (venv, caches, OS files, backups)
├── .streamlit/
│   └── config.toml         # Streamlit server & telemetry configuration
└── README.md               # Project documentation and guide
```

---

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd local_image_reco
```

### 2. Create and Activate a Virtual Environment

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate

# Windows (Command Prompt)
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Run the Streamlit App

```bash
streamlit run app.py
```

Open your browser at `http://localhost:8501`.

---

## 🛠️ Optional: Build FAISS Neural Index

To generate CLIP embeddings and a FAISS index for semantic image searching:

```bash
python build_index.py
```

This will scan `images/`, filter out perceptual duplicates, generate `clip-ViT-B-32` embeddings, and produce `image_index.faiss` and `metadata.json`.

--

## 📄 License

MIT License. Free for personal and commercial use.
