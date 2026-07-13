import sqlite3
import os

try:
    conn = sqlite3.connect('/code/db.sqlite3')
    cur = conn.cursor()
    cur.execute('SELECT username FROM users;')
    print('Users:', cur.fetchall())
    cur.execute('SELECT username FROM admins;')
    print('Admins:', cur.fetchall())
except Exception as e:
    print(e)
