# FastAPI web application providing TikTok metadata inspection, video download, and slider photo extraction.
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
import yt_dlp
import urllib.parse
import os
import io
import uuid
import tempfile
import zipfile
from curl_cffi import requests
from extractor import get_tiktok_metadata, FFMPEG_PATH

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

@app.get("/proxy-image")
async def proxy_image(url: str):
    """Proxy image request to bypass referer restrictions and CORS."""
    try:
        res = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            impersonate="chrome110"
        )
        return Response(content=res.content, media_type=res.headers.get("content-type", "image/jpeg"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/info")
async def get_info(url: str):
    """Retrieve post metadata including slider status, photo list, and audio availability."""
    try:
        data = get_tiktok_metadata(url)
        is_slider = data.get("is_slider", False)
        images = data.get("images", [])
        return {
            "title": data.get("title", "TikTok Post"),
            "thumbnail": data.get("thumbnail"),
            "duration": data.get("duration", 0),
            "uploader": data.get("uploader", ""),
            "is_slider": is_slider,
            "type": data.get("type", "slider" if is_slider else "video"),
            "images": images,
            "total_images": len(images),
            "audio_url": data.get("audio_url"),
            "has_video": bool(data.get("download_url")),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/download-image")
async def download_image(url: str, filename: str = "slide.jpg"):
    """Download a single slide image with attachment Content-Disposition header."""
    try:
        res = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            impersonate="chrome110",
            timeout=15
        )
        if res.status_code != 200:
            raise HTTPException(status_code=400, detail="Could not retrieve image")
        
        invalid_chars = '\\/: *?"<>|'
        filename_clean = "".join(c if c not in invalid_chars else "_" for c in filename).strip("_").strip()[:100]
        if not filename_clean:
            filename_clean = "slide.jpg"
        if not filename_clean.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            filename_clean += ".jpg"
            
        encoded_filename = urllib.parse.quote(filename_clean)
        return Response(
            content=res.content,
            media_type=res.headers.get("content-type", "image/jpeg"),
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
                "X-Content-Type-Options": "nosniff",
            }
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/download-zip")
async def download_zip(url: str):
    """Package and stream all slider images in a ZIP archive."""
    try:
        metadata = get_tiktok_metadata(url)
        images = metadata.get("images", [])
        if not images and metadata.get("thumbnail"):
            images = [metadata.get("thumbnail")]

        if not images:
            raise HTTPException(status_code=400, detail="No images found for this slider post.")

        caption = metadata.get("title", "tiktok_slides")
        invalid_chars = '\\/: *?"<>|'
        filename_clean = "".join(c if c not in invalid_chars else "_" for c in caption).strip("_").strip()[:150]
        if not filename_clean:
            filename_clean = "tiktok_slides"
        encoded_filename = urllib.parse.quote(f"{filename_clean}.zip")

        zip_buffer = io.BytesIO()
        session = requests.Session()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for idx, img_url in enumerate(images, start=1):
                try:
                    res = session.get(
                        img_url,
                        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                        impersonate="chrome110",
                        timeout=12
                    )
                    if res.status_code == 200:
                        content_type = res.headers.get("content-type", "")
                        ext = "jpg"
                        if "png" in content_type:
                            ext = "png"
                        elif "webp" in content_type:
                            ext = "webp"
                        zf.writestr(f"slide_{idx:02d}.{ext}", res.content)
                except Exception:
                    continue

        return Response(
            content=zip_buffer.getvalue(),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
                "Content-Type": "application/zip",
                "X-Content-Type-Options": "nosniff",
            }
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/download-audio")
async def download_audio(url: str):
    """Stream background sound or music associated with the post."""
    try:
        metadata = get_tiktok_metadata(url)
        audio_url = metadata.get("audio_url")
        if not audio_url:
            raise HTTPException(status_code=404, detail="No audio track found for this post.")

        caption = metadata.get("title", "tiktok_audio")
        invalid_chars = '\\/: *?"<>|'
        filename_clean = "".join(c if c not in invalid_chars else "_" for c in caption).strip("_").strip()[:150]
        if not filename_clean:
            filename_clean = "tiktok_audio"
        encoded_filename = urllib.parse.quote(f"{filename_clean}.mp3")

        session = requests.Session()
        res = session.get(audio_url, impersonate="chrome110", timeout=12)
        return Response(
            content=res.content,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
                "Content-Type": "audio/mpeg",
                "X-Content-Type-Options": "nosniff",
            }
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/download")
async def download(url: str, background_tasks: BackgroundTasks):
    """Download video stream or safely fall back to ZIP if the post is a slider without video."""
    try:
        metadata = get_tiktok_metadata(url)
        
        # If it is a slider and lacks a video stream, stream slider ZIP instead of failing
        if metadata.get("is_slider") and not metadata.get("download_url"):
            return await download_zip(url)

        filename = f"{uuid.uuid4()}.mp4"
        output_path = os.path.join(tempfile.gettempdir(), filename)

        download_url = metadata.get("download_url")
        caption = metadata.get("title", "tiktok_video")

        if metadata.get("source") == "ytdlp" and metadata.get("info_dict"):
            ydl_opts = {
                "outtmpl": output_path,
                "format": (
                    "bestvideo[height>=1080][ext=mp4]+bestaudio[ext=m4a]/"
                    "bestvideo[height>=1080]+bestaudio/"
                    "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
                    "bestvideo+bestaudio/"
                    "best"
                ),
                "merge_output_format": "mp4",
                "prefer_ffmpeg": True,
                "quiet": True,
                "ffmpeg_location": FFMPEG_PATH if os.path.exists(FFMPEG_PATH) else None,
                "postprocessor_args": {
                    "ffmpeg": [
                        "-c:a", "aac",
                        "-b:a", "320k",
                        "-ar", "48000",
                        "-af", "loudnorm=I=-14:LRA=11:TP=-1.5",
                    ],
                },
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        elif download_url:
            res = requests.get(
                download_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                    "Referer": "https://snaptik.app/"
                },
                impersonate="chrome110",
                stream=True
            )
            with open(output_path, "wb") as f:
                for chunk in res.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
        else:
            ydl_opts = {
                "outtmpl": output_path,
                "quiet": True,
                "ffmpeg_location": FFMPEG_PATH if os.path.exists(FFMPEG_PATH) else None,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

        invalid_chars = '\\/: *?"<>|'
        filename_clean = "".join(c if c not in invalid_chars else "_" for c in caption).strip("_").strip()
        filename_clean = filename_clean[:200]
        if not filename_clean:
            filename_clean = "tiktok_video"
        encoded_filename = urllib.parse.quote(filename_clean)

        def file_stream():
            with open(output_path, "rb") as f:
                while chunk := f.read(1024 * 64):
                    yield chunk

        background_tasks.add_task(os.remove, output_path)

        return StreamingResponse(
            file_stream(),
            media_type="video/mp4",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}.mp4",
                "Content-Type": "video/mp4",
                "X-Content-Type-Options": "nosniff",
            }
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))