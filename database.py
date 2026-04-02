import aiosqlite
import os
from datetime import datetime

# Dùng biến môi trường DB_PATH khi deploy lên server (Render Persistent Disk, VPS, v.v.)
# Fallback là "gacha.db" khi chạy local
DB_NAME = os.getenv("DB_PATH", "gacha.db")


async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0
            )
        ''')
        
        await db.execute('CREATE TABLE IF NOT EXISTS server_configs (key TEXT PRIMARY KEY, value INTEGER)')
        await db.execute('INSERT OR IGNORE INTO server_configs (key, value) VALUES ("bank_fund", 0)')

        # Cập nhật Schema cho các cột mới nếu chưa tồn tại (Tránh duplicate)
        async with db.execute("PRAGMA table_info(users)") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]

        if 'join_date' not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN join_date TEXT")
        if 'crime_success' not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN crime_success INTEGER DEFAULT 0")
        if 'crime_failure' not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN crime_failure INTEGER DEFAULT 0")
        if 'loan_amount' not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN loan_amount INTEGER DEFAULT 0")
        if 'loan_timestamp' not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN loan_timestamp TEXT")

        await db.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                user_id INTEGER,
                waifu_id INTEGER,
                quantity INTEGER DEFAULT 1,
                PRIMARY KEY (user_id, waifu_id)
            )
        ''')
        await db.commit()

async def get_balance(user_id: int) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT balance FROM users WHERE id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0]
            return 0

async def update_balance(user_id: int, amount: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT balance FROM users WHERE id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                new_balance = max(0, row[0] + amount)
                await db.execute('UPDATE users SET balance = ? WHERE id = ?', (new_balance, user_id))
            else:
                new_balance = max(0, amount)
                await db.execute('INSERT INTO users (id, balance) VALUES (?, ?)', (user_id, new_balance))
        await db.commit()

async def init_user_join_date(user_id: int):
    """Lưu mốc join date nếu user chưa có"""
    now_str = datetime.now().isoformat()
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT join_date FROM users WHERE id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                if row[0] is None:
                    await db.execute('UPDATE users SET join_date = ? WHERE id = ?', (now_str, user_id))
            else:
                await db.execute('INSERT INTO users (id, balance, join_date) VALUES (?, 0, ?)', (user_id, now_str))
        await db.commit()

async def update_crime_stats(user_id: int, success: bool):
    """Cộng dồn chỉ số phi vụ"""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT crime_success, crime_failure FROM users WHERE id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                c_s = row[0] or 0
                c_f = row[1] or 0
                if success: c_s += 1
                else: c_f += 1
                await db.execute('UPDATE users SET crime_success = ?, crime_failure = ? WHERE id = ?', (c_s, c_f, user_id))
            else:
                c_s = 1 if success else 0
                c_f = 0 if success else 1
                await db.execute('INSERT INTO users (id, balance, crime_success, crime_failure) VALUES (?, 0, ?, ?)', (user_id, c_s, c_f))
        await db.commit()

async def get_user_profile(user_id: int) -> dict:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT balance, join_date, crime_success, crime_failure, loan_amount, loan_timestamp FROM users WHERE id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "balance": row[0] or 0,
                    "join_date": row[1],
                    "crime_success": row[2] or 0,
                    "crime_failure": row[3] or 0,
                    "loan_amount": row[4] or 0,
                    "loan_timestamp": row[5]
                }
            return {
                "balance": 0, "join_date": None, "crime_success": 0, "crime_failure": 0, "loan_amount": 0, "loan_timestamp": None
            }

async def add_waifu(user_id: int, waifu_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT quantity FROM inventory WHERE user_id = ? AND waifu_id = ?', (user_id, waifu_id)) as cursor:
            row = await cursor.fetchone()
            if row:
                await db.execute('UPDATE inventory SET quantity = quantity + 1 WHERE user_id = ? AND waifu_id = ?', (user_id, waifu_id))
            else:
                await db.execute('INSERT INTO inventory (user_id, waifu_id, quantity) VALUES (?, ?, 1)', (user_id, waifu_id))
        await db.commit()

async def get_inventory(user_id: int) -> list:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT waifu_id, quantity FROM inventory WHERE user_id = ?', (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return rows

async def get_bank_fund() -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT value FROM server_configs WHERE key="bank_fund"') as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def add_bank_fund(amount: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE server_configs SET value = value + ? WHERE key="bank_fund"', (amount,))
        await db.commit()

async def set_bank_fund(amount: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE server_configs SET value = ? WHERE key="bank_fund"', (amount,))
        await db.commit()

async def get_loan_info(user_id: int) -> tuple:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT loan_amount, loan_timestamp FROM users WHERE id=?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            return (row[0], row[1]) if row else (0, None)

async def get_total_debt() -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT SUM(loan_amount) FROM users WHERE loan_amount > 0') as cursor:
            row = await cursor.fetchone()
            return row[0] if (row and row[0]) else 0

async def set_loan(user_id: int, amount: int, timestamp: str):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT id FROM users WHERE id=?', (user_id,)) as c:
            if not await c.fetchone():
                await db.execute('INSERT INTO users (id, balance) VALUES (?, 0)', (user_id,))
        await db.execute('UPDATE users SET loan_amount = ?, loan_timestamp = ? WHERE id = ?', (amount, timestamp, user_id))
        await db.commit()

async def remove_waifu(user_id: int, waifu_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT quantity FROM inventory WHERE user_id=? AND waifu_id=?', (user_id, waifu_id)) as c:
            row = await c.fetchone()
            if row:
                if row[0] > 1:
                    await db.execute('UPDATE inventory SET quantity = quantity - 1 WHERE user_id=? AND waifu_id=?', (user_id, waifu_id))
                else:
                    await db.execute('DELETE FROM inventory WHERE user_id=? AND waifu_id=?', (user_id, waifu_id))
        await db.commit()

async def empty_balance(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE users SET balance = 0 WHERE id=?', (user_id,))
        await db.commit()

async def execute_trade(user_a: int, user_b: int, waifu_a: int, waifu_b: int, fee: int) -> str:
    async with aiosqlite.connect(DB_NAME) as db:
        try:
            ca = await db.execute('SELECT balance FROM users WHERE id = ?', (user_a,))
            cb = await db.execute('SELECT balance FROM users WHERE id = ?', (user_b,))
            row_a = await ca.fetchone()
            row_b = await cb.fetchone()
            if not row_a or row_a[0] < fee: return f"Người chơi {user_a} không đủ {fee} phí giao dịch."
            if not row_b or row_b[0] < fee: return f"Người chơi {user_b} không đủ {fee} phí giao dịch."

            ia = await db.execute('SELECT quantity FROM inventory WHERE user_id=? AND waifu_id=?', (user_a, waifu_a))
            ib = await db.execute('SELECT quantity FROM inventory WHERE user_id=? AND waifu_id=?', (user_b, waifu_b))
            item_a = await ia.fetchone()
            item_b = await ib.fetchone()
            if not item_a or item_a[0] < 1: return f"Người chơi {user_a} không còn giữ nhân vật này."
            if not item_b or item_b[0] < 1: return f"Người chơi {user_b} không còn giữ nhân vật này."

            await db.execute('UPDATE users SET balance = balance - ? WHERE id = ?', (fee, user_a))
            await db.execute('UPDATE users SET balance = balance - ? WHERE id = ?', (fee, user_b))
            
            if item_a[0] > 1: await db.execute('UPDATE inventory SET quantity = quantity - 1 WHERE user_id=? AND waifu_id=?', (user_a, waifu_a))
            else: await db.execute('DELETE FROM inventory WHERE user_id=? AND waifu_id=?', (user_a, waifu_a))

            iv_a2 = await db.execute('SELECT quantity FROM inventory WHERE user_id=? AND waifu_id=?', (user_a, waifu_b))
            if await iv_a2.fetchone(): await db.execute('UPDATE inventory SET quantity = quantity + 1 WHERE user_id=? AND waifu_id=?', (user_a, waifu_b))
            else: await db.execute('INSERT INTO inventory (user_id, waifu_id, quantity) VALUES (?, ?, 1)', (user_a, waifu_b))

            if item_b[0] > 1: await db.execute('UPDATE inventory SET quantity = quantity - 1 WHERE user_id=? AND waifu_id=?', (user_b, waifu_b))
            else: await db.execute('DELETE FROM inventory WHERE user_id=? AND waifu_id=?', (user_b, waifu_b))

            iv_b2 = await db.execute('SELECT quantity FROM inventory WHERE user_id=? AND waifu_id=?', (user_b, waifu_a))
            if await iv_b2.fetchone(): await db.execute('UPDATE inventory SET quantity = quantity + 1 WHERE user_id=? AND waifu_id=?', (user_b, waifu_a))
            else: await db.execute('INSERT INTO inventory (user_id, waifu_id, quantity) VALUES (?, ?, 1)', (user_b, waifu_a))

            await db.execute('UPDATE server_configs SET value = value + ? WHERE key="bank_fund"', (fee * 2,))
            await db.commit()
            return "success"
        except Exception as e:
            return str(e)
