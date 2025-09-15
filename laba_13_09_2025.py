import requests
import telebot
from telebot.types import ReplyKeyboardMarkup
from datetime import datetime
import pandas as pd
import functools
import os
import signal
import sys
from secr import TOKEN

bot_running = True

def signal_handler(sig, frame):
    """Обработчик сигналов для graceful shutdown"""
    global bot_running
    print("Получен сигнал остановки...")
    bot_running = False
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Получаем абсолютный путь к текущей директории
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
CSV_FILE = os.path.join(LOGS_DIR, 'bot_log.csv')

print(f"Текущая директория: {BASE_DIR}")
print(f"Папка логов: {LOGS_DIR}")
print(f"CSV файл логов: {CSV_FILE}")

# Список кнопок для поиска
KEYBOARD_BUTTONS = [
    "Погода на неделю",
    "Курсы валют НБРБ",
    "Криптовалюты",
    "Помощь"
]

def logging(func):
    """Декоратор для логирования"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        msg = extract_message(args)
        user_id, username, motion, api_text = extract_user_data(msg)
        date_str = datetime.now().strftime("%Y-%m-%d")
        time_str = datetime.now().strftime("%H:%M:%S")

        result = func(*args, **kwargs)

        # Определяем ответ для лога
        if motion == "Button click":
            if isinstance(result, tuple) and len(result) == 2:
                api_response, success = result
                api_answer = api_response  # Используем оригинальный ответ API
            elif isinstance(result, str):
                api_answer = result
            else:
                api_answer = "No response"
        else:
            api_answer = result if isinstance(result, str) else "NONE"

        save_log(user_id, username, motion, api_text, date_str, time_str, api_answer)
        return result
    return wrapper

def extract_message(args):
    """Для поиска сообщений"""
    for arg in args:
        if hasattr(arg, "from_user") and hasattr(arg, "text"):
            return arg
    return None

def extract_user_data(msg):
    """Unic_ID, @TG_nick, Motion, API"""
    if msg:
        user_id = msg.from_user.id
        username = f"@{msg.from_user.username}" if msg.from_user.username else msg.from_user.first_name
        
        if msg.text and msg.text.strip() in KEYBOARD_BUTTONS:
            motion = "Button click"
            api_text = msg.text.strip()
        elif hasattr(msg, 'text') and msg.text.startswith('/'):
            motion = "Command"
            api_text = "NONE"
        else:
            motion = "Keyboard typing"
            api_text = "NONE"
        
        return user_id, username, motion, api_text
    return "Unknown", "Unknown", "Unknown", "NONE"

def save_log(user_id, username, motion, api_text, date_str, time_str, api_answer):
    """Сохранение лога в CSV файл"""
    try:
        # Создаем папку если ее нет
        os.makedirs(os.path.dirname(CSV_FILE), exist_ok=True)
        
        # Очищаем текст от эмодзи и специальных символов
        def clean_text(text):
            if isinstance(text, str):
                return ''.join(c for c in text if ord(c) < 128 and c.isprintable())
            return str(text)
        
        # Создаем новую запись
        new_entry = pd.DataFrame([{
            "Unic ID": clean_text(str(user_id)),
            "@TG nick": clean_text(username),
            "Motion": clean_text(motion),
            "API": clean_text(api_text),
            "Date": date_str,
            "Time": time_str,
            "API answer": clean_text(str(api_answer))  # Сохраняем полный ответ
        }])

        # Проверяем существует ли файл
        file_exists = os.path.exists(CSV_FILE)

        # Сохраняем в CSV
        new_entry.to_csv(
            CSV_FILE,
            mode="a",
            index=False,
            encoding="utf-8-sig",
            header=not file_exists  # Заголовки только при первом создании
        )
        
        print(f"Записано в лог: {user_id} - {motion} - {api_text}")
        
    except Exception as e:
        print(f"Ошибка записи в лог: {e}")

# Создаем папку для логов при запуске
os.makedirs(LOGS_DIR, exist_ok=True)

BOT_TOKEN = TOKEN 
bot = telebot.TeleBot(BOT_TOKEN)

keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.row('Погода на неделю')
keyboard.row('Курсы валют НБРБ')
keyboard.row('Криптовалюты')
keyboard.row('Помощь')

def get_weather_minsk():
    """Получение прогноза погоды в Минске на 7 дней"""
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            'latitude': 53.9,
            'longitude': 27.5667,
            'hourly': 'temperature_2m,weathercode',
            'daily': 'weathercode,temperature_2m_max,temperature_2m_min',
            'timezone': 'Europe/Minsk',
            'forecast_days': 7
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if 'daily' not in data:
            error_msg = "Ошибка получения данных о погоде"
            return error_msg, False
        
        daily = data['daily']
        result = "Погода в Минске на неделю:\n\n"
        
        weather_codes = {
            0: "Ясно", 1: "Преимущественно ясно", 2: "Переменная облачность",
            3: "Пасмурно", 45: "Туман", 48: "Инейный туман",
            51: "Легкая морось", 53: "Умеренная морось", 55: "Сильная морось",
            61: "Небольшой дождь", 63: "Умеренный дождь", 65: "Сильный дождь",
            80: "Ливень", 81: "Сильный ливень", 82: "Очень сильный ливень",
            95: "Гроза", 96: "Гроза с градом", 99: "Сильная гроза с градом"
        }
        
        for i in range(min(7, len(daily['time']))):
            date = datetime.fromisoformat(daily['time'][i]).strftime('%d.%m.%Y')
            temp_max = daily['temperature_2m_max'][i]
            temp_min = daily['temperature_2m_min'][i]
            weather_code = daily['weathercode'][i]
            
            weather_desc = weather_codes.get(weather_code, "Неизвестная погода")
            
            result += f"Дата: {date}:\n"
            result += f"   Температура: {temp_min:.0f}C - {temp_max:.0f}C\n"
            result += f"   {weather_desc}\n\n"
        
        return result, True
        
    except Exception as e:
        error_msg = f"Ошибка получения данных о погоде: {str(e)}"
        return error_msg, False

def get_exchange_rates_nbrb():
    """Получение курсов валют от Национального банка РБ"""
    try:
        currencies = {
            'USD': 'Доллар США',
            'EUR': 'Евро',
            'RUB': 'Российский рубль',
            'CNY': 'Китайский юань',
            'KZT': 'Казахстанский тенге'
        }
        
        result = "Курсы валют НБРБ:\n\n"
        
        for code, name in currencies.items():
            url = f"https://www.nbrb.by/api/exrates/rates/{code}?parammode=2"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                rate = data['Cur_OfficialRate']
                scale = data['Cur_Scale']
                result += f"{name} ({code}):\n"
                result += f"   {scale} {code} = {rate:.4f} BYN\n\n"
            else:
                result += f"{name} ({code}):\n"
                result += f"   Данные временно недоступны\n\n"
        
        result += "Источник: Национальный банк Республики Беларусь"
        return result, True
        
    except Exception as e:
        error_msg = f"Ошибка получения курсов валют: {str(e)}"
        return error_msg, False

def get_crypto_prices():
    """Получение курсов криптовалют в USD"""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            'ids': 'bitcoin,ethereum,binancecoin,cardano,solana',
            'vs_currencies': 'usd',
            'include_24hr_change': 'true'
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        result = "Курсы криптовалют (USD):\n\n"
        
        crypto_names = {
            'bitcoin': 'Bitcoin',
            'ethereum': 'Ethereum',
            'binancecoin': 'Binance Coin',
            'cardano': 'Cardano',
            'solana': 'Solana'
        }
        
        for crypto_id, info in data.items():
            if crypto_id in crypto_names:
                price = info['usd']
                change = info['usd_24h_change']
                change_icon = '▲' if change > 0 else '▼'
                
                result += f"{crypto_names[crypto_id]}:\n"
                result += f"   Цена: ${price:,.2f}\n"
                result += f"   Изменение: {change_icon} {change:+.1f}% (24ч)\n\n"
        
        return result, True
        
    except Exception as e:
        error_msg = f"Ошибка получения курсов криптовалют: {str(e)}"
        return error_msg, False

@bot.message_handler(commands=['start'])
@logging
def send_welcome(message):
    """Обработчик команды /start"""
    welcome_text = f"Привет, {message.from_user.first_name}!\nЯ бот с полезной информацией! Выберите один из вариантов:"
    bot.send_message(message.chat.id, welcome_text, reply_markup=keyboard)
    return welcome_text

@bot.message_handler(commands=['help'])
@logging
def send_help(message):
    """Обработчик команды /help"""
    help_text = "Используйте кнопки для получения информации: Погода, Курсы валют, Криптовалюты"
    bot.send_message(message.chat.id, help_text, reply_markup=keyboard)
    return help_text

@bot.message_handler(func=lambda message: message.text == "Погода на неделю")
@logging
def handle_weather(message):
    """Обработка кнопки погоды"""
    weather_info, success = get_weather_minsk()
    bot.send_message(message.chat.id, weather_info)
    return weather_info, success

@bot.message_handler(func=lambda message: message.text == "Курсы валют НБРБ")
@logging
def handle_exchange(message):
    """Обработка кнопки курсов валют"""
    exchange_info, success = get_exchange_rates_nbrb()
    bot.send_message(message.chat.id, exchange_info)
    return exchange_info, success

@bot.message_handler(func=lambda message: message.text == "Криптовалюты")
@logging
def handle_crypto(message):
    """Обработка кнопки криптовалют"""
    crypto_info, success = get_crypto_prices()
    bot.send_message(message.chat.id, crypto_info)
    return crypto_info, success

@bot.message_handler(func=lambda message: message.text == "Помощь")
@logging
def handle_help_button(message):
    """Обработка кнопки помощи"""
    help_text = "Используйте кнопки для получения информации: Погода, Курсы валют, Криптовалюты"
    bot.send_message(message.chat.id, help_text, reply_markup=keyboard)
    return help_text, True

@bot.message_handler(func=lambda message: True)
@logging
def handle_message(message):
    """Обработка текстовых сообщений"""
    text = message.text
    response_text = f"Неизвестная команда: {text}. Используйте кнопки или /help"
    bot.send_message(message.chat.id, response_text, reply_markup=keyboard)
    return response_text

def run_bot():
    """Функция для запуска бота"""
    try:
        print("Запуск бота...")
        
        try:
            bot_info = bot.get_me()
            print(f"Бот подключен: @{bot_info.username}")
        except Exception as e:
            print(f"Ошибка подключения к Telegram API: {e}")
            return
        
        print("Бот запущен и готов к работе!")
        print("Для остановки нажмите Ctrl+C")
        print("-" * 50)
        print("Логи сохраняются в:", CSV_FILE)
        print("-" * 50)
        
        # Записываем запись о запуске бота
        save_log('', 'SYSTEM', 'BOT STARTED', '', 
                datetime.now().strftime("%Y-%m-%d"), 
                datetime.now().strftime("%H:%M:%S"), 
                'Бот запущен')
        
        bot.infinity_polling(timeout=30, long_polling_timeout=20)
        
    except KeyboardInterrupt:
        print("Бот остановлен пользователем")
    except Exception as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    print("Инициализация бота...")
    
    try:
        run_bot()
    except KeyboardInterrupt:
        print("Бот остановлен")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
    finally:
        print("Работа бота завершена")