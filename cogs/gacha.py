import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
import database
import json
import os
import time
from datetime import datetime

GACHA_COST_X1 = 130
GACHA_COST_X10 = 1300
GACHA_TAX_RATE = 0.05   # 5% chảy vào Ngân Khố
DAILY_REWARD = 5000
COOLDOWN_WORK = 60
COOLDOWN_CRIME = 120

# Biến tạm lưu trữ án phạt vượt ngục khẩn cấp (thêm 5 phút)
PUNISHED_USERS = {}

# Trọng số quay: R (70%), SR (25%), SSR (5%)
RARITY_WEIGHTS = {"R": 70, "SR": 25, "SSR": 5}

WAIFUS = {}
LIST_R = []
LIST_SR = []
LIST_SSR = []

def load_characters():
    global WAIFUS, LIST_R, LIST_SR, LIST_SSR
    file_path = "data/characters.json"
    if not os.path.exists(file_path):
        print(f"Không tìm thấy file {file_path}")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        for k, v in data.items():
            waifu_id = int(k)
            if waifu_id in WAIFUS:
                continue
                
            WAIFUS[waifu_id] = v
            if v["rarity"] == "R":
                LIST_R.append(waifu_id)
            elif v["rarity"] == "SR":
                LIST_SR.append(waifu_id)
            elif v["rarity"] == "SSR":
                LIST_SSR.append(waifu_id)

load_characters()

def get_next_id():
    if not WAIFUS: return 1
    return max(WAIFUS.keys()) + 1

def get_random_waifu():
    rarities = list(RARITY_WEIGHTS.keys())
    weights = list(RARITY_WEIGHTS.values())
    rolled_rarity = random.choices(rarities, weights=weights, k=1)[0]
    
    if rolled_rarity == "SSR" and not LIST_SSR:
        rolled_rarity = "R"
    elif rolled_rarity == "SR" and not LIST_SR:
        rolled_rarity = "R"
        
    if rolled_rarity == "R" and LIST_R:
        waifu_id = random.choice(LIST_R)
    elif rolled_rarity == "SR" and LIST_SR:
        waifu_id = random.choice(LIST_SR)
    elif rolled_rarity == "SSR" and LIST_SSR:
        waifu_id = random.choice(LIST_SSR)
    else:
        waifu_id = random.choice(list(WAIFUS.keys()))
        rolled_rarity = WAIFUS[waifu_id]["rarity"]
        
    return waifu_id, rolled_rarity

async def check_debt(interaction: discord.Interaction) -> bool:
    """Hệ thống xiết nợ ngầm - chạy trước các lệnh kinh tế"""
    amount, ts = await database.get_loan_info(interaction.user.id)
    if amount > 0 and ts:
        try:
            loan_time = datetime.fromisoformat(ts)
            if (datetime.now() - loan_time).total_seconds() > 86400: # 24h
                inv = await database.get_inventory(interaction.user.id)
                if not inv:
                    # Rỗng tuếch -> Xiết sạch tiền, gia hạn thêm khoản nợ 24h để lần sau xiết đồ
                    await database.empty_balance(interaction.user.id)
                    await database.set_loan(interaction.user.id, amount, datetime.now().isoformat())
                    embed = discord.Embed(
                        title="🚨 NGÂN HÀNG ĐEN XIẾT NỢ CƯỠNG CHẾ 🚨", 
                        description="Hạn trả nợ qua rồi! Bổn ngân hàng đã móc cạn túi của bạn dẫu trong đó chả có nổi Waifu nào.\n\n*Nợ vẫn còn nguyên, nộp lại 24h sau sẽ thanh tra tiếp.*", 
                        color=discord.Color.dark_red())
                    await interaction.channel.send(content=f"<@{interaction.user.id}>", embed=embed)
                    if not interaction.response.is_done():
                        await interaction.response.send_message("❌ Lệnh bị gián đoạn vì bạn vừa bị xiết nợ.", ephemeral=True)
                    return False
                else:
                    rarity_order = {"SSR": 0, "SR": 1, "R": 2}
                    def sort_k(x):
                        w = WAIFUS.get(x[0])
                        return rarity_order.get(w["rarity"], 99) if w else 99
                    
                    inv.sort(key=sort_k)
                    target_waifu_id = inv[0][0]
                    w_data = WAIFUS.get(target_waifu_id)
                    
                    await database.remove_waifu(interaction.user.id, target_waifu_id)
                    await database.set_loan(interaction.user.id, 0, None)
                    
                    if w_data and w_data["rarity"] == "SSR":
                        msg = f"🚨 TIN CHẤN ĐỘNG: Đại gia chân đất **{interaction.user.display_name}** vừa bị Ngân Hàng Đen tịch thu siêu phẩm **🌟 [SSR] {w_data['name']}** do nợ nần chồng chất! Mọi khoản nợ đã được xoá sạch. Chia buồn cùng thí chủ, lần sau nhớ trả đúng hạn nhé! 💸🔥"
                        embed = discord.Embed(title="🚨 Báo Động Đỏ Toàn Máy Chủ", description=msg, color=discord.Color.dark_red())
                        await interaction.channel.send(content=f"<@{interaction.user.id}>", embed=embed)
                    else:
                        msg = f"Ngân Hàng Đen đã cưỡng chế tịch thu em nhân vật **{w_data['emoji']} [{w_data['rarity']}] {w_data['name']}** để thay khoản nợ xấu của bạn.\n\n*Khoản nợ của bạn đã được xóa sạch.*"
                        embed = discord.Embed(title="🚨 XIẾT NỢ CƯỠNG CHẾ", description=msg, color=discord.Color.dark_red())
                        await interaction.channel.send(content=f"<@{interaction.user.id}>", embed=embed)
                    
                    if not interaction.response.is_done():
                        await interaction.response.send_message("❌ Lệnh bị gián đoạn vì bạn bị xiết nợ, hãy thử lại.", ephemeral=True)
                    return False
        except Exception as e:
            print("Debt check error:", e)
    return True

def get_pity_waifu() -> tuple:
    """Lượt bảo hiểm: 95% SR, 5% SSR"""
    pool = []
    weights = []
    if LIST_SR:
        pool.append("SR")
        weights.append(95)
    if LIST_SSR:
        pool.append("SSR")
        weights.append(5)
    if not pool:  # Fallback nếu không có SR/SSR nào
        return get_random_waifu()
    
    rarity = random.choices(pool, weights=weights, k=1)[0]
    if rarity == "SR":
        return random.choice(LIST_SR), "SR"
    return random.choice(LIST_SSR), "SSR"

async def resolve_image_url(url: str) -> str:
    """Kiểm tra link ảnh hợp lệ, trả về placeholder nếu lỗi"""
    if not url:
        return "https://via.placeholder.com/500?text=No+Image"
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.head(url, timeout=2, headers={'User-Agent': 'Mozilla/5.0'}) as resp:
                if resp.status < 400:
                    return url
    except Exception:
        pass
    return "https://via.placeholder.com/500?text=Image+NotFound"

def rarity_rank(rarity: str) -> int:
    return {"SSR": 0, "SR": 1, "R": 2}.get(rarity, 99)

def rarity_color(rarity: str) -> discord.Color:
    return {"SSR": discord.Color.gold(), "SR": discord.Color.purple()}.get(rarity, discord.Color.blue())

def rarity_emoji(rarity: str) -> str:
    return {"SSR": "🌟", "SR": "💜", "R": "💙"}.get(rarity, "")

# ===== GACHA CORE ENGINE =====

async def perform_gacha_x1(user_id: int) -> dict:
    """Quay x1, trừ tiền + thuế, trả về data"""
    waifu_id, rarity = get_random_waifu()
    cost = GACHA_COST_X1
    tax = max(1, int(cost * GACHA_TAX_RATE))
    await database.update_balance(user_id, -cost)
    await database.add_bank_fund(tax)
    await database.add_waifu(user_id, waifu_id)
    return {"waifu_id": waifu_id, "rarity": rarity, "cost": cost, "tax": tax}

async def perform_gacha_x10(user_id: int) -> list:
    """Quay x10 với Pity (bảo hiểm lượt 10), trả về list 10 kết quả"""
    cost = GACHA_COST_X10
    tax = max(1, int(cost * GACHA_TAX_RATE))
    await database.update_balance(user_id, -cost)
    await database.add_bank_fund(tax)

    results = []
    has_rare = False
    for i in range(10):
        if i == 9 and not has_rare:
            # Kích hoạt Bảo Hiểm: Guaranteed SR hoặc SSR (95/5)
            waifu_id, rarity = get_pity_waifu()
        else:
            waifu_id, rarity = get_random_waifu()
        
        if rarity in ("SR", "SSR"):
            has_rare = True
        
        await database.add_waifu(user_id, waifu_id)
        results.append({"waifu_id": waifu_id, "rarity": rarity})
    
    return results

# ===== GACHA ACTION VIEW (Nút quay tiếp) =====

class GachaActionView(discord.ui.View):
    """View nút bấm Quay tiếp sau mỗi lần roll thành công"""
    def __init__(self, user: discord.Member):
        super().__init__(timeout=60)
        self.user = user

    async def _handle_roll(self, interaction: discord.Interaction, mode: str):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Máy quay này không phải của bạn!", ephemeral=True)
            return

        cost = GACHA_COST_X1 if mode == "x1" else GACHA_COST_X10
        balance = await database.get_balance(self.user.id)

        if balance < cost:
            broke_embed = discord.Embed(
                title="💸 Túi Tiền Đã Khô Cạn!",
                description=f"Bạn cần **{cost}** 💰 để quay {mode} nhưng chỉ còn **{balance}** 💰.\n\n"
                            f"💡 Hãy ghé **Ngân Hàng Đen** (`/borrow`) để tìm kiếm vận may!\n"
                            f"   Hoặc cày thêm qua `/work` và `/daily`.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=broke_embed, ephemeral=True)
            return

        # Disable nút, cho thấy loading
        for child in self.children:
            child.disabled = True
        loading = discord.Embed(
            title=f"✨ Đang Triệu Hồi {mode.upper()}... ⏳",
            description="Vận mệnh đang được định đoạt...",
            color=discord.Color.blurple()
        )
        await interaction.response.edit_message(embed=loading, view=self)
        await asyncio.sleep(1.2)

        new_balance = await database.get_balance(self.user.id)
        new_view = GachaActionView(self.user)

        if mode == "x1":
            result = await perform_gacha_x1(self.user.id)
            w = WAIFUS[result["waifu_id"]]
            final_url = await resolve_image_url(w.get("image", ""))
            after_bal = new_balance - result["cost"]
            embed = discord.Embed(
                title="🎉 Kết Quả Triệu Hồi x1 🎉",
                description=f"**{w['emoji']} [{result['rarity']}] {w['name']}**\n"
                            f"Nguồn: *{w.get('origin', 'Không rõ')}*\n\n"
                            f"💰 Còn lại: **{after_bal}** 💰  ( -{result['cost']} | Thuế: {result['tax']} → 🏦 )",
                color=rarity_color(result["rarity"])
            )
            embed.set_image(url=final_url)
        else:  # x10
            results = await perform_gacha_x10(self.user.id)
            embed, new_view = await _build_x10_embed(self.user, results, new_balance)

        await interaction.edit_original_response(embed=embed, view=new_view)

    @discord.ui.button(label="🎴 Quay tiếp x1 (130💰)", style=discord.ButtonStyle.primary)
    async def roll_x1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_roll(interaction, "x1")

    @discord.ui.button(label="🎰 Quay tiếp x10 (1300💰)", style=discord.ButtonStyle.success)
    async def roll_x10(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_roll(interaction, "x10")

async def _build_x10_embed(user: discord.Member, results: list, balance_before: int):
    """Xây Embed summary kết quả x10 + GachaActionView"""
    rarity_order = {"SSR": 0, "SR": 1, "R": 2}
    # Sắp xếp theo độ hiếm để lấy con xịn nhất
    sorted_results = sorted(results, key=lambda r: rarity_order.get(r["rarity"], 99))
    best = sorted_results[0]
    best_w = WAIFUS[best["waifu_id"]]

    lines = []
    for i, r in enumerate(results, 1):
        w = WAIFUS[r["waifu_id"]]
        star = "✦" if r["rarity"] == "SSR" else ("◆" if r["rarity"] == "SR" else "·")
        pity_tag = " ⚡*Bảo Hiểm*" if i == 10 and r["rarity"] in ("SR", "SSR") else ""
        lines.append(f"`{i:02d}.` {w['emoji']} **[{r['rarity']}]** {w['name']}{pity_tag}")

    tax_total = max(1, int(GACHA_COST_X10 * GACHA_TAX_RATE))
    after_bal = balance_before - GACHA_COST_X10

    embed = discord.Embed(
        title=f"{rarity_emoji(best['rarity'])} Kết Quả Triệu Hồi x10 {rarity_emoji(best['rarity'])}",
        description="\n".join(lines),
        color=rarity_color(best["rarity"])
    )
    embed.add_field(
        name="📊 Tổng Kết",
        value=f"💰 Còn lại: **{after_bal}** 💰  ( -{GACHA_COST_X10} | Thuế: {tax_total} → 🏦 )",
        inline=False
    )
    # Ảnh: con hiếm nhất
    best_url = await resolve_image_url(best_w.get("image", ""))
    embed.set_image(url=best_url)
    embed.set_footer(text=f"Nhân vật xịn nhất: {best_w['emoji']} {best_w['name']} [{best['rarity']}]")

    new_view = GachaActionView(user)
    return embed, new_view


class WaifuSelectMenu(discord.ui.Select):
    def __init__(self, parent_view, options):
        super().__init__(placeholder="🌟 Xem chi tiết nhân vật...", min_values=1, max_values=1, options=options)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.parent_view.user.id:
            await interaction.response.send_message("Đây không phải túi đồ của bạn!", ephemeral=True)
            return
            
        self.parent_view.detail_waifu_id = int(self.values[0])
        self.parent_view.render_components()
        await interaction.response.edit_message(embed=await self.parent_view.generate_detail_embed(), view=self.parent_view)

class ProfileView(discord.ui.View):
    def __init__(self, user: discord.Member, profile_data: dict, inventory_list: list):
        super().__init__(timeout=120)
        self.user = user
        self.profile_data = profile_data
        self.inventory_list = inventory_list
        self.current_page = 0
        self.items_per_page = 10
        self.max_page = max(0, (len(inventory_list) - 1) // self.items_per_page)
        self.show_inventory = False
        self.detail_waifu_id = None

    def generate_profile_embed(self) -> discord.Embed:
        balance = self.profile_data["balance"]
        join_date = self.profile_data["join_date"]
        c_s = self.profile_data["crime_success"]
        c_f = self.profile_data["crime_failure"]

        display_days = "Không rõ"
        if join_date:
            try:
                jd = datetime.fromisoformat(join_date).date()
                today = datetime.now().date()
                days_diff = (today - jd).days
                if days_diff == 0: display_days = "Ngày đầu tiên"
                else: display_days = f"Ngày thứ {days_diff + 1}"
            except: pass

        ssr_count = sr_count = r_count = 0
        for w_id, _ in self.inventory_list:
            w = WAIFUS.get(w_id)
            if w:
                if w["rarity"] == "SSR": ssr_count += 1
                elif w["rarity"] == "SR": sr_count += 1
                elif w["rarity"] == "R": r_count += 1

        total_waifu = len(WAIFUS)
        collected_waifu = len(self.inventory_list)

        embed = discord.Embed(title=f"Hồ Sơ Của {self.user.display_name}", color=discord.Color.blue())
        embed.add_field(name="💰 Tài chính", value=f"**{balance}** 💰", inline=False)
        if self.profile_data.get("loan_amount", 0) > 0:
            loan = self.profile_data["loan_amount"]
            embed.add_field(name="🏦 Dư Nợ Tín Dụng", value=f"**{loan}** 💰 (Sẽ bị xiết nợ sau 24h)", inline=False)
        embed.add_field(name="🎒 Bộ sưu tập", value=f"**{collected_waifu}/{total_waifu}**, Loại: (SSR: {ssr_count}, SR: {sr_count}, R: {r_count})", inline=False)
        embed.add_field(name="🎭 Hành trình", value=f"**{display_days}**", inline=False)
        embed.add_field(name="⚖️ Tiền án", value=f"**{c_s}** thành công | **{c_f}** lần bị còng", inline=False)
        
        if self.user.display_avatar:
            embed.set_thumbnail(url=self.user.display_avatar.url)
        return embed

    def generate_inventory_embed(self) -> discord.Embed:
        embed = discord.Embed(title=f"🎒 Túi đồ của {self.user.display_name}", color=discord.Color.purple())
        if not self.inventory_list:
            embed.description = "Túi của bạn trống trơn!"
            return embed

        start_idx = self.current_page * self.items_per_page
        end_idx = start_idx + self.items_per_page
        page_items = self.inventory_list[start_idx:end_idx]

        desc = ""
        for waifu_id, quantity in page_items:
            w_data = WAIFUS.get(waifu_id)
            if w_data:
                origin = w_data.get('origin', 'Không rõ')
                desc += f"`[{w_data['rarity']}]` {w_data['emoji']} **{w_data['name']}** ({origin}) x{quantity}\n"
            else:
                desc += f"Nhân vật ID {waifu_id} x{quantity}\n"
        
        embed.description = desc
        embed.set_footer(text=f"Trang {self.current_page + 1}/{self.max_page + 1}")
        return embed

    async def generate_detail_embed(self) -> discord.Embed:
        w_data = WAIFUS.get(self.detail_waifu_id)
        embed = discord.Embed(
            title=f"🌟 {w_data['emoji']} {w_data['name']} 🌟",
            description=f"**Độ hiếm**: {w_data['rarity']}\n**Nguồn gốc**: {w_data.get('origin', 'Không rõ')}",
            color=discord.Color.gold()
        )
        
        final_image_url = "https://via.placeholder.com/500?text=Image+NotFound"
        if w_data.get("image"):
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    headers = {'User-Agent': 'Mozilla/5.0'}
                    async with session.head(w_data["image"], timeout=2, headers=headers) as resp:
                        if resp.status < 400: final_image_url = w_data["image"]
            except: pass
        
        embed.set_image(url=final_image_url)
        embed.set_footer(text=f"Sở hữu bởi {self.user.display_name}")
        return embed

    def render_components(self):
        self.clear_items()
        
        if self.detail_waifu_id is not None:
            btn_share = discord.ui.Button(label="📢 Chia sẻ", style=discord.ButtonStyle.success)
            btn_share.callback = self.on_share_click
            self.add_item(btn_share)

            btn_back = discord.ui.Button(label="🔙 Quay lại", style=discord.ButtonStyle.danger)
            btn_back.callback = self.on_detail_back_click
            self.add_item(btn_back)
            
        elif not self.show_inventory:
            btn_inv = discord.ui.Button(label="🎒 Xem Túi Đồ", style=discord.ButtonStyle.primary)
            btn_inv.callback = self.on_inventory_click
            self.add_item(btn_inv)

            btn_achieve = discord.ui.Button(label="🏆 Thành Tựu", style=discord.ButtonStyle.secondary, disabled=True)
            self.add_item(btn_achieve)
        else:
            start_idx = self.current_page * self.items_per_page
            end_idx = start_idx + self.items_per_page
            page_items = self.inventory_list[start_idx:end_idx]
            
            options = []
            for w_id, qty in page_items:
                w = WAIFUS.get(w_id)
                if w:
                    options.append(discord.SelectOption(
                        label=f"{w['name']} x{qty}",
                        description=f"Độ hiếm: {w['rarity']}",
                        emoji=w['emoji'],
                        value=str(w_id)
                    ))
            
            if options:
                self.add_item(WaifuSelectMenu(self, options))

            btn_prev = discord.ui.Button(label="⬅️ Trang trước", style=discord.ButtonStyle.secondary, disabled=self.current_page == 0)
            btn_prev.callback = self.prev_page
            self.add_item(btn_prev)

            btn_next = discord.ui.Button(label="Trang sau ➡️", style=discord.ButtonStyle.secondary, disabled=self.current_page >= self.max_page)
            btn_next.callback = self.next_page
            self.add_item(btn_next)

            btn_back = discord.ui.Button(label="🔙 Quay lại", style=discord.ButtonStyle.danger)
            btn_back.callback = self.on_back_click
            self.add_item(btn_back)

    async def on_share_click(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id: return
        w_data = WAIFUS.get(self.detail_waifu_id)
        if not w_data: return
        
        share_embed = discord.Embed(
            description=f"🌟 {self.user.mention} đang khoe nhân vật **{w_data['name']}** cực xịn!",
            color=discord.Color.gold()
        )
        if w_data.get("image"): share_embed.set_image(url=w_data["image"])
        await interaction.channel.send(embed=share_embed)
        await interaction.response.send_message("✅ Đã gửi hình ảnh lên kênh!", ephemeral=True)

    async def on_detail_back_click(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id: return
        self.detail_waifu_id = None
        self.render_components()
        await interaction.response.edit_message(embed=self.generate_inventory_embed(), view=self)

    async def on_inventory_click(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id: return
        self.show_inventory = True
        self.render_components()
        await interaction.response.edit_message(embed=self.generate_inventory_embed(), view=self)

    async def on_back_click(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id: return
        self.show_inventory = False
        self.render_components()
        await interaction.response.edit_message(embed=self.generate_profile_embed(), view=self)

    async def prev_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id: return
        self.current_page -= 1
        self.render_components()
        await interaction.response.edit_message(embed=self.generate_inventory_embed(), view=self)

    async def next_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id: return
        self.current_page += 1
        self.render_components()
        await interaction.response.edit_message(embed=self.generate_inventory_embed(), view=self)

class CrimeView(discord.ui.View):
    def __init__(self, user: discord.Member):
        super().__init__(timeout=30)
        self.user = user

    @discord.ui.button(label="💸 Hối lộ (300 💰)", style=discord.ButtonStyle.success)
    async def bribe_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id: return
        balance = await database.get_balance(self.user.id)
        if balance < 300:
            await interaction.response.send_message("Bạn không đủ 300 💰 để hối lộ đâu!", ephemeral=True)
            return

        for child in self.children: child.disabled = True
        await database.update_balance(self.user.id, 700)
        
        embed = interaction.message.embeds[0]
        embed.description += "\n\n💸 **Cập nhật:** Bạn đã hối lộ thành công và được thả tự do!"
        embed.color = discord.Color.gold()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🏃 Vượt ngục", style=discord.ButtonStyle.danger)
    async def escape_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id: return
        for child in self.children: child.disabled = True

        embed = interaction.message.embeds[0]
        if random.random() <= 0.25:
            await database.update_balance(self.user.id, 1000)
            embed.description += "\n\n🔥 **Kết quả:** Đào hầm trốn thoát ngoạn mục! 🕶️"
            embed.color = discord.Color.green()
        else:
            await database.update_balance(self.user.id, -500)
            PUNISHED_USERS[self.user.id] = time.time() + 300
            embed.description += "\n\n⛓️ **Khởi tố thêm:** Bị phạt 500 💰.\nHình phạt 5 phút án tù đã kích hoạt."
            embed.color = discord.Color.dark_red()

        await interaction.response.edit_message(embed=embed, view=self)

# ================= TRADE CLASSES ================= 

class TradeTargetSelectMenu(discord.ui.Select):
    def __init__(self, parent_view, options):
        super().__init__(placeholder="🌟 Chọn vật phẩm cướp từ người ấy...", min_values=1, max_values=1, options=options)
        self.parent_view = parent_view
        
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.parent_view.user_a.id:
            await interaction.response.send_message("Bạn không phải người tạo giao dịch!", ephemeral=True)
            return

        self.parent_view.waifu_b = int(self.values[0])
        for child in self.parent_view.children: child.disabled = True
        await interaction.response.edit_message(embed=discord.Embed(description="✅ Hệ thống đang vứt Hợp Đồng vào Kênh. Đọc kênh nhé!"), view=None)
        await self.parent_view.start_confirm(interaction)

class TradeSetupSelectMenu(discord.ui.Select):
    def __init__(self, parent_view, options):
        super().__init__(placeholder="🌟 Chọn Waifu bạn đem ra mồi chài...", min_values=1, max_values=1, options=options)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.parent_view.user_a.id:
            await interaction.response.send_message("Đây không phải giao dịch của bạn!", ephemeral=True)
            return
            
        self.parent_view.waifu_a = int(self.values[0])
        await self.parent_view.step_two(interaction)

class TradeConfirmView(discord.ui.View):
    def __init__(self, user_a, user_b, waifu_a, waifu_b):
        super().__init__(timeout=60)
        self.user_a = user_a
        self.user_b = user_b
        self.waifu_a = waifu_a
        self.waifu_b = waifu_b

    @discord.ui.button(label="✅ Đồng ý", style=discord.ButtonStyle.success)
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_b.id:
            await interaction.response.send_message("Bạn có phải dân bị gạ kèo đâu mà click?", ephemeral=True)
            return

        for child in self.children: child.disabled = True
        status = await database.execute_trade(self.user_a.id, self.user_b.id, self.waifu_a, self.waifu_b, 500)
        embed = interaction.message.embeds[0]

        if status == "success":
            embed.title = "✅ GIAO DỊCH THÀNH CÔNG"
            embed.color = discord.Color.green()
            embed.description += "\n\n🤝 Hợp đồng đã đóng mộc đỏ! Hai bên mất 500 💰 tiền thuế, Ngân Hàng nhét đầy mồm 1000 💰."
        else:
            embed.title = "❌ BỂ KÈO! QUÁ TRÌNH HOÁN ĐỔI BỊ CHẶN LẠI!"
            embed.color = discord.Color.red()
            embed.description += f"\n\nLỗi: {status}"
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="❌ Từ chối", style=discord.ButtonStyle.danger)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in [self.user_a.id, self.user_b.id]:
            await interaction.response.send_message("Bạn đâu có phận sự trong hợp đồng này?", ephemeral=True)
            return

        for child in self.children: child.disabled = True
        embed = interaction.message.embeds[0]
        embed.title = "❌ GIAO DỊCH BỊ XÉ BỎ"
        embed.color = discord.Color.dark_grey()
        embed.description += "\n\nHợp đồng rác này đã bị đốt."
        await interaction.response.edit_message(embed=embed, view=self)

class TradeSetupView(discord.ui.View):
    def __init__(self, user_a, user_b, target_inv):
        super().__init__(timeout=60)
        self.user_a = user_a
        self.user_b = user_b
        self.target_inv = target_inv
        self.waifu_a = None
        self.waifu_b = None

    async def step_two(self, interaction: discord.Interaction):
        self.clear_items()
        options = []
        for w_id, qty in self.target_inv[:25]:
            w = WAIFUS.get(w_id)
            if w: options.append(discord.SelectOption(label=f"{w['name']}", description=f"{w['rarity']}", emoji=w['emoji'], value=str(w_id)))
        
        self.add_item(TradeTargetSelectMenu(self, options))
        embed = discord.Embed(title="Giao dịch - Bước 2/2", description=f"Chọn món bạn nhắm tới từ giỏ hàng của {self.user_b.display_name}. (Chỉ hiện 25 con đầu)", color=discord.Color.blue())
        await interaction.response.edit_message(embed=embed, view=self)

    async def start_confirm(self, interaction: discord.Interaction):
        view = TradeConfirmView(self.user_a, self.user_b, self.waifu_a, self.waifu_b)
        wa = WAIFUS.get(self.waifu_a)
        wb = WAIFUS.get(self.waifu_b)
        desc = f"📜 **{self.user_a.mention}** đã đặt một khế ước lên bàn và rủ **{self.user_b.mention}** ký tên!\n\n"
        desc += f"💱 Bạn đưa nó: **{wa['emoji']} [{wa['rarity']}] {wa['name']}**\n"
        desc += f"💱 Nó bị móc mất: **{wb['emoji']} [{wb['rarity']}] {wb['name']}**\n\n"
        desc += "💰 Phí Môi Giới: **500 💰** trừ vào kho mỗi người.\n\n"
        desc += f"➡️ Cân nhắc kỹ lưỡng và xác nhận đi nhé, hỡi {self.user_b.mention}! (60s)"
        embed = discord.Embed(title="🤝 YÊU CẦU TIẾN HÀNH GIAO DỊCH", description=desc, color=discord.Color.gold())
        await interaction.channel.send(content=f"{self.user_b.mention}", embed=embed, view=view)


class GachaCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="daily", description="Nhận tiền mỗi 24 giờ!")
    @app_commands.checks.cooldown(1, 86400.0, key=lambda i: i.user.id)
    async def daily(self, interaction: discord.Interaction):
        if not await check_debt(interaction): return
        await database.update_balance(interaction.user.id, DAILY_REWARD)
        await database.init_user_join_date(interaction.user.id)
        balance = await database.get_balance(interaction.user.id)
        
        embed = discord.Embed(
            title="🎁 Phần Thưởng Hàng Ngày",
            description=f"Bạn vừa nhận được **{DAILY_REWARD}** 💰!\nTổng tài sản: **{balance}** 💰",
            color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed)

    @daily.error
    async def daily_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            mins, secs = divmod(int(error.retry_after), 60)
            hours, mins = divmod(mins, 60)
            await interaction.response.send_message(f"⌛ Bạn đã nhận quà rồi! Hãy quay lại sau `{hours}h {mins}m {secs}s`.", ephemeral=True)

    @app_commands.command(name="gacha", description="Quay triệu hồi nhân vật (x1: 130💰 | x10: 1300💰 + Bảo Hiểm)")
    @app_commands.describe(mode="Chọn x1 để quay đơn hoặc x10 để quay gói (có Bảo Hiểm SR/SSR)")
    @app_commands.choices(mode=[
        app_commands.Choice(name="🎴 Quay x1 — 130 💰", value="x1"),
        app_commands.Choice(name="🎰 Quay x10 — 1300 💰 (Bảo Hiểm SR/SSR)", value="x10"),
    ])
    async def gacha(self, interaction: discord.Interaction, mode: str = "x1"):
        if not await check_debt(interaction): return
        cost = GACHA_COST_X1 if mode == "x1" else GACHA_COST_X10
        balance = await database.get_balance(interaction.user.id)

        if balance < cost:
            broke_embed = discord.Embed(
                title="💸 Túi Tiền Trống Rỗng!",
                description=f"Bạn cần **{cost}** 💰 để quay **{mode}** nhưng chỉ có **{balance}** 💰.\n\n"
                            f"💡 Hãy ghé **Ngân Hàng Đen** (`/borrow`) để tìm kiếm vận may!\n"
                            f"   Hoặc cày thêm tiền qua `/work` và `/daily`.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=broke_embed, ephemeral=True)
            return

        # Hiển thị loading
        loading_embed = discord.Embed(
            title=f"✨ Đang Triệu Hồi {mode.upper()}... ⏳",
            description="Vận mệnh đang được định đoạt...",
            color=discord.Color.blurple()
        )
        await interaction.response.send_message(embed=loading_embed)
        await asyncio.sleep(1.2)

        new_balance = await database.get_balance(interaction.user.id)

        if mode == "x1":
            result = await perform_gacha_x1(interaction.user.id)
            w = WAIFUS[result["waifu_id"]]
            final_url = await resolve_image_url(w.get("image", ""))
            after_bal = new_balance - result["cost"]
            embed = discord.Embed(
                title="🎉 Kết Quả Triệu Hồi x1 🎉",
                description=f"**{w['emoji']} [{result['rarity']}] {w['name']}**\n"
                            f"Nguồn: *{w.get('origin', 'Không rõ')}*\n\n"
                            f"💰 Còn lại: **{after_bal}** 💰  ( -{result['cost']} | Thuế: {result['tax']} → 🏦 )",
                color=rarity_color(result["rarity"])
            )
            embed.set_image(url=final_url)
            view = GachaActionView(interaction.user)
        else:
            results = await perform_gacha_x10(interaction.user.id)
            embed, view = await _build_x10_embed(interaction.user, results, new_balance)

        await interaction.edit_original_response(embed=embed, view=view)


    @app_commands.command(name="work", description="Làm công ăn lương (500-1000 💰)")
    @app_commands.checks.cooldown(1, float(COOLDOWN_WORK), key=lambda i: i.user.id)
    async def work(self, interaction: discord.Interaction):
        if not await check_debt(interaction): return
        reward = random.randint(500, 1000)
        await database.update_balance(interaction.user.id, reward)
        embed = discord.Embed(
            title="🛠️ Làm Việc Chăm Chỉ",
            description=f"Thành quả lao động của bạn là nhận được **{reward}** 💰!",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @work.error
    async def work_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            m, s = divmod(int(error.retry_after), 60)
            await interaction.response.send_message(f"⌛ Đang mệt! Hãy nghỉ ngơi `{m}m {s}s` nữa.", ephemeral=True)

    @app_commands.command(name="crime", description="Thử vận may phi pháp (Thưởng cao, phạt đậm)")
    @app_commands.checks.cooldown(1, float(COOLDOWN_CRIME), key=lambda i: i.user.id)
    async def crime(self, interaction: discord.Interaction):
        if not await check_debt(interaction): return
        if interaction.user.id in PUNISHED_USERS:
            rem = PUNISHED_USERS[interaction.user.id] - time.time()
            if rem > 0:
                m, s = divmod(int(rem), 60)
                await interaction.response.send_message(f"⛓️ Đang trong giờ giam lỏng. Mãn hạn trong `{m}m {s}s`.", ephemeral=True)
                return
            else:
                del PUNISHED_USERS[interaction.user.id]

        if random.random() <= 0.45:
            reward = random.randint(2000, 5000)
            await database.update_balance(interaction.user.id, reward)
            await database.update_crime_stats(interaction.user.id, True)
            embed = discord.Embed(title="🦹 Phi Vụ Trót Lọt", description=f"Không có bóng cớm nào. Ẵm trọn **{reward}** 💰.", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)
        else:
            await database.update_balance(interaction.user.id, -1000)
            await database.update_crime_stats(interaction.user.id, False)
            embed = discord.Embed(title="🚓 Bị Tóm Cổ!~", description=f"Đã bị bắt quả tang! Đóng xấp phạt **1000** 💰.\n\n*Vậy bạn làm gì? Hối lộ hay vượt biên?*", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, view=CrimeView(interaction.user))
        
    @crime.error
    async def crime_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            m, s = divmod(int(error.retry_after), 60)
            await interaction.response.send_message(f"🚓 Cảnh sát đầy đường. Rình lại sau `{m}m {s}s`.", ephemeral=True)

    @app_commands.command(name="profile", description="Xem sơ yếu lý lịch và tải sản (Kho Đồ)")
    async def profile(self, interaction: discord.Interaction):
        p_data = await database.get_user_profile(interaction.user.id)
        if not p_data: p_data = {"balance": 0, "join_date": None, "crime_success": 0, "crime_failure": 0}
        inventory = await database.get_inventory(interaction.user.id)
        
        rarity_order = {"SSR": 0, "SR": 1, "R": 2}
        def sort_key(item):
            w = WAIFUS.get(item[0])
            return (rarity_order.get(w["rarity"], 3), w["name"]) if w else (99, "")
        sorted_inv = sorted(inventory, key=sort_key)
        
        view = ProfileView(interaction.user, p_data, sorted_inv)
        view.render_components() 
        await interaction.response.send_message(embed=view.generate_profile_embed(), view=view)

    @app_commands.command(name="trade", description="Cáp kèo trade nhân vật với bạn bè (Kèo máu 500đ phí/người)")
    async def trade(self, interaction: discord.Interaction, target: discord.Member):
        if not await check_debt(interaction): return
        if target.bot:
            await interaction.response.send_message("Bot không có nhu cầu cờ bạc với loài người.", ephemeral=True)
            return
        if interaction.user.id == target.id:
            await interaction.response.send_message("Bạn bị ảo giác à? Tự trade với mình?", ephemeral=True)
            return

        inv_a = await database.get_inventory(interaction.user.id)
        inv_b = await database.get_inventory(target.id)

        if not inv_a:
            await interaction.response.send_message("Nhà nghèo rớt mồng tơi làm gì có đồ mà đi Trade?", ephemeral=True)
            return
        if not inv_b:
            await interaction.response.send_message(f"Tội nghiệp {target.display_name}, họ chả có tài sản nào cả.", ephemeral=True)
            return

        view = TradeSetupView(interaction.user, target, inv_b)
        options = []
        for w_id, qty in inv_a[:25]:
            w = WAIFUS.get(w_id)
            if w: options.append(discord.SelectOption(label=f"{w['name']}", description=f"{w['rarity']}", emoji=w['emoji'], value=str(w_id)))

        view.add_item(TradeSetupSelectMenu(view, options))
        embed = discord.Embed(title="Giao Dịch - Bước 1/2", description="Chọn con hàng bạn mang đi thế mạng. (Tối đa 25 con đầu)", color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="borrow", description="Vay 20% lãi suất từ Ngân hàng Đen. (Tối đa 50% quỹ tổng hiện tại)")
    async def borrow(self, interaction: discord.Interaction, amount: int):
        if amount <= 0:
            await interaction.response.send_message("Mức vay không hợp lệ!", ephemeral=True)
            return
        
        bank_fund = await database.get_bank_fund()
        max_borrow = bank_fund // 2

        if amount > max_borrow:
            embed = discord.Embed(
                title="🏦 Yêu Cầu Từ Chối",
                description=f"Ngân khố hiện tại chỉ có **{bank_fund}** 💰.\n⚠️ Mức vay tối đa (50%) của bạn là: **{max_borrow}** 💰.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        current_loan, _ = await database.get_loan_info(interaction.user.id)
        if current_loan > 0:
            await interaction.response.send_message("Vẫn còn nợ xấu chưa thanh toán! Trả hết nợ cũ đi đã!", ephemeral=True)
            return

        total_debt = int(amount * 1.2)
        await database.update_balance(interaction.user.id, amount)
        await database.add_bank_fund(-amount)
        await database.set_loan(interaction.user.id, total_debt, datetime.now().isoformat())

        embed = discord.Embed(
            title="🏦 Hợp Đồng Cho Vay Nặng Lãi", 
            description=f"Ngân hàng Đen đã giải ngân **{amount}** 💰.\n📌 Tổng dư nợ phải trả sau 24h là: **{total_debt}** 💰.\n\n*Nếu không trả, Waifu đắt giá nhất của bạn sẽ ra đi!*",
            color=discord.Color.dark_grey()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="bank", description="Xem trạng thái tài chính của Ngân Khố Server")
    async def bank(self, interaction: discord.Interaction):
        bank_fund = await database.get_bank_fund()
        is_admin = interaction.user.guild_permissions.administrator
        
        status = "Bình thường"
        if bank_fund < 1000: status = "Sắp phá sản (Rất nghèo)"
        elif bank_fund >= 10000: status = "Dồi dào (Kho xịn)"
        elif bank_fund >= 50000: status = "Phú Khả Địch Quốc (Siêu giàu)"

        embed = discord.Embed(
            title="🏦 Quản Lý Ngân Khố Máy Chủ",
            description=f"**Tình trạng:** {status}",
            color=discord.Color.dark_theme()
        )
        embed.add_field(name="💰 Tổng Ngân Khố", value=f"**{bank_fund}** 💰", inline=False)
        
        if is_admin:
            total_debt = await database.get_total_debt()
            embed.add_field(name="💸 Dư Nợ Tín Dụng Lũy Kế", value=f"**{total_debt}** 💰", inline=False)
            embed.set_footer(text="Góc nhìn của Quản trị viên (Admin)")
            
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="admin_setbank", description="[ADMIN] Kiểm soát hoàn toàn thiết lập Ngân Khố")
    async def admin_setbank(self, interaction: discord.Interaction, amount: int):
        # Nếu Không phải admin -> Báo lỗi
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Kẻ mạo danh! Lệnh này chỉ dành cho Admin Server.", ephemeral=True)
            return

        if amount < 0:
            await interaction.response.send_message("❌ Số lượng tiền set vào không hợp lệ.", ephemeral=True)
            return
            
        await database.set_bank_fund(amount)
        embed = discord.Embed(
            title="🏦 Can Thiệp Ngân Khố Đặc Biệt",
            description=f"Admin **{interaction.user.display_name}** đã điều chỉnh mạch máu tiền tệ!\n💰 Số dư Ngân khố hiện tại được thiết lập cứng thành: **{amount}**.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="payback", description="Trả nợ cho xã hội đen.")
    async def payback(self, interaction: discord.Interaction):
        current_loan, _ = await database.get_loan_info(interaction.user.id)
        if current_loan <= 0:
            await interaction.response.send_message("Mày có nợ anh đồng nào đâu mà trả?", ephemeral=True)
            return

        balance = await database.get_balance(interaction.user.id)
        if balance < current_loan:
            await interaction.response.send_message(f"Tài khoản chỉ có {balance} cục tiền chẵn, làm sao trả khoản nợ đầm đìa {current_loan} đây hả? Lo gom lúa đi con trai!", ephemeral=True)
            return

        await database.update_balance(interaction.user.id, -current_loan)
        await database.add_bank_fund(current_loan)
        await database.set_loan(interaction.user.id, 0, None)

        await interaction.response.send_message(embed=discord.Embed(title="🏦 Xóa Nợ", description=f"Sòng phẳng! Đã đập **{current_loan}** 💰 vào mặt Ngân Hàng, nợ nần được phong ấn.", color=discord.Color.green()))

async def setup(bot):
    await bot.add_cog(GachaCog(bot))
