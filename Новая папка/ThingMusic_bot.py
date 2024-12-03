import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
import deezer

# Установите токен Telegram-бота
API_TOKEN = 'ВАШ_ТОКЕН'

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)

# Создаем объекты бота и диспетчера
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Инициализация клиента Deezer
deezer_client = deezer.Client()

# Виртуальные базы данных
user_playlists = {}
user_history = {}

OWNER_ID = "ВАШ_TELEGRAM_ID"  # Ваш Telegram ID для админ-функций

# Команда /start
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_playlists:
        user_playlists[user_id] = []
    if user_id not in user_history:
        user_history[user_id] = []

    await message.reply(
        "Привет! Напиши название трека, чтобы найти его. Используй /help для помощи.\n"
        "Теперь вы можете делиться своими плейлистами с друзьями! Используйте /share для генерации ссылки на свой плейлист."
    )

# Команда /help
@dp.message_handler(commands=['help'])
async def help_command(message: types.Message):
    await message.reply(
        "📌 Доступные команды:\n"
        "/start - Перезапустить бота\n"
        "/playlist - Посмотреть ваш плейлист\n"
        "/share - Поделиться плейлистом\n"
        "/help - Показать эту справку\n"
        "/stats - Административная статистика (для владельца бота)\n"
        "Просто напиши название трека для поиска!"
    )

# Команда /playlist
@dp.message_handler(commands=['playlist'])
async def playlist(message: types.Message):
    user_id = message.from_user.id
    playlist = user_playlists.get(user_id, [])
    if not playlist:
        await message.reply("Ваш плейлист пуст. Найдите трек и добавьте его в плейлист!")
        return

    response = "🎶 Ваш плейлист:\n"
    for i, track in enumerate(playlist, 1):
        response += f"{i}. {track['title']} — {track['artist']} [Слушать]({track['link']})\n"
    await message.reply(response, parse_mode="Markdown")

# Команда /share — делимся ссылкой на плейлист
@dp.message_handler(commands=['share'])
async def share_playlist(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_playlists or not user_playlists[user_id]:
        await message.reply("Ваш плейлист пуст, нечего делиться!")
        return

    share_link = f"playlist_{user_id}"
    keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton("Посмотреть плейлист", callback_data=share_link))
    await message.reply("🔗 Поделитесь этой ссылкой, чтобы другие могли увидеть ваш плейлист:", reply_markup=keyboard)

# Обработка нажатий на плейлист друга
@dp.callback_query_handler(lambda call: call.data.startswith("playlist_"))
async def view_friend_playlist(call: types.CallbackQuery):
    user_id = int(call.data.split("_")[1])
    playlist = user_playlists.get(user_id, [])

    if not playlist:
        await call.message.reply("Плейлист этого пользователя пуст.")
        return

    response = "🎶 Плейлист пользователя:\n"
    for i, track in enumerate(playlist, 1):
        response += f"{i}. {track['title']} — {track['artist']} [Слушать]({track['link']})\n"

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Добавить все в свой плейлист", callback_data=f"add_friend_{user_id}"))
    await call.message.reply(response, reply_markup=keyboard, parse_mode="Markdown")

# Копирование чужого плейлиста
@dp.callback_query_handler(lambda call: call.data.startswith("add_friend_"))
async def add_friend_playlist(call: types.CallbackQuery):
    friend_id = int(call.data.split("_")[2])
    user_id = call.from_user.id

    if friend_id not in user_playlists or not user_playlists[friend_id]:
        await call.message.reply("У этого пользователя нет треков в плейлисте.")
        return

    friend_playlist = user_playlists[friend_id]
    user_playlists[user_id].extend(friend_playlist)

    await call.message.reply("✅ Все треки из плейлиста друга добавлены в ваш плейлист!")

# Поиск трека
@dp.message_handler()
async def search_track(message: types.Message):
    query = message.text
    user_id = message.from_user.id

    # Сохраняем запрос в историю
    user_history[user_id] = user_history.get(user_id, []) + [query]

    try:
        tracks = deezer_client.search(query)
        if not tracks:
            await message.reply("Ничего не найдено. Попробуйте другой запрос.")
            return

        track = tracks[0]
        artist = track.artist.name

        # Кнопки
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("Похожие треки", callback_data=f"similar_{track.id}"))
        keyboard.add(InlineKeyboardButton("Треки исполнителя", callback_data=f"artist_{artist}"))
        keyboard.add(InlineKeyboardButton("Добавить в плейлист", callback_data=f"add_{track.id}"))
        keyboard.add(InlineKeyboardButton("Рекомендации по жанру", callback_data=f"genre_{track.genre_id}"))

        # Отправляем трек
        await message.reply(
            f"🔊 Название: {track.title}\n🎤 Исполнитель: {artist}\n🔗 [Ссылка на трек]({track.link})",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.reply("Произошла ошибка. Попробуйте позже.")
        logging.error(e)

# Обработка добавления трека в плейлист
@dp.callback_query_handler(lambda call: call.data.startswith("add_"))
async def add_to_playlist(call: types.CallbackQuery):
    track_id = call.data.split("_")[1]
    user_id = call.from_user.id

    try:
        track = deezer_client.get_track(track_id)
        user_playlists[user_id].append({
            "title": track.title,
            "artist": track.artist.name,
            "link": track.link
        })
        await call.message.reply(f"✅ Трек {track.title} добавлен в ваш плейлист!")
    except Exception as e:
        await call.message.reply("Не удалось добавить трек в плейлист.")
        logging.error(e)

# Админ-функции
@dp.message_handler(commands=['stats'])
async def stats(message: types.Message):
    if str(message.from_user.id) != OWNER_ID:
        await message.reply("У вас нет доступа к этой функции.")
        return

    user_count = len(user_playlists)
    await message.reply(f"📊 Статистика бота:\n- Пользователей: {user_count}")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
