import sqlite3
path = r'C:\Users\HP\OneDrive\Рабочий стол\schedule-main\db.sqlite3'
conn = sqlite3.connect(path)
cursor = conn.cursor()
cursor.execute("DELETE FROM core_user WHERE username = 'name'")
conn.commit()
print(f"Записей удалено: {cursor.rowcount}")
conn.close()