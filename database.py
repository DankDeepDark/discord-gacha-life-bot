import os
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient

# ===== KẾT NỐI MONGODB =====
# Đọc MONGO_URI từ biến môi trường (Render / .env)
MONGO_URI = os.getenv("MONGO_URI", "")

_client: AsyncIOMotorClient = None
_db = None

def _get_db():
    """Trả về database instance (lazy init)."""
    return _db

# ===== KHỞI TẠO DB =====

async def init_db():
    """Khởi tạo kết nối MongoDB và tạo collections + indexes cần thiết."""
    global _client, _db

    if not MONGO_URI:
        print("❌ LỖI: Biến môi trường MONGO_URI chưa được thiết lập!")
        raise ValueError("❌ Biến môi trường MONGO_URI chưa được thiết lập!")

    try:
        # Thêm serverSelectionTimeoutMS=5000 (5 giây) để nếu rớt mạng/sai IP là báo lỗi ngay
        _client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        _db = _client["gacha_bot"]

        # Kiêm tra kết nối thực tế bằng ping
        await _client.admin.command('ping')
        
        # Tạo unique index cho users và inventory
        await _db["users"].create_index("user_id", unique=True)
        await _db["inventory"].create_index([("user_id", 1), ("waifu_id", 1)], unique=True)

        # Khởi tạo Ngân Khố nếu chưa có — mặc định 1,000,000 💰
        existing = await _db["server_configs"].find_one({"key": "bank_fund"})
        if not existing:
            await _db["server_configs"].insert_one({"key": "bank_fund", "value": 1_000_000})
            print("✅ Đã khởi tạo Ngân Khố với 1,000,000 💰")

        print("✅ Đã kết nối MongoDB Atlas thành công!")
    except Exception as e:
        print(f"❌ LỖI KẾT NỐI MONGODB: {str(e)}")
        print("💡 HƯỚNG DẪN: Hãy kiểm tra MONGO_URI trong Environment Variables của Render.")
        print("💡 Đảm bảo bạn đã Whitelist IP 0.0.0.0/0 trên trang MongoDB Atlas.")
        raise e

# ===== USER HELPERS =====

def _default_user(user_id: int) -> dict:
    return {
        "user_id": user_id,
        "balance": 0,
        "join_date": None,
        "crime_success": 0,
        "crime_failure": 0,
        "loan_amount": 0,
        "loan_timestamp": None,
    }

async def _ensure_user(user_id: int):
    """Tạo document user nếu chưa tồn tại."""
    await _db["users"].update_one(
        {"user_id": user_id},
        {"$setOnInsert": _default_user(user_id)},
        upsert=True
    )

# ===== BALANCE =====

async def get_balance(user_id: int) -> int:
    doc = await _db["users"].find_one({"user_id": user_id}, {"balance": 1})
    return doc["balance"] if doc else 0

async def update_balance(user_id: int, amount: int):
    await _ensure_user(user_id)
    doc = await _db["users"].find_one({"user_id": user_id}, {"balance": 1})
    current = doc["balance"] if doc else 0
    new_balance = max(0, current + amount)
    await _db["users"].update_one({"user_id": user_id}, {"$set": {"balance": new_balance}})

async def empty_balance(user_id: int):
    await _db["users"].update_one({"user_id": user_id}, {"$set": {"balance": 0}})

# ===== PROFILE =====

async def init_user_join_date(user_id: int):
    """Ghi join_date lần đầu tiên nếu chưa có."""
    await _ensure_user(user_id)
    now_str = datetime.now().isoformat()
    await _db["users"].update_one(
        {"user_id": user_id, "join_date": None},
        {"$set": {"join_date": now_str}}
    )

async def update_crime_stats(user_id: int, success: bool):
    await _ensure_user(user_id)
    field = "crime_success" if success else "crime_failure"
    await _db["users"].update_one({"user_id": user_id}, {"$inc": {field: 1}})

async def get_user_profile(user_id: int) -> dict:
    doc = await _db["users"].find_one({"user_id": user_id})
    if doc:
        return {
            "balance": doc.get("balance", 0),
            "join_date": doc.get("join_date"),
            "crime_success": doc.get("crime_success", 0),
            "crime_failure": doc.get("crime_failure", 0),
            "loan_amount": doc.get("loan_amount", 0),
            "loan_timestamp": doc.get("loan_timestamp"),
        }
    return {
        "balance": 0, "join_date": None,
        "crime_success": 0, "crime_failure": 0,
        "loan_amount": 0, "loan_timestamp": None,
    }

# ===== INVENTORY =====

async def add_waifu(user_id: int, waifu_id: int):
    await _db["inventory"].update_one(
        {"user_id": user_id, "waifu_id": waifu_id},
        {"$inc": {"quantity": 1}},
        upsert=True
    )

async def get_inventory(user_id: int) -> list:
    cursor = _db["inventory"].find({"user_id": user_id}, {"waifu_id": 1, "quantity": 1, "_id": 0})
    docs = await cursor.to_list(length=None)
    return [(d["waifu_id"], d["quantity"]) for d in docs]

async def remove_waifu(user_id: int, waifu_id: int):
    doc = await _db["inventory"].find_one({"user_id": user_id, "waifu_id": waifu_id})
    if not doc:
        return
    if doc["quantity"] > 1:
        await _db["inventory"].update_one(
            {"user_id": user_id, "waifu_id": waifu_id},
            {"$inc": {"quantity": -1}}
        )
    else:
        await _db["inventory"].delete_one({"user_id": user_id, "waifu_id": waifu_id})

# ===== BANK FUND =====

async def get_bank_fund() -> int:
    doc = await _db["server_configs"].find_one({"key": "bank_fund"})
    return doc["value"] if doc else 0

async def add_bank_fund(amount: int):
    await _db["server_configs"].update_one(
        {"key": "bank_fund"},
        {"$inc": {"value": amount}},
        upsert=True
    )

async def set_bank_fund(amount: int):
    await _db["server_configs"].update_one(
        {"key": "bank_fund"},
        {"$set": {"value": amount}},
        upsert=True
    )

# ===== LOAN =====

async def get_loan_info(user_id: int) -> tuple:
    doc = await _db["users"].find_one({"user_id": user_id}, {"loan_amount": 1, "loan_timestamp": 1})
    if doc:
        return (doc.get("loan_amount", 0), doc.get("loan_timestamp"))
    return (0, None)

async def get_total_debt() -> int:
    pipeline = [
        {"$match": {"loan_amount": {"$gt": 0}}},
        {"$group": {"_id": None, "total": {"$sum": "$loan_amount"}}}
    ]
    result = await _db["users"].aggregate(pipeline).to_list(length=1)
    return result[0]["total"] if result else 0

async def set_loan(user_id: int, amount: int, timestamp):
    await _ensure_user(user_id)
    await _db["users"].update_one(
        {"user_id": user_id},
        {"$set": {"loan_amount": amount, "loan_timestamp": timestamp}}
    )

# ===== ATOMIC TRADE =====

async def execute_trade(user_a: int, user_b: int, waifu_a: int, waifu_b: int, fee: int) -> str:
    """Hoán đổi Waifu giữa hai người dùng. Atomic check trước khi thực thi."""
    try:
        # --- Kiểm tra số dư ---
        bal_a = await get_balance(user_a)
        bal_b = await get_balance(user_b)
        if bal_a < fee:
            return f"Người chơi <@{user_a}> không đủ {fee} 💰 phí giao dịch."
        if bal_b < fee:
            return f"Người chơi <@{user_b}> không đủ {fee} 💰 phí giao dịch."

        # --- Kiểm tra inventory ---
        inv_a = await _db["inventory"].find_one({"user_id": user_a, "waifu_id": waifu_a})
        inv_b = await _db["inventory"].find_one({"user_id": user_b, "waifu_id": waifu_b})
        if not inv_a or inv_a["quantity"] < 1:
            return f"Người chơi <@{user_a}> không còn giữ nhân vật này."
        if not inv_b or inv_b["quantity"] < 1:
            return f"Người chơi <@{user_b}> không còn giữ nhân vật này."

        # --- Trừ phí ---
        await update_balance(user_a, -fee)
        await update_balance(user_b, -fee)

        # --- Hoán đổi Waifu A → B ---
        await remove_waifu(user_a, waifu_a)
        await add_waifu(user_b, waifu_a)

        # --- Hoán đổi Waifu B → A ---
        await remove_waifu(user_b, waifu_b)
        await add_waifu(user_a, waifu_b)

        # --- Phí vào Ngân Khố ---
        await add_bank_fund(fee * 2)

        return "success"
    except Exception as e:
        return str(e)
