# CasaOS 1-Click Import & Troubleshooting Guide

---

## ⚠️ Why Did "Error response from daemon: No such image" Happen?

```text
Error response from daemon: No such image: manga-dup-finder:latest
```

### The Root Cause:
1. `pull_policy: always` instructs the Docker daemon: **"Never use a local image; always pull from the remote container registry."**
2. The image name `manga-dup-finder:latest` is a local name that does not exist on Docker Hub.
3. CasaOS's Custom Install UI does not build images locally; it expects an existing image from a registry.
4. When CasaOS tried to pull `docker.io/library/manga-dup-finder:latest`, Docker Hub returned `No such image`.

---

## 🛠️ How to Fix (Choose Option A, B, or C)

---

### Option A (Recommended): Use GitHub Container Registry (GHCR) with `pull_policy: always`

We have added a GitHub Actions workflow in [`.github/workflows/docker-publish.yml`](.github/workflows/docker-publish.yml).

1. Push your latest code to GitHub:
   ```bash
   git add .
   git commit -m "Add GitHub Actions workflow and update CasaOS compose"
   git push origin main
   ```
2. GitHub will automatically build the multi-arch container and publish it to:
   ```text
   ghcr.io/alexlx4773h/findduplicates:latest
   ```
   *(Ensure your package visibility on GitHub is set to Public under GitHub Profile $\rightarrow$ Packages $\rightarrow$ FindDuplicates $\rightarrow$ Package Settings $\rightarrow$ Change visibility $\rightarrow$ Public).*

3. In CasaOS, import [`docker-compose.casaos.yml`](docker-compose.casaos.yml) (specifically formatted for CasaOS App Store schema with `type: bind` and `category: Utilities` to prevent CasaOS from auto-routing to `/DATA/Media`):

```yaml
name: findduplicates
version: "3.8"

services:
  manga-dup-finder:
    image: ghcr.io/alexlx4773h/findduplicates:latest
    pull_policy: always
    container_name: manga-dup-finder
    restart: unless-stopped
    network_mode: bridge
    ports:
      - target: 8765
        published: 8765
        protocol: tcp
    environment:
      - TZ=UTC
      - SCAN_PATHS=/sg2b/Share2sgb/Manga,/media/devmon/L500/Vere NewFolder
      - MANGA_SCAN_PATH=/sg2b/Share2sgb/Manga
      - DOUJINSHI_SCAN_PATH=/media/devmon/L500/Vere NewFolder
      - OUTPUT_DIR=/reports
      - ARCHIVE_DIR=/archive
      - DETECT_PARTIALS=true
      - MIN_PAGE_RATIO=0.6
      - REPORT_FORMAT=html,json,csv
    volumes:
      # Manga direct 1:1 host storage mount
      - type: bind
        source: "/sg2b/Share2sgb/Manga"
        target: "/sg2b/Share2sgb/Manga"
      # Doujinshi direct 1:1 host storage mount
      - type: bind
        source: "/media/devmon/L500/Vere NewFolder"
        target: "/media/devmon/L500/Vere NewFolder"
      # Reports output and archive target folder in CasaOS AppData
      - type: bind
        source: "/DATA/AppData/FindDuplicates/reports"
        target: "/reports"
      - type: bind
        source: "/DATA/AppData/FindDuplicates/archive"
        target: "/archive"
    labels:
      icon: "https://raw.githubusercontent.com/AlexLX4773H/FindDuplicates/main/assets/icon.png"

    x-casaos:
      volumes:
        - container: "/sg2b/Share2sgb/Manga"
          description:
            en_us: "Manga storage directory"
        - container: "/media/devmon/L500/Vere NewFolder"
          description:
            en_us: "Doujinshi storage directory"
        - container: "/reports"
          description:
            en_us: "Deduplication reports output folder"
        - container: "/archive"
          description:
            en_us: "Archive folder for moved duplicates"
      ports:
        - container: "8765"
          description:
            en_us: "Web UI port"

x-casaos:
  architectures:
    - amd64
    - arm64
    - arm
  main: manga-dup-finder
  port_map: "8765"
  index: "/"
  scheme: "http"
  title:
    en_us: "FindDuplicates"
  tagline:
    en_us: "Manga & Doujinshi Interactive Duplicate Finder"
  category: "Utilities"
```

---

### Option B (Instant): Run Directly with Official `python:3.12-slim` Image

If you want to run it in CasaOS **right now** without waiting for a GitHub Actions build or pushing an image:

Use official `python:3.12-slim` (which is already on Docker Hub, so `pull_policy: always` succeeds immediately), and mount your `FindDuplicates` directory on the server into `/app`:

```yaml
version: "3.8"

services:
  manga-dup-finder:
    image: python:3.12-slim
    pull_policy: always
    container_name: manga-dup-finder
    restart: unless-stopped
    ports:
      - "8765:8765"
    working_dir: /app
    command: >
      sh -c "apt-get update && apt-get install -y --no-install-recommends unzip p7zip-full &&
             pip install --no-cache-dir -r /app/requirements.txt &&
             python -m src.main server --host 0.0.0.0 --port 8765"
    environment:
      - TZ=UTC
      - SCAN_PATHS=/sg2b/Share2sgb/Manga,/media/devmon/L500/Vere NewFolder
      - MANGA_SCAN_PATH=/sg2b/Share2sgb/Manga
      - DOUJINSHI_SCAN_PATH=/media/devmon/L500/Vere NewFolder
      - OUTPUT_DIR=/reports
      - ARCHIVE_DIR=/archive
      - DETECT_PARTIALS=true
      - MIN_PAGE_RATIO=0.6
      - REPORT_FORMAT=html,json,csv
    volumes:
      # Map the FindDuplicates repository directory on your server to /app
      - "/DATA/AppData/FindDuplicates:/app"
      # Direct 1:1 host storage mounts
      - "/sg2b/Share2sgb/Manga:/sg2b/Share2sgb/Manga"
      - "/media/devmon/L500/Vere NewFolder:/media/devmon/L500/Vere NewFolder"
      - "/DATA/AppData/FindDuplicates/reports:/reports"
      - "/DATA/AppData/FindDuplicates/archive:/archive"
    labels:
      icon: "https://raw.githubusercontent.com/AlexLX4773H/FindDuplicates/main/assets/icon.png"

x-casaos:
  architectures:
    - amd64
    - arm64
    - arm
  main: manga-dup-finder
  port_map: "8765"
  index: "/"
  scheme: "http"
  title:
    en_us: "FindDuplicates"
  category: "Media"
```

---

### Option C: Build the Image Locally on Your Server First

If you prefer building the image locally on your CasaOS server:

1. SSH into your CasaOS server and navigate to your `FindDuplicates` directory:
   ```bash
   cd /path/to/FindDuplicates
   docker build -t manga-dup-finder:latest .
   ```
2. Once the local image is built, change `pull_policy: always` to `pull_policy: if-not-present` or `never` in your compose file:
   ```yaml
   services:
     manga-dup-finder:
       image: manga-dup-finder:latest
       pull_policy: if-not-present
       # ...
   ```
   *(Because `pull_policy: always` forces Docker to contact Docker Hub, changing it to `if-not-present` allows Docker to use your locally built image).*
