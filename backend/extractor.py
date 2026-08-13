import os
import re
import json
import uuid
import time
import urllib.parse
import yt_dlp
from curl_cffi import requests
from Crypto.Cipher import AES
from Crypto.Hash import SHA256
import base64

import imageio_ffmpeg

try:
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "venv", "bin", "ffmpeg")

def solve_snaptik_token(token_id: str, token_p: str) -> str:
    key_str = "sn4pt1k_v3r1fy2026:" + token_id
    key_bytes = SHA256.new(key_str.encode("utf-8")).digest()
    
    p_bytes = base64.b64decode(token_p)
    iv = p_bytes[:16]
    ciphertext = p_bytes[16:]
    
    cipher = AES.new(key_bytes, AES.MODE_CBC, iv)
    decrypted = cipher.decrypt(ciphertext)
    pad_len = decrypted[-1]
    decrypted = decrypted[:-pad_len]
    
    data = json.loads(decrypted.decode("utf-8"))
    e_val = data["_e"]
    h_val = data["_h"]
    del data["_e"]
    del data["_h"]
    
    t_type = data.get("t")
    if t_type == "b":
        val = ((data["a"] ^ data["b"]) >> data["s"]) & 255
    elif t_type == "r":
        val = sum(data["n"]) * 2 + 1
    elif t_type == "c":
        val = ord(data["w"][data["i"]]) * data["m"]
    elif t_type == "m":
        val = ((data["a"] + data["b"]) % 100) * data["c"]
    elif t_type == "n":
        val = data["a"] * data["b"] + data["b"] * data["c"] + data["c"] * data["a"] - data["a"]
    else:
        val = 0
        
    return f"{token_id}:{val}:{e_val}:{h_val}"


def extract_via_snaptik(url: str):
    try:
        session = requests.Session()
        token_res = session.post(
            "https://snaptik.app/api/token",
            headers={"X-Requested-With": "XMLHttpRequest", "Referer": "https://snaptik.app/en3"},
            impersonate="chrome110",
            timeout=10
        )
        t_json = token_res.json()
        token_id = t_json["id"]
        token_p = t_json["p"]
        solved_token = solve_snaptik_token(token_id, token_p)
        
        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "X-Verify": solved_token,
            "Referer": "https://snaptik.app/en3"
        }
        res = session.get(f"https://snaptik.app/api/extract?url={urllib.parse.quote(url)}", headers=headers, impersonate="chrome110", timeout=12)
        if res.status_code == 200:
            data = res.json()
            if data.get("success") is not False:
                # Format result
                video_data = data.get("data") or data
                dl_url = video_data.get("downloadUrl") or video_data.get("download_url") or video_data.get("hdDownloadUrl") or video_data.get("url") or (video_data.get("urls", [None])[0] if isinstance(video_data.get("urls"), list) else None)
                if dl_url and dl_url.startswith("/"):
                    dl_url = "https://snaptik.app" + dl_url
                    
                return {
                    "title": video_data.get("title") or video_data.get("description") or "TikTok Video",
                    "thumbnail": video_data.get("thumbnail") or video_data.get("cover"),
                    "duration": video_data.get("duration"),
                    "uploader": video_data.get("author", {}).get("nickname") or video_data.get("author", {}).get("unique_id") or "",
                    "download_url": dl_url,
                    "source": "snaptik"
                }
    except Exception:
        pass
    return None


def extract_via_ytdlp(url: str):
    try:
        ydl_opts = {
            "quiet": True,
            "ffmpeg_location": FFMPEG_PATH if os.path.exists(FFMPEG_PATH) else None,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            }
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                "title": info.get("title", "TikTok Video"),
                "thumbnail": info.get("thumbnail"),
                "duration": info.get("duration"),
                "uploader": info.get("uploader") or info.get("creator") or "",
                "download_url": info.get("url"),
                "info_dict": info,
                "source": "ytdlp"
            }
    except Exception:
        pass
    return None


def fetch_oembed_metadata(url: str):
    try:
        res = requests.get(f"https://www.tiktok.com/oembed?url={urllib.parse.quote(url)}", impersonate="chrome110", timeout=5)
        if res.status_code == 200:
            data = res.json()
            return {
                "title": data.get("title"),
                "thumbnail": data.get("thumbnail_url"),
                "uploader": data.get("author_unique_id") or data.get("author_name"),
            }
    except Exception:
        pass
    return {}


def get_tiktok_metadata(url: str):
    info = extract_via_snaptik(url)
    if not info:
        info = extract_via_ytdlp(url)
    
    if info:
        oembed = fetch_oembed_metadata(url)
        if oembed.get("thumbnail"):
            info["thumbnail"] = oembed["thumbnail"]
        if oembed.get("title") and (not info.get("title") or info.get("title") == "TikTok Video"):
            info["title"] = oembed["title"]
        if oembed.get("uploader") and not info.get("uploader"):
            info["uploader"] = oembed["uploader"]
        return info

    raise ValueError("Could not extract TikTok video info. Please verify the link.")
