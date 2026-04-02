import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import database

# Tải Token từ file .env
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Cấu hình Intents
intents = discord.Intents.default()
intents.message_content = True

class GachaBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        # Khởi tạo database
        await database.init_db()
        print("Đã khởi tạo Database.")
        
        # Load các cogs
        await self.load_extension("cogs.gacha")
        print("Đã tải cog Gacha.")

        # Đồng bộ Slash Commands
        await self.tree.sync()
        print("Đã đồng bộ Slash Commands.")

bot = GachaBot()

@bot.event
async def on_ready():
    print(f'--- Bot {bot.user.name} đã sẵn sàng kết nối! ---')

if __name__ == '__main__':
    bot.run(TOKEN)
