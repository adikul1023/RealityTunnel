import sqlite3

try:
    conn = sqlite3.connect('/code/db.sqlite3')
    cur = conn.cursor()
    cur.execute("UPDATE admins SET hashed_password='$2b$12$K.BMRK6Cq6RNGFVbaB9Nlud7AxW6SbvWzrU.dIw.lN0EiszkCbmca' WHERE username='billing-api-svc'")
    conn.commit()
    print("Password updated successfully.")
except Exception as e:
    print(e)
