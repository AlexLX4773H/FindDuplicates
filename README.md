# Manga & Doujinshi Duplicate & Partial Chapter Finder

<p align="center">
  <img src="assets/banner.png" alt="Manga & Doujinshi Duplicate Finder Banner" width="800">
</p>

<p align="center">
  <a href="#"><img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20CasaOS-blue?style=flat-square" alt="Platform"></a>
  <a href="#"><img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker" alt="Docker"></a>
  <a href="#"><img src="https://img.shields.io/badge/CasaOS-Compatible-00D1B2?style=flat-square" alt="CasaOS"></a>
  <a href="#"><img src="https://img.shields.io/badge/Python-3.12-yellow?style=flat-square&logo=python" alt="Python"></a>
  <a href="#"><img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License"></a>
</p>

An intelligent, multi-job deduplication, verification, and collection management engine for digital **Manga, Manhwa, Webtoon, and Doujinshi (H)** libraries across single or multiple directory structures (Windows local drives, SMB network shares, and Linux/CasaOS storage mounts).

Includes a modern **Interactive Web Dashboard** inside Docker and CasaOS allowing you to view visual duplicate reports, compare releases side-by-side, and **click-to-confirm what stays, what moves to archive, or what gets deleted**.

---

## 🌟 Key Features

- 🖥️ **Interactive Web Dashboard (Docker & CasaOS)**:
  - Fast, responsive web UI served on port `8765`.
  - Compare duplicate releases side-by-side with scanlator tags, page counts, resolution badges, and AI retention recommendations.
  - One-click actions per release: **Keep**, **Move to Archive**, or **Delete**.
  - **Batch Actions**: "Auto-Select Best" automatically marks the highest quality copy to stay and duplicates to be archived.
  - **Safe Execution Engine**: Includes Dry-Run mode by default and full audit logging.
- 📚 **Targeted Manga Deduplication (Intra-Series)**:
  - Scans within each manga title to detect duplicate chapters, competing scanlation releases, and split fractional sub-chapters (e.g. `Ch 10.1`, `Ch 10.2` coexisting with `Ch 10`).
  - Cleans download scraper hex hashes (`Chapter 10_48a245` $\rightarrow$ `Chapter 10`).
- 🌸 **Global Doujinshi Deduplication (Cross-Directory)**:
  - Scans across all staging roots (`000 NEW`, `TempD`, `TempT`, `ORIGINAL`, `Old`, archives).
  - Automatically collapses leaf chapter subfolders (`_chapter`, `Chapter`, `<artist>_chapter`) into their parent doujinshi works.
  - Matches by Circle/Artist, Event, Japanese/English dual titles, and tags (`[Decensored]`, `[Digital]`).
- 👁️ **Visual Perceptual Hashing (dHash / pHash)**:
  - Compares Page 1/Cover, Mid-page, and Last-page hashes to verify identical artwork across different scanlations or translated titles.
- 📂 **Offline Tree Dump Parser**:
  - Ingests raw text files generated via `tree /a` or `tree /f` (like `sample_data/Manga/manga.txt` or `sample_data/H/h_new_b2.txt`) for instant analysis without mounting physical storage.
- 🐳 **CasaOS & Docker Native**:
  - Pre-configured `x-casaos` integration in `docker-compose.yml` for 1-click install in CasaOS App Store.
  - Custom vector icons, app badges, and store banners in `assets/`.

---

## 📁 Repository Structure

```text
Find Duplicates/
├── .gitignore                      # Configured to ignore sample_data/ and caches
├── README.md                       # Project documentation
├── PLAN.md                         # Detailed architecture and implementation plan
├── Dockerfile                      # Multi-arch (amd64/arm64) Docker container
├── docker-compose.yml              # CasaOS application template (with x-casaos schema)
├── docker-compose.windows.yml      # Windows Docker Desktop profile
├── requirements.txt                # Python dependencies
├── config.example.yaml             # Template configuration file
├── assets/                         # CasaOS icons, banners, and vector sprites
│   ├── icon.svg                    # Scalable vector icon
│   ├── icon.png                    # 512x512 CasaOS App Store icon
│   ├── banner.svg                  # Scalable vector banner
│   └── banner.png                  # 1024x500 CasaOS App Store banner
└── src/
    ├── __init__.py
    ├── config.py                   # Path normalization & YAML loader
    ├── models.py                   # Data classes (ChapterItem, DoujinshiWork, DuplicateGroup)
    ├── parser.py                   # Heuristic tokenizers & tree dump parsers
    ├── scanner.py                  # Real filesystem & archive walker (.cbz, .zip)
    ├── detector.py                 # Intra-series & global cross-directory duplicate engines
    ├── image_hasher.py             # Visual perceptual hashing & page extractors
    ├── actions.py                  # Safe file execution engine (Keep, Move, Delete, Dry-Run)
    ├── reporter.py                 # Terminal tables, JSON, CSV & standalone HTML dashboards
    ├── main.py                     # Unified CLI & server runner
    └── web/
        ├── app.py                  # FastAPI backend server
        └── templates/
            └── index.html          # Interactive dark-mode dashboard
```

---

## 🚀 Quick Start

### 1. Interactive Web Dashboard (Local or Docker)

#### Run locally:
```bash
pip install -r requirements.txt
python -m src.main server --port 8765
```
Open **`http://localhost:8765`** in your browser.

#### Run with Docker / CasaOS:
```bash
# Windows Docker Desktop
docker compose -f docker-compose.windows.yml up --build

# Linux / CasaOS
docker compose up -d
```
Access the dashboard at `http://<your-server-ip>:8765`.

---

### 2. Specialized CLI Jobs

#### Manga Intra-Series Scanner:
```bash
# Name-based fast scan
python -m src.main manga --by name --scan "G:\LX\Manga"

# Image perceptual hash verification
python -m src.main manga --by image --scan "G:\LX\Manga"
```

#### Doujinshi Global Cross-Directory Scanner:
```bash
# Name-based global scan
python -m src.main doujinshi --by name --scan "G:\LX\H" --scan "G:\LX\H_Staging"

# Image cover perceptual hash clustering
python -m src.main doujinshi --by image --scan "G:\LX\H"
```

#### Offline Tree Dump Ingestion:
Instantly parse and detect duplicates from text files generated via `tree /a` or `tree /f`:
```bash
# Analyze manga tree dump
python -m src.main parse-tree --file "sample_data/Manga/manga.txt"

# Analyze doujinshi tree dump
python -m src.main parse-tree --file "sample_data/H/h_new_b2.txt"
```

Reports are automatically generated and saved to `./reports` in HTML, JSON, and CSV formats.

---

## 📖 Architecture & Heuristics

See [`PLAN.md`](PLAN.md) for full architectural documentation, regex heuristics, and perceptual hash algorithms.
