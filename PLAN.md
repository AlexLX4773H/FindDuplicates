# Manga & Doujinshi Duplicate & Partial Chapter Finder
## Architecture, Design & Implementation Plan

---

## 1. Project Overview & Objectives

Managing large local or network manga and doujinshi libraries often leads to duplicate files and fragmented collections. Duplications occur across multiple directories, different scanlation team releases, different naming schemes, and partial chapter releases (e.g., fractional chapters `Ch. 10.1`, `Ch. 10.2` versus a consolidated `Ch. 10`, or incomplete page archives).

### Core Objectives:
1. **Directory Traversal**: Recursively scan one or multiple user-specified root folders on Windows (local drives, SMB shares) or Linux (Ubuntu Server, CasaOS storage mounts).
2. **Duplicate Chapter Detection**:
   - Detect identical chapter numbers under the same manga/doujinshi title.
   - Recognize different scanlation groups translating the same chapter.
   - Distinguish between loose image folders, `.cbz`, `.zip`, `.cbr`, and `.rar` archives.
3. **Partial Chapter Detection**:
   - Detect fractional releases (e.g., `Ch. 5.1`, `Ch. 5.5`, `Part 1`, `Part 2`) where a full chapter or overlapping sub-chapters exist.
   - Detect incomplete chapters based on comparative page counts or suspicious file size drops.
   - Identify chapter tags such as `[Incomplete]`, `[Sample]`, `[Preview]`, `[Missing Pages]`.
4. **Cross-Platform Path Abstraction**:
   - Seamlessly handle Windows drive paths (`G:\LX\Manga\...`, `\\NAS\Share\...`) and POSIX paths (`/DATA/Media/Manga/...`).
   - Support path translation for containerized environments.
5. **Docker & CasaOS Native Support**:
   - Provide a lightweight, multi-arch Docker image (`amd64` and `arm64`).
   - Provide CasaOS-ready `docker-compose.yml` with `x-casaos` app metadata, volume mounts, and Web UI/CLI execution.
   - Include custom CasaOS application icons, banners, and sprites.

---

## 2. Directory Structure & Naming Conventions

The application expects or adapts to the following primary structures:

### Structure A: Folder of loose images
```text
Root_Directory/
└── <Manga Name>/
    ├── Chapter 01/
    │   ├── 001.jpg
    │   ├── 002.jpg
    │   └── ...
    ├── Chapter 02/
    │   └── ...
    └── Chapter 02.5 [Extra]/
        └── ...
```

### Structure B: Archive files (.cbz / .zip / .cbr)
```text
Root_Directory/
└── <Manga Name>/
    ├── [Group] Manga Name - c001.cbz
    ├── [Group] Manga Name - c002.cbz
    └── [Group B] Manga Name - Ch. 002 [v2].zip
```

### Structure C: Multi-Root / Multi-Drive Setup (e.g., CasaOS merge or secondary drive)
```text
Path 1: /DATA/Media/Manga/Berserk/Chapter 10/
Path 2: /DATA/Secondary/Manga/Berserk/Chapter 010 [EvilGenius]/
Path 3: /DATA/Media/Doujinshi/[Circle (Artist)] Title/
```

> **Note**: Specific directory formats provided by the user in future steps will be integrated via pluggable naming parsers.

---

## 3. Detection Engine & Heuristics

The detection engine operates in four stages:

```
+--------------------+      +--------------------+      +--------------------+      +--------------------+
|  1. File Discovery | ---> |  2. Title & Token  | ---> |  3. Heuristic &    | ---> | 4. Report & Action |
|  & Normalization   |      |     Extraction     |      |  Content Analysis  |      |     Generation     |
+--------------------+      +--------------------+      +--------------------+      +--------------------+
```

### 3.1 Normalization & Tokenization
- **Title Sanitization**: Strips scanlation group tags (`[...]`), resolution tags (`[1080p]`, `[x265]`), language tags (`[ENG]`, `[JAP]`), and release flags (`[v2]`, `[HQ]`).
- **Chapter Number Extraction**:
  - Handles integer chapters: `Ch. 1`, `c001`, `Chapter 12`.
  - Handles fractional / decimal chapters: `Ch. 12.5`, `12.1`, `Chapter 03.b`.
  - Handles chapter ranges: `Ch. 01-03`, `Chapters 10 to 15`.
  - Handles specials: `Prologue`, `Omake`, `Extra`, `Epilogue`, `Volume 01 Omake`.
- **Doujinshi Parsing**:
  - Circle/Artist pattern: `[Circle (Artist)] Title (Event/Convention) [Language]`.

### 3.2 Duplicate Classification Matrix

| Category | Description | Detection Rule | Action Recommendation |
| :--- | :--- | :--- | :--- |
| **Exact Duplicate** | Same series, same chapter number, identical or near-identical page counts. | `Series_A == Series_B` AND `Chapter_Num_A == Chapter_Num_B` AND `PageCount_Delta == 0` | Mark for safe deduplication (keep highest quality/resolution). |
| **Alternative Scanlation** | Same series & chapter, different scanlation team. | `Series_A == Series_B` AND `Chapter_Num_A == Chapter_Num_B` AND `Group_A != Group_B` | Highlight for user preference (show page counts, resolutions, file sizes). |
| **Fractional / Partial** | Sub-chapters vs. full chapter (e.g., `Ch 10.1` + `Ch 10.2` when `Ch 10` is present). | `floor(Ch_A) == floor(Ch_B)` with decimal components. | Flag as potential redundant split or missing segment. |
| **Truncated / Incomplete** | Chapter with significantly fewer pages than companion release (e.g., 6 pages vs 24 pages). | Same chapter with `PageCount < 0.6 * MaxPageCount` or `[Incomplete]` keyword in folder name. | Flag as defective / sample / partial. |
| **Duplicate Across Paths** | Same manga located in two different monitored directories (e.g., Download staging vs Archive). | Cross-directory match of Series + Chapter index. | Suggest consolidation. |

### 3.3 Optional Content Verification
- Quick page count check (reading image count in directory or archive zip header without full extraction).
- Perceptual image hashing (pHash) on first and last pages to definitively verify whether two chapters with differing names contain the same artwork.

---

## 4. Architecture & Module Breakdown

```text
Find Duplicates/
├── .gitignore
├── README.md
├── PLAN.md
├── Dockerfile                      # Multi-arch (amd64 / arm64) image
├── docker-compose.yml              # CasaOS application definition
├── docker-compose.windows.yml      # Windows Docker Desktop profile
├── config.example.yaml             # Scan paths & detection rules configuration
├── assets/                         # CasaOS icons, banners, and sprites
│   ├── icon.svg                    # Vector app icon
│   ├── icon.png                    # 512x512 app icon
│   ├── icon-256.png                # 256x256 app icon
│   ├── icon-128.png                # 128x128 app icon
│   ├── banner.svg                  # Banner vector
│   └── banner.png                  # 1024x500 CasaOS app store banner
└── src/
    ├── __init__.py
    ├── config.py                   # Path config & environment parser
    ├── scanner.py                  # Multi-threaded filesystem & archive walker
    ├── parser.py                   # Regex tokenizers for manga/doujinshi naming
    ├── detector.py                 # Duplicate & partial chapter analysis logic
    ├── comparator.py               # Page counts, archive inspectors & image hashers
    ├── reporter.py                 # Terminal tables, JSON, CSV & HTML reports
    └── main.py                     # Entry point (CLI & Web API modes)
```

---

## 5. Path Management: Windows vs. Linux (CasaOS)

To ensure scripts run smoothly on both Windows workstations and Linux / CasaOS servers:

1. **Path Abstraction**:
   - Uses Python's `pathlib.Path` with automatic slash conversion.
   - Accepts Windows drive letters (`G:\LX\Manga`), UNC network shares (`\\192.168.1.100\manga`), and POSIX paths (`/DATA/Media/Manga`).
2. **Docker Path Mapping**:
   - Host paths are mapped to standard container mount points:
     - `/data/media1`
     - `/data/media2`
   - A path translation dictionary maps internal container paths back to host paths in reports, ensuring clickable or actionable links point to the actual storage location.
3. **Configuration Driven**:
   - Scan targets can be specified via `config.yaml`, CLI flags (`--scan "D:\Manga" --scan "E:\Doujinshi"`), or Docker environment variables (`SCAN_PATHS=/data/manga1,/data/manga2`).

---

## 6. Docker & CasaOS Integration

### CasaOS Features:
- **`x-casaos` Extension**: Integrated metadata enabling the container to appear in the CasaOS Web UI dashboard with custom icon, description, category, and storage mount shortcuts.
- **Volume Mounts**: Pre-configured templates mapping CasaOS storage pools (`/DATA/Media/...`) into the container.
- **Resource Efficiency**: Based on `python:3.12-alpine` or `python:3.12-slim` with minimal memory footprint (< 100MB RAM during scanning).

---

## 7. Icons & Visual Assets Specification

CasaOS uses specific visual dimensions for custom apps and App Store entries:

| Asset | File | Dimensions | Format | Usage |
| :--- | :--- | :--- | :--- | :--- |
| **App Icon** | `assets/icon.png` | 512 x 512 px | PNG (RGBA) | CasaOS Dashboard app icon |
| **Vector Icon** | `assets/icon.svg` | Scalable Vector | SVG | High-DPI displays & documentation |
| **Store Banner** | `assets/banner.png` | 1024 x 500 px | PNG | CasaOS App Store header / card |
| **Vector Banner**| `assets/banner.svg`| 1024 x 500 px | SVG | Scalable banner |
| **Sprite Sizes** | `assets/icon-*.png`| 256, 128, 64 px | PNG | Notification & dashboard badges |

**Design Motif**:
- Dual manga pages / open book symbolizing manga and doujinshi collections.
- Twin overlapping layers representing duplicate detection.
- Modern magnifying lens / scan reticle with gradient colors (coral pink / electric violet / cyan) matching CasaOS design language.

---

## 8. Implementation Roadmap

- [x] **Phase 1: Foundation & Planning** *(Current)*
  - Initialize public Git repository with standard `.gitignore` (ignoring `sample_data/`).
  - Author detailed architecture and plan specification (`PLAN.md`).
  - Create CasaOS icons, banners, and vector sprites in `assets/`.
  - Provide `docker-compose.yml` with `x-casaos` integration.
- [ ] **Phase 2: Data Structure Alignment**
  - Ingest the user's specific directory and file structure examples.
  - Implement parsing heuristics for manga and doujinshi chapter formats.
- [ ] **Phase 3: Core Detection Engine**
  - Implement `scanner.py`, `parser.py`, and `detector.py`.
  - Handle archive files (`.cbz`, `.zip`, `.cbr`, `.rar`) and loose folders.
  - Implement partial chapter detection algorithms.
- [ ] **Phase 4: Output, Reporting & Containerization**
  - Interactive CLI output with rich progress bars and summary tables.
  - Export reports to JSON, CSV, and HTML.
  - Build and verify Docker container execution across Windows and Linux (CasaOS).
