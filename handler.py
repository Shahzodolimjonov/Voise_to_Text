import os
import logging
import re
import subprocess
import traceback
import speech_recognition as sr
from aiogram import Bot, Router, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from database import async_session, VoiceMessage

logger = logging.getLogger(__name__)

router = Router()
recognizer = sr.Recognizer()


async def _clear():
    files = ['audio.ogg', 'audio.wav']
    for file in files:
        if os.path.exists(file):
            os.remove(file)


async def voice_recognizer(language: str) -> str:
    logger.info(f"Starting recognition for language: {language}")
    try:
        subprocess.run(['ffmpeg', '-i', 'audio.ogg', '-ar', '16000', '-ac', '1', 'audio.wav', '-y'], check=True)

        with sr.AudioFile('audio.wav') as source:
            audio = recognizer.record(source)
            text = recognizer.recognize_google(audio, language=language)
            formatted_text = format_card_number(text)
            logger.info(f"Recognized text ({language}): {text}")
            return formatted_text
    except sr.UnknownValueError:
        logger.error(f"Could not understand audio for language: {language}")
        return "Matnni tanib bo'lmadi."
    except sr.RequestError as e:
        logger.error(f"Google API error: {e}")
        return "Matnni tanib bo'lmadi."
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return "Matnni tanib bo'lmadi."


def format_card_number(text):
    numbers = ''.join([c for c in text if c.isdigit()])
    formatted = ' '.join([numbers[i:i+4] for i in range(0, len(numbers), 4)])
    return formatted


async def save_to_db(user_id, username, language, text):
    async with async_session() as session:
        try:
            logger.info(f"Saving to DB: user_id={user_id}, username={username}, language={language}, text={text}")
            message = VoiceMessage(
                user_id=user_id,
                username=username,
                language=language,
                text=text
            )
            session.add(message)
            await session.commit()
            logger.info("Data successfully saved to the database.")
        except Exception as e:
            logger.error(f"Database error: {e}")
            await session.rollback()


@router.message(Command("start"))
async def start_message(message: types.Message):
    await message.answer("Salom! Menga Uzbek, Rus tillarida ovozli xabar yuboring. Men uni matn qilib beraman.\n"
                         "Здравствуйте! Отправьте мне голосовое сообщение на узбекском и русском языках."
                         " Я преобразую его в текст.")


@router.message(lambda msg: msg.voice is not None)
async def voice_handler(message: types.Message, bot: Bot):
    logger.info("Voice message received")
    file_id = message.voice.file_id
    file = await bot.get_file(file_id)

    if message.voice.file_size >= 715000:
        await message.answer("Fayl hajmi juda katta.")
        return

    file_path = file.file_path
    downloaded_file = await bot.download_file(file_path)
    with open("audio.ogg", "wb") as f:
        f.write(downloaded_file.getvalue())

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇺🇿 O‘zbekcha", callback_data="uzbek")],
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="russian")]
    ])
    await message.answer("Tilni tanlang:", reply_markup=markup)


@router.callback_query()
async def process_language_choice(callback: types.CallbackQuery):
    print(callback.data)
    language = "uz_UZ" if callback.data == "uzbek" else "ru_RU"
    text = await voice_recognizer(language)
    print(text)
    await callback.message.answer(text)
    if text != "Matnni tanib bo'lmadi.":
        await save_to_db(
            user_id=callback.from_user.id,
            username=callback.from_user.username,
            language=language,
            text=text
        )
    await _clear()
