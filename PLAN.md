# Manga & Doujinshi Duplicate & Partial Chapter Finder
## Architecture, Design & Implementation Plan (Updated with Real-World Data Analysis)

---

## 1. Project Overview & Repository Identity

### What Kind of Repository Is This?
**FindDuplicates** is a specialized, cross-platform deduplication, verification, and collection integrity tool tailored for digital manga, manhwa, webtoons, and doujinshi (H) libraries.

Large manga and doujinshi collections are plagued by duplicate downloads, multiple scanlation group releases, fragmented sub-chapters (e.g., `Ch. 10.1`, `Ch. 10.2` coexisting with `Ch. 10`), version updates (`[v2]`, `_fixed_`, `HQ`), and copies scattered across staging folders (`000 NEW`, `TempD`, `TempT`), download drives, and long-term storage archives.

### Primary Objectives & Capabilities:
1. **Targeted Manga Deduplication (Intra-Series Scope)**:
   - Identify duplicate chapters, competing scanlation releases, fractional sub-chapter splits, and incomplete pages **within each individual manga/manhwa series**.
2. **Global Doujinshi Deduplication (Cross-Directory Scope)**:
   - Identify duplicate works and alternative releases **across the entire directory structure** (regardless of whether they sit in staging folders like `000 NEW`, `TempD`, `TempT`, `ORIGINAL`, `Old`, or archive volumes).
3. **Decoupled Job Architecture**:
   - Provide independent, specialized jobs:
     - **Name-Based Jobs**: Lightning-fast string, regex, and metadata tokenizers operating on filesystem names or offline `tree` text dumps without requiring image decompression.
     - **Image-Based Jobs**: Deep visual inspection utilizing perceptual hashing (dHash/pHash), page count audits, and resolution comparisons to definitively detect identical artwork across different names or translations.
4. **Offline Tree Dump Ingestion**:
   - Ability to run deduplication directly against exported Windows `tree /a` or `tree /f` text dumps (such as the files in `sample_data/`) without needing physical access to network storage or NAS shares.
5. **Cross-Platform & Home Server Ready**:
   - Native support for Windows drive letters (`G:\...`, UNC paths `\\NAS\share`) and Linux mount paths (`/DATA/Media/...`).
   - CasaOS and Docker integration with custom icons, banners, and dashboard metadata.

---

## 2. Real-World Data Analysis (`sample_data/`)

Analysis of actual collection structures provided in `sample_data/Manga` and `sample_data/H` reveals distinct structural patterns, directory depths, and naming anomalies.

```
                    COLLECTION HIERARCHY MAP
                    
  [MANGA / MANHWA / WEBTOON]                    [DOUJINSHI (H)]
  Scope: Intra-Series                          Scope: Global Cross-Directory
  
  Volume / Root                                Heterogeneous Staging & Archive Roots
  ├── Manga_1, Manga_A2, Manga_CBZ_1...        ├── 000 NEW, TempD, TempT, Vere2, Old...
  │   └── Category / Status Bucket             │   ├── Standalone Doujinshi Folder
  │       ├── Axe, Completed, Current...       │   │   ├── (C96) [Circle (Artist)] Title [Eng]
  │       │   └── Series Title                 │   │   │   └── _chapter / Chapter / loose pages
  │       │       └── Chapter Folder / Archive │   │   └── [Dokukinokojin] Title.zip
  │       │           ├── Ch. 1_48a245         │   └── Multi-Chapter / Anthology Series
  │       │           ├── Fuyuking_Ch.1...     │       └── Inran Seifuku Hame Nikki
  │       │           └── [Group] Ch.01.cbz    │           ├── Chapter 001
  │                                            │           └── Chapter 002
```

### 2.1 Manga & Manhwa Dataset Analysis (`sample_data/Manga/manga.txt`)
- **Scale**: 47,707 lines representing **7 volumes/roots**, **26 status buckets**, **739 series titles**, and **46,509 chapters**.
- **Directory Hierarchy (Fixed 4-Level Depth)**:
  - **Depth 0 (Root Volume)**: e.g., `Manga_1`, `Manga_A2`, `Manga_CBZ_1`, `Manga_CBZ_A2`, `Manhwa_CBZ_1`, `Manhwa_CBZ_H3`, `Webtoon_1`.
  - **Depth 1 (Status Category)**: e.g., `Axe`, `Completed`, `Completed Current3`, `Current`, `Current Axe4`, `Current Old5`, `Current Standard`, `Current U`.
  - **Depth 2 (Series Title)**: e.g., `Flag Capture in the First Move`, `Don't XX Ms. Tsukimine`, `Never Die Extra`.
  - **Depth 3 (Chapter Folder or Archive)**:
    - Loose image folders downloaded via Tachiyomi/Mihon/Mangadex scrapers with 6-character hex chapter IDs appended: `Chapter 10_48a245`, `Chapter 20.1_3f306b`.
    - Group-prefixed chapters: `Fuyuking_Ch.1 - Honest-Considerate MC vs Shy Senior_f62cb7` vs `RingHeilgh_Ch.1 - Kind and good-hearing mc VS over-matrue senpai_c3b128`.
    - Fractional chapters: `TeruTeruScans_Ch.12.5 - Twitter Extra...` alongside full chapters.
    - Compressed archives: Series under `_CBZ_` volumes contain `.cbz` archive files or loose sub-chapter folders.
- **Deduplication Statistics**:
  - **104 series** were found to contain duplicate chapters.
  - **276 duplicate chapter groups** identified (e.g., Chapter 1, 5, 13 translated by multiple groups; version replacements like `Waffle Castle & Paean Scans_Ch.13 - HQ version_066174` vs `Waffle Castle_Ch.13 - Tsundere Girl vs Special Christmas Hero_33e062`).
  - **Cross-category series duplication**: 0 instances. Series exist uniquely in a single status bucket, confirming that **Manga deduplication is strictly intra-series**.

### 2.2 Doujinshi (H) Dataset Analysis (`sample_data/H/*.txt`)
- **Scale**: Over 61,000 lines across 5 dump files (`h_archive_zip.txt`, `h_new_b2.txt`, `h_temp_d.txt`, `h_temp_t.txt`, `h_vere_all.txt`), encompassing **14,059 unique works**.
- **Directory Hierarchy (Dynamic Variable Depth)**:
  - Items are scattered across arbitrary staging folders: `000 NEW`, `000 CC`, `Old/2002-03`, `Vere2`, `Vere3`, `TempD`, `TempT`, `ORIGINAL`, `ORIGINAL 2`, `Folder`, `L1`, etc.
  - **Two Content Structures**:
    1. **Standalone Doujinshi**: Formatted as `(Event) [Circle (Artist)] Title (Parody) [Language] [Scanlator] [Tags]`.
       - *Crucial discovery*: Scraper downloaders create a dummy inner leaf subfolder: `Chapter`, `_Chapter`, `_chapter`, `read the chapter`, or `<artist>_chapter` (e.g., `aquadrop_Chapter`, `rbooks_Chapter`). The true doujinshi entity is the **parent** directory, not the leaf subfolder.
       - Some standalone works exist as archive files: `[Dokukinokojin] Furusato no Tama-baasama ~ Chapter 2 ~.zip`.
    2. **Multi-Chapter / Anthology Series**: Multi-part works where the parent folder is the series title (`Inran Seifuku Hame Nikki`, `Zettai Harem`, `Pitapita Kyouei Mizugi EX`) and child folders are chapters (`1 - CL-Orc 1`, `Chapter 001`, `10 - Zettai Harem v3 - Chapter 17`).
- **Deduplication Statistics**:
  - Over **269 verified duplicate groups** found across different directories.
  - Typical duplicates span across staging buckets and long-term storage:
    - `new12/[Kurogoma Seizou Koujou (Goma Gorilla)] Fukujuu OL [English] [FuDeORS] [Decensored] [Digital]` (in `h_new_b2.txt`) coexists with `Folder/[Kurogoma Seizou Koujou (Goma Gorilla)] Fukujuu OL [English] [FuDeORS] [Decensored] [Digital]` (in `h_temp_t.txt`).
    - `L1/[Mousou Engine] Totsuzen Tomari ni Kita Juushi o Otosu Hanashi [English]` coexists with `ORIGINAL/[Mousou Engine] Totsuzen Tomari ni Kita Juushi o Otosu Hanashi [English]`.
    - Tag variants: `[COMPLETE]` vs `[WataTL & head empty] [Digital]`, censored vs `[Decensored]`.

---

## 3. Deduplication Strategy & Scopes

| Dimension | Manga / Manhwa / Webtoon | Doujinshi / H |
| :--- | :--- | :--- |
| **Deduplication Scope** | **Intra-Series**: Confined strictly within each series folder. | **Global / Inter-Directory**: Spans across the entire monitored library and all staging folders. |
| **Primary Identifier** | Series Title + Normalized Chapter Number (float: `1.0`, `12.5`). | Circle/Artist + Clean Normalized Title (Japanese / English). |
| **Secondary Identifiers**| Scanlator group, version tags (`v2`, `fixed`, `HQ`), hash suffix. | Convention/Event (`(C96)`), scanlator, decensored flags, language. |
| **Chapter Variants** | Fractional chapters (`12.1`, `12.2` vs `12.0`), omakes, specials. | Multi-chapter series vs standalone single tankoubon releases. |
| **Storage Forms** | Loose page folders with hex hashes, `.cbz` archives. | Loose page folders, inner `_chapter` subfolders, `.zip`/`.cbz` archives. |

---

## 4. Multi-Job System Architecture

To avoid massive I/O bottlenecks and provide fast, actionable feedback, the deduplication engine is separated into distinct, specialized jobs:

```
                                  CLI & CONFIG ENGINE
                                           │
         ┌─────────────────────────────────┴─────────────────────────────────┐
         ▼                                                                   ▼
  ┌───────────────────────────────┐                   ┌───────────────────────────────┐
  │     JOB 1: NAME-BASED         │                   │    JOB 2: IMAGE-BASED         │
  │     METADATA ENGINE           │                   │    PERCEPTUAL HASH ENGINE     │
  └──────────────┬────────────────┘                   └──────────────┬────────────────┘
                 │                                                   │
     ┌───────────┼───────────┐                           ┌───────────┴───────────┐
     ▼           ▼           ▼                           ▼                       ▼
┌─────────┐ ┌─────────┐ ┌─────────┐                 ┌─────────┐             ┌─────────┐
│ Job 1A  │ │ Job 1B  │ │ Job 1C  │                 │ Job 2A  │             │ Job 2B  │
│ Manga   │ │ Doujin  │ │ Offline │                 │ Manga   │             │ Doujin  │
│ Names   │ │ Names   │ │ Tree    │                 │ Visual  │             │ Global  │
│ (Intra) │ │(Global) │ │ Parser  │                 │ Verify  │             │ Cluster │
└─────────┘ └─────────┘ └─────────┘                 └─────────┘             └─────────┘
```

---

### 4.1 Job 1: Name & Metadata-Based Deduplication (Fast)

Fast execution requiring zero image decompression. Runs in seconds even on tens of thousands of items.

#### Job 1A: Manga Name-Based Deduplication (`--job manga-names`)
- **Scope**: Within each manga series directory.
- **Workflow**:
  1. Traverse directory to find Series level (handling depth 2 in `Volume/Status/Series/Chapter` or standard roots).
  2. For each chapter item (folder or `.cbz`/`.zip` archive):
     - Strip trailing hex hash: `_([0-9a-f]{6})$`.
     - Extract normalized chapter number (`1`, `12.5`, `10.1`).
     - Extract scanlator group prefix or bracketed tag: `Fuyuking_...`, `[Group]...`.
     - Detect partial keywords (`[Incomplete]`, `[Sample]`, `[Missing]`).
     - Detect version updates (`_fixed_`, `[v2]`, `HQ version`).
  3. Group chapters by normalized chapter number.
  4. Flag:
     - **Exact Duplicate Chapters**: Same chapter number from different scanlation groups or duplicate downloads.
     - **Fractional Overlap**: Sub-chapters (`Ch 20.1`, `Ch 20.2`) coexisting with full chapter (`Ch 20`).
     - **Version Upgrades**: Older un-fixed versions when `_fixed_` or `[v2]` exists.

#### Job 1B: Doujinshi Name-Based Deduplication (`--job doujinshi-names`)
- **Scope**: Entire directory tree across all monitored folders.
- **Workflow**:
  1. Recursively walk all target directories.
  2. Detect Doujinshi work entities:
     - Collapse leaf subfolders named `Chapter`, `_Chapter`, `_chapter`, `read the chapter`, or `<artist>_chapter` into their parent directory.
     - Detect single `.zip`/`.cbz` archive files.
  3. Extract metadata tokens:
     - **Event**: `(C96)`, `(COMIC1☆10)`, `(SC54)`.
     - **Circle & Artist**: `[Circle (Artist)]` or `[Artist]`.
     - **Title**: Clean English, Romaji, and secondary translated titles (handling separators `_`, `~`, `/`).
     - **Tags**: `[English]`, `[Decensored]`, `[Digital]`, `[COMPLETE]`.
  4. Build composite keys:
     - Primary Key: `(Normalized_Artist, Normalized_Title)`.
     - Secondary Key: `Normalized_Title` (for uncredited artist releases or title-only folders).
     - Fuzzy Match: Levenshtein / Token Sort Ratio ($\ge 88\%$) to match titles with punctuation or romanization differences.
  5. Flag duplicate copies across paths, highlighting version differences (e.g. Decensored vs Censored, complete vs partial).

#### Job 1C: Offline Tree Dump Parser (`--job parse-tree`)
- **Purpose**: Deduplicate directly from text files generated via `tree /a` or `tree /f` (such as `sample_data/Manga/manga.txt` and `sample_data/H/*.txt`).
- **Features**:
  - Automatically identifies whether the file is a Manga hierarchy (4-level fixed) or Doujinshi tree (variable depth with staging buckets).
  - Generates instant duplicate reports without needing network mounts, external hard drives, or CasaOS storage active.

---

### 4.2 Job 2: Image & Content-Based Deduplication (Perceptual Hashing)

Deep inspection utilizing visual hashing (`imagehash` library) and page geometry.

#### Job 2A: Manga Visual Chapter Verifier (`--job manga-images`)
- **Scope**: Target chapters already flagged as name-based duplicates within a series, or chapters with differing page counts.
- **Workflow**:
  1. Extract representative pages from both chapter releases:
     - First non-credit page (Page 1 or 2).
     - Middle story page (Page $N/2$).
     - Last page (Page $N$).
  2. Calculate 64-bit difference hash (`dHash`) or perceptual hash (`pHash`).
  3. Compute Hamming distance between corresponding pages:
     - **Distance $\le 4$**: Identical raw artwork. Confirms safe deduplication.
     - **Distance $5 - 12$**: Re-scanned, different scanlation redraws, or resolution differences. Compare resolution and file size.
     - **Distance $> 12$**: Different content despite matching chapter numbers (e.g., mislabeled special or different omake).
  4. **Quality Recommendation**: If identical artwork, recommend keeping the version with higher resolution, cleaner aspect ratio, and absence of compression artifacts.

#### Job 2B: Doujinshi Global Perceptual Hash Clustering (`--job doujinshi-images`)
- **Scope**: Global index across the entire H library to find identical works with completely different titles (e.g., Original Japanese Title vs Translated Title vs Romaji).
- **Three-Stage Pipeline**:
  ```
  +---------------------------------------------------------------------------------+
  | STAGE 1: Cover Page Indexing                                                    |
  | Read first image of every doujinshi (from folder or archive header).             |
  | Compute 64-bit dHash/pHash. Index into BK-Tree or VP-Tree for fast search.      |
  +---------------------------------------------------------------------------------+
                                         │
                                         ▼
  +---------------------------------------------------------------------------------+
  | STAGE 2: Candidate Verification via Multi-Page Fingerprint                      |
  | For candidate matches with Cover Hamming Distance <= 6:                        |
  | Sample Page 3, Page 8, and Last Page. Compute joint hash vector.                |
  | Filter out false positives caused by shared anthology or magazine covers.       |
  +---------------------------------------------------------------------------------+
                                         │
                                         ▼
  +---------------------------------------------------------------------------------+
  | STAGE 3: Quality & Retention Assessment                                         |
  | Extract image dimensions (e.g. 1200x1800 vs 800x1200) and page counts.          |
  | Tag: Highest Resolution, Most Complete Page Count, Decensored preference.       |
  +---------------------------------------------------------------------------------+
  ```

---

## 5. Tokenization & Normalization Rules

Derived directly from patterns observed in the sample data:

### 5.1 Manga Cleaning Rules
- **Hex Hash Removal**: Strip `_[0-9a-f]{6}$` from folder names (e.g., `Chapter 10_48a245` $\rightarrow$ `Chapter 10`).
- **Scanlator Extraction**: Matches leading prefix before chapter indicator:
  - `^(?:(?P<group>[^_]+)_)?(?:Vol\.\d+\s+)?(?:Ch\.|Chapter|c)\s*(?P<num>\d+(?:\.\d+)?)`
- **Fractional Chapter Matching**:
  - `floor(Ch_A) == floor(Ch_B)` when one has decimal component.
- **Version Indicators**:
  - `_fixed_`, `[v2]`, `HQ version`, `[HQ]` $\rightarrow$ Prioritize over unflagged earlier releases.

### 5.2 Doujinshi Cleaning Rules
- **Leaf Folder Collapse**:
  - If leaf folder matches `^(?:_?chapter|read the chapter|.+_chapter)$` (case-insensitive), the doujinshi work title is taken from `path.parent.name`.
- **Event Extraction**:
  - `^\s*\((?P<event>C\d+|COMIC1[^\)]*|SC\d+|FF\d+|AC\d+|M3[^\)]*)\)`
- **Circle & Artist Parsing**:
  - `\[(?P<circle>[^\(\]]+)(?:\s*\((?P<artist>[^\)]+)\))?\]`
- **Title Normalization**:
  - Strip trailing `[Language]`, `[Scanlator]`, `[Decensored]`, `[Digital]`, `(Parody)`.
  - Handle dual titles: Many releases contain `Japanese Title _ English Title`. Both sub-titles are extracted and indexed so that a Japanese-titled copy matches an English-titled copy.
  - Alphanumeric lowercasing: `re.sub(r'[^a-zA-Z0-9]', '', title).lower()`.

---

## 6. CLI Command Interface & Configuration

### 6.1 Unified CLI Interface
```bash
# === MANGA JOBS ===
# 1. Name-based intra-series duplicate scan
python -m src.main manga --by name --scan "G:\LX\Manga"

# 2. Image perceptual hash verification on duplicate/partial candidates
python -m src.main manga --by image --scan "G:\LX\Manga"

# === DOUJINSHI JOBS ===
# 3. Name-based global cross-directory duplicate scan
python -m src.main doujinshi --by name --scan "G:\LX\H" --scan "G:\LX\H_Staging"

# 4. Global visual perceptual hash clustering across all folders
python -m src.main doujinshi --by image --scan "G:\LX\H" --cover-cache "./cache/covers"

# === OFFLINE TREE DUMP ANALYZER ===
# 5. Fast offline analysis of tree dump files
python -m src.main parse-tree --file "sample_data/Manga/manga.txt" --type manga
python -m src.main parse-tree --file "sample_data/H/h_new_b2.txt" --type doujinshi
```

### 6.2 Configuration Schema (`config.yaml`)
```yaml
# Library root paths
manga:
  scan_paths:
    - "G:/LX/Manga"
  detect_fractional: true
  min_page_ratio: 0.60
  supported_archives: [".cbz", ".zip"]

doujinshi:
  scan_paths:
    - "G:/LX/H"
    - "G:/LX/H_Staging"
  fuzzy_threshold: 88
  cross_directory: true
  leaf_chapter_names: ["chapter", "_chapter", "read the chapter"]

image_inspection:
  enabled: true
  hash_algorithm: "dhash" # dhash or phash
  hash_size: 8
  hamming_threshold: 4
  cache_directory: "./cache"

output:
  report_directory: "./reports"
  formats: ["terminal", "html", "json", "csv"]
```

---

## 7. Docker & CasaOS Home Server Integration

### 7.1 CasaOS Native Features
- **Application App Card**: Integration via `docker-compose.yml` with `x-casaos` extension for CasaOS dashboard launcher, description, and status widgets.
- **Visual Assets**:
  - App Icon: `assets/icon.png` (512x512 PNG) and `assets/icon.svg`.
  - Store Banner: `assets/banner.png` (1024x500 PNG) and `assets/banner.svg`.
  - Badges/Sprites: 256px and 128px dashboard icons.
- **Volume Mappings**: Maps CasaOS storage pools (e.g., `/DATA/Media/Manga`, `/DATA/Media/Doujinshi`) to standard container targets `/data/manga` and `/data/doujinshi`.
- **Scheduled Deduplication**: Built-in cron / scheduled background runner to auto-scan incoming downloads and output web reports.

---

## 8. Implementation Roadmap

- [x] **Phase 1: Foundation & Planning** *(Complete)*
  - Initial repository layout and CasaOS visual assets (`assets/`).
  - Core dataclasses and baseline scanner modules.
- [x] **Phase 2: Real-World Data Ingestion & Analysis** *(Complete)*
  - Ingested and parsed `sample_data/Manga` and `sample_data/H` dump files.
  - Determined intra-series scope for Manga and global cross-directory scope for Doujinshi.
  - Quantified duplicate patterns (104 manga duplicate series, 269+ H cross-directory duplicate works).
- [ ] **Phase 3: Multi-Job Architecture Refactoring**
  - Refactor `src/` into specialized job modules:
    - `src/jobs/manga_names.py`: Intra-series manga chapter duplicate detector.
    - `src/jobs/doujinshi_names.py`: Global cross-directory doujinshi matcher with artist/circle and title tokenizers.
    - `src/jobs/tree_parser.py`: Offline tree dump parser for instant analysis without live storage.
    - `src/jobs/image_hasher.py`: Perceptual hashing (dHash/pHash) and visual page comparator.
- [ ] **Phase 4: CLI Dispatcher & Configuration Alignment**
  - Implement subcommands (`manga`, `doujinshi`, `parse-tree`).
  - Add fuzzy matching support for doujinshi title variations.
  - Support archive reading (`.cbz`, `.zip`, `.rar`, `.cbr`) with streaming header page counting.
- [ ] **Phase 5: Reporting & Container Verification**
  - Multi-tab HTML report (Manga Duplicates, Doujinshi Duplicates, Partial/Fractional Issues, Quality Recommendations).
  - Verify container build and test run against sample data on Windows and CasaOS/Linux.
