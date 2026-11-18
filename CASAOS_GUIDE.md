# CasaOS 1-Click Import & Setup Guide

This guide walks you through importing **FindDuplicates** into CasaOS with your exact library paths pre-configured.

---

## 🗂️ Pre-Configured Storage Paths

Your library storage paths have been mapped inside [`docker-compose.yml`](docker-compose.yml):

| Content Type | Host Storage Path | Container Path | Purpose |
| :--- | :--- | :--- | :--- |
| **Manga / Manhwa** | `/sg2b/Share2sgb/Manga` | `/media/manga` & `/sg2b/Share2sgb/Manga` | Intra-series duplicate & partial scan |
| **Doujinshi (H)** | `/media/devmon/L500/Vere NewFolder` | `/media/doujinshi` & `/media/devmon/L500/Vere NewFolder` | Global cross-directory duplicate scan |
| **Archive Target** | `./archive` | `/archive` | Relocation target for confirmed duplicates |
| **Reports Output** | `./reports` | `/reports` | HTML, JSON, and CSV duplicate reports |

> **Note**: Both standard mount points (`/media/manga`, `/media/doujinshi`) and direct 1:1 host mount paths (`/sg2b/Share2sgb/Manga`, `/media/devmon/L500/Vere NewFolder`) are mapped. This means whether you type `/media/manga` or your full host path `/sg2b/Share2sgb/Manga` in the Web UI, both resolve directly to your files!

---

## 🚀 3-Step Import into CasaOS

### Step 1: Open CasaOS App Store
1. Log in to your CasaOS dashboard in your browser (`http://<casaos-ip>`).
2. Open the **App Store**.
3. In the top right corner of the App Store, click **Custom Install**.

```
  +-------------------------------------------------------------+
  |  App Store                       [ Custom Install ] [ v ]   |
  +-------------------------------------------------------------+
```

### Step 2: Import the Docker Compose YAML
1. In the Custom Install window, click the **Import** icon (top right corner, next to the close button).
2. Copy and paste the entire YAML block below into the text box:

```yaml
version: "3.8"

services:
  manga-dup-finder:
    image: manga-dup-finder:latest
    build:
      context: https://github.com/Alex/Find-Duplicates.git#main
      dockerfile: Dockerfile
    container_name: manga-dup-finder
    restart: unless-stopped
    ports:
      - "8765:8765"
    environment:
      - TZ=UTC
      - SCAN_PATHS=/media/manga,/media/doujinshi
      - MANGA_SCAN_PATH=/media/manga
      - DOUJINSHI_SCAN_PATH=/media/doujinshi
      - OUTPUT_DIR=/reports
      - ARCHIVE_DIR=/archive
      - DETECT_PARTIALS=true
      - MIN_PAGE_RATIO=0.6
      - REPORT_FORMAT=html,json,csv
    volumes:
      # Manga storage mount (host path -> container path)
      - "/sg2b/Share2sgb/Manga:/media/manga"
      - "/sg2b/Share2sgb/Manga:/sg2b/Share2sgb/Manga"
      # Doujinshi storage mount (host path -> container path)
      - "/media/devmon/L500/Vere NewFolder:/media/doujinshi"
      - "/media/devmon/L500/Vere NewFolder:/media/devmon/L500/Vere NewFolder"
      # Reports output and archive target folder
      - "./reports:/reports"
      - "./archive:/archive"
      # Optional configuration file
      - "./config.example.yaml:/app/config.yaml:ro"
    labels:
      icon: "https://raw.githubusercontent.com/Alex/Find-Duplicates/main/assets/icon.png"

x-casaos:
  architectures:
    - amd64
    - arm64
    - arm
  main: manga-dup-finder
  port_map: "8765"
  index: "/"
  scheme: "http"
  description:
    en_us: "Scan, detect, and resolve duplicate chapters across Manga and Doujinshi libraries. Features intra-series and global cross-directory duplicate detection, perceptual image hashing, and an interactive UI to click-and-confirm what stays, what moves to archive, or what gets deleted."
  tagline:
    en_us: "Manga & Doujinshi Interactive Duplicate Finder"
  developer: "Alex"
  author: "Alex"
  icon: "https://raw.githubusercontent.com/Alex/Find-Duplicates/main/assets/icon.png"
  thumbnail: "https://raw.githubusercontent.com/Alex/Find-Duplicates/main/assets/banner.png"
  title:
    en_us: "FindDuplicates"
  category: "Media"
```

### Step 3: Click Submit
1. Click **Submit** in CasaOS.
2. CasaOS will build/pull the container and add the **FindDuplicates** app tile to your CasaOS dashboard with its custom icon and banner.
3. Click the app icon on your CasaOS dashboard (or open `http://<your-casaos-ip>:8765`).

---

## 🖥️ Using the Docker Web UI

Once the container is running:

1. **Trigger Scans with Custom Paths**:
   - Click the **"🚀 Run Scan"** button in the top navbar.
   - Choose your target: **Manga**, **Doujinshi**, or **Both**.
   - Choose modality: **Name & Metadata (Fast)** or **Visual Perceptual Hashing (Deep Image)**.
   - Enter one or multiple directories (or click the quick-add path buttons).
   - Click **Start Scan**.
2. **Review Duplicate Releases**:
   - Switch between **Manga (Intra)**, **Doujinshi (Global)**, and **Partials / Splits** tabs.
   - Review side-by-side comparison cards showing scanlators, page counts, file locations, and quality badges (`[HQ]`, `[Fixed]`, `[Decensored]`, `[Digital]`).
3. **Decide & Confirm Actions**:
   - For each release, choose **Keep**, **Archive**, or **Delete**.
   - Click **"✨ Auto-Select Best"** to automatically select the highest quality copy to stay and duplicates to be archived.
   - Click **"⚡ Review & Confirm"** to open the confirmation drawer.
   - Review the counts and toggle **Dry Run Mode** (checked by default) to test before committing changes.
   - Click **Execute Actions**.
