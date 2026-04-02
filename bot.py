import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

# 1. Tải Token từ file .env
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# 2. Cấu hình Intents (Quyền hạn của bot)
# Intents giúp bot có quyền đọc tin nhắn và theo dõi thành viên
intents = discord.Intents.default()
intents.message_content = True  # Cho phép đọc nội dung tin nhắn
intents.members = True          # Cho phép theo dõi thành viên mới

# 3. Khởi tạo Bot với tiền tố lệnh là '!'
bot = commands.Bot(command_prefix='!', intents=intents)

# Sự kiện: Khi bot đã sẵn sàng hoạt động
@bot.event
async def on_ready():
    print(f'--- Bot {bot.user.name} đã sẵn sàng kết nối! ---')

# Sự kiện: Chào mừng thành viên mới
@bot.event
async def on_member_join(member):
    channel = member.guild.system_channel # Lấy kênh hệ thống của server
    if channel:
        await channel.send(f"Chào mừng {member.mention} đã gia nhập server! 🎉")

# Lệnh: !hello
@bot.command()
async def hello(ctx):
    await ctx.send(f"Chào {ctx.author.name}! Tôi là bot hỗ trợ của bạn đây. 🤖")

# Lệnh: !clear [số lượng] (Chỉ dành cho Admin)
@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int):
    await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"Đã dọn dẹp {amount} tin nhắn!", delete_after=5)

# Xử lý lỗi nếu người dùng không có quyền admin khi dùng lệnh !clear
@clear.error
async def clear_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("Bạn không có quyền 'Quản lý tin nhắn' để dùng lệnh này!")

# Chạy bot
bot.run(TOKEN)