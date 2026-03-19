import discord
from discord.ext import commands
from colorama import init, Fore, Style
import os
import asyncio
import tempfile
from difflib import get_close_matches
import time
from collections import defaultdict

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

class RateLimiter:
    def __init__(self, initial_concurrency=10):
        self.concurrency = initial_concurrency
        self.max_concurrency = 50
        self.min_concurrency = 1
        self.backoff_factor = 0.5
        self.recovery_factor = 1.1
        self.last_rate_limit = 0
        self.cooldown = 5

    async def execute(self, tasks, task_func):
        if not tasks:
            return []
        results = []
        for i in range(0, len(tasks), self.concurrency):
            batch = tasks[i:i+self.concurrency]
            try:
                batch_results = await asyncio.gather(*[task_func(item) for item in batch], return_exceptions=True)
                for res in batch_results:
                    if isinstance(res, Exception):
                        if isinstance(res, discord.HTTPException) and res.status == 429:
                            self.concurrency = max(self.min_concurrency, int(self.concurrency * self.backoff_factor))
                            self.last_rate_limit = time.time()
                            await asyncio.sleep(5)
                        else:
                            pass
                    else:
                        results.append(res)
            except Exception as e:
                print(Fore.RED + f"Batch error: {e}" + Style.RESET_ALL)
            if time.time() - self.last_rate_limit > self.cooldown and self.concurrency < self.max_concurrency:
                self.concurrency = min(self.max_concurrency, int(self.concurrency * self.recovery_factor))
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
async def setup_hook():
    bot.loop.create_task(cmd_loop())

bot.run(TOKEN)
