"""
Программа для резервного копирования картинок с сайта cataas.com на Яндекс.Диск
Курсовая работа "Резервное копирование" по курсу "Python-разработчик с нуля"
"""

import requests
import json
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from tqdm import tqdm
import time


@dataclass
class FileInfo:
    """Класс для хранения информации о файле"""
    filename: str
    size_bytes: int
    text: str
    download_url: str
    yandex_path: str


class YandexDiskClient:
    """Клиент для работы с API Яндекс.Диска"""
    
    BASE_URL = "https://cloud-api.yandex.net/v1/disk"
    
    def __init__(self, token: str):
        """
        Инициализация клиента Яндекс.Диска
        
        Args:
            token: OAuth-токен Яндекс.Диска
        """
        self.token = token
        self.headers = {'Authorization': f'OAuth {token}'}
        self.logger = logging.getLogger(__name__)
    
    def create_folder(self, folder_name: str) -> bool:
        """
        Создание папки на Яндекс.Диске
        
        Args:
            folder_name: Название папки
            
        Returns:
            bool: Успешно ли создана папка
        """
        url = f"{self.BASE_URL}/resources"
        params = {'path': folder_name}
        
        try:
            # Сначала проверяем, существует ли папка
            check_response = requests.get(
                url, 
                headers=self.headers, 
                params={'path': folder_name}
            )
            
            if check_response.status_code == 200:
                self.logger.info(f"Папка '{folder_name}' уже существует")
                return True
            
            # Создаем папку, если она не существует
            response = requests.put(url, headers=self.headers, params=params)
            
            if response.status_code in [201, 409]:  # 201 - создана, 409 - уже существует
                self.logger.info(f"Папка '{folder_name}' создана/существует")
                return True
            else:
                self.logger.error(f"Ошибка создания папки: {response.json()}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Ошибка при создании папки: {e}")
            return False
    
    def upload_by_url(self, file_url: str, save_path: str) -> bool:
        """
        Загрузка файла по URL на Яндекс.Диск
        
        Args:
            file_url: URL файла для загрузки
            save_path: Путь для сохранения на Яндекс.Диске
            
        Returns:
            bool: Успешно ли загружен файл
        """
        url = f"{self.BASE_URL}/resources/upload"
        params = {
            'url': file_url,
            'path': save_path,
            'disable_redirects': 'true'
        }
        
        try:
            self.logger.info(f"Начинаю загрузку {save_path} по URL...")
            
            # Запрашиваем загрузку по URL
            response = requests.post(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            # Проверяем статус загрузки
            operation_id = response.json().get('href', '').split('operation_id=')[-1]
            
            if operation_id:
                # Ждем завершения операции
                return self._check_upload_status(operation_id, save_path)
            
            return True
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Ошибка при загрузке по URL: {e}")
            return False
    
    def _check_upload_status(self, operation_id: str, filename: str) -> bool:
        """
        Проверка статуса загрузки файла
        
        Args:
            operation_id: ID операции загрузки
            filename: Имя файла для отображения в прогрессе
            
        Returns:
            bool: Успешно ли завершена загрузка
        """
        url = f"{self.BASE_URL}/operations/{operation_id}"
        
        # Создаем прогресс-бар
        with tqdm(total=100, desc=f"Загрузка {filename}", unit="%") as pbar:
            last_progress = 0
            
            for _ in range(30):  # Максимум 30 попыток (30 секунд)
                try:
                    response = requests.get(url, headers=self.headers)
                    response.raise_for_status()
                    
                    data = response.json()
                    status = data.get('status')
                    
                    if status == 'success':
                        pbar.update(100 - last_progress)
                        self.logger.info(f"Файл {filename} успешно загружен")
                        return True
                    elif status == 'in-progress':
                        progress = data.get('progress', 0)
                        pbar.update(progress - last_progress)
                        last_progress = progress
                    elif status == 'failed':
                        self.logger.error(f"Ошибка загрузки: {data.get('message')}")
                        return False
                    
                    time.sleep(1)  # Ждем 1 секунду перед следующей проверкой
                    
                except requests.exceptions.RequestException as e:
                    self.logger.error(f"Ошибка проверки статуса: {e}")
                    return False
        
        self.logger.warning("Превышено время ожидания загрузки")
        return False


class CataasClient:
    """Клиент для работы с API Cataas.com"""
    
    BASE_URL = "https://cataas.com"
    
    def __init__(self):
        """Инициализация клиента Cataas"""
        self.logger = logging.getLogger(__name__)
    
    def get_cat_image_url(self, text: str) -> Optional[str]:
        """
        Получение URL изображения кота с текстом
        
        Args:
            text: Текст для отображения на картинке
            
        Returns:
            Optional[str]: URL изображения или None при ошибке
        """
        try:
            # Эндпоинт для получения кота с текстом
            url = f"{self.BASE_URL}/cat/says/{requests.utils.quote(text)}"
            
            # Делаем HEAD запрос для получения информации о файле
            response = requests.head(url)
            
            if response.status_code == 200:
                self.logger.info(f"Получен URL для изображения с текстом: {text}")
                return url
            else:
                self.logger.error(f"Ошибка получения URL: {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Ошибка при получении URL изображения: {e}")
            return None


class BackupManager:
    """Менеджер резервного копирования"""
    
    def __init__(self, netology_group: str):
        """
        Инициализация менеджера резервного копирования
        
        Args:
            netology_group: Название группы в Нетологии
        """
        self.netology_group = netology_group
        self.uploaded_files = []
        self.logger = self._setup_logging()
    
    def _setup_logging(self) -> logging.Logger:
        """Настройка логирования"""
        logger = logging.getLogger('CatBackup')
        logger.setLevel(logging.INFO)
        
        # Форматтер для логов
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Обработчик для вывода в консоль
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # Обработчик для записи в файл
        file_handler = logging.FileHandler('backup.log')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        return logger
    
    def run_backup(self, text: str, yandex_token: str) -> bool:
        """
        Выполнение резервного копирования
        
        Args:
            text: Текст для изображения
            yandex_token: Токен Яндекс.Диска
            
        Returns:
            bool: Успешно ли выполнено резервное копирование
        """
        self.logger.info("=" * 50)
        self.logger.info("Начало процесса резервного копирования")
        self.logger.info(f"Текст: {text}, Группа: {self.netology_group}")
        
        try:
            # 1. Получаем URL изображения с Cataas
            self.logger.info("Этап 1: Получение изображения с Cataas")
            cataas_client = CataasClient()
            image_url = cataas_client.get_cat_image_url(text)
            
            if not image_url:
                self.logger.error("Не удалось получить URL изображения")
                return False
            
            # 2. Работа с Яндекс.Диском
            self.logger.info("Этап 2: Подготовка Яндекс.Диска")
            yandex_client = YandexDiskUploader(yandex_token)
            
            # Создаем папку
            if not yandex_client.create_folder(self.netology_group):
                self.logger.error("Не удалось создать папку на Яндекс.Диске")
                return False
            
            # 3. Загрузка на Яндекс.Диск
            self.logger.info("Этап 3: Загрузка на Яндекс.Диск")
            
            # Формируем имя файла (текст без пробелов и спецсимволов)
            safe_filename = self._sanitize_filename(text) + ".jpg"
            yandex_path = f"{self.netology_group}/{safe_filename}"
            
            # Загружаем по URL (без сохранения локально)
            if not yandex_client.upload_by_url(image_url, yandex_path):
                self.logger.error("Не удалось загрузить файл на Яндекс.Диск")
                return False
            
            # 4. Сохраняем информацию о файле
            file_info = FileInfo(
                filename=safe_filename,
                size_bytes=self._get_remote_file_size(image_url),
                text=text,
                download_url=image_url,
                yandex_path=yandex_path
            )
            
            self.uploaded_files.append(file_info)
            
            # 5. Сохраняем информацию в JSON
            self._save_to_json()
            
            self.logger.info("Резервное копирование успешно завершено!")
            self.logger.info("=" * 50)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Критическая ошибка: {e}", exc_info=True)
            return False
    
    def _sanitize_filename(self, text: str) -> str:
        """
        Очистка имени файла от недопустимых символов
        
        Args:
            text: Исходный текст
            
        Returns:
            str: Очищенное имя файла
        """
        # Заменяем пробелы и недопустимые символы
        invalid_chars = '<>:"/\\|?* '
        for char in invalid_chars:
            text = text.replace(char, '_')
        
        # Ограничиваем длину имени файла
        return text[:100]
    
    def _get_remote_file_size(self, url: str) -> int:
        """
        Получение размера файла по URL
        
        Args:
            url: URL файла
            
        Returns:
            int: Размер файла в байтах
        """
        try:
            response = requests.head(url)
            if 'content-length' in response.headers:
                return int(response.headers['content-length'])
            return 0
        except:
            return 0
    
    def _save_to_json(self):
        """Сохранение информации о загруженных файлах в JSON"""
        if not self.uploaded_files:
            self.logger.warning("Нет данных для сохранения в JSON")
            return
        
        data = []
        for file_info in self.uploaded_files:
            data.append({
                "filename": file_info.filename,
                "size_bytes": file_info.size_bytes,
                "text": file_info.text,
                "download_url": file_info.download_url,
                "yandex_path": file_info.yandex_path,
                "backup_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "group_name": self.netology_group
            })
        
        json_filename = f"backup_info_{self.netology_group}.json"
        
        try:
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"Информация сохранена в файл: {json_filename}")
            
        except IOError as e:
            self.logger.error(f"Ошибка сохранения JSON: {e}")


def main():
    """Основная функция программы"""
    print("=" * 60)
    print("   ПРОГРАММА РЕЗЕРВНОГО КОПИРОВАНИЯ КАРТИНОК")
    print("=" * 60)
    
    # Получение данных от пользователя
    text = input("Введите текст для картинки: ").strip()
    
    if not text:
        print("Ошибка: текст не может быть пустым")
        return
    
    yandex_token = input("Введите токен Яндекс.Диска: ").strip()
    
    if not yandex_token:
        print("Ошибка: токен не может быть пустым")
        return
    
    # Название группы в Нетологии
    NETOLOGY_GROUP_NAME = "SPD-142"
    
    print(f"\nНачинаем резервное копирование...")
    print(f"Текст: {text}")
    print(f"Группа: {NETOLOGY_GROUP_NAME}")
    print("-" * 40)
    
    # Запуск процесса резервного копирования
    backup_manager = BackupManager(NETOLOGY_GROUP_NAME)
    
    if backup_manager.run_backup(text, yandex_token):
        print("\n✅ Резервное копирование успешно завершено!")
        print(f"📁 Папка на Яндекс.Диске: {NETOLOGY_GROUP_NAME}")
        print(f"📄 JSON файл: backup_info_{NETOLOGY_GROUP_NAME}.json")
        print("📋 Логи: backup.log")
    else:
        print("\n❌ Резервное копирование не удалось")
        print("Проверьте логи в файле backup.log")
    
    print("=" * 60)


if __name__ == "__main__":
    main()

