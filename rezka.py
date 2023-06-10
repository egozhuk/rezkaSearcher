from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import smtplib
import imaplib
import email
import time
import datetime
import pytz
import webbrowser

EMAIL = "filmshdrezka@yandex.ru"
PASSWORD = "qljhvtswecmudkvl"
RECIPIENT = "mirror@hdrezka.org"
SMTP_SERVER = "smtp.yandex.ru"
IMAP_SERVER = "imap.yandex.ru"


def search_hdrezka(query, url):
    driver_path = '/Users/vladislavzukov/Documents/chromedriver_mac_arm64/chromedriver'

    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-images')

    service = Service(executable_path=driver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)

    driver.get(url)

    search_input = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, '//*[@id="search-field"]'))
    )
    search_input.send_keys(query)
    search_input.send_keys(Keys.ENTER)

    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, '.b-content__inline_item'))
    )

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    search_results = soup.find_all('div', class_='b-content__inline_item')

    results = []
    for item in search_results:
        title = item.find('div', class_='b-content__inline_item-link').find('a').text.strip()
        link = item.find('div', class_='b-content__inline_item-link').find('a')['href']
        results.append((title, link))

    driver.quit()
    return results


def mark_email_as_read(mail, msg_id):
    mail.store(msg_id, '+FLAGS', '\\Seen')


def check_recent_email():
    now_utc = datetime.datetime.now(pytz.utc)
    last_hour = now_utc - datetime.timedelta(hours=1)

    with imaplib.IMAP4_SSL(IMAP_SERVER) as mail:
        mail.login(EMAIL, PASSWORD)
        mail.select("inbox")
        _, msg_ids = mail.search(None, f'FROM "{RECIPIENT}"')
        msg_ids = msg_ids[0].split()

        for msg_id in reversed(msg_ids):
            _, msg_data = mail.fetch(msg_id, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])
            msg_date = email.utils.parsedate_to_datetime(msg["Date"])

            if msg_date >= last_hour:
                return get_text_from_msg(msg)

    return None


def send_email():
    subject = "Тестовое письмо"
    message = f"Subject: {subject}\n\nЭто тестовое письмо."
    with smtplib.SMTP_SSL(SMTP_SERVER, 465) as server:
        server.login(EMAIL, PASSWORD)
        server.sendmail(EMAIL, RECIPIENT, message.encode('utf-8'))


def get_text_from_msg(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                return part.get_payload(decode=True).decode('utf-8')
        return None
    else:
        return msg.get_payload(decode=True).decode('utf-8')


def wait_for_reply():
    while True:
        time.sleep(5)
        with imaplib.IMAP4_SSL(IMAP_SERVER) as mail:
            mail.login(EMAIL, PASSWORD)
            mail.select("inbox")
            _, msg_ids = mail.search(None, f'FROM "{RECIPIENT}" UNSEEN')
            msg_ids = msg_ids[0].split()
            if msg_ids:
                _, msg_data = mail.fetch(msg_ids[-1], "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])
                mark_email_as_read(mail, msg_ids[-1])
                return get_text_from_msg(msg)


def extract_link(text):
    links = re.findall('hdrez(?:[-\w.]|(?:%[\da-fA-F]{2}))+', text)
    return links[0] if links else None


import re
import json


def get_video_url(driver, link):
    driver.get(link)
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, '#player_code'))
    )

    script_tag = driver.find_element(By.CSS_SELECTOR, '#player_code').get_attribute('innerHTML')
    matches = re.search(r"var pl_data = ({.*});", script_tag)

    if matches:
        pl_data = json.loads(matches.group(1))
        video_url = pl_data['file']
        return video_url
    else:
        return None


if __name__ == '__main__':
    link = input("У вас есть ссылка на зеркало? Введите ссылку, либо введите \'1\' чтобы получить ее: ")
    if link == '1':
        oldText = check_recent_email()
        if (oldText != None):
            link = extract_link(oldText)
            if link == None:
                print(oldText)
                link = input(
                    "Нам не удалось распарсить ссылку. Скопируйте ее из текста и напишитее ее сюда(дописывать https:// не нужно):")
            link = "https://" + link
        else:
            send_email()

            response_text = wait_for_reply()

            link = extract_link(response_text)
            if link == None:
                print(response_text)
                link = input(
                    "Нам не удалось распарсить ссылку. Скопируйте ее из текста и напишитее ее сюда(дописывать https:// не нужно):")
            link = "https://" + link

    print(f'Текущее зеркало: {link}')
    search = '1'
    while search == '1':
        if search != '1':
            break
        query = input('Введите название фильма или сериала: ')
        print("Ведется поиск, это займет не более 30 секунд...")
        results = search_hdrezka(query, link)

        if not results:
            print('Ничего не найдено.')
        else:
            print('Результаты поиска:')
            i = 1
            for title, link in results:
                year = link[-9:-5] if link[-9:-5].isdigit() else "Unknown"
                print(f'{i}) {title} {year}')
                i += 1

        open = input("Какой фильм хотите открыть? Напишите номер из списка, нажмите enter если не хотите: ")
        if open.isdigit():
            result = results[int(open) - 1]
            title, link = result
            webbrowser.open(link)
        search = input("Хотите выполнить повторный поиск? Введите \'1\' если да или \'0\' если нет: ")
