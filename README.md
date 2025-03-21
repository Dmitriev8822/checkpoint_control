# Система контроля доступа по автомобильным номерам

## Описание проекта
Данный проект представляет собой систему автоматического распознавания автомобильных номеров для контроля доступа на территорию предприятия. Приложение обрабатывает видеопоток с камер, фиксирует въезды и выезды автомобилей, автоматически пропускает зарегистрированные автомобили и требует подтверждения для незарегистрированных.

## Технологии
- **Язык программирования**: Python
- **Графический интерфейс**: PyQt5
- **База данных**: PostgreSQL
- **Модель распознавания номеров**: YOLO + LPRNet
- **Обработка видеопотока**: OpenCV

## Основные возможности
- Получение видеопотока с камер (въезд/выезд)
- Распознавание номеров автомобилей с использованием нейросети
- Запись данных о въездах и выездах в базу данных
- Автоматическое предоставление доступа зарегистрированным автомобилям
- Требование подтверждения для незарегистрированных автомобилей
- Возможность загрузки изображения для проверки номера
- Просмотр таблицы с историей въездов и выездов

## Установка
1. Клонируйте репозиторий:
   ```sh
   git clone https://github.com/your-username/your-repository.git
   ```
2. Установите зависимости:
   ```sh
   pip install -r requirements.txt
   ```
3. Настройте подключение к базе данных PostgreSQL в файле конфигурации.
4. Запустите приложение:
   ```sh
   python main.py
   ```
