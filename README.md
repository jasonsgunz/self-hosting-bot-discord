# Self Hosting Discord Bot, short SHDB.
This Project is a open source, self hosting bot. it has lots of features u can experiment with. 

# REQUIREMENTS

-- Latest version of Python [Download Python](https://www.python.org/downloads/)

-- A Discord Bot with Bot token [Click here to create a Bot](https://discord.com/developers/applications)

-- Python set to default for running .py files

-- in the python terminal (without any code used in it), paste `pip install discord.py colorama` for the code to work flawlessly

# NOTE

-- Without these steps, u wont get it work so proceed when done.

# INSTALLATION

--1. Download  start bot.py

--2. run it and follow the steps.

--3. Now, everything runs automatic on start up.

--4. add the bot to your server and choose the server its in upon start.

-- type ,,help'' to view all commands.

# INFORMATION

-- The Bot has a Auto Updater so u dont have to change the FIle manually.

-- If the Bot has any Errors, or u have questions DM s9q9 on Discord.

--The Bot is Open Source so u can modify it to ur needs.

-- Go over all steps again if u get into a Error.

# WHAT ALL THE COMMANDS DO & INFO

# Discord Bot Commands

`kick <username/all>` - Kicks a specific user or all members from the server  
`ban <username/all>` - Bans a specific user or all members from the server  
`unban <userid>` - Unbans a user by their ID  
`dm <username/all> <message>` - Sends a direct message to a specific user or all members  
`nickname <username> <new_nick>` - Changes the nickname of a specific user  
`nicknameall <new_nick>` - Changes the nickname of every member in the server  
`timeout <username>` - Deletes any new messages from the user in the current server  
`untimeout <username>` - Removes timeout from a user  
`lockdown [channel]` - Prevents @everyone from sending messages in a channel (current or specified)  
`unlock [channel]` - Re-enables sending messages in a locked channel  
`log <username>` - Starts logging all messages from a user (appears in bot CMD)  
`stoplog <username>` - Stops logging and saves the log file to your Downloads folder (or sends via DM if requested)  
`deleteallchannels` - Deletes every channel in the server  
`renameallchannels <newname>` - Renames all channels to the same name  
`createchannel <name> [number]` - Creates 1 or more text channels  
`bomb <count> <basename> <message>` - Deletes all channels, creates 'count' new ones with 'basename', and sends 'message' in each  
`thedestroyer <channel> <message>` - Sends a warning with ⚠️ reaction; if anyone reacts, it deletes all channels & roles and creates a new '#oops' channel with your message + @everyone  
`messageall <message>` - Sends a message to every text channel  
`everyone <channel> <message>` - Sends an @everyone ping with your message in a specific channel  
`listchannels` - Lists all channels in the current server  
`renameserver <new_name>` - Renames the entire server  
`buttonurl <channel> <url>` - Sends a clickable button with a link in the specified channel  
`invitelink` - Generates a permanent invite link for the server  
`deletespecificmessages <keyword> <channel>` - Deletes all messages containing a keyword in a channel  
`deleteallchannelmessages [channel]` - Deletes all messages in a channel (current or specified)  
`refreshservers` - Re-select the current server from the list  
`clear` - Clears the CMD screen  
`help` - Shows this command list
`startdoom <channel>` starts a ,,doom like" experience u can play using buttons (its really shit so dont expect anything mindblowing only use it as a template if u wanna make games in discord.
`ping <channel> <minutes>` basically @everyone every timespan u choose in the channel
`unping` stops pinging

---

## Usage Notes

- `<parameter>` = required | `[parameter]` = optional
- Usernames support fuzzy matching (you don't need to type the exact name)
- Commands can be used in Discord with `!` prefix OR directly in the bot's CMD window
- The bot automatically updates itself from GitHub on every launch
- Your bot token is stored securely in `token.txt` next to the bot file
- Log files are saved to your Downloads folder when using `stoplog` in CMD mode
