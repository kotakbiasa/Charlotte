import logging
import os
import asyncio
import re

import yt_dlp
from yt_dlp.utils import sanitize_filename
import urllib.request

from utils import update_metadata, search_music, get_all_tracks_from_playlist_deezer


class DeezerDownloader:
    def __init__(self, output_path: str = "other/downloadsTemp"):
        """
        Initialize the Deezer downloader with an output path for downloads.

        Parameters:
        ----------
        output_path : str, optional
            The directory where downloaded files will be saved (default is "other/downloadsTemp").
        """
        self.output_path = output_path
        os.makedirs(self.output_path, exist_ok=True)
        self.yt_dlp_options = {
            # 'sponsorblock-mark': "music_offtopic, sponsor, selfpromo, interaction, intro, outro, preview",
            # 'sponsorblock-remove': "music_offtopic, sponsor, selfpromo, interaction, intro, outro, preview",
            "format": "m4a/bestaudio/best",
            "outtmpl": f"{output_path}/{sanitize_filename('%(title)s')}",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                },
            ],
        }

    async def download(self, url: str, format: str = "audio"):
        """
        Downloads a single track or playlist

        Parameters:
        ----------
        url : str
            The Deezer URL to download.
        format : str
            The format of the download (Crutch, not used).

        Returns:
        -------
        AsyncGenerator
            Returns an async generator yielding audio and cover filenames or None if an error occurs.
        """
        try:
            if re.match(r"https?://deezer\.page\.link/([\w-]+)", url):
                # Single track
                async for result in self._download_single_track(url):
                    yield result
            elif re.match(r"https:\/\/www\.deezer\.com\/[a-z]{2}\/playlist\/\d+", url):
                # Playlist
                async for result in self._download_playlist(url):
                    yield result
            else:
                logging.error(f"Unsupported URL: {url}")
                yield None, None
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            yield None, None

    async def _download_single_track(self, url: str):
        """
        Downloads a single Deezer track.

        Parameters:
        ----------
        url : str
            The URL of the Deezer track to download.

        Yields:
        -------
        tuple
            Yields the file paths of the downloaded audio and cover image, or None if an error occurs.
        """
        yield await self._download_track(url)

    async def _download_playlist(self, url: str):
        """
        Downloads a Deezer playlist by iterating over each track in the playlist.

        Parameters:
        ----------
        url : str
            The URL of the Deezer playlist to download.

        Yields:
        -------
        tuple
            Yields the file paths of the downloaded audio and cover image for each track, or None if an error occurs.
        """
        tracks = get(url)
        for track in tracks:
            yield await self._download_track(track)

    async def _download_track(
        self, url: str, output_path: str = "other/downloadsTemp", format: str = "audio"
    ):
        """
        Downloads audio from YouTube based on a Deezer track's artist and title.

        Given a Deezer URL, the function retrieves the artist and title, searches for a corresponding YouTube video,
        and downloads the audio if the duration is 10 minutes or less. After the download, it updates the metadata and
        adds the cover image from the Deezer track.

        Parameters:
        -----------
        url : str
            The Deezer track URL.
        output_path : str, optional
            Directory where the downloaded audio and cover image will be saved (default is "other/downloadsTemp").
        format : str, optional
            Format of the media to download. For this function, only "audio" is supported (default is "audio").

        Returns:
        --------
        tuple
            Returns a tuple containing:
            - audio_filename (str): The path to the downloaded audio file.
            - cover_filename (str): The path to the downloaded cover image.
        """
        ydl = yt_dlp.YoutubeDL(self.yt_dlp_options)

        deezer_track_info_dict = await asyncio.to_thread(
            ydl.extract_info, url, download=False
        )

        artist = deezer_track_info_dict.get("description").split("-")[0].strip()
        title = deezer_track_info_dict.get("title").strip()
        cover_url = deezer_track_info_dict.get("thumbnail")

        video_link = await search_music(artist, title)

        try:
            info_dict = await asyncio.to_thread(
                ydl.extract_info, video_link, download=False
            )
            ydl_title = info_dict.get("title")

            await asyncio.to_thread(ydl.download, [video_link])

            audio_filename = os.path.join(
                output_path, f"{sanitize_filename(ydl_title)}.mp3"
            )
            cover_filename = os.path.join(
                output_path, f"{sanitize_filename(ydl_title)}.jpg"
            )

            urllib.request.urlretrieve(cover_url, cover_filename)

            update_metadata(audio_filename, artist, title, cover_filename)

            if os.path.exists(audio_filename) and os.path.exists(cover_filename):
                return audio_filename, cover_filename

        except Exception as e:
            logging.error(f"Error downloading YouTube Audio: {str(e)}")
            return None
