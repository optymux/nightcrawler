import os
import asyncio
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from openai import AsyncOpenAI
from telegram import Bot
import openai

# ========== Ajan Ayarları ==========
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
TELEGRAM_CHAT_ID = os.environ['TELEGRAM_CHAT_ID']
OPENAI_API_KEY = os.environ['OPENAI_API_KEY']
OPENAI_MODEL = "gpt-4.1-mini"

openai.api_key = OPENAI_API_KEY
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

NIGHTCRAWLER_PERSONA = (
    "Sen NightCrawler adında bir gölge ajanısın. Ahmet Erol Bayrak'a çalışıyorsun, o senin patronun. "
    "Az ve öz konuşursun. Casus gibi, stratejik ve soğukkanlı cevaplar verirsin."
)

# ========== OSTİM Sayfası Kontrol ==========
def selenium_check_ostim_site():
    result = False
    trigger_line = ""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(f"--user-data-dir=/tmp/chrome_userdata_{int(time.time())}")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    try:
        url = "https://ostimteknik.edu.tr/blog/duyuru-5772"
        driver.get(url)
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        page_text = soup.get_text().lower()

        keywords = [
            "2025-2026 akademik takvim",
            "akademik takvim yayınlandı",
            "2025-2026 eğitim öğretim yılı",
            "akademik takvim"
        ]

        for line in page_text.split('\n'):
            line_clean = line.strip().lower()
            if any(keyword in line_clean for keyword in keywords):
                result = True
                trigger_line = line.strip()[:120]
                break
    except Exception as e:
        trigger_line = f"Hata oluştu: {e}"
    finally:
        driver.quit()
    return result, trigger_line

# ========== Telegram Bildirim ==========
async def send_telegram(msg):
    bot = Bot(token=TELEGRAM_TOKEN)
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)

# ========== OpenAI Mesaj Üretimi ==========
async def generate_cryptic_message():
    prompt = (
        "Senin adın NightCrawler. Bir ipucu bulunduğuna dair bir Telegram mesajı yaz. Mesajı İngilizce yaz. "
        "Örneğin: \"It's NightCrawler, got something for ya...\" Bu tarzda olsun birebir aynı kelimeleri yazmana gerek yok."
    )
    try:
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "system", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"NC: Gölgede kıpırtı var. [OpenAI Hatası: {e}]"

async def generate_daily_report(last_trigger_time, last_trigger_info):
    if not last_trigger_time:
        extra = "Ses yok, iz yok, tüm gece temiz geçti."
    else:
        extra = f"Son tespit: {last_trigger_time.strftime('%H:%M:%S')} -> {last_trigger_info}"
    prompt = (
        "Henüz istenen filtrelerde bir olmadığını resmi bir dille belirt."
        f"Bilgi: {extra}"
    )
    try:
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "system", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except:
        return "NC: Gece sessiz geçti, kıpırtı yok."

# ========== Ajan Döngüsü ==========
async def agent_loop():
    last_trigger_time = None
    last_trigger_info = ""
    daily_report_hour = 9
    daily_reported_date = None

    while True:
        now = datetime.now()

        # SAATLİK KONTROL
        found, trigger_line = selenium_check_ostim_site()
        if found:
            msg = await generate_cryptic_message()
            msg += f"\n[Tetikleyici: {trigger_line}]"
            await send_telegram(msg)
            last_trigger_time = now
            last_trigger_info = trigger_line

        # GÜNLÜK RAPOR
        if now.hour == daily_report_hour and (not daily_reported_date or daily_reported_date != now.date()):
            report = await generate_daily_report(last_trigger_time, last_trigger_info)
            await send_telegram(report)
            daily_reported_date = now.date()
            last_trigger_time = None
            last_trigger_info = ""

        await asyncio.sleep(60 * 60)

# ========== Başlatıcı ==========
async def main():
    await send_telegram("NightCrawler is active, all systems are functional. 🕷️")
    await agent_loop()

if __name__ == "__main__":
    asyncio.run(main())