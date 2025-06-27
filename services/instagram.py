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
        result = []
        try:
            # Coba API eksternal untuk reel/video
            if re.match(r'https://www\.instagram\.com/reel/([A-Za-z0-9_-]+)', url):
                api_result = await download_instagram_with_api(url, self.output_path)
                if api_result:
                    result.append(api_result)
                    return result
                # fallback ke yt-dlp jika API gagal

            media_urls, filenames = await self._get_instagram_post(url)

            downloaded = await download_all_media(media_urls, filenames)

            if isinstance(downloaded, BotError):
                raise BotError(
                    code=ErrorCode.DOWNLOAD_FAILED,
                    message=f"{downloaded.message}",
                    url=url,
                    critical=True,
                    is_logged=True,
                )

            for path in downloaded:
                if isinstance(path, str):
                    result.append(
                        MediaContent(
                            type=MediaType.PHOTO if path.endswith(".jpg") else MediaType.VIDEO,
                            path=Path(path)
                        )
                    )

            return result
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

    async def _get_instagram_post(self, url: str) -> Tuple[List[str], List[str]]:
        pattern = r'https://www\.instagram\.com/(?:p|reel)/([A-Za-z0-9_-]+)'
        match = re.match(pattern, url)
        if match:
            shortcode = match.group(1)
        else:
            raise ValueError("Invalid Instagram URL")

        try:
            loop = asyncio.get_event_loop()

            L = instaloader.Instaloader()

            post = await loop.run_in_executor(
                self._download_executor,
                lambda: instaloader.Post.from_shortcode(L.context, shortcode)
            )

            if post is None:
                raise BotError(
                    code=ErrorCode.INVALID_URL,
                    message="Instagram: Post not found",
                    url=url,
                    critical=False,
                    is_logged=False,
                )

            images = []
            filenames = []

            if post.typename == 'GraphSidecar':
                for i, node in enumerate(post.get_sidecar_nodes(), start=1):
                    images.append(node.display_url)
                    filenames.append(f"{i}_{shortcode}.jpg")
            elif post.typename == 'GraphImage':
                images.append(post.url)
                filenames.append(f"{shortcode}.jpg")
            elif post.typename == 'GraphVideo':
                images.append(post.video_url)
                filenames.append(f"{shortcode}.mp4")
            else:
                raise BotError(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=f"Unknown post type: {post.typename}",
                    url=url,
                    critical=False,
                    is_logged=True,
                )

            return images, filenames
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

async def download_instagram_with_api(url: str, output_path: str) -> MediaContent | None:
    import aiohttp
    from models.media_models import MediaContent, MediaType
    from pathlib import Path

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
                video_url = result.get("url")
                ext = result.get("extension", "mp4")
                if not video_url:
                    return None
                filename = f"ig_api_{os.urandom(4).hex()}.{ext}"
                filepath = os.path.join(output_path, filename)
                async with session.get(video_url) as vresp:
                    if vresp.status != 200:
                        return None
                    f = await aiofiles.open(filepath, "wb")
                    await f.write(await vresp.read())
                    await f.close()
                return MediaContent(
                    type=MediaType.VIDEO,
                    path=Path(filepath)
                )
    except Exception:
        return None

def clean_dict(d):
    return {str(k): str(v) for k, v in d.items() if v is not None and k is not None}
