from aiogram import Router, types
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.sequence import pad_sequences
import numpy as np
import joblib
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- Настройки доступа к Google Sheets ---
scope = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file(
    "../venv/citizen-requests-476714-da2e73c20db3.json", scopes=scope
)
client = gspread.authorize(creds)
SHEET_ID = "1v3MMitqxBkEGqilOsRh_RouepCUN15JHKIvsyK7OrTU"
sheet = client.open_by_key(SHEET_ID).sheet1

# --- Функция добавления записи в Google Sheets ---
def add_to_google_sheets(text, category, probs_dict):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    probs_values = [f"{probs_dict.get(label, 0):.2f}%" for label in label_encoder.classes_]
    new_row = [timestamp, text, category] + probs_values
    sheet.append_row(new_row, value_input_option="USER_ENTERED")

# --- Инициализация роутера ---
user_private_router = Router()

# --- Загрузка модели и вспомогательных объектов ---
model = load_model("../venv/best_model.h5")
tokenizer = joblib.load("../venv/best_tokens.pkl")
label_encoder = joblib.load("../venv/best_labels.pkl")

max_len = 100

# --- Функция классификации текста ---
def classify_text_with_probs(text: str):
    seq = pad_sequences(tokenizer.texts_to_sequences([text]), maxlen=max_len)
    probs = model.predict(seq)[0]
    top_idx = np.argmax(probs)
    top_label = label_encoder.inverse_transform([top_idx])[0]
    probs_dict = dict(zip(label_encoder.classes_, np.round(probs * 100, 2)))
    return top_label, probs_dict


# --- Команда /start ---
@user_private_router.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer(
        "👋 Привет! Я помощник оператора приёма обращений.\n\n"
        "Отправьте текст обращения — я обработаю его и занесу в базу (Google Sheets).\n"
        "Используйте /menu, чтобы увидеть все доступные команды."
    )


# --- Команда /menu ---
@user_private_router.message(Command("menu"))
async def menu_cmd(message: types.Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Оставить обращение", callback_data="request")],
            [InlineKeyboardButton(text="📊 Последние обращения", callback_data="latest")],
            [InlineKeyboardButton(text="ℹ️ О системе", callback_data="about")],
        ]
    )
    await message.answer(
        "📋 Главное меню:\n\n"
        "Выберите действие из списка ниже.",
        reply_markup=keyboard,
    )


# --- Функция показа последних обращений ---
async def show_latest_entries(message: types.Message):
    try:
        records = sheet.get_all_values()

        if len(records) <= 1:
            await message.answer("📭 Пока нет обращений.")
            return

        data = records[1:]  # пропускаем заголовок
        latest = data[-5:]  # последние 5 строк

        text_lines = []
        for r in latest:
            timestamp = r[0] if len(r) > 0 else "—"
            text = r[1] if len(r) > 1 else "(нет текста)"
            category = r[2] if len(r) > 2 else "(не определено)"
            text_lines.append(f"🕒 <b>{timestamp}</b>\n📄 {text}\n📂 Категория: {category}")

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_latest")],
                [InlineKeyboardButton(
                    text="📊 Открыть таблицу",
                    url=f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
                )]
            ]
        )

        await message.answer(
            "🧾 <b>Последние обращения:</b>\n\n" + "\n\n".join(text_lines),
            parse_mode="HTML",
            reply_markup=keyboard,
        )

    except Exception as e:
        await message.answer(f"⚠️ Ошибка при чтении данных: {e}")


# --- Команда /latest ---
@user_private_router.message(Command("latest"))
async def latest_cmd(message: types.Message):
    await show_latest_entries(message)


# --- Callback для кнопки обновления ---
@user_private_router.callback_query(lambda c: c.data == "refresh_latest")
async def refresh_latest_callback(callback: types.CallbackQuery):
    await show_latest_entries(callback.message)
    await callback.answer("✅ Обновлено")


# --- Callback для кнопки «Оставить обращение» ---
@user_private_router.callback_query(lambda c: c.data == "request")
async def request_callback(callback: types.CallbackQuery):
    await callback.message.answer(
        "📝 Введите текст обращения — бот обработает и добавит его в базу."
    )
    await callback.answer()


# --- Callback для кнопки «О системе» ---
@user_private_router.callback_query(lambda c: c.data == "about")
async def about_callback(callback: types.CallbackQuery):
    await callback.message.answer(
        "ℹ️ Этот бот помогает операторам:\n\n"
        "• Принимать обращения граждан\n"
        "• Классифицировать их автоматически (ML)\n"
        "• Сохранять данные в Google Sheets\n"
        "• Просматривать свежие записи через /latest",
        parse_mode="HTML",
    )
    await callback.answer()


# --- Обработка обращений ---
@user_private_router.message()
async def handle_message(message: types.Message):
    user_text = message.text.strip()
    if not user_text:
        await message.answer("❗ Пожалуйста, введите текст обращения.")
        return

    # Классификация
    category, probs_dict = classify_text_with_probs(user_text)

    # Добавление в таблицу
    add_to_google_sheets(user_text, category, probs_dict)

    # Ответ пользователю
    await message.answer(
        "✅ Обращение принято и передано оператору.\n"
        "📊 Запись добавлена в Google Sheets.\n\n"
        "Чтобы просмотреть последние обращения, используйте команду /latest.",
        parse_mode="HTML",
    )
