import discord
from discord.ext import commands, tasks
from discord import app_commands, Webhook
import aiohttp
import asyncio
import json
import os
from datetime import datetime

# --- CONFIGURATION ---
TOKEN = "Put token here"
API_URL = "https://test-hub.kys.gay/api/stock"
DATA_FILE = "stock.json"
LOGO_URL = "https://cdn.discordapp.com/avatars/1373611245206372444/f847c5205b749a3490607ad8a308d77f.png?size=1024"
SUPPORT_URL = "https://discord.gg/Zg2XkS5hq9"
BOT_NAME = "AvalonX • Live Stock Bot"
POLL_INTERVAL = 60 
DEFAULT_COLOR = 0x2b2d31 
COOLDOWN_TIME = 5.0

# --- EMOJI MAPPING ---
FRUIT_EMOJIS = {
    "Blade": "<:blade:1491476837279334583>",
    "Blizzard": "<:blizzard:1491476841645740275>",
    "Bomb": "<:bomb:1491476846456475652>",
    "Buddha": "<:buddha:1491476850709495919>",
    "Control": "<:control:1491476854597750916>",
    "Creation": "<:creation:1491476857848205342>",
    "Dark": "<:dark:1491476861182546095>",
    "Diamond": "<:diamond:1491476864982581432>",
    "Dough": "<:dough:1491476875657216121>",
    "Dragon": "<:dragon:1491476879729754153>",
    "Falcon": "<:eagle:1491476884368785550>",
    "Flame": "<:flame:1491476888361894033>",
    "Gas": "<:gas:1491476905604415538>",
    "Ghost": "<:ghost:1491476910272807133>",
    "Pain": "<:pain:1491476892321317067>",
    "Shadow": "<:shadow:1491476973548081343>",
    "Mammoth": "<:mammoth:1491476940325126324>",
    "Sand": "<:sand:1491476966400983231>",
    "Magma": "<:magma:1491476937732788464>",
    "Rubber": "<:rubber:1491476962277986417>",
    "Love": "<:love:1491476933123510286>",
    "Rocket": "<:rocket:1491476958737862697>",
    "Light": "<:light:1491476927117000935>",
    "Kitsune": "<:kitsune:1491476922075447316>",
    "Quake": "<:quake:1491476955688865995>",
    "Ice": "<:ice:1491476919625973982>",
    "Portal": "<:portal:1491476950999630055>",
    "Gravity": "<:gravity:1491476915268227299>",
    "Phoenix": "<:phoenix:1491476946578837615>",
    "Smoke": "<:smoke:1491476978090508369>",
    "Sound": "<:sound:1491476981366394912>",
    "Spider": "<:spider:1491476985342591057>",
    "Spike": "<:spike:1491476990031823040>",
    "Spin": "<:spin:1491476994041319424>",
    "Spirit": "<:spirit:1491476997875175580>",
    "Spring": "<:spring:1491477000408268910>",
    "Yeti": "<:yeti:1491476832682246256>"
}
MONEY_EMOJI = "<:dollar:1491476870888423587>"

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({"webhooks": []}, f)

# --- HELPERS ---
def format_stock_display(stock_list: list) -> str:
    if not stock_list: return "Currently no items in stock."
    lines = []
    for item in stock_list:
        name = item.get('name', 'Unknown')
        price = item.get('price_beli', 0)
        emoji = FRUIT_EMOJIS.get(name, "🍎")
        lines.append(f"{emoji} **{name} • {MONEY_EMOJI}`{price:,}`**")
    return "\n".join(lines)

def stock_signature(stock_list: list) -> frozenset:
    return frozenset(item.get('name', '') for item in stock_list)

# --- BOT CLASS ---
class AvalonBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.prev_sigs = {} 

    async def setup_hook(self):
        self.auto_stock_loop.start()
        await self.tree.sync()

    def create_ui_view(self, title, message, is_error=False):
        view = discord.ui.LayoutView()
        color = 0xff0000 if is_error else DEFAULT_COLOR
        container = discord.ui.Container(accent_colour=discord.Colour(color))
        container.add_item(discord.ui.TextDisplay(content=f"# {title}\n{message}"))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(content=f"-# {BOT_NAME} • System Notification"))
        view.add_item(container)
        return view

    def create_alert_card(self, shop_name, stock_list, timer_val):
        view = discord.ui.LayoutView()
        container = discord.ui.Container(accent_colour=discord.Colour(DEFAULT_COLOR))
        container.add_item(discord.ui.TextDisplay(content=f"### Current {shop_name}\n{format_stock_display(stock_list)}"))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(content=f"⏰ Stock Change in - `{timer_val}`"))
        btn = discord.ui.Button(style=discord.ButtonStyle.link, label="💬 Support Server", url=SUPPORT_URL)
        container.add_item(discord.ui.ActionRow(btn))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(content=f"-# {BOT_NAME} • Auto Update"))
        view.add_item(container)
        return view

    @tasks.loop(seconds=POLL_INTERVAL)
    async def auto_stock_loop(self):
        try:
            with open(DATA_FILE, "r") as f: db = json.load(f)
        except: return
        if not db["webhooks"]: return
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(API_URL, timeout=15) as resp:
                    if resp.status != 200: return
                    json_data = await resp.json()
            except: return

            data, timers = json_data.get('data', {}), json_data.get('timers', {})
            cur_m_sig = stock_signature(data.get('mirage_stock', []))
            cur_n_sig = stock_signature(data.get('normal_stock', []))

            updated_list = []
            for wh in db["webhooks"]:
                gid = str(wh["guild_id"])
                prev = self.prev_sigs.get(gid, (None, None))
                is_startup = prev == (None, None)
                m_reset = not is_startup and cur_m_sig != prev[0]
                n_reset = not is_startup and cur_n_sig != prev[1]

                try:
                    webhook = Webhook.from_url(wh["url"], session=session)
                    if is_startup or n_reset:
                        await webhook.send(view=self.create_alert_card("Normal Stock", data.get('normal_stock', []), timers.get('normal_reset_in')), username=BOT_NAME, avatar_url=LOGO_URL)
                    if is_startup or m_reset:
                        await webhook.send(view=self.create_alert_card("Mirage Stock", data.get('mirage_stock', []), timers.get('mirage_reset_in')), username=BOT_NAME, avatar_url=LOGO_URL)
                    updated_list.append(wh)
                except: continue

                self.prev_sigs[gid] = (cur_m_sig, cur_n_sig)
            db["webhooks"] = updated_list
            with open(DATA_FILE, "w") as f: json.dump(db, f, indent=4)

bot = AvalonBot()

# --- SLASH COMMANDS ---

@bot.tree.command(name="stock", description="Check the current fruit stock")
@app_commands.guild_only()
@app_commands.checks.cooldown(1, COOLDOWN_TIME)
async def stock(interaction: discord.Interaction):
    await interaction.response.defer()
    
    # Fix: Checking permissions safely
    if interaction.guild and interaction.channel and hasattr(interaction.channel, 'permissions_for'):
        if not interaction.channel.permissions_for(interaction.guild.me).use_external_emojis:
            return await interaction.followup.send("⚠️ Bot is missing the `Use External Emojis` permission!", ephemeral=True)

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(API_URL) as resp:
                json_data = await resp.json()
                data, timers = json_data.get('data', {}), json_data.get('timers', {})
                
                view = discord.ui.LayoutView()
                container = discord.ui.Container(accent_colour=discord.Colour(DEFAULT_COLOR))
                container.add_item(discord.ui.TextDisplay(content=f"### 🏝️ Mirage Island Stock\n{format_stock_display(data.get('mirage_stock', []))}"))
                container.add_item(discord.ui.Separator())
                container.add_item(discord.ui.TextDisplay(content=f"### 🛒 Normal Shop Stock\n{format_stock_display(data.get('normal_stock', []))}"))
                container.add_item(discord.ui.Separator())
                timer_txt = f"### ⏰ Timers\n⏳ Mirage Reset: `{timers.get('mirage_reset_in')}`\n🛒 Normal Reset: `{timers.get('normal_reset_in')}`"
                container.add_item(discord.ui.TextDisplay(content=timer_txt))
                container.add_item(discord.ui.Separator())
                btn = discord.ui.Button(style=discord.ButtonStyle.link, label="💬 Support Server", url=SUPPORT_URL)
                container.add_item(discord.ui.ActionRow(btn))
                container.add_item(discord.ui.Separator())
                container.add_item(discord.ui.TextDisplay(content=f"-# {BOT_NAME} • BloxFruit Stock Notifier"))
                view.add_item(container)
                await interaction.followup.send(view=view)
        except Exception as e:
            await interaction.followup.send(view=bot.create_ui_view("Error", f"API Connection Failed: {e}", True))

alerts = app_commands.Group(name="alerts", description="Manage automatic notifications")

@alerts.command(name="set", description="Set up the automatic notification channel")
@app_commands.guild_only()
@app_commands.checks.has_permissions(administrator=True)
async def alerts_set(interaction: discord.Interaction, channel: discord.TextChannel):
    await interaction.response.defer(ephemeral=True)
    
    bot_perms = channel.permissions_for(interaction.guild.me)
    missing = []
    if not bot_perms.manage_webhooks: missing.append("Manage Webhooks")
    if not bot_perms.send_messages: missing.append("Send Messages")
    if not bot_perms.use_external_emojis: missing.append("Use External Emojis")

    if missing:
        view = bot.create_ui_view("BloxFruits Notifications", f"Bot requires the following permissions in {channel.mention}: `{', '.join(missing)}`", True)
        await interaction.followup.send(view=view)
        return

    guild_id = interaction.guild_id
    with open(DATA_FILE, "r") as f: db = json.load(f)
    existing = next((w for w in db["webhooks"] if w["guild_id"] == guild_id), None)
    
    try:
        if existing:
            async with aiohttp.ClientSession() as session:
                webhook = Webhook.from_url(existing["url"], session=session)
                await webhook.edit(channel=channel, name=BOT_NAME)
                existing["channel_id"] = channel.id
                msg = f"Notifications have been moved to {channel.mention}"
        else:
            webhook = await channel.create_webhook(name=BOT_NAME)
            db["webhooks"].append({"guild_id": guild_id, "channel_id": channel.id, "url": webhook.url})
            msg = f"Notifications have been activated in {channel.mention}"

        with open(DATA_FILE, "w") as f: json.dump(db, f, indent=4)
        await interaction.followup.send(view=bot.create_ui_view("BloxFruits Notifications", msg))
    except Exception as e:
        await interaction.followup.send(view=bot.create_ui_view("Error", str(e), True))

@alerts.command(name="remove", description="Disable automatic notifications")
@app_commands.guild_only()
@app_commands.checks.has_permissions(administrator=True)
async def alerts_remove(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    with open(DATA_FILE, "r") as f:
        db = json.load(f)
    
    existing = next((w for w in db["webhooks"] if w["guild_id"] == interaction.guild_id), None)
    
    if not existing:
        view = bot.create_ui_view("BloxFruits Notifications", "alerts is not enabled in this channel! Use `/alerts set` to turn it on.", True)
        await interaction.followup.send(view=view)
        return

    db["webhooks"] = [w for w in db["webhooks"] if w["guild_id"] != interaction.guild_id]
    with open(DATA_FILE, "w") as f:
        json.dump(db, f, indent=4)
        
    view = bot.create_ui_view("BloxFruits Notifications", "Automatic notifications have been disabled for this server.", False)
    await interaction.followup.send(view=view)

bot.tree.add_command(alerts)
bot.run(TOKEN)
