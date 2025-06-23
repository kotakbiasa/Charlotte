from aiogram import Bot, F
from aiogram.enums.chat_member_status import ChatMemberStatus
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from aiogram.utils.i18n import gettext as _

from filters.settings_filter import EmojiTextFilter
from functions.db import db_change_lang
from main import custom_i18n
from loader import dp


class Settings(StatesGroup):
    language = State()


@dp.message(Command("settings"))
async def settings_command(message: Message, state: FSMContext) -> None:
    chat = message.chat

    if chat.type == "group" or chat.type == "supergroup":
        is_admin_or_owner = await check_if_admin_or_owner(
            message.bot, chat.id, message.from_user.id
        )
        if not is_admin_or_owner:
            await message.answer(_("Anda tidak memiliki hak untuk mengubah pengaturan ini!"))
            return

    button_lang_eng = KeyboardButton(text="English 🇺🇲")
    button_lang_id = KeyboardButton(text="Indonesia 🇮🇩")
    button_cancel = KeyboardButton(text="Batal ❌")

    language_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [button_lang_eng, button_lang_id],
            # Jika ada tombol lain, tambahkan di sini
            [button_cancel],
        ],
        resize_keyboard=True,
    )

    await state.set_state(Settings.language)
    await message.answer(_("Pilih bahasa!"), reply_markup=language_keyboard)


@dp.message(Settings.language, EmojiTextFilter("English 🇺🇲"))
async def process_settings_english(message: Message, state: FSMContext) -> None:
    await state.clear()
    await db_change_lang(message.chat.id, "en")

    custom_i18n.clear_cache(message.chat.id)

    await message.answer(
        "Your language has been changed to English", reply_markup=ReplyKeyboardRemove()
    )


@dp.message(Settings.language, EmojiTextFilter("Indonesia 🇮🇩"))
async def process_settings_indonesia(message: Message, state: FSMContext) -> None:
    await state.clear()
    await db_change_lang(message.chat.id, "id")

    custom_i18n.clear_cache(message.chat.id)

    await message.answer(
        "Bahasa Anda telah diubah ke Bahasa Indonesia",
        reply_markup=ReplyKeyboardRemove(),
    )


@dp.message(Settings.language, EmojiTextFilter("Batal ❌"))
async def process_settings_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(_("Dibatalkan!"), reply_markup=ReplyKeyboardRemove())


@dp.message(Command("cancel"))
@dp.message(F.text.casefold() == "batal")
async def cancel_handler(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is None:
        return

    await state.clear()
    await message.answer(_("Dibatalkan!"), reply_markup=ReplyKeyboardRemove())


async def check_if_admin_or_owner(bot: Bot, chat_id: int, user_id: int) -> bool:
    chat_member = await bot.get_chat_member(chat_id, user_id)

    if chat_member.status in [ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR]:
        return True
    else:
        return False