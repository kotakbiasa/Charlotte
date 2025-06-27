import re
import aiohttp
import os
from typing import Optional
from models.media_models import MediaContent, MediaType
from pathlib import Path

async def download_instagram_api_pyrogram_style(url: str) -> Optional[MediaContent]:
    """
    Download Instagram media using the same API and logic as the Pyrogram example.
    """
    api_url = f"https://insta-dl.hazex.workers.dev/?url={url}"
    async with aiohttp.ClientSession() as session:
        resp = await session.get(api_url)
        if resp.status != 200:
            return None
        try:
            result = await resp.json()
            if result.get("error"):
                return None
            data = result["result"]
            video_url = data["url"]
            ext = data.get("extension", "mp4")
            filename = f"ig_api_{os.urandom(4).hex()}.{ext}"
            filepath = os.path.join("other/downloadsTemp", filename)
            vresp = await session.get(video_url)
            if vresp.status != 200:
                return None
            import aiofiles
            async with aiofiles.open(filepath, "wb") as f:
                await f.write(await vresp.read())
            return MediaContent(
                type=MediaType.VIDEO if ext in ("mp4", "mov") else MediaType.PHOTO,
                path=Path(filepath)
            )
        except Exception:
            return None