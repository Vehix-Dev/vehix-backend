import sqlite3

def check_users():
    conn = sqlite3.connect('db.sqlite3')
    cursor = conn.cursor()
    
    # Get user table name
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cursor.fetchall()]
    print("All tables:", tables)
    
    user_table = next((t for t in tables if t.lower() == 'users_user'), None)
    if not user_table:
         user_table = next((t for t in tables if 'user' in t.lower() and 'image' not in t.lower() and 'profile' not in t.lower() and 'group' not in t.lower() and 'perm' not in t.lower() and 'token' not in t.lower()), None)
         
    if not user_table:
        print("User table not found.")
        return
        
    print(f"Table name: {user_table}")
    cursor.execute(f"PRAGMA table_info({user_table});")
    cols = [c[1] for c in cursor.fetchall()]
    print("Columns:", cols)
    
    cursor.execute(f"SELECT id, username, email, phone, role, is_staff, is_superuser, is_active FROM {user_table};")
    rows = cursor.fetchall()
    
    for r in rows:
        print(dict(zip(['id', 'username', 'email', 'phone', 'role', 'is_staff', 'is_superuser', 'is_active'], r)))
        
    conn.close()

if __name__ == "__main__":
    check_users()
