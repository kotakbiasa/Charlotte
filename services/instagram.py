import asyncio
import logging
import os
import re
from functools import partial
from pathlib import Path
from typing import List, Tuple
import instaloader
from concurrent.futures import ThreadPoolExecutor

import aiofiles
import aiohttp
import yt_dlp

from models.media_models import MediaContent, MediaType
from services.base_service import BaseService
from utils.error_handler import BotError, ErrorCode

logger = logging.getLogger(__name__)


class InstagramService(BaseService):
    name = "Instagram"
    _download_executor = ThreadPoolExecutor(max_workers=5)

    def __init__(self, output_path: str = "other/downloadsTemp"):
        self.output_path = output_path
        os.makedirs(self.output_path, exist_ok=True)
        self.yt_dlp_opts = {
            "outtmpl": f"{self.output_path}/%(id)s_{yt_dlp.utils.sanitize_filename('%(title)s')}.%(ext)s",
            "quiet": True,
        }

    def is_supported(self, url: str) -> bool:
        return bool(
            re.match(
                r"https://www\.instagram\.com/(?:p|reel|tv|stories)/([A-Za-z0-9_-]+)/",
                url,
            )
        )

    def is_playlist(self, url: str) -> bool:
        return False

    async def download(self, url: str) -> List[MediaContent]:
        try:
            media = await download_instagram_with_api(url, self.output_path)
            if not media:
                raise BotError(
                    code=ErrorCode.DOWNLOAD_FAILED,
                    message="Failed to download Instagram media via API.",
                    url=url,
                    critical=True,
                    is_logged=True,
                )
            return [media]
        except BotError as e:
            raise e
        except Exception as e:
            raise BotError(
                code=ErrorCode.DOWNLOAD_FAILED,
                message=f"Instagram: {e}",
                url=url,
                critical=True,
                is_logged=True,
            )

async def download_instagram_with_api(url: str, output_path: str) -> Optional[MediaContent]:
    api_url = f"https://insta-dl.hazex.workers.dev/?url={url}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                if data.get("error"):
                    return None
                result = data.get("result", {})
                media_url = result.get("url")
                ext = result.get("extension", "mp4")
                if not media_url:
                    return None
                filename = f"ig_api_{os.urandom(4).hex()}.{ext}"
                filepath = os.path.join(output_path, filename)
                async with session.get(media_url) as mresp:
                    if mresp.status != 200:
                        return None
                    async with aiofiles.open(filepath, "wb") as f:
                        await f.write(await mresp.read())
                return MediaContent(
                    type=MediaType.VIDEO if ext in ("mp4", "mov") else MediaType.PHOTO,
                    path=Path(filepath)
                )
    except Exception as e:
        logger.error(f"Instagram API download failed: {e}")
        return None

async def run_in_thread(func, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(func, *args))


async def download_media(session, url, filename) -> str:
    try:
        async with session.get(url) as response:
            if response.status == 200:
                async with aiofiles.open(filename, "wb") as f:
                    await f.write(await response.read())
                return filename
            else:
                raise BotError(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=f"Failed to download Instagram media: {response.status}",
                    url=url,
                    critical=False,
                    is_logged=True,
                )
    except BotError as e:
        raise e
    except Exception as e:
        raise BotError(
            code=ErrorCode.DOWNLOAD_FAILED,
            message=f"Instagram download: {type(e).__name__} – {e}",
            url=url,
            critical=True,
            is_logged=True,
        )


async def download_all_media(media_urls, filenames):
    async with aiohttp.ClientSession() as session:
        tasks = []
        for url, name in zip(media_urls, filenames):
            if name.endswith(".mp4"):
                tasks.append(download_video_with_ytdlp(url, name))
            else:
                tasks.append(download_media(session, url, name))
        results = await asyncio.gather(*tasks)
        return results

async def download_video_with_ytdlp(url: str, filename: str) -> str:
    try:
        def _download():
            ydl_opts = {
                'outtmpl': "other/downloadsTemp/%(id)s.%(ext)s",
                'quiet': True,
                'format': 'mp4',
                'merge_output_format': 'mp4',
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)

        downloaded_path = await run_in_thread(_download)

        final_path = os.path.join("other/downloadsTemp", filename)
        os.rename(downloaded_path, final_path)
        return final_path

    except Exception as e:
        raise BotError(
            code=ErrorCode.DOWNLOAD_FAILED,
            message=f"yt-dlp failed: {type(e).__name__} – {e}",
            url=url,
            critical=True,
            is_logged=True,
        )

def clean_dict(d):
    return {str(k): str(v) for k, v in d.items() if v is not None and k is not None}
async def run_in_thread(func, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(func, *args))


async def download_media(session, url, filename) -> str:
    try:
        async with session.get(url) as response:
            if response.status == 200:
                async with aiofiles.open(filename, "wb") as f:
                    await f.write(await response.read())
                return filename
            else:
                raise BotError(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=f"Failed to download Instagram media: {response.status}",
                    url=url,
                    critical=False,
                    is_logged=True,
                )
    except BotError as e:
        raise e
    except Exception as e:
        raise BotError(
            code=ErrorCode.DOWNLOAD_FAILED,
            message=f"Instagram download: {type(e).__name__} – {e}",
            url=url,
            critical=True,
            is_logged=True,
        )


async def download_all_media(media_urls, filenames):
    async with aiohttp.ClientSession() as session:
        tasks = []
        for url, name in zip(media_urls, filenames):
            if name.endswith(".mp4"):
                tasks.append(download_video_with_ytdlp(url, name))
            else:
                tasks.append(download_media(session, url, name))
        results = await asyncio.gather(*tasks)
        return results

async def download_video_with_ytdlp(url: str, filename: str) -> str:
    try:
        def _download():
            ydl_opts = {
                'outtmpl': "other/downloadsTemp/%(id)s.%(ext)s",
                'quiet': True,
                'format': 'mp4',
                'merge_output_format': 'mp4',
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)

        downloaded_path = await run_in_thread(_download)

        final_path = os.path.join("other/downloadsTemp", filename)
        os.rename(downloaded_path, final_path)
        return final_path

    except Exception as e:
        raise BotError(
            code=ErrorCode.DOWNLOAD_FAILED,
            message=f"yt-dlp failed: {type(e).__name__} – {e}",
            url=url,
            critical=True,
            is_logged=True,
        )

def clean_dict(d):
    return {str(k): str(v) for k, v in d.items() if v is not None and k is not None}
