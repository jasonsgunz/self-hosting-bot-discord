import discord
from discord.ext import commands
from colorama import init, Fore, Style
import os
import asyncio
from difflib import get_close_matches

# ===== TOKEN MANAGEMENT =====
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token.txt")   # <-- ONLY CHANGE

async def validate_token(token):
    """Test if a token works by attempting a short-lived login."""
    try:
        client = discord.Client(intents=discord.Intents.default())
        await client.login(token)
        await client.close()
        return True
    except discord.LoginFailure:
        return False
    except Exception as e:
        # Catch network errors etc.
        print(Fore.RED + f"[-] Could not validate token: {e}" + Style.RESET_ALL)
        return False

def load_token():
    """Read token from file, return None if file missing/empty."""
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            token = f.read().strip()
            if token:
                return token
    return None

def save_token(token):
    """Write token to file."""
    with open(TOKEN_FILE, "w") as f:
        f.write(token)

def get_valid_token():
    """Prompt user until a valid token is entered, save it."""
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
            # Fallback if asyncio.run fails (shouldn't happen)
            print(Fore.RED + "[-] Validation error, please try again." + Style.RESET_ALL)
            continue
        if valid:
            save_token(token)
            print(Fore.GREEN + "[+] Token saved and validated." + Style.RESET_ALL)
            return token
        else:
            print(Fore.RED + "[-] Invalid token. Please re-enter." + Style.RESET_ALL)

# ===== CONFIG =====
# Load or prompt for token
TOKEN = load_token()
if TOKEN is None:
    TOKEN = get_valid_token()
else:
    # Validate existing token
    print("Validating saved token...")
    try:
        valid = asyncio.run(validate_token(TOKEN))
    except RuntimeError:
        valid = False
    if not valid:
        print(Fore.RED + "[-] Saved token is invalid or expired." + Style.RESET_ALL)
        os.remove(TOKEN_FILE)  # Delete bad token file
        TOKEN = get_valid_token()
    else:
        print(Fore.GREEN + "[+] Saved token is valid." + Style.RESET_ALL)

# ===== BOT SETUP =====
PREFIX = "!"
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.dm_messages = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

log_targets = {}          # member.id : list of logs (global)
timeout_targets = {}      # guild.id : set of member ids in timeout

cmd_guild = None          # separate guild for CMD interface

# ===== Utility Functions =====
def print_banner():
    os.system("cls")
    print(Fore.GREEN + "===============================")
    print("           BOT PANEL")
    print("===============================" + Style.RESET_ALL)

def get_member_by_name_or_closest(guild, name):
    for member in guild.members:
        if member.name == name:
            return member
    member_names = [member.name for member in guild.members]
    matches = get_close_matches(name, member_names, n=1, cutoff=0.1)
    if matches:
        for member in guild.members:
            if member.name == matches[0]:
                return member
    return None

# ===== CMD Input Loop =====
async def cmd_loop():
    global cmd_guild
    await bot.wait_until_ready()
    print_banner()
    await choose_server()
    print(Fore.CYAN + "[INFO] Type 'help' to see available commands" + Style.RESET_ALL)

    while True:
        cmd = await asyncio.to_thread(input, Fore.GREEN + "bot> " + Style.RESET_ALL)
        await execute_command(cmd)

# ===== Server Selection Helper =====
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

# ===== Command Execution =====
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

        # ----- HELP -----
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
clear
            """ + Style.RESET_ALL)

        # ----- LIST CHANNELS -----
        elif main == "listchannels":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            print(Fore.CYAN + f"\nChannels in {guild.name}:\n" + Style.RESET_ALL)
            for channel in guild.channels:
                print(f"- {channel.name}")

        # ----- RENAME SERVER -----
        elif main == "renameserver":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            new_name = " ".join(parts[1:])
            await guild.edit(name=new_name)
            print(Fore.YELLOW + f"[+] Server renamed to: {new_name}" + Style.RESET_ALL)

        # ----- KICK -----
        elif main == "kick":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            if len(parts) < 2:
                print(Fore.RED + "[-] Usage: kick <username|all>" + Style.RESET_ALL)
                return
            username = parts[1]
            if username.lower() == "all":
                for member in guild.members:
                    if member != bot.user:
                        try:
                            await member.kick()
                        except:
                            pass
                print(Fore.YELLOW + "[+] Kicked all members" + Style.RESET_ALL)
            else:
                member = get_member_by_name_or_closest(guild, username)
                if member:
                    await member.kick()
                    print(Fore.YELLOW + f"[+] Kicked {member.name}" + Style.RESET_ALL)
                else:
                    print(Fore.RED + f"[-] Member not found: {username}" + Style.RESET_ALL)

        # ----- BAN -----
        elif main == "ban":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            if len(parts) < 2:
                print(Fore.RED + "[-] Usage: ban <username|all>" + Style.RESET_ALL)
                return
            username = parts[1]
            if username.lower() == "all":
                for member in guild.members:
                    if member != bot.user:
                        try:
                            await member.ban()
                        except:
                            pass
                print(Fore.YELLOW + "[+] Banned all members" + Style.RESET_ALL)
            else:
                member = get_member_by_name_or_closest(guild, username)
                if member:
                    await member.ban()
                    print(Fore.YELLOW + f"[+] Banned {member.name}" + Style.RESET_ALL)
                else:
                    print(Fore.RED + f"[-] Member not found: {username}" + Style.RESET_ALL)

        # ----- UNBAN -----
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

        # ----- DM -----
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
                for member in guild.members:
                    if member != bot.user:
                        try:
                            await member.send(message)
                        except:
                            pass
                print(Fore.YELLOW + "[+] DM sent to all members" + Style.RESET_ALL)
            else:
                member = get_member_by_name_or_closest(guild, username)
                if member:
                    await member.send(message)
                    print(Fore.YELLOW + f"[+] DM sent to {member.name}" + Style.RESET_ALL)
                else:
                    print(Fore.RED + f"[-] Member not found: {username}" + Style.RESET_ALL)

        # ----- LOG -----
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

        # ----- STOPLOG -----
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
                answer = await asyncio.to_thread(input, "Wanna save the log as txt? (y/n): ")
                if answer.lower() == "y":
                    filename = f"{member.name}_log.txt"
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write("\n".join(log_data))
                    print(Fore.YELLOW + f"[+] Log saved as {filename}" + Style.RESET_ALL)
                else:
                    print(Fore.YELLOW + "[+] Log discarded." + Style.RESET_ALL)
            else:
                print(Fore.RED + f"[-] User not being logged: {username}" + Style.RESET_ALL)

        # ----- TIMEOUT -----
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
                # Add to per-guild timeout set
                timeout_targets.setdefault(guild.id, set()).add(member.id)
                print(Fore.YELLOW + f"[+] {member.name} is now timed out in this server (messages will be deleted)." + Style.RESET_ALL)
            else:
                print(Fore.RED + f"[-] Member not found: {username}" + Style.RESET_ALL)

        # ----- UNTIMEOUT -----
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
                    # Clean up empty set
                    if not timeout_targets[guild.id]:
                        del timeout_targets[guild.id]
                    print(Fore.YELLOW + f"[+] {member.name} is no longer timed out in this server." + Style.RESET_ALL)
                else:
                    print(Fore.RED + f"[-] {member.name} is not timed out in this server." + Style.RESET_ALL)
            else:
                print(Fore.RED + f"[-] Member not found: {username}" + Style.RESET_ALL)

        # ----- DELETE ALL CHANNELS -----
        elif main == "deleteallchannels":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            for channel in guild.channels:
                try:
                    await channel.delete()
                    print(Fore.YELLOW + f"[+] Deleted {channel.name}" + Style.RESET_ALL)
                except:
                    pass

        # ----- RENAME ALL CHANNELS -----
        elif main == "renameallchannels":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            if len(parts) < 2:
                print(Fore.RED + "[-] Usage: renameallchannels <newname>" + Style.RESET_ALL)
                return
            new_name = " ".join(parts[1:])
            for channel in guild.channels:
                try:
                    await channel.edit(name=new_name)
                    print(Fore.YELLOW + f"[+] Renamed {channel.name} to {new_name}" + Style.RESET_ALL)
                except:
                    pass

        # ----- MESSAGE ALL -----
        elif main == "messageall":
            if not guild:
                print(Fore.RED + "[-] No server selected/available!" + Style.RESET_ALL)
                return
            if len(parts) < 2:
                print(Fore.RED + "[-] Usage: messageall <message>" + Style.RESET_ALL)
                return
            message = " ".join(parts[1:])
            for channel in guild.text_channels:
                try:
                    await channel.send(message)
                except:
                    pass
            print(Fore.YELLOW + f"[+] Messageall executed in {guild.name}" + Style.RESET_ALL)

        # ----- EVERYONE -----
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

        # ----- BUTTON URL -----
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

        # ----- DELETE SPECIFIC MESSAGES -----
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
                async for message in channel.history(limit=None):
                    if keyword in message.content:
                        try:
                            await message.delete()
                        except:
                            pass
                print(Fore.GREEN + f"[+] Finished deleting messages with keyword '{keyword}' in {channel_name}" + Style.RESET_ALL)

        # ----- DELETE ALL CHANNEL MESSAGES -----
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
            async for msg in channel.history(limit=None):
                try:
                    await msg.delete()
                except:
                    pass
            print(Fore.YELLOW + f"[+] Deleted all messages in {channel.name}" + Style.RESET_ALL)

        # ----- CREATE CHANNEL -----
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
            for i in range(1, amount + 1):
                try:
                    channel_name = f"{name}-{i}" if amount > 1 else name
                    await guild.create_text_channel(channel_name)
                    print(Fore.GREEN + f"[+] Created channel: {channel_name}" + Style.RESET_ALL)
                except Exception as e:
                    print(Fore.RED + f"[-] Failed creating {name}-{i}: {e}" + Style.RESET_ALL)

        # ----- INVITE LINK -----
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

        # ----- BOMB -----
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
            for channel in guild.channels:
                try:
                    await channel.delete()
                except:
                    pass
            for i in range(1, channel_count + 1):
                new_channel = await guild.create_text_channel(f"{base_name}-{i}")
                await new_channel.send(message)
            print(Fore.CYAN + "[+] Bomb completed successfully!" + Style.RESET_ALL)

        # ----- REFRESH SERVERS -----
        elif main == "refreshservers":
            await choose_server()

        # ----- CLEAR -----
        elif main == "clear":
            print_banner()

        else:
            print(Fore.RED + "Unknown command. Type 'help'." + Style.RESET_ALL)

    except Exception as e:
        print(Fore.RED + f"Error: {e}" + Style.RESET_ALL)

# ===== Discord Events =====
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Log messages if user is being tracked (global)
    if message.author.id in log_targets:
        channel_name = "DM" if isinstance(message.channel, discord.DMChannel) else message.channel.name
        log_entry = f"[{channel_name}] {message.author}: {message.content}"
        log_targets[message.author.id].append(log_entry)
        print(Fore.MAGENTA + log_entry + Style.RESET_ALL)

    # Timeout: delete messages from timed out users in this guild
    if message.guild and message.author.id in timeout_targets.get(message.guild.id, set()):
        try:
            await message.delete()
            print(Fore.RED + f"[TIMEOUT] Deleted message from {message.author} in {message.guild.name}: {message.content}" + Style.RESET_ALL)
        except:
            pass  # No permission to delete – just ignore

    # Handle commands with prefix
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

# ===== Setup Hook =====
@bot.event
async def setup_hook():
    bot.loop.create_task(cmd_loop())

# ===== Start Bot =====
bot.run(TOKEN)
