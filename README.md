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

An intelligent Python scanner and deduplication engine designed to traverse manga and doujinshi libraries across single or multiple directory structures (Windows local drives, SMB network shares, and Linux/CasaOS storage mounts).

It accurately identifies **duplicate chapters**, **alternative scanlation releases**, and **partial/fractional releases** (e.g. `Ch 10.1`, missing page counts, or incomplete samples).

---

## 🌟 Key Features

- 🔍 **Duplicate Chapter Detection**: Groups chapters by series name and chapter number across separate directories and storage pools.
- 🧩 **Partial & Fractional Chapter Detection**:
  - Highlights split releases (e.g. `Ch. 12.1`, `Ch. 12.2`) when a full `Ch. 12` already exists or vice-versa.
  - Flags incomplete chapters based on comparative page counts (e.g. sample releases with < 60% of peer page counts).
  - Detects keywords such as `[Incomplete]`, `[Sample]`, `[Preview]`, `[Missing]`.
- 🗂️ **Universal Archive & Folder Support**: Inspects both loose image folders (`.jpg`, `.png`, `.webp`, `.avif`) and comic archives (`.cbz`, `.zip`) with zero-extraction header reading.
- 💻 **Cross-Platform Path Support**:
  - Windows paths: `G:\LX\Manga`, `\\192.168.1.100\Storage\Manga`.
  - Linux & CasaOS paths: `/DATA/Media/Manga`, `/DATA/Media/Doujinshi`.
- 🐳 **CasaOS & Docker Native**:
  - Includes `x-casaos` integration in `docker-compose.yml` for 1-click CasaOS App Store installation.
  - Includes custom icons and banners in `assets/`.
- 📊 **Rich Reporting**: Outputs summary results directly to the terminal, and exports structured JSON, CSV, and interactive HTML dashboards.

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
│   ├── icon-256.png                # 256x256 sprite
│   ├── icon-128.png                # 128x128 sprite
│   ├── icon-64.png                 # 64x64 sprite
│   ├── banner.svg                  # Scalable vector banner
│   └── banner.png                  # 1024x500 CasaOS App Store banner
├── scripts/
│   └── generate_assets.py          # Asset & sprite generation utility
└── src/
    ├── __init__.py
    ├── config.py                   # Path normalization & YAML loader
    ├── scanner.py                  # Multi-threaded filesystem & archive walker
    ├── parser.py                   # Regex tokenizers for manga/doujinshi naming
    ├── detector.py                 # Duplicate & partial chapter analysis logic
    ├── reporter.py                 # Terminal tables, JSON, CSV & HTML reports
    └── main.py                     # CLI entrypoint
```

---

## 🚀 Quick Start

### 1. Local CLI Execution (Windows or Linux)

#### Install Dependencies:
```bash
pip install -r requirements.txt
```

#### Scan via Command Line:
```bash
# Windows
python -m src.main --scan "G:\LX\Manga" --scan "D:\Manga Collections"

# Linux / CasaOS
python -m src.main --scan "/DATA/Media/Manga" --scan "/DATA/Media/Doujinshi"
```

#### Scan using `config.yaml`:
```bash
cp config.example.yaml config.yaml
# Edit config.yaml with your scan paths, then run:
python -m src.main --config config.yaml
```

---

## 🐳 Docker & CasaOS Deployment

### Option A: CasaOS on Ubuntu Server

1. Open your CasaOS Dashboard.
2. Go to **App Store** -> **Custom Install** -> Click **Import** (top right).
3. Paste the contents of [`docker-compose.yml`](docker-compose.yml) or import this repo.
4. Set your volume paths to match your CasaOS storage drives (e.g. `/DATA/Media/Manga`).
5. Click **Submit** to run.

### Option B: Windows Docker Desktop

Run with the Windows-specific compose file:
```powershell
docker compose -f docker-compose.windows.yml up --build
```

---

## 🎨 CasaOS Icons & Sprites

The `assets/` directory provides app store ready graphics conforming to CasaOS design guidelines:
- `assets/icon.png`: 512x512 high-resolution app icon.
- `assets/icon.svg`: Vector icon.
- `assets/banner.png`: 1024x500 preview banner for the CasaOS app card.

---

## 📖 Architecture & Next Steps

See [`PLAN.md`](PLAN.md) for full architectural documentation, heuristic matrices, and roadmap phases.
