<div align="center">

  <img src="https://raw.githubusercontent.com/pkief/vscode-material-icon-theme/main/icons/folder-video.svg" width="120" height="120" alt="TikSave Logo" />

  # TikSave — TikTok Video Downloader

  **High-Performance, Watermark-Free TikTok Video Extraction & Streaming Engine**

  [![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
  [![FastAPI](https://img.shields.io/badge/FastAPI-0.110.0-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
  [![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.4-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
  [![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
  [![Status](https://img.shields.io/badge/Status-Active-brightgreen?style=for-the-badge)]()

  <p align="center">
    An open-source, full-stack web application designed to extract and stream TikTok videos in original 1080p Full HD resolution without watermarks. Powered by an AES-CBC challenge-solving engine, Chrome TLS impersonation, and a sleek dark-mode UI.
  </p>

</div>

---

## ✨ Key Features

- 🚫 **No Watermark**: Downloads the original clean video stream directly from TikTok's CDN.
- 📺 **1080p Full HD & 60 FPS**: Retrieves master uncompressed video streams (HEVC/H.264) without re-encoding quality degradation.
- ⚡ **Multi-Engine Extraction Architecture**:
  1. **Primary**: Snaptik reverse-engineered API engine with custom `AES-CBC` token solver (`PyCryptodome`) and `X-Verify` signature generation.
  2. **Metadata Enrichment**: Official TikTok oEmbed API integration for valid high-resolution thumbnail signed URLs.
  3. **Fallback**: `yt-dlp` integration for edge-case URL structures.
- 🔒 **Chrome TLS Impersonation**: Uses `curl_cffi` to mimic Chrome browser TLS fingerprints, bypassing aggressive Cloudflare & TikTok anti-bot protections.
- 🖼 **Image Proxy Endpoint**: Bypasses hotlink protection on TikTok CDN thumbnails for seamless web previews.
- 🎨 **Modern Dark UI**: Designed with Tailwind CSS, featuring subtle micro-animations, real-time download status, and responsive layouts.

---

## 🛠 Tech Stack

### **Backend Framework & Core**
| Technology | Badge | Description |
| :--- | :--- | :--- |
| **Python** | `Python 3.12` | Core programming language |
| **FastAPI** | `FastAPI` | Asynchronous high-performance REST API framework |
| **Uvicorn** | `Uvicorn` | Lightning-fast ASGI server implementation |
| **curl-cffi** | `curl-cffi` | Python binding for `curl-impersonate` (TLS fingerprinting) |
| **PyCryptodome** | `PyCryptodome` | Cryptographic library for AES-CBC challenge solving |
| **yt-dlp** | `yt-dlp` | Modular media downloader used as fallback engine |
| **imageio-ffmpeg** | `FFmpeg` | Multimedia framework binary wrapper |

### **Frontend & Interface**
| Technology | Badge | Description |
| :--- | :--- | :--- |
| **HTML5 / ES6 JS** | `HTML5 / JavaScript` | Modular vanilla web client logic |
| **Tailwind CSS** | `Tailwind CSS` | Utility-first CSS framework (Custom dark theme) |
| **Google Fonts** | `Plus Jakarta Sans` | Modern UI typography |

---

## 📐 System Architecture

```
[ User Browser ]
       │
       ├───────────────────────────────┐
       ▼                               ▼
 (HTML5 / Tailwind UI)         (API Requests)
  http://localhost:3000          http://localhost:8000
                                       │
                                       ▼
                              ┌──────────────────┐
                              │ FastAPI Router   │
                              └────────┬─────────┘
                                       │
                 ┌─────────────────────┼─────────────────────┐
                 ▼                     ▼                     ▼
        ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
        │ /info Endpoint   │  │ /download        │  │ /proxy-image     │
        └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
                 │                     │                     │
                 ▼                     ▼                     ▼
        ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
        │ Snaptik / oEmbed │  │ Direct CDN Stream│  │ Bypass Hotlink   │
        │ Metadata Extractor│ │ (No Re-encoding) │  │ Image Stream     │
        └──────────────────┘  └──────────────────┘  └──────────────────┘
```

---

## 🚀 Getting Started

### Prerequisites

Ensure you have the following installed on your system:
- **Python**: Version `3.10` or higher
- **Git**: For repository cloning
- **OS**: Linux (Ubuntu/Debian recommended), macOS, or Windows (WSL2)

---

### Quick Start (Automated Script)

The repository includes a ready-to-run startup script (`start.sh`) that creates the virtual environment, installs required dependencies, and launches both the backend and frontend servers.

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/tiksave.git
   cd tiksave
   ```

2. **Make the script executable and run**:
   ```bash
   chmod +x start.sh
   ./start.sh
   ```

3. **Open the web application**:
   - **Frontend App**: [http://localhost:3000](http://localhost:3000)
   - **Interactive API Documentation (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

### Manual Setup

If you prefer to set up the environment manually:

1. **Create and activate a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install backend dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r backend/requirements.txt
   ```

3. **Start the FastAPI Backend**:
   ```bash
   cd backend
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

4. **Start the Static Frontend** (in a separate terminal):
   ```bash
   cd frontend
   python3 -m http.server 3000
   ```

---

## 🔌 API Documentation

### `GET /info`
Extracts metadata, preview information, title, and author details for a given TikTok video URL.

**Query Parameters:**
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `url` | `string` | **Yes** | Full TikTok video URL (e.g. `https://www.tiktok.com/@user/video/123456789`) |

**Sample Response (`200 OK`):**
```json
{
  "title": "Orihime!! Bleach Thousand Year Blood War!! #bleachanime #bleach",
  "thumbnail": "https://p16-common-sign.tiktokcdn.com/tos-alisg-p-0037/...",
  "duration": 60,
  "uploader": "mind.amvs"
}
```

---

### `GET /download`
Initiates a high-speed video stream download for the target TikTok video without watermarks.

**Query Parameters:**
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `url` | `string` | **Yes** | Full TikTok video URL |

**Headers Returned:**
- `Content-Type`: `video/mp4`
- `Content-Disposition`: `attachment; filename*=UTF-8''<clean_title>.mp4`

---

### `GET /proxy-image`
Proxies TikTok CDN image requests to bypass browser `CORS` and referrer hotlink protection.

**Query Parameters:**
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `url` | `string` | **Yes** | Encoded URL of the TikTok thumbnail image |

---

## 📂 Directory Structure

```
TikSave/
├── backend/
│   ├── extractor.py         # Primary extraction engine & Snaptik token solver
│   ├── main.py              # FastAPI endpoints & streaming proxy server
│   └── requirements.txt     # Python dependency lockfile
├── frontend/
│   └── index.html           # Full-featured single-page web interface (Tailwind CSS)
├── .gitignore               # Standard git ignore patterns
├── README.md                # Project documentation
└── start.sh                 # One-click startup script
```

---

## 🛡 Security & Performance Highlights

- **Zero-Storage Footprint**: Video files downloaded during processing are streamed directly to the user and automatically cleaned up from disk via FastAPI `BackgroundTasks`.
- **Dynamic Decryption Engine**: Automatically solves AES-CBC cryptographic puzzles sent by Snaptik's API protection layer to guarantee high availability.
- **Resource Efficient**: Low memory overhead utilizing Python generators for chunked file streaming (`64 KB` buffer size).

---

## 🤝 Contributing

Contributions are what make the open-source community an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git checkout -b feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.

<div align="center">
  <sub>Built with ❤️ for the open-source community.</sub>
</div>
