import imaplib
import email
import requests
import time
import os
from email.header import decode_header
import logging
import sys
from bs4 import BeautifulSoup
from email import policy
from email.parser import BytesParser
# Настройка логирования для записи в stdout
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
EMAIL = os.getenv('EMAIL')
PASSWORD = os.getenv('PASSWORD')  
TOKEN = os.getenv('TOKEN') 
CHAT_ID = os.getenv('CHAT_ID')  
ALLOWED_DOMAINS = os.getenv('SENDER', '').split(',') #{"it.mos.ru", "spetsdor.ru", "mod-sol.ru", "megapolis-it.ru", "zntr.ru", "yandex.ru", "tsoddvl.ru"}
IMAP_SERVER= os.getenv('IMAP_SERVER') #"imap.yandex.ru"
MESSAGE_THREAD_ID=os.getenv('MESSAGE_THREAD_ID')
EMAIL2 = os.getenv('EMAIL2')
PASSWORD2 = os.getenv('PASSWORD2')
ALLOWED_DOMAINS2 = os.getenv('SENDER2', '').split(',')
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
            if content_type in ["text/plain", "text/html"] and "attachment" not in content_disposition:
                body = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8')
                return clean_html(body)  # Очищаем HTML
    else:
        return clean_html(msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8'))
    return None
def clean_html(raw_html):
    """Удаляет HTML-теги и возвращает чистый текст."""
    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.get_text(separator="\n").strip()
def check_email(mail, allowed_domains):
    try:
        logging.info("Проверка новых писем")
        mail.select('inbox')
        
        # Формирование запроса для поиска писем
        sender_query = ' OR '.join([f'FROM "*@{domain.strip()}"' for domain in allowed_domains])
        
        # Поиск непрочитанных писем от разрешенных отправителей
        result, data = mail.search(None, f'(UNSEEN ({sender_query}))')    
        
        if result != 'OK':
            logging.error("Ошибка при поиске писем.")
            return
        
        mail_ids = data[0].split() if data[0] else []
        
        if not mail_ids:
            logging.info("Нет новых писем.")
            return

        for num in mail_ids:
            result, msg_data = mail.fetch(num, '(RFC822)')
            if result != 'OK':
                logging.error(f"Ошибка при получении письма с ID {num}.")
                continue
            
            msg = email.message_from_bytes(msg_data[0][1])
            subject = decode_mime_words(msg['Subject'])
            body = get_email_body(msg)
            from_address = decode_mime_words(msg['From'])  # Декодируем адрес отправителя
            
            if any(from_address.endswith(domain) for domain in allowed_domains):
                if body:
                    # Формируем сообщение без лишних данных
                    clean_message = f'Новое письмо от: {from_address}\nТема: {subject}\n\n{body}'
                    logging.info(f'Новое письмо от {from_address}: {subject}')
                    send_telegram_message(clean_message)
                else:
                    logging.warning(f'Не удалось извлечь тело письма от {from_address} с темой: {subject}')
                
                # Пометить письмо как прочитанное
                mail.store(num, '+FLAGS', '\\Seen')
    except Exception as e:
        logging.error(f'Ошибка при проверке почты: {e}')
def check_mailbox_accessibility():
    try:
        with imaplib.IMAP4_SSL(IMAP_SERVER) as mail, imaplib.IMAP4_SSL(IMAP_SERVER) as mail2:
            mail.login(EMAIL, PASSWORD)
            mail2.login(EMAIL2, PASSWORD2)
            logging.info("Доступ к почте проверен успешно.")
            return True
    except Exception as e:
        logging.error(f'Ошибка при проверке доступности почты: {e}')
        return False
def main():
    if not check_mailbox_accessibility():
        logging.error("Невозможно подключиться к почте support. Завершение работы.")
        return
    if not check_mailbox_accessibility():
        logging.error("Невозможно подключиться к моей почте. Завершение работы.")
        return
    if not check_telegram_bot_accessibility():
        logging.error("Невозможно подключиться к боту Telegram. Завершение работы.")
        return
    try:
        logging.info("Подключение к почте")  
        with imaplib.IMAP4_SSL(IMAP_SERVER) as mail, imaplib.IMAP4_SSL(IMAP_SERVER) as mail2:
            mail.login(EMAIL, PASSWORD)
            mail2.login(EMAIL2, PASSWORD2)
            while True:
                check_email(mail, ALLOWED_DOMAINS)  # Проверяем EMAIL с ALLOWED_DOMAINS
                check_email(mail2, ALLOWED_DOMAINS2)  # Проверяем EMAIL2 с ALLOWED_DOMAINS2
                time.sleep(60)  
    except Exception as e:
        logging.error(f'Ошибка при подключении к почте: {e}')
if __name__ == "__main__":
    main()