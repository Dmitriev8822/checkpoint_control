import sqlite3
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_name="cars.db"):
        self.db_name = db_name
        self.connection = None
        self.cursor = None
        self.connect()
        self.create_table()

    def connect(self):
        """Подключение к базе данных и создание курсора."""
        self.connection = sqlite3.connect(self.db_name)
        self.cursor = self.connection.cursor()

    def create_table(self):
        """Создание таблицы Cars с полями id, plate, position и time."""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS Cars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plate TEXT NOT NULL,
                position TEXT NOT NULL,
                time TEXT NOT NULL
            )
        ''')
        self.connection.commit()

    def add_car(self, plate, position):
        """Добавление новой записи в таблицу Cars с текущим временем."""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cursor.execute('''
            INSERT INTO Cars (plate, position, time) VALUES (?, ?, ?)
        ''', (plate, position, current_time))
        self.connection.commit()

    def get_all_cars(self):
        """Получение всех данных из таблицы Cars."""
        self.cursor.execute('SELECT * FROM Cars')
        return self.cursor.fetchall()

    def close(self):
        """Закрытие соединения с базой данных."""
        if self.connection:
            self.connection.close()
