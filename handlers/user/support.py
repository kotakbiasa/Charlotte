from aiogram import types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.i18n import gettext as _

from loader import dp


@dp.message(Command("support"))
async def support_handler(message: types.Message, state: FSMContext):
    answer_message = _(
        "Setelah dipikir-pikir, saya memberanikan diri meninggalkan tautan untuk mendukung proyek ini. Jika Anda ingin meningkatkan kinerja Sosmed Downloader, silakan gunakan tautan ini. Setiap rupiah membantu Sosmed Downloader tetap berjalan di server yang baik – khusus untuk Anda. Anda tidak wajib membayar. Hanya jika Anda benar-benar ingin!!!!\n"
    )

    await message.answer(answer_message, parse_mode=ParseMode.HTML)
