import logging

from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.i18n import gettext as _

from functions.db import db_add_chat
from loader import dp

logger = logging.getLogger(__name__)


@dp.message(CommandStart())
async def start_command(message: Message, state: FSMContext):
    try:
        await db_add_chat(chat_id=message.chat.id, locale="en", anonime_statistic=0)

        await message.answer(
            _(
                "Halo!\n\n"
                "Senang sekali bisa berkenalan dengan Anda, {name}!\n\n"
                "Saya Sosmed Downloader - saya siap membantu Anda mengunduh berbagai konten dari media sosial.\n\n"
                "Gunakan _/help_ untuk mengetahui informasi lebih lanjut tentang saya, daftar perintah, dan fitur lainnya!\n\n"
                "Jika ada kendala, silakan hubungi @KotakBiasa, atau akan lebih baik jika Anda mengirimkan tautan yang gagal diunduh🧡\n\n"
                "P.S.: Tersedia juga Sosmed Downloader Basement, tempat update terbaru atau status layanan di @KotakBiasaCH"
            ).format(name=message.from_user.first_name),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as err:
        logger.error(f"Error handling /start command: {err}")
