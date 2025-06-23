from aiogram import types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.i18n import gettext as _
from .url import TaskManager

from loader import dp


@dp.message(Command("help"))
async def help_command(message: types.Message, state: FSMContext) -> None:
    user = message.from_user
    if user is None:
        return

    await message.answer(
        _(
            "<b>Hai, {name}! Saya di sini untuk membantu Anda</b>\n\n"
            "Berikut adalah perintah utama:\n"
            "  /start – Mulai menggunakan bot\n"
            "  /help – Tampilkan pesan bantuan ini\n"
            "  /settings – Pengaturan bot\n"
            "  /support – Dukung pembuat saya\n\n"
            "Saya dapat mengunduh media dari berbagai platform.\n"
            "Berikut yang saya dukung:\n\n"
            "<b>Platform Musik</b>\n"
            "  - Spotify\n"
            "  - Apple Music\n"
            "  - SoundCloud\n"
            "    Saya akan mengambil musik beserta judul, artis, dan sampul.\n\n"
            "<b>Platform Video</b>\n"
            "  - TikTok – Video dan gambar\n"
            "  - Facebook – Video dan gambar\n"
            "  - BiliBili – Dukungan video penuh (dengan batasan)\n"
            "  - Instagram – Reels dan postingan\n"
            "  - Twitter – Video dan gambar\n"
            "  - Reddit – Media dari postingan\n\n"
            "<b>Platform Seni</b>\n"
            "  - Pixiv – Saya bisa mengunduh ilustrasi untuk Anda\n\n"
            "  - Pinterest – Saya bisa mengunduh semua media untuk Anda\n"
            "Cukup kirimkan tautan — dan saya akan mengurus sisanya."
        ).format(name=user.first_name or user.username),
        parse_mode=ParseMode.HTML,
    )


@dp.message(Command("cancel"))
async def cancel_command(message: types.Message, state: FSMContext) -> None:
    user = message.from_user
    if user is None:
        return

    canceled = TaskManager().cancel_task(user.id)
    if canceled:
        await message.answer(_("Your download has been cancelled."))
    else:
        await message.answer(_("No active download task found to cancel."))
