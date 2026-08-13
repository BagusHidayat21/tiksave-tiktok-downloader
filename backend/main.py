from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
import yt_dlp
import urllib.parse
import os
import uuid
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
    try:
        data = get_tiktok_metadata(url)
        return {
            "title": data.get("title", "TikTok Video"),
            "thumbnail": data.get("thumbnail"),
            "duration": data.get("duration"),
            "uploader": data.get("uploader", ""),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


import tempfile

@app.get("/download")
async def download(url: str, background_tasks: BackgroundTasks):
    try:
        filename = f"{uuid.uuid4()}.mp4"
        output_path = os.path.join(tempfile.gettempdir(), filename)

        metadata = get_tiktok_metadata(url)
        download_url = metadata.get("download_url")
        caption = metadata.get("title", "tiktok_video")

        if metadata.get("source") == "ytdlp" and metadata.get("info_dict"):
            # Use yt-dlp download pipeline with ffmpeg processing
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
            # Download file using curl_cffi for fast TLS streaming
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
            # Fallback to direct yt-dlp download attempt
            ydl_opts = {
                "outtmpl": output_path,
                "quiet": True,
                "ffmpeg_location": FFMPEG_PATH if os.path.exists(FFMPEG_PATH) else None,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

        # Clean up filename for header
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