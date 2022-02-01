import os
import sys
import time
import http
import logging
import telegram
import requests
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s, %(levelname)s, %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправка сообщения о статусе домашней работы."""
    return bot.send_message(TELEGRAM_CHAT_ID, message)


def get_api_answer(current_timestamp):
    """Получаем данные о проверке домашней работы."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}

    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if response.status_code != http.HTTPStatus.OK:
        logger.error('Ошибка при запросе к API')
        raise requests.exceptions.RequestException
    return response.json()


def check_response(response):
    """Проверка типа данных."""
    if not isinstance(response, dict):
        raise TypeError('Данные не соответсвуют типу словарь.')

    if not isinstance(response.get('homeworks'), list):
        raise TypeError('Данные под ключом "homeworks" не типа list')
    return response.get('homeworks')


def parse_status(homework):
    """Извлечение информации о домашней работе."""
    if not homework:
        return None

    try:
        homework_name = homework.get('homework_name')
        homework_status = homework.get('status')
    except KeyError:
        logger.error('Отсутствует ключ')
        raise

    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности переменных окружения."""
    tokens = [
        PRACTICUM_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID
    ]

    for token in tokens:
        if not token:
            logger.critical(f'Отсутствует переменная окружения {token}')
            return False
        return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        sys.exit()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            if not homework:
                logger.debug('Отсутствует новый статус.')
                current_timestamp = response.get(
                    'current_date',
                    current_timestamp
                )
                time.sleep(RETRY_TIME)
                continue
            homework = homework[0]
            message = parse_status(homework)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(f'Сбой в работе программы: {error}')
            send_message(bot, message)
            time.sleep(RETRY_TIME)
        else:
            send_message(bot, message)
            logger.info('Успешная отправка оповещения.')
            current_timestamp = response.get(
                'current_date',
                current_timestamp
            )
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
