import http
import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv
from telegram import error

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


VERDICTS = {
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
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except error.BadRequest:
        logger.error('Ошибка отправки сообщения')


def get_api_answer(current_timestamp):
    """Получаем данные о проверке домашней работы."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}

    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.exceptions.RequestException as err:
        logger.error('Ошибка при запросе к API')
        raise err('Ошибка при запросе к API')

    if response.status_code != http.HTTPStatus.OK:
        logger.error(f'Код ответ не равен {http.HTTPStatus.OK}')
        raise requests.exceptions.RequestException('Ошибка запроса к API')

    try:
        return response.json()
    except requests.exceptions.JSONDecodeError as err:
        logger.error('Ошибка конвертации JSON')
        raise err('Ошибка конвертации JSON')


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

    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if not isinstance(homework_name, str):
        logger.error('Отсутствует значение homework_name')
        raise KeyError('Отсутствует значение homework_name')

    if not isinstance(homework_status, str):
        logger.error('Отсутствует значение status')
        raise KeyError('Отсутствует значение status')

    try:
        verdict = VERDICTS[homework_status]
    except KeyError as err:
        logger.error('Отсутствует ключ')
        raise err('Отсутствует ключ')
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
    new_error = None

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
            if error != new_error:
                message = f'Сбой в работе программы: {error}'
                logger.error(f'Сбой в работе программы: {error}')
                send_message(bot, message)
                new_error = error
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
