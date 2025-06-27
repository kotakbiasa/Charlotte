import asyncio
import logging
import os
import re
from functools import partial
from pathlib import Path
from typing import List, Tuple, Optional
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

    def __init__(self, output_path: str = "other/downloadsTemp"):
        self.output_path = output_path
        os.makedirs(self.output_path, exist_ok=True)

    def is_supported(self, url: str) -> bool:
        return bool(
            re.match(
                r"^(https?://)?(www\.)?(instagram\.com|instagr\.am)/.*$",
                url,
            )
        )

    def is_playlist(self, url: str) -> bool:
        return False

    async def download(self, url: str) -> List[MediaContent]:
        try:
            api_url = f"https://insta-dl.hazex.workers.dev/?url={url}"
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as resp:
                    if resp.status != 200:
                        raise BotError(
                            code=ErrorCode.DOWNLOAD_FAILED,
                            message="Failed to connect to Instagram API.",
                            url=url,
                            critical=True,
                            is_logged=True,
                        )
                    result = await resp.json()
            if result.get("error"):
                raise BotError(
                    code=ErrorCode.DOWNLOAD_FAILED,
                    message="Instagram API returned error.",
                    url=url,
                    critical=True,
                    is_logged=True,
                )
            data = result.get("result", {})
            video_url = data.get("url")
            duration = data.get("duration")
            quality = data.get("quality")
            ext = data.get("extension", "mp4")
            size = data.get("formattedSize")
            if not video_url:
                raise BotError(
                    code=ErrorCode.DOWNLOAD_FAILED,
                    message="No media URL found in API response.",
                    url=url,
                    critical=True,
                    is_logged=True,
                )
            filename = f"ig_api_{os.urandom(4).hex()}.{ext}"
            filepath = os.path.join(self.output_path, filename)
            async with aiohttp.ClientSession() as session:
                async with session.get(video_url) as vresp:
                    if vresp.status != 200:
                        raise BotError(
                            code=ErrorCode.DOWNLOAD_FAILED,
                            message="Failed to download media file.",
                            url=url,
                            critical=True,
                            is_logged=True,
                        )
                    async with aiofiles.open(filepath, "wb") as f:
                        await f.write(await vresp.read())
            # Optionally, you can attach metadata to MediaContent if needed
            return [
                MediaContent(
                    type=MediaType.VIDEO if ext in ("mp4", "mov") else MediaType.PHOTO,
                    path=Path(filepath)
                )
            ]
        except BotError as e:
            raise e
        except Exception as e:
            logger.error(f"Instagram API download failed: {e}")
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

def clean_dict(d):
    return {str(k): str(v) for k, v in d.items() if v is not None and k is not None}
    return {str(k): str(v) for k, v in d.items() if v is not None and k is not None}
