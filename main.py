import os
import logging
import subprocess
from enum import Enum

import speech_recognition as sr
from fastapi import FastAPI, File, UploadFile, HTTPException, Form

app = FastAPI()
recognizer = sr.Recognizer()
logger = logging.getLogger(__name__)


def _clear():
    files = ['audio.ogg', 'audio.wav']
    for file in files:
        if os.path.exists(file):
            os.remove(file)


def format_card_number(text):
    numbers = ''.join([c for c in text if c.isdigit()])
    formatted = ' '.join([numbers[i:i+4] for i in range(0, len(numbers), 4)])
    return formatted


class LanguageEnum(str, Enum):
    uz = "uz_UZ"
    ru = "ru_RU"


def convert_audio_to_text(file_path: str, language: str) -> str:
    try:
        subprocess.run(['ffmpeg', '-i', file_path, '-ar', '16000', '-ac', '1', 'audio.wav', '-y'], check=True)

        with sr.AudioFile('audio.wav') as source:
            audio = recognizer.record(source)
            text = recognizer.recognize_google(audio, language=language)
            formatted_text = format_card_number(text)
            print(formatted_text)
            return formatted_text

    except sr.UnknownValueError:
        raise HTTPException(status_code=400, detail="Audio tanib bo'lmadi.")
    except sr.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Google API xatosi: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Noma'lum xato: {e}")
    finally:
        _clear()


@app.post("/recognize/")
async def recognize_voice(file: UploadFile = File(...), language: LanguageEnum = Form(...)):
    allowed_content_types = ["video/ogg", "audio/ogg", "audio/mpeg", "audio/wav", "audio/x-wav"]

    print("file", file.content_type)

    if file.content_type not in allowed_content_types:
        raise HTTPException(
            status_code=400,
            detail="shu formatdagi audio qabul qilinadi: ogg, mp3, wav"
        )
    file_extension_map = {
        "video/ogg": ".ogg",
        "audio/ogg": ".ogg",
        "audio/mpeg": ".mp3",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
    }
    file_extension = file_extension_map.get(file.content_type, "")
    file_path = f"{file_extension}"
    with open(file_path, "wb") as audio_file:
        audio_file.write(file.file.read())

    try:
        text = convert_audio_to_text(file_path, language.value)
        return {"language": language.value, "text": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

