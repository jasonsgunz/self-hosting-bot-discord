import discord
from discord.ext import commands
from colorama import init, Fore, Style
import os
import asyncio
import tempfile
from difflib import get_close_matches
import time
import random
from collections import defaultdict
import datetime

TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token.txt")

async def validate_token(token):
    try:
        client = discord.Client(intents=discord.Intents.default())
        await client.login(token)
        await client.close()
        return True
    except discord.LoginFailure:
        return False
    except Exception as e:
        print(Fore.RED + f"[-] Could not validate token: {e}" + Style.RESET_ALL)
        return False

def load_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            token = f.read().strip()
            if token:
                return token
    return None

def save_token(token):
    with open(TOKEN_FILE, "w") as f:
        f.write(token)

def get_valid_token():
    print(Fore.CYAN + "=== Bot Token Setup ===" + Style.RESET_ALL)
    while True:
        token = input("Enter your bot token: ").strip()
        if not token:
            print(Fore.RED + "[-] Token cannot be empty." + Style.RESET_ALL)
            continue
        print("Validating token...")
        try:
            valid = asyncio.run(validate_token(token))
        except RuntimeError:
            print(Fore.RED + "[-] Validation error, please try again." + Style.RESET_ALL)
            continue
        if valid:
            save_token(token)
            print(Fore.GREEN + "[+] Token saved and validated." + Style.RESET_ALL)
            return token
        else:
            print(Fore.RED + "[-] Invalid token. Please re-enter." + Style.RESET_ALL)

TOKEN = load_token()
if TOKEN is None:
    TOKEN = get_valid_token()
else:
    print("Validating saved token...")
    try:
        valid = asyncio.run(validate_token(TOKEN))
    except RuntimeError:
        valid = False
    if not valid:
        print(Fore.RED + "[-] Saved token is invalid or expired." + Style.RESET_ALL)
        os.remove(TOKEN_FILE)
        TOKEN = get_valid_token()
    else:
        print(Fore.GREEN + "[+] Saved token is valid." + Style.RESET_ALL)

PREFIX = "!"
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.dm_messages = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

log_targets = {}
timeout_targets = {}
cmd_guild = None
member_cache = {}
cache_timestamp = 0
CACHE_DURATION = 60
active_ping_tasks = {}
active_doom_games = {}

class RateLimiter:
    def __init__(self, initial_concurrency=45):
        self.concurrency = initial_concurrency
        self.max_concurrency = 50
        self.min_concurrency = 1
        self.rate_limit_count = 0
        self.hardcoded_mode = False
        self.safe_concurrency = 5
        self.backoff_factor = 0.5
        self.speedup_factor = 1.2

    async def execute(self, tasks, task_func):
        if not tasks:
            return []
        self.rate_limit_count = 0
        self.hardcoded_mode = False
        concurrency = self.concurrency
        results = []

        for i in range(0, len(tasks), concurrency):
            batch = tasks[i:i+concurrency]
            try:
                batch_results = await asyncio.gather(*[task_func(item) for item in batch], return_exceptions=True)
                had_rate_limit = False
                for res in batch_results:
                    if isinstance(res, Exception):
                        if isinstance(res, discord.HTTPException) and res.status == 429:
                            self.rate_limit_count += 1
                            had_rate_limit = True
                            concurrency = max(self.min_concurrency, int(concurrency * self.backoff_factor))
                            if self.rate_limit_count >= 3:
                                self.hardcoded_mode = True
                                concurrency = self.safe_concurrency
                                print(Fore.YELLOW + "[!] Rate limit threshold reached. Switching to hardcoded mode (safe concurrency)." + Style.RESET_ALL)
                        else:
                            pass
                    else:
                        results.append(res)
                if not had_rate_limit and not self.hardcoded_mode:
                    concurrency = min(self.max_concurrency, int(concurrency * self.speedup_factor))
                if len(batch) > concurrency * 0.8:
                    await asyncio.sleep(0.1)
            except Exception as e:
                print(Fore.RED + f"Batch error: {e}" + Style.RESET_ALL)
        self.concurrency = concurrency
        return results

rate_limiter = RateLimiter()

def refresh_cache(guild):
    global member_cache, cache_timestamp
    now = time.time()
    if now - cache_timestamp > CACHE_DURATION or guild.id not in member_cache:
        member_cache[guild.id] = {member.name: member for member in guild.members}
        cache_timestamp = now

def get_member_by_name_or_closest(guild, name):
    refresh_cache(guild)
    cache = member_cache.get(guild.id, {})
    if name in cache:
        return cache[name]
    matches = get_close_matches(name, list(cache.keys()), n=1, cutoff=0.1)
    if matches:
        return cache[matches[0]]
    return None

def print_banner():
    os.system("cls")
    print(Fore.GREEN + "===============================")
    print("           BOT PANEL")
    print("===============================" + Style.RESET_ALL)

async def cmd_loop():
    global cmd_guild
    await bot.wait_until_ready()
    print_banner()
    await choose_server()
    print(Fore.CYAN + "[INFO] Type 'help' to see available commands" + Style.RESET_ALL)
    while True:
        cmd = await asyncio.to_thread(input, Fore.GREEN + "bot> " + Style.RESET_ALL)
        await execute_command(cmd)

async def choose_server():
    global cmd_guild
    if not bot.guilds:
        print(Fore.RED + "[-] Bot is not in any servers!" + Style.RESET_ALL)
        return
    print(Fore.CYAN + "[INFO] Your bot is in the following servers:" + Style.RESET_ALL)
    for i, g in enumerate(bot.guilds, start=1):
        print(f"{i}. {g.name}")
    while True:
        choice = await asyncio.to_thread(input, "Select a server by number: ")
        try:
            index = int(choice) - 1
            if 0 <= index < len(bot.guilds):
                cmd_guild = bot.guilds[index]
                print(Fore.YELLOW + f"[+] Current server set to: {cmd_guild.name}" + Style.RESET_ALL)
                break
            else:
                print(Fore.RED + "[-] Invalid choice" + Style.RESET_ALL)
        except ValueError:
            print(Fore.RED + "[-] Enter a valid number" + Style.RESET_ALL)

async def ping_loop(channel, minutes):
    try:
        while True:
            msg = await channel.send("@everyone")
            await asyncio.sleep(1)
            try:
                await msg.delete()
            except:
                pass
            await asyncio.sleep(minutes * 60)
    except asyncio.CancelledError:
        pass

GRID_SIZE = 24
WALL = '▪'
FLOOR = '▫'
PLAYER = '🟢'
ENEMY = '🔴'
AMMO = '🔫'
HEALTH = '❤️'

class DoomGame:
    def __init__(self, channel_id):
        self.channel_id = channel_id
        self.grid = []
        self.player_pos = None
        self.enemies = []
        self.ammo_pickups = []
        self.health_pickups = []
        self.player_health = 100
        self.player_ammo = 10
        self.score = 0
        self.facing = 'right'
        self.message = None
        self.view = None
        self.generate_maze()

    def generate_maze(self):
        self.grid = [[WALL for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        stack = [(1,1)]
        self.grid[1][1] = FLOOR
        while stack:
            x, y = stack[-1]
            neighbors = []
            for dx, dy in [(2,0), (-2,0), (0,2), (0,-2)]:
                nx, ny = x+dx, y+dy
                if 0 < nx < GRID_SIZE-1 and 0 < ny < GRID_SIZE-1 and self.grid[ny][nx] == WALL:
                    neighbors.append((nx, ny, dx//2, dy//2))
            if neighbors:
                nx, ny, cx, cy = random.choice(neighbors)
                self.grid[ny][nx] = FLOOR
                self.grid[y+cy][x+cx] = FLOOR
                stack.append((nx, ny))
            else:
                stack.pop()
        for _ in range(GRID_SIZE * 2):
            x = random.randint(1, GRID_SIZE-2)
            y = random.randint(1, GRID_SIZE-2)
            self.grid[y][x] = FLOOR
        self.player_pos = (1,1)
        self.grid[1][1] = PLAYER
        num_enemies = random.randint(5, 8)
        for _ in range(num_enemies):
            while True:
                x = random.randint(1, GRID_SIZE-2)
                y = random.randint(1, GRID_SIZE-2)
                if (x,y) != self.player_pos and self.grid[y][x] == FLOOR:
                    self.grid[y][x] = ENEMY
                    self.enemies.append((x,y))
                    break
        num_ammo = random.randint(3,5)
        for _ in range(num_ammo):
            while True:
                x = random.randint(1, GRID_SIZE-2)
                y = random.randint(1, GRID_SIZE-2)
                if (x,y) != self.player_pos and self.grid[y][x] == FLOOR and (x,y) not in self.enemies:
                    self.ammo_pickups.append((x,y))
                    break
        num_health = random.randint(2,3)
        for _ in range(num_health):
            while True:
                x = random.randint(1, GRID_SIZE-2)
                y = random.randint(1, GRID_SIZE-2)
                if (x,y) != self.player_pos and self.grid[y][x] == FLOOR and (x,y) not in self.enemies and (x,y) not in self.ammo_pickups:
                    self.health_pickups.append((x,y))
                    break

    def render(self):
        rows = []
        for y in range(GRID_SIZE):
            row = []
            for x in range(GRID_SIZE):
                if (x,y) == self.player_pos:
                    row.append(PLAYER)
                elif (x,y) in self.enemies:
                    row.append(ENEMY)
                elif (x,y) in self.ammo_pickups:
                    row.append(AMMO)
                elif (x,y) in self.health_pickups:
                    row.append(HEALTH)
                else:
                    row.append(self.grid[y][x])
            rows.append(''.join(row))
        map_str = '\n'.join(rows)
        stats = f"❤️ {self.player_health}  🔫 {self.player_ammo}  🎯 {self.score}  🧭 {self.facing}"
        return f"{stats}\n{map_str}"

    def move_player(self, dx, dy):
        x, y = self.player_pos
        nx, ny = x+dx, y+dy
        if not (0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE):
            return False
        if dx != 0:
            self.facing = 'right' if dx > 0 else 'left'
        elif dy != 0:
            self.facing = 'down' if dy > 0 else 'up'
        if self.grid[ny][nx] == WALL:
            return False
        if (nx, ny) in self.enemies:
            self.player_health -= 20
            if self.player_health <= 0:
                return True
            return True
        self.grid[y][x] = FLOOR
        if (nx, ny) in self.ammo_pickups:
            self.ammo_pickups.remove((nx, ny))
            self.player_ammo += 5
            self.score += 10
        if (nx, ny) in self.health_pickups:
            self.health_pickups.remove((nx, ny))
            self.player_health = min(100, self.player_health + 25)
            self.score += 10
        self.player_pos = (nx, ny)
        self.grid[ny][nx] = PLAYER
        return True

    def shoot(self):
        if self.player_ammo <= 0:
            return False
        self.player_ammo -= 1
        x, y = self.player_pos
        dx, dy = 0,0
        if self.facing == 'right':
            dx = 1
        elif self.facing == 'left':
            dx = -1
        elif self.facing == 'down':
            dy = 1
        elif self.facing == 'up':
            dy = -1
        nx, ny = x+dx, y+dy
        while 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE:
            if self.grid[ny][nx] == WALL:
                break
            if (nx, ny) in self.enemies:
                self.enemies.remove((nx, ny))
                self.grid[ny][nx] = FLOOR
                self.score += 50
                return True
            nx += dx
            ny += dy
        return False

    def enemy_turn(self):
        for enemy in self.enemies[:]:
            ex, ey = enemy
            px, py = self.player_pos
            dx = 0
            dy = 0
            if abs(px - ex) > abs(py - ey):
                dx = 1 if px > ex else -1
            else:
                dy = 1 if py > ey else -1
            nx, ny = ex+dx, ey+dy
            if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE and self.grid[ny][nx] != WALL and (nx,ny) != self.player_pos:
                self.grid[ey][ex] = FLOOR
                self.grid[ny][nx] = ENEMY
                self.enemies.remove((ex,ey))
                self.enemies.append((nx,ny))
            else:
                possible = []
                for dx2, dy2 in [(1,0), (-1,0), (0,1), (0,-1)]:
                    nx2, ny2 = ex+dx2, ey+dy2
                    if 0 <= nx2 < GRID_SIZE and 0 <= ny2 < GRID_SIZE and self.grid[ny2][nx2] != WALL and (nx2,ny2) != self.player_pos:
                        possible.append((dx2,dy2))
                if possible:
                    dx2, dy2 = random.choice(possible)
                    nx2, ny2 = ex+dx2, ey+dy2
                    self.grid[ey][ex] = FLOOR
                    self.grid[ny2][nx2] = ENEMY
                    self.enemies.remove((ex,ey))
                    self.enemies.append((nx2,ny2))

class DoomView(discord.ui.View):
    def __init__(self, game):
        super().__init__(timeout=None)
        self.game = game

    async def update(self, interaction):
        await self.game.message.edit(content=self.game.render(), view=self)
        await interaction.response.defer()

    @discord.ui.button(label='⬆️ Up', style=discord.ButtonStyle.primary)
    async def up_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = self.game
        game.move_player(0, -1)
        if game.player_health <= 0:
            await interaction.response.send_message("You died! Game over.", ephemeral=True)
            await game.message.delete()
            del active_doom_games[game.channel_id]
            return
        game.enemy_turn()
        if game.player_health <= 0:
            await interaction.response.send_message("You died! Game over.", ephemeral=True)
            await game.message.delete()
            del active_doom_games[game.channel_id]
            return
        await self.update(interaction)

    @discord.ui.button(label='⬇️ Down', style=discord.ButtonStyle.primary)
    async def down_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = self.game
        game.move_player(0, 1)
        if game.player_health <= 0:
            await interaction.response.send_message("You died! Game over.", ephemeral=True)
            await game.message.delete()
            del active_doom_games[game.channel_id]
            return
        game.enemy_turn()
        if game.player_health <= 0:
            await interaction.response.send_message("You died! Game over.", ephemeral=True)
            await game.message.delete()
            del active_doom_games[game.channel_id]
            return
        await self.update(interaction)

    @discord.ui.button(label='⬅️ Left', style=discord.ButtonStyle.primary)
    async def left_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = self.game
        game.move_player(-1, 0)
        if game.player_health <= 0:
            await interaction.response.send_message("You died! Game over.", ephemeral=True)
            await game.message.delete()
            del active_doom_games[game.channel_id]
            return
        game.enemy_turn()
        if game.player_health <= 0:
            await interaction.response.send_message("You died! Game over.", ephemeral=True)
            await game.message.delete()
            del active_doom_games[game.channel_id]
            return
        await self.update(interaction)

    @discord.ui.button(label='➡️ Right', style=discord.ButtonStyle.primary)
    async def right_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = self.game
        game.move_player(1, 0)
        if game.player_health <= 0:
            await interaction.response.send_message("You died! Game over.", ephemeral=True)
            await game.message.delete()
            del active_doom_games[game.channel_id]
            return
        game.enemy_turn()
        if game.player_health <= 0:
            await interaction.response.send_message("You died! Game over.", ephemeral=True)
            await game.message.delete()
            del active_doom_games[game.channel_id]
            return
        await self.update(interaction)

    @discord.ui.button(label='🔫 Shoot', style=discord.ButtonStyle.danger)
    async def shoot_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = self.game
        if game.player_ammo <= 0:
            await interaction.response.send_message("Out of ammo!", ephemeral=True)
            return
        game.shoot()
        game.enemy_turn()
        if game.player_health <= 0:
            await interaction.response.send_message("You died! Game over.", ephemeral=True)
            await game.message.delete()
            del active_doom_games[game.channel_id]
            return
        await self.update(interaction)

    @discord.ui.button(label='❌ End Game', style=discord.ButtonStyle.danger)
    async def end_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
        del active_doom_games[self.game.channel_id]
        await interaction.response.send_message("Game ended.", ephemeral=True)

class TestConfirmView(discord.ui.View):
    def __init__(self, requester):
        super().__init__(timeout=30)
        self.requester = requester
        self.confirmed = False

    @discord.ui.button(label='✅ Proceed', style=discord.ButtonStyle.success)
    async def proceed(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.requester:
            await interaction.response.send_message("You cannot interact with this.", ephemeral=True)
            return
        self.confirmed = True
        await interaction.message.delete()
        self.stop()

    @discord.ui.button(label='❌ Quit', style=discord.ButtonStyle.danger)
    async def quit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.requester:
            await interaction.response.send_message("You cannot interact with this.", ephemeral=True)
            return
        await interaction.message.delete()
        self.stop()

async def run_tests(guild, requester_id):
    test_channel_name = f"test-{random.randint(1000,9999)}"
    test_channel = None
    original_name = guild.name
    original_nick = guild.me.nick
    created_channels = []
    success_count = 0
    fail_count = 0
    report_lines = []  # will store (success, msg) tuples

    def add_report(success, msg):
        nonlocal success_count, fail_count
        if success:
            success_count += 1
        else:
            fail_count += 1
        report_lines.append((success, msg))

    try:
        test_channel = await guild.create_text_channel(test_channel_name, reason="Bot test")
        created_channels.append(test_channel)
        add_report(True, f"Created test channel #{test_channel.name}")

        await test_channel.send("Testing listchannels... (no visible output)")
        add_report(True, "listchannels: channel list fetched")

        temp_name = f"TestServer-{random.randint(1000,9999)}"
        await guild.edit(name=temp_name)
        add_report(True, f"renameserver: changed name to {temp_name}")
        await guild.edit(name=original_name)
        add_report(True, "renameserver: restored original name")

        test_nick = "TestBot"
        await guild.me.edit(nick=test_nick)
        add_report(True, f"nickname: changed bot nickname to {test_nick}")
        await guild.me.edit(nick=original_nick)
        add_report(True, "nickname: restored original nickname")

        overwrite = test_channel.overwrites_for(guild.default_role)
        overwrite.send_messages = False
        await test_channel.set_permissions(guild.default_role, overwrite=overwrite)
        add_report(True, "lockdown: channel locked")
        overwrite.send_messages = None
        await test_channel.set_permissions(guild.default_role, overwrite=overwrite)
        add_report(True, "unlock: channel unlocked")

        test_msg = "Test message from messageall"
        await test_channel.send(test_msg)
        add_report(True, "messageall: sent message to test channel")

        await test_channel.send("@everyone test message")
        add_report(True, "everyone: sent @everyone in test channel")

        class TempButton(discord.ui.View):
            def __init__(self):
                super().__init__()
                self.add_item(discord.ui.Button(label="Test Link", url="https://discord.com"))
        await test_channel.send("Test button:", view=TempButton())
        add_report(True, "buttonurl: button sent")

        keyword = "delete_me"
        for _ in range(3):
            await test_channel.send(f"Message with {keyword} {random.randint(1,100)}")
        messages = []
        async for msg in test_channel.history(limit=50):
            if keyword in msg.content:
                messages.append(msg)
        await rate_limiter.execute(messages, lambda m: m.delete())
        add_report(True, "deletespecificmessages: deleted messages with keyword")

        messages = []
        async for msg in test_channel.history(limit=50):
            messages.append(msg)
        await rate_limiter.execute(messages, lambda m: m.delete())
        add_report(True, "deleteallchannelmessages: cleared test channel")

        temp_channel = await guild.create_text_channel(f"temp-{random.randint(1000,9999)}")
        created_channels.append(temp_channel)
        add_report(True, "createchannel: created temporary channel")

        invite = await test_channel.create_invite(max_age=60, max_uses=1)
        add_report(True, f"invitelink: created invite {invite.url}")

        ping_task = asyncio.create_task(ping_loop(test_channel, 0.1))
        await asyncio.sleep(2)
        ping_task.cancel()
        add_report(True, "ping/unping: ping loop started and stopped")

        owner = guild.owner
        if owner:
            try:
                await owner.kick(reason="Test")
                add_report(False, "kick: unexpected success (should have been blocked)")
            except discord.Forbidden:
                add_report(True, "kick: command logic works (blocked as expected)")
            except Exception as e:
                add_report(False, f"kick: unexpected error {e}")

            try:
                await owner.ban(reason="Test")
                add_report(False, "ban: unexpected success")
            except discord.Forbidden:
                add_report(True, "ban: command logic works (blocked as expected)")
            except Exception as e:
                add_report(False, f"ban: unexpected error {e}")

            try:
                await guild.unban(discord.Object(id=0))
                add_report(False, "unban: unexpected success")
            except discord.NotFound:
                add_report(True, "unban: command logic works (user not found error)")
            except Exception as e:
                add_report(False, f"unban: unexpected error {e}")
        else:
            add_report(False, "Could not find server owner for ban/kick test")

        game = DoomGame(test_channel.id)
        view = DoomView(game)
        msg = await test_channel.send(game.render(), view=view)
        game.message = msg
        game.view = view
        await msg.delete()
        add_report(True, "startdoom: game started and ended")

        print(Fore.CYAN + "\n=== Test Results ===" + Style.RESET_ALL)
        print(Fore.CYAN + f"Test Done. {success_count} Succeeded / {fail_count} Failed." + Style.RESET_ALL)
        for success, msg in report_lines:
            if success:
                print(Fore.GREEN + msg + Style.RESET_ALL)
            else:
                print(Fore.RED + msg + Style.RESET_ALL)

    except Exception as e:
        print(Fore.RED + f"Test failed: {e}" + Style.RESET_ALL)
    finally:
        for ch in created_channels:
            try:
                await ch.delete()
            except:
                pass
        if guild.name != original_name:
            try:
                await guild.edit(name=original_name)
            except:
                pass
        if guild.me.nick != original_nick:
            try:
                await guild.me.edit(nick=original_nick)
            except:
                pass

async def execute_command(cmd, ctx_guild=None, ctx_author=None, message_obj=None):
    if ctx_guild:
        guild = ctx_guild
        print(Fore.CYAN + f"[DISCORD COMMAND] {cmd} executed by {ctx_author} in {guild.name}" + Style.RESET_ALL)
    else:
        guild = cmd_guild
    try:
        parts = cmd.split()
        if not parts:
            return
        main = parts[0].lower()
        if main == "help":
            print(Fore.CYAN + """
Available commands:
kick <username|all>
ban <username|all>
unban <userid>
dm <username|all> <message>
log <username>
stoplog <username>
timeout <username>
untimeout <username>
nickname <username> <new_nick>
nicknameall <new_nick>
lockdown [channel]
unlock [channel]
thedestroyer <channel> <message>
ping <channel> <minutes>
unping <channel>
startdoom <channel>
testbot
listchannels
renameserver <new_name>
deleteallchannels
renameallchannels <newname>
messageall <message>
everyone <channel_name> <message>
buttonurl <channel_name> <url>
deletespecificmessages <keyword> <channelname>
deleteallchannelmessages [channel_name]
createchannel <name> [number]
bomb <number_of_channels> <channel_base_name> <message>
invitelink
refreshservers
renewtoken
clear
            """ + Style.RESET_ALL)
        elif main == "testbot":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            if not ctx_author:
                print(Fore.RED + "[-] testbot command can only be used in Discord." + Style.RESET_ALL)
                return
            view = TestConfirmView(ctx_author)
            embed = discord.Embed(
                title="⚠️ Bot Test",
                description=(
                    "This will test most bot features (excluding destructive commands).\n\n"
                    "**Commands NOT tested:** `kick`, `ban`, `unban`, `clear`, `help`, and any CMD‑only commands.\n"
                    "If you need to verify those, please test them manually.\n\n"
                    "The test will create temporary channels and briefly rename the server.\n"
                    "Do you want to proceed?"
                ),
                color=discord.Color.orange()
            )
            msg = await message_obj.channel.send(embed=embed, view=view)
            await view.wait()
            if view.confirmed:
                await run_tests(guild, ctx_author.id)
            else:
                await msg.delete()
                await message_obj.channel.send("Test cancelled.", delete_after=5)
        elif main == "listchannels":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            print(Fore.CYAN + f"\nChannels in {guild.name}:\n" + Style.RESET_ALL)
            for channel in guild.channels:
                print(f"- {channel.name}")
        elif main == "renameserver":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            new_name = " ".join(parts[1:])
            await guild.edit(name=new_name)
            print(Fore.YELLOW + f"[+] Server renamed to: {new_name}" + Style.RESET_ALL)
        elif main == "kick":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            if len(parts) < 2:
                print(Fore.RED + "[-] Usage: kick <username|all>" + Style.RESET_ALL)
                return
            username = parts[1]
            if username.lower() == "all":
                members = [m for m in guild.members if m != bot.user]
                await rate_limiter.execute(members, lambda m: m.kick())
                print(Fore.YELLOW + "[+] Kicked all members" + Style.RESET_ALL)
            else:
                member = get_member_by_name_or_closest(guild, username)
                if member:
                    await member.kick()
                    print(Fore.YELLOW + f"[+] Kicked {member.name}" + Style.RESET_ALL)
                else:
                    print(Fore.RED + f"[-] Member not found: {username}" + Style.RESET_ALL)
        elif main == "ban":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            if len(parts) < 2:
                print(Fore.RED + "[-] Usage: ban <username|all>" + Style.RESET_ALL)
                return
            username = parts[1]
            if username.lower() == "all":
                members = [m for m in guild.members if m != bot.user]
                await rate_limiter.execute(members, lambda m: m.ban())
                print(Fore.YELLOW + "[+] Banned all members" + Style.RESET_ALL)
            else:
                member = get_member_by_name_or_closest(guild, username)
                if member:
                    await member.ban()
                    print(Fore.YELLOW + f"[+] Banned {member.name}" + Style.RESET_ALL)
                else:
                    print(Fore.RED + f"[-] Member not found: {username}" + Style.RESET_ALL)
        elif main == "unban":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            if len(parts) < 2:
                print(Fore.RED + "[-] Usage: unban <userid>" + Style.RESET_ALL)
                return
            try:
                user_id = int(parts[1])
            except:
                print(Fore.RED + "[-] Invalid user ID." + Style.RESET_ALL)
                return
            bans = [entry async for entry in guild.bans()]
            for ban_entry in bans:
                if ban_entry.user.id == user_id:
                    await guild.unban(ban_entry.user)
                    print(Fore.YELLOW + f"[+] Unbanned {ban_entry.user}" + Style.RESET_ALL)
                    return
            print(Fore.RED + "[-] User not found in ban list." + Style.RESET_ALL)
        elif main == "dm":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            if len(parts) < 3:
                print(Fore.RED + "[-] Usage: dm <username|all> <message>" + Style.RESET_ALL)
                return
            username = parts[1]
            message = " ".join(parts[2:])
            if username.lower() == "all":
                members = [m for m in guild.members if m != bot.user]
                await rate_limiter.execute(members, lambda m: m.send(message))
                print(Fore.YELLOW + "[+] DM sent to all members" + Style.RESET_ALL)
            else:
                member = get_member_by_name_or_closest(guild, username)
                if member:
                    await member.send(message)
                    print(Fore.YELLOW + f"[+] DM sent to {member.name}" + Style.RESET_ALL)
                else:
                    print(Fore.RED + f"[-] Member not found: {username}" + Style.RESET_ALL)
        elif main == "log":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            if len(parts) < 2:
                print(Fore.RED + "[-] Usage: log <username>" + Style.RESET_ALL)
                return
            username = parts[1]
            member = get_member_by_name_or_closest(guild, username)
            if member:
                log_targets[member.id] = []
                print(Fore.YELLOW + f"[+] Logging messages from {member.name}" + Style.RESET_ALL)
            else:
                print(Fore.RED + f"[-] Member not found: {username}" + Style.RESET_ALL)
        elif main == "stoplog":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            if len(parts) < 2:
                print(Fore.RED + "[-] Usage: stoplog <username>" + Style.RESET_ALL)
                return
            username = parts[1]
            member = get_member_by_name_or_closest(guild, username)
            if member and member.id in log_targets:
                log_data = log_targets.pop(member.id)
                if not log_data:
                    print(Fore.RED + "[-] No messages logged for this user." + Style.RESET_ALL)
                    return
                downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
                filename = os.path.join(downloads_dir, f"{member.name}_log.txt")
                with open(filename, "w", encoding="utf-8") as f:
                    f.write("\n".join(log_data))
                if ctx_author:
                    answer = await asyncio.to_thread(input, "Want the log sent to your DMs as a txt? (y/n): ")
                    if answer.lower() == "y":
                        try:
                            with open(filename, "rb") as f:
                                await ctx_author.send(file=discord.File(f, f"{member.name}_log.txt"))
                            print(Fore.YELLOW + f"[+] Log sent to {ctx_author} via DM." + Style.RESET_ALL)
                        except Exception as e:
                            print(Fore.RED + f"[-] Failed to send DM: {e}" + Style.RESET_ALL)
                        finally:
                            os.remove(filename)
                    else:
                        os.remove(filename)
                        print(Fore.YELLOW + "[+] Log discarded." + Style.RESET_ALL)
                else:
                    print(Fore.YELLOW + f"[+] The log file got saved in Downloads!" + Style.RESET_ALL)
            else:
                print(Fore.RED + f"[-] User not being logged: {username}" + Style.RESET_ALL)
        elif main == "timeout":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            if len(parts) < 2:
                print(Fore.RED + "[-] Usage: timeout <username>" + Style.RESET_ALL)
                return
            username = parts[1]
            member = get_member_by_name_or_closest(guild, username)
            if member:
                timeout_targets.setdefault(guild.id, set()).add(member.id)
                print(Fore.YELLOW + f"[+] {member.name} is now timed out in this server (messages will be deleted)." + Style.RESET_ALL)
            else:
                print(Fore.RED + f"[-] Member not found: {username}" + Style.RESET_ALL)
        elif main == "untimeout":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            if len(parts) < 2:
                print(Fore.RED + "[-] Usage: untimeout <username>" + Style.RESET_ALL)
                return
            username = parts[1]
            member = get_member_by_name_or_closest(guild, username)
            if member:
                if guild.id in timeout_targets and member.id in timeout_targets[guild.id]:
                    timeout_targets[guild.id].remove(member.id)
                    if not timeout_targets[guild.id]:
                        del timeout_targets[guild.id]
                    print(Fore.YELLOW + f"[+] {member.name} is no longer timed out in this server." + Style.RESET_ALL)
                else:
                    print(Fore.RED + f"[-] {member.name} is not timed out in this server." + Style.RESET_ALL)
            else:
                print(Fore.RED + f"[-] Member not found: {username}" + Style.RESET_ALL)
        elif main == "nickname":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            if len(parts) < 3:
                print(Fore.RED + "[-] Usage: nickname <username> <new_nick>" + Style.RESET_ALL)
                return
            username = parts[1]
            new_nick = " ".join(parts[2:])
            member = get_member_by_name_or_closest(guild, username)
            if member:
                try:
                    await member.edit(nick=new_nick)
                    print(Fore.YELLOW + f"[+] Changed nickname of {member.name} to {new_nick}" + Style.RESET_ALL)
                except Exception as e:
                    print(Fore.RED + f"[-] Failed to change nickname: {e}" + Style.RESET_ALL)
            else:
                print(Fore.RED + f"[-] Member not found: {username}" + Style.RESET_ALL)
        elif main == "nicknameall":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            if len(parts) < 2:
                print(Fore.RED + "[-] Usage: nicknameall <new_nick>" + Style.RESET_ALL)
                return
            new_nick = " ".join(parts[1:])
            members = [m for m in guild.members if m != bot.user]
            await rate_limiter.execute(members, lambda m: m.edit(nick=new_nick))
            print(Fore.YELLOW + f"[+] Changed nickname of all members to {new_nick}" + Style.RESET_ALL)
        elif main == "lockdown":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            if len(parts) >= 2:
                channel_name = parts[1]
                channel = discord.utils.get(guild.text_channels, name=channel_name)
            else:
                if message_obj:
                    channel = message_obj.channel
                else:
                    print(Fore.RED + "[-] No channel specified and not in a Discord channel. Usage: lockdown <channel>" + Style.RESET_ALL)
                    return
            if not channel:
                print(Fore.RED + f"[-] Channel not found: {channel_name}" + Style.RESET_ALL)
                return
            overwrite = channel.overwrites_for(guild.default_role)
            overwrite.send_messages = False
            try:
                await channel.set_permissions(guild.default_role, overwrite=overwrite)
                print(Fore.YELLOW + f"[+] Locked down {channel.name}" + Style.RESET_ALL)
            except Exception as e:
                print(Fore.RED + f"[-] Failed to lock channel: {e}" + Style.RESET_ALL)
        elif main == "unlock":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            if len(parts) >= 2:
                channel_name = parts[1]
                channel = discord.utils.get(guild.text_channels, name=channel_name)
            else:
                if message_obj:
                    channel = message_obj.channel
                else:
                    print(Fore.RED + "[-] No channel specified and not in a Discord channel. Usage: unlock <channel>" + Style.RESET_ALL)
                    return
            if not channel:
                print(Fore.RED + f"[-] Channel not found: {channel_name}" + Style.RESET_ALL)
                return
            overwrite = channel.overwrites_for(guild.default_role)
            overwrite.send_messages = None
            try:
                await channel.set_permissions(guild.default_role, overwrite=overwrite)
                print(Fore.YELLOW + f"[+] Unlocked {channel.name}" + Style.RESET_ALL)
            except Exception as e:
                print(Fore.RED + f"[-] Failed to unlock channel: {e}" + Style.RESET_ALL)
        elif main == "thedestroyer":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            if len(parts) < 3:
                print(Fore.RED + "[-] Usage: thedestroyer <channel> <message>" + Style.RESET_ALL)
                return
            channel_name = parts[1]
            message_content = " ".join(parts[2:])
            channel = discord.utils.get(guild.text_channels, name=channel_name)
            if not channel:
                print(Fore.RED + f"[-] Channel not found: {channel_name}" + Style.RESET_ALL)
                return
            warning_text = "DONT REACT OR ELSE..."
            sent = await channel.send(warning_text)
            await sent.add_reaction("⚠️")
            print(Fore.YELLOW + "[+] The Destroyer trap set. Waiting for a reaction..." + Style.RESET_ALL)
            async def destroy_trigger():
                try:
                    def check(reaction, user):
                        return user != bot.user and reaction.message.id == sent.id
                    reaction, user = await bot.wait_for('reaction_add', timeout=None, check=check)
                    print(Fore.RED + f"[!] Reaction detected from {user}! Initiating destruction..." + Style.RESET_ALL)
                    await rate_limiter.execute(guild.channels, lambda ch: ch.delete())
                    for role in guild.roles:
                        if role.name != "@everyone" and role < guild.me.top_role:
                            try:
                                await role.delete()
                            except:
                                pass
                    new_channel = await guild.create_text_channel("oops")
                    await new_channel.send(f"@everyone {message_content}")
                    print(Fore.CYAN + "[+] Destruction complete. Created #oops with your message." + Style.RESET_ALL)
                except Exception as e:
                    print(Fore.RED + f"[-] Destroyer error: {e}" + Style.RESET_ALL)
            asyncio.create_task(destroy_trigger())
        elif main == "ping":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            if len(parts) < 3:
                print(Fore.RED + "[-] Usage: ping <channel> <minutes>" + Style.RESET_ALL)
                return
            channel_name = parts[1]
            try:
                minutes = int(parts[2])
                if minutes < 1:
                    print(Fore.RED + "[-] Minutes must be at least 1." + Style.RESET_ALL)
                    return
            except ValueError:
                print(Fore.RED + "[-] Minutes must be a number." + Style.RESET_ALL)
                return
            channel = discord.utils.get(guild.text_channels, name=channel_name)
            if not channel:
                print(Fore.RED + f"[-] Channel not found: {channel_name}" + Style.RESET_ALL)
                return
            if channel.id in active_ping_tasks:
                active_ping_tasks[channel.id].cancel()
                del active_ping_tasks[channel.id]
            task = asyncio.create_task(ping_loop(channel, minutes))
            active_ping_tasks[channel.id] = task
            print(Fore.YELLOW + f"[+] Ping loop started in {channel.name} every {minutes} minute(s)." + Style.RESET_ALL)
        elif main == "unping":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            if len(parts) < 2:
                print(Fore.RED + "[-] Usage: unping <channel>" + Style.RESET_ALL)
                return
            channel_name = parts[1]
            channel = discord.utils.get(guild.text_channels, name=channel_name)
            if not channel:
                print(Fore.RED + f"[-] Channel not found: {channel_name}" + Style.RESET_ALL)
                return
            if channel.id in active_ping_tasks:
                active_ping_tasks[channel.id].cancel()
                del active_ping_tasks[channel.id]
                print(Fore.YELLOW + f"[+] Ping loop stopped for {channel.name}." + Style.RESET_ALL)
            else:
                print(Fore.RED + f"[-] No active ping loop for {channel.name}." + Style.RESET_ALL)
        elif main == "startdoom":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            if len(parts) < 2:
                print(Fore.RED + "[-] Usage: startdoom <channel>" + Style.RESET_ALL)
                return
            channel_name = parts[1]
            channel = discord.utils.get(guild.text_channels, name=channel_name)
            if not channel:
                print(Fore.RED + f"[-] Channel not found: {channel_name}" + Style.RESET_ALL)
                return
            if channel.id in active_doom_games:
                print(Fore.RED + "[-] A Doom game is already active in that channel. Use the End Game button to stop it." + Style.RESET_ALL)
                return
            game = DoomGame(channel.id)
            view = DoomView(game)
            msg = await channel.send(game.render(), view=view)
            game.message = msg
            game.view = view
            active_doom_games[channel.id] = game
            print(Fore.YELLOW + f"[+] Doom game started in {channel.name}." + Style.RESET_ALL)
        elif main == "deleteallchannels":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            await rate_limiter.execute(guild.channels, lambda ch: ch.delete())
            print(Fore.YELLOW + "[+] Deleted all channels" + Style.RESET_ALL)
        elif main == "renameallchannels":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            if len(parts) < 2:
                print(Fore.RED + "[-] Usage: renameallchannels <newname>" + Style.RESET_ALL)
                return
            new_name = " ".join(parts[1:])
            await rate_limiter.execute(guild.channels, lambda ch: ch.edit(name=new_name))
            print(Fore.YELLOW + f"[+] Renamed all channels to {new_name}" + Style.RESET_ALL)
        elif main == "messageall":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            if len(parts) < 2:
                print(Fore.RED + "[-] Usage: messageall <message>" + Style.RESET_ALL)
                return
            message = " ".join(parts[1:])
            await rate_limiter.execute(guild.text_channels, lambda ch: ch.send(message))
            print(Fore.YELLOW + f"[+] Messageall executed in {guild.name}" + Style.RESET_ALL)
        elif main == "everyone":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            if len(parts) < 3:
                print(Fore.RED + "[-] Usage: everyone <channel_name> <message>" + Style.RESET_ALL)
                return
            channel_name = parts[1]
            message = " ".join(parts[2:])
            channel = discord.utils.get(guild.text_channels, name=channel_name)
            if channel:
                await channel.send(f"@everyone {message}")
                print(Fore.YELLOW + f"[+] Sent @everyone in {channel_name}" + Style.RESET_ALL)
            else:
                print(Fore.RED + f"[-] Channel not found: {channel_name}" + Style.RESET_ALL)
        elif main == "buttonurl":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            if len(parts) < 3:
                print(Fore.RED + "[-] Usage: buttonurl <channel_name> <url>" + Style.RESET_ALL)
                return
            channel_name = parts[1]
            url = parts[2]
            class LinkButton(discord.ui.View):
                def __init__(self):
                    super().__init__()
                    self.add_item(discord.ui.Button(label="Open Link", url=url))
            channel = discord.utils.get(guild.text_channels, name=channel_name)
            if channel:
                await channel.send("Click the button:", view=LinkButton())
                print(Fore.YELLOW + f"[+] Button sent in {channel_name}" + Style.RESET_ALL)
            else:
                print(Fore.RED + f"[-] Channel not found: {channel_name}" + Style.RESET_ALL)
        elif main == "deletespecificmessages":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            if len(parts) < 3:
                print(Fore.RED + "[-] Usage: deletespecificmessages <keyword> <channelname>" + Style.RESET_ALL)
                return
            keyword = parts[1]
            channel_name = parts[2]
            channel = discord.utils.get(guild.text_channels, name=channel_name)
            if channel:
                messages = []
                async for msg in channel.history(limit=None):
                    if keyword in msg.content:
                        messages.append(msg)
                await rate_limiter.execute(messages, lambda m: m.delete())
                print(Fore.GREEN + f"[+] Finished deleting messages with keyword '{keyword}' in {channel_name}" + Style.RESET_ALL)
        elif main == "deleteallchannelmessages":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            if message_obj:
                channel = message_obj.channel
            else:
                if len(parts) < 2:
                    print(Fore.RED + "[-] Specify a channel name in CMD!" + Style.RESET_ALL)
                    return
                channel_name = parts[1]
                channel = discord.utils.get(guild.text_channels, name=channel_name)
            if not channel:
                print(Fore.RED + "[-] Channel not found!" + Style.RESET_ALL)
                return
            messages = []
            async for msg in channel.history(limit=None):
                messages.append(msg)
            await rate_limiter.execute(messages, lambda m: m.delete())
            print(Fore.YELLOW + f"[+] Deleted all messages in {channel.name}" + Style.RESET_ALL)
        elif main == "createchannel":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            if len(parts) < 2:
                print(Fore.RED + "[-] Usage: createchannel <name> [number]" + Style.RESET_ALL)
                return
            name = parts[1]
            amount = 1
            if len(parts) >= 3:
                try:
                    amount = int(parts[2])
                except:
                    print(Fore.RED + "[-] Number must be an integer." + Style.RESET_ALL)
                    return
            if amount < 1:
                print(Fore.RED + "[-] Amount must be at least 1." + Style.RESET_ALL)
                return
            print(Fore.CYAN + f"[INFO] Creating {amount} channel(s)..." + Style.RESET_ALL)
            tasks = []
            for i in range(1, amount + 1):
                channel_name = f"{name}-{i}" if amount > 1 else name
                tasks.append(guild.create_text_channel(channel_name))
            await asyncio.gather(*tasks)
            print(Fore.GREEN + f"[+] Created {amount} channel(s)" + Style.RESET_ALL)
        elif main == "invitelink":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            channel = None
            for ch in guild.text_channels:
                if ch.permissions_for(guild.me).create_instant_invite:
                    channel = ch
                    break
            if not channel:
                print(Fore.RED + "[-] No channel where the bot can create invites." + Style.RESET_ALL)
                return
            invite = await channel.create_invite(max_age=0, max_uses=0)
            print(Fore.GREEN + f"[+] Invite link: {invite}" + Style.RESET_ALL)
        elif main == "bomb":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            if len(parts) < 4:
                print(Fore.RED + "[-] Usage: bomb <number_of_channels> <channel_base_name> <message>" + Style.RESET_ALL)
                return
            try:
                channel_count = int(parts[1])
            except:
                print(Fore.RED + "[-] Number of channels must be an integer." + Style.RESET_ALL)
                return
            base_name = parts[2]
            message = " ".join(parts[3:])
            confirm = await asyncio.to_thread(input, f"WARNING! This will DELETE all channels and create {channel_count} new ones. Continue? (y/n): ")
            if confirm.lower() != "y":
                print(Fore.YELLOW + "[+] Bomb cancelled." + Style.RESET_ALL)
                return
            await rate_limiter.execute(guild.channels, lambda ch: ch.delete())
            tasks = []
            for i in range(1, channel_count + 1):
                tasks.append(guild.create_text_channel(f"{base_name}-{i}"))
            new_channels = await asyncio.gather(*tasks)
            await rate_limiter.execute(new_channels, lambda ch: ch.send(message))
            print(Fore.CYAN + "[+] Bomb completed successfully!" + Style.RESET_ALL)
        elif main == "renewtoken":
            if ctx_author:
                print(Fore.RED + "[-] This command can only be used in the bot's CMD window." + Style.RESET_ALL)
                return
            get_valid_token()
            print(Fore.YELLOW + "[+] Token updated. Please restart the bot for changes to take effect." + Style.RESET_ALL)
        elif main == "refreshservers":
            await choose_server()
        elif main == "clear":
            print_banner()
        else:
            print(Fore.RED + "Unknown command. Type 'help'." + Style.RESET_ALL)
    except Exception as e:
        print(Fore.RED + f"Error: {e}" + Style.RESET_ALL)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if message.author.id in log_targets:
        channel_name = "DM" if isinstance(message.channel, discord.DMChannel) else message.channel.name
        log_entry = f"[{channel_name}] {message.author}: {message.content}"
        log_targets[message.author.id].append(log_entry)
        print(Fore.MAGENTA + log_entry + Style.RESET_ALL)
    if message.guild and message.author.id in timeout_targets.get(message.guild.id, set()):
        try:
            await message.delete()
            print(Fore.RED + f"[TIMEOUT] Deleted message from {message.author} in {message.guild.name}: {message.content}" + Style.RESET_ALL)
        except:
            pass
    if message.content.startswith(PREFIX):
        if not message.guild:
            print(Fore.RED + "[-] Commands are not supported in DMs." + Style.RESET_ALL)
            return
        command_text = message.content[len(PREFIX):]
        try:
            await execute_command(command_text, message.guild, message.author, message_obj=message)
        except Exception as e:
            print(Fore.RED + f"[DISCORD COMMAND ERROR] {e}" + Style.RESET_ALL)
        finally:
            try:
                await message.delete()
            except:
                pass
        return
    await bot.process_commands(message)

@bot.event
async def on_guild_join(guild):
    inviter = "Someone"
    try:
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.bot_add):
            if entry.user:
                inviter = str(entry.user)
                break
    except:
        pass
    print(Fore.CYAN + f"[+] {inviter} added your Bot to a Server called {guild.name}. Type 'refreshservers' to select it!" + Style.RESET_ALL)

@bot.event
async def setup_hook():
    bot.loop.create_task(cmd_loop())

bot.run(TOKEN)
