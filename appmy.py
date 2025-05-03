import imaplib
import email
import requests
import time
import os
from email.header import decode_header
import logging
import sys
import traceback
from bs4 import BeautifulSoup
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


BOT_URL = os.getenv('BOT_URL')
BOT_TOKEN = os.getenv('BOT_TOKEN')
IMAP_SERVER= os.getenv('IMAP_SERVER')
EMAIL = os.getenv('EMAIL')
PASSWORD = os.getenv('PASSWORD')  
TOKEN = os.getenv('TOKEN') 
CHAT_ID = os.getenv('CHAT_ID')  
SENDER = os.getenv('SENDER')
MESSAGE_THREAD_ID=os.getenv('MESSAGE_THREAD_ID')
MAX_RECONNECT_ATTEMPTS = 30
def send_glpi_ticket(name, content, recipient_id, priority, initiator_login):
    ticket_data = {
        "name": name,
        "content": content,
        "recipientID": recipient_id,
        "priority": priority,
        "initiatorLogin": initiator_login
    }
    headers = {
        'Content-Type': 'application/json',
        'X-External-Token': BOT_TOKEN
    }

    try:
        response = requests.post(BOT_URL, json=ticket_data, headers=headers)
        
        if response.status_code == 200:
            logging.info(f"Тикет успешно создан: {response.json()}")
        else:
            logging.error(f"Ошибка при создании тикета: {response.status_code} - {response.text}")
    except Exception as e:
        logging.error(f'Ошибка при отправке запроса: {e}')

def send_telegram_message(message):
    try:
        url = f'https://api.telegram.org/bot{TOKEN}/sendMessage'
        data = {
            'chat_id': CHAT_ID,
            'text': message,
            'message_thread_id': MESSAGE_THREAD_ID,
        }
        response = requests.post(url, data=data)
        response.raise_for_status()
        logging.info("Сообщение успешно отправлено в Telegram.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при отправке сообщения в Telegram: {e}")
def check_telegram_bot_accessibility():
    try:
        url = f'https://api.telegram.org/bot{TOKEN}/getMe'
        response = requests.get(url)
        response.raise_for_status()
        logging.info("Доступ к боту Telegram проверен успешно.")
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f'Ошибка при проверке доступности бота Telegram: {e}')
        return False

def decode_mime_words(s):
    decoded_words = decode_header(s)
    return ''.join(
        str(text, encoding if encoding else 'utf-8') if isinstance(text, bytes) else text
        for text, encoding in decoded_words
    )

def get_email_body(msg):
    """Извлекает текстовое содержимое из email-сообщения."""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                return part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8')
            elif content_type == "text/html" and "attachment" not in content_disposition:
                # Можно добавить обработку HTML, если нужно
                return part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8')
    else:
        return msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8')
    return None
def clean_html(raw_html):
    """Удаляет HTML-теги и возвращает чистый текст."""
    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.get_text(separator="\n").strip()
def check_email(mail):
        #try:
        #logging.info("Проверка новых писем")
        #mail.select('inbox')
        #result, data = mail.search(None, f'(UNSEEN FROM "{SENDER}")')
        #if result != 'OK':
        #    logging.error("Ошибка при поиске писем.")
        #    return
        #if not data[0]:
        #    logging.info("Нет новых писем.") 
    try:
        logging.info("Проверка новых писем")
        mail.select('inbox')
        
        # Формируем строку поиска
        search_criteria = f'(UNSEEN FROM "{SENDER}")'
        logging.info(f"Поиск по критериям: {search_criteria}")
        
        result, data = mail.search(None, search_criteria)
        
        if result != 'OK':
            logging.error("Ошибка при поиске писем.")
            return
        
        if not data[0]:
            logging.info("Нет новых писем от указанного отправителя.")
            return
        mail_ids = data[0].split() if data[0] else []
        #last_mail_ids = mail_ids[-10:] #
        for num in mail_ids: # в случае чего убираю дастт мэил и ставли мэил идс
            result, msg_data = mail.fetch(num, '(RFC822)')
            if result != 'OK':
                logging.error(f"Ошибка при получении письма с ID {num}.")
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            subject = decode_mime_words(msg['Subject'])
            body = get_email_body(msg)
            if body:
                logging.info(f'Новое письмо от {SENDER}: {subject}')
                send_telegram_message(f'Проверьте личную почту пришло новое письмо от {SENDER}: {subject}\n\n{body}')
                send_glpi_ticket(
                    name=subject,
                    content=body,
                    recipient_id=1,  
                    priority=3,      
                    initiator_login=""
                )
            
            else:
                logging.warning(f'Не удалось извлечь тело письма от {SENDER} с темой: {subject}')
                result = mail.store(num, '+FLAGS', '\Seen')
            if result[0] != 'OK':
                logging.error(f'Не удалось пометить письмо с ID {num} как прочитанное: {result[1]}')
    except Exception as e:
        logging.error(f'Ошибка при проверке почты: {e}')
        logging.error(traceback.format_exc())

def check_mailbox_accessibility():
    try:
       with imaplib.IMAP4_SSL(IMAP_SERVER) as mail:
            mail.login(EMAIL, PASSWORD)
            logging.info("Доступ к почте проверен успешно.")
            return True
    except Exception as e:
        logging.error(f'Ошибка при проверке доступности почты: {e}')
        return False
def main(): #первая рабочая 
    if not check_mailbox_accessibility():
        logging.error("Невозможно подключиться к почте. Завершение работы.")
        return
    if not check_telegram_bot_accessibility():
        logging.error("Невозможно подключиться к боту Telegram. Завершение работы.")
        return

    try:
        logging.info("Подключение к почте")
        with imaplib.IMAP4_SSL(IMAP_SERVER) as mail:
            mail.login(EMAIL, PASSWORD)
            logging.info("Успешно подключено к почте")
            while True:
                try:
                    check_email(mail)
                    time.sleep(20)
                except Exception as e:
                    logging.error(f'Ошибка во время проверки почты: {e}')
                    time.sleep(60)  
    except Exception as e:
        logging.error(f'Ошибка при подключении к почте: {e}')  
        logging.info("Попробую переподключиться через 5 секунд...")
        time.sleep(5)               
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()