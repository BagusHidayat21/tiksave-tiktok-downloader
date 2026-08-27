# TikTok metadata and media extraction module supporting both videos and photo sliders.
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
import hashlib
import base64

import imageio_ffmpeg

try:
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "venv", "bin", "ffmpeg")


def resolve_canonical_url(url: str) -> str:
    """Resolve shortened TikTok URLs like vt.tiktok.com or vm.tiktok.com to canonical URL."""
    try:
        if any(domain in url for domain in ["vt.tiktok.com", "vm.tiktok.com", "/t/"]):
            session = requests.Session()
            res = session.head(url, allow_redirects=True, impersonate="chrome110", timeout=6)
            return res.url
    except Exception:
        pass
    return url


def is_slider_url(url: str) -> bool:
    """Check if the provided TikTok URL represents a photo slider/carousel post."""
    return "/photo/" in url


def solve_snaptik_token(token_id: str, token_p: str) -> str:
    """Solve the cryptographic challenge required by Snaptik API."""
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
    """Extract media details and images/video using Snaptik API."""
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
                video_data = data.get("data") or data
                
                # Check for carousel / slider post
                data_type = video_data.get("type", "")
                raw_images = video_data.get("images") or video_data.get("photos") or []
                is_slider = data_type in ["carousel", "slide", "photo", "image"] or bool(raw_images) or is_slider_url(url)

                images = []
                for item in raw_images:
                    img_url = None
                    if isinstance(item, str):
                        img_url = item
                    elif isinstance(item, dict):
                        img_url = item.get("display") or item.get("url") or item.get("thumbnail") or item.get("downloadUrl")
                    if img_url:
                        if img_url.startswith("/"):
                            img_url = "https://snaptik.app" + img_url
                        images.append(img_url)

                dl_url = video_data.get("downloadUrl") or video_data.get("download_url") or video_data.get("hdDownloadUrl") or video_data.get("url") or (video_data.get("urls", [None])[0] if isinstance(video_data.get("urls"), list) else None)
                if dl_url and dl_url.startswith("/"):
                    dl_url = "https://snaptik.app" + dl_url

                audio_url = video_data.get("musicUrl") or video_data.get("audioUrl") or video_data.get("music") or video_data.get("audio")
                if audio_url and isinstance(audio_url, dict):
                    audio_url = audio_url.get("url") or audio_url.get("playUrl")

                thumb = video_data.get("thumbnail") or video_data.get("cover")
                if not thumb and images:
                    thumb = images[0]

                return {
                    "title": video_data.get("title") or video_data.get("description") or "TikTok Post",
                    "thumbnail": thumb,
                    "duration": video_data.get("duration") if not is_slider else 0,
                    "uploader": video_data.get("author", {}).get("nickname") or video_data.get("author", {}).get("unique_id") or "",
                    "download_url": dl_url,
                    "audio_url": audio_url,
                    "is_slider": is_slider,
                    "type": "slider" if is_slider else "video",
                    "images": images,
                    "source": "snaptik"
                }
    except Exception:
        pass
    return None


def solve_tiktok_waf_challenge(webpage: str):
    """Solve TikTok WAF Slardar challenge and return authentication cookies."""
    cs_m = re.search(r'id="cs"\s+class="([^"]+)"', webpage)
    wci_m = re.search(r'id="wci"\s+class="([^"]+)"', webpage)
    rci_m = re.search(r'id="rci"\s+class="([^"]+)"', webpage)
    rs_m = re.search(r'id="rs"\s+class="([^"]*)"', webpage)

    if not cs_m:
        return None

    try:
        cs_val = cs_m.group(1)
        pad = '=' * ((4 - len(cs_val) % 4) % 4)
        data = json.loads(base64.b64decode(cs_val + pad))
        base_hash = hashlib.sha256(base64.b64decode(data['v']['a']))
        expected = base64.b64decode(data['v']['c'])

        for i in range(1000001):
            h = base_hash.copy()
            h.update(str(i).encode())
            if h.digest() == expected:
                data['d'] = base64.b64encode(str(i).encode()).decode()
                break
        else:
            return None

        cookie_val = base64.b64encode(json.dumps(data, separators=(',', ':')).encode()).decode()
        wci_name = wci_m.group(1) if wci_m else '_wafchallengeid'
        cookies = {wci_name: cookie_val}
        if rci_m and rs_m and rs_m.group(1):
            cookies[rci_m.group(1)] = rs_m.group(1)
        return cookies
    except Exception:
        return None


def extract_via_tiktok_web(url: str):
    """Extract TikTok metadata and slider images directly from TikTok webpage."""
    try:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        res = session.get(url, headers=headers, impersonate="chrome120", timeout=8)
        webpage = res.text

        if "__UNIVERSAL_DATA_FOR_REHYDRATION__" not in webpage and "SIGI_STATE" not in webpage:
            cookies = solve_tiktok_waf_challenge(webpage)
            if cookies:
                res2 = session.get(url, headers=headers, cookies=cookies, impersonate="chrome120", timeout=8)
                webpage = res2.text

        images = []
        title = "TikTok Post"
        uploader = ""
        audio_url = None
        is_slider = is_slider_url(url)

        m = re.search(r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>', webpage)
        if m:
            try:
                data = json.loads(m.group(1))
                item_struct = (
                    data.get("__DEFAULT_SCOPE__", {})
                    .get("webapp.video-detail", {})
                    .get("itemInfo", {})
                    .get("itemStruct", {})
                )
                if item_struct:
                    title = item_struct.get("desc") or title
                    uploader = item_struct.get("author", {}).get("nickname") or item_struct.get("author", {}).get("uniqueId") or ""
                    audio_url = item_struct.get("music", {}).get("playUrl")
                    image_post = item_struct.get("imagePostInfo", {}) or item_struct.get("image_post_info", {})
                    if image_post and image_post.get("images"):
                        is_slider = True
                        for img in image_post.get("images", []):
                            urls = (
                                img.get("display_image", {}).get("url_list")
                                or img.get("imageURL", {}).get("urlList")
                                or img.get("url_list")
                            )
                            if urls and isinstance(urls, list) and len(urls) > 0:
                                images.append(urls[0])
            except Exception:
                pass

        if not images:
            m_sigi = re.search(r'<script id="SIGI_STATE"[^>]*>(.*?)</script>', webpage)
            if m_sigi:
                try:
                    sigi = json.loads(m_sigi.group(1))
                    item_module = sigi.get("ItemModule", {})
                    for _, item in item_module.items():
                        title = item.get("desc") or title
                        uploader = item.get("author") or uploader
                        audio_url = item.get("music", {}).get("playUrl") or audio_url
                        image_post = item.get("imagePostInfo", {}) or item.get("image_post_info", {})
                        if image_post and image_post.get("images"):
                            is_slider = True
                            for img in image_post.get("images", []):
                                urls = (
                                    img.get("display_image", {}).get("url_list")
                                    or img.get("imageURL", {}).get("urlList")
                                    or img.get("url_list")
                                )
                                if urls and isinstance(urls, list) and len(urls) > 0:
                                    images.append(urls[0])
                except Exception:
                    pass

        if images or is_slider:
            return {
                "title": title,
                "thumbnail": images[0] if images else None,
                "duration": 0,
                "uploader": uploader,
                "download_url": None,
                "audio_url": audio_url,
                "is_slider": is_slider,
                "type": "slider" if is_slider else "video",
                "images": images,
                "source": "tiktok_web"
            }
    except Exception:
        pass
    return None


def extract_via_ytdlp(url: str):
    """Extract media details using yt-dlp."""
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
            formats = info.get("formats", [])
            has_video_stream = any(f.get("vcodec") and f.get("vcodec") != "none" for f in formats)
            is_slider = is_slider_url(url) or is_slider_url(info.get("webpage_url", "")) or not has_video_stream
            
            audio_url = None
            for f in formats:
                if f.get("vcodec") == "none" and f.get("url"):
                    audio_url = f.get("url")
                    break

            raw_thumbnails = info.get("thumbnails", [])
            images = []
            if is_slider:
                for t in raw_thumbnails:
                    if t.get("url"):
                        images.append(t["url"])

            return {
                "title": info.get("title", "TikTok Post"),
                "thumbnail": info.get("thumbnail"),
                "duration": info.get("duration") if not is_slider else 0,
                "uploader": info.get("uploader") or info.get("creator") or "",
                "download_url": info.get("url") if has_video_stream else None,
                "audio_url": audio_url,
                "is_slider": is_slider,
                "type": "slider" if is_slider else "video",
                "images": images,
                "info_dict": info,
                "source": "ytdlp"
            }
    except Exception:
        pass
    return None


def fetch_oembed_metadata(url: str):
    """Fetch oEmbed basic metadata from TikTok API."""
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
    """Retrieve full TikTok post metadata, classifying post type as slider or video."""
    canonical_url = resolve_canonical_url(url)
    is_slider_by_url = is_slider_url(canonical_url) or is_slider_url(url)

    info = extract_via_snaptik(canonical_url)
    if not info or (is_slider_by_url and not info.get("images")):
        web_info = extract_via_tiktok_web(canonical_url)
        if web_info:
            if not info:
                info = web_info
            elif web_info.get("images"):
                info["images"] = web_info["images"]
                info["is_slider"] = True
                info["type"] = "slider"
                if not info.get("thumbnail") and web_info.get("thumbnail"):
                    info["thumbnail"] = web_info["thumbnail"]

    if not info:
        info = extract_via_ytdlp(canonical_url)

    if info:
        if is_slider_by_url:
            info["is_slider"] = True
            info["type"] = "slider"
            info["duration"] = 0

        oembed = fetch_oembed_metadata(canonical_url)
        if oembed.get("thumbnail") and not info.get("thumbnail"):
            info["thumbnail"] = oembed["thumbnail"]
        if oembed.get("title") and (not info.get("title") or info.get("title") in ["TikTok Video", "TikTok Post"]):
            info["title"] = oembed["title"]
        if oembed.get("uploader") and not info.get("uploader"):
            info["uploader"] = oembed["uploader"]
            
        return info

    raise ValueError("Could not extract TikTok info. Please verify the link.")
