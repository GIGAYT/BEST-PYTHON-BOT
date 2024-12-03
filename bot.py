import webcolors
import datetime
import requests
import discord
import asyncio
import aiohttp
import logging
import random
import time
import json
import io
import os
import re
from discord import Interaction, ButtonStyle, ActionRow, Button, app_commands, Embed, Color, TextChannel, Permissions, Member, Interaction, PermissionOverwrite
from discord.ui import Button, View, Modal, Select, TextInput
from collections import defaultdict
from discord.ext import commands
from dotenv import load_dotenv
from datetime import timedelta
from datetime import timezone
from discord.utils import get
from discord.ext import tasks
from typing import Optional

load_dotenv()

DATABASE_FILE = "database.json"

# Function to load the database
def load_database():
    try:
        with open(DATABASE_FILE, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {
            "extra_owners": {},
            "trusted_admins": {},
            "alert_channels": {},
            "alerting_enabled": {},
            "message_alert_channels": {},
            "message_alerting_enabled": {}
        }

# Function to save the database
def save_database(data):
    data["extra_owners"] = {key: list(value) for key, value in data["extra_owners"].items()}
    data["trusted_admins"] = {key: list(value) for key, value in data["trusted_admins"].items()}

    with open(DATABASE_FILE, 'w') as file:
        json.dump(data, file, indent=4)

if not os.path.exists(DATABASE_FILE) or os.path.getsize(DATABASE_FILE) == 0:
    initial_data = {
        "extra_owners": {},
        "trusted_admins": {},
        "alert_channels": {},
        "alerting_enabled": {},
        "message_alert_channels": {},
        "message_alerting_enabled": {}
    }
    save_database(initial_data)

database = load_database()
extra_owners = {k: set(v) for k, v in database.get("extra_owners", {}).items()}
trusted_admins = {k: set(v) for k, v in database.get("trusted_admins", {}).items()}
alert_channels = database.get("alert_channels", {})
alerting_enabled = database.get("alerting_enabled", {})
message_alert_channels = database.get("message_alert_channels", {})
message_alerting_enabled = database.get("message_alerting_enabled", {})

# Dictionaries to store roles and alert channels
alert_channels = {}
alerting_enabled = {}
extra_owners = {}
trusted_admins = {}
message_alert_channels = {}
message_alerting_enabled = {}

# Setup basic logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Define the intents
intents = discord.Intents.default()
intents.guilds = True
intents.guilds = True
intents.guilds = True
intents.members = True
intents.guild_messages = True
intents.message_content = True

# Create your bot instance without a prefix and disabling the help command
bot = commands.Bot(intents=intents, command_prefix="!", help_command=None)

# Bot token and other sensitive info from the .env file
BOT_ID = os.getenv('BOT_ID')
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
TOP_GG_API_TOKEN = os.getenv('TOP_GG_API_TOKEN')
EXEMPT_USER_ID = int(os.getenv('EXEMPT_USER_ID'))

# Function to check if user has voted recently
async def check_user_voted_recently(user_id):
    url = f"https://top.gg/api/bots/{BOT_ID}/check"
    headers = {"Authorization": TOP_GG_API_TOKEN}
    params = {"userId": user_id}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                voted = data.get('voted') == 1
                last_vote_timestamp = data.get('lastVote', 0) / 1000  # Convert milliseconds to seconds
                current_time = datetime.datetime.now().timestamp()

                # If voted is True but last_vote_timestamp is 0.0, assume they voted recently.
                if voted and last_vote_timestamp == 0:
                    voted_recently = True
                else:
                    voted_recently = voted and (last_vote_timestamp >= (current_time - 24 * 60 * 60))

                # Debugging logs
                print(f"user_id: {user_id}")
                print(f"voted: {voted}")
                print(f"last_vote_timestamp: {last_vote_timestamp}")
                print(f"current_time: {current_time}")
                print(f"voted_recently: {voted_recently}")

                return voted_recently
            else:
                # Debugging log
                print(f"Failed to fetch vote data, status code: {response.status}")
                return False

# Function to check if the user has the required permissions
def has_permission(user: discord.Member, guild: discord.Guild, check_roles=False):
    # Define allowed user IDs
    allowed_user_ids = {1288797573674569740}

    # Convert the guild ID to a string since the keys in the dictionaries are strings
    guild_id_str = str(guild.id)

    # Check if the user is in allowed_user_ids, the guild owner, extra owners, or trusted admins
    if check_roles:
        return (user.id in allowed_user_ids or 
                user == guild.owner or
                user.id in extra_owners.get(guild_id_str, []) or 
                user.id in trusted_admins.get(guild_id_str, []))

    return (user.id in allowed_user_ids or 
            user == guild.owner or
            user.id in extra_owners.get(guild_id_str, []) or 
            user.id in trusted_admins.get(guild_id_str, []))

# Event for when the bot is ready & setting up the bot status
@bot.event
async def on_ready():
    await bot.change_presence(status=discord.Status.idle, activity=discord.Activity(type=discord.ActivityType.listening, name="/help | Made By TeamSpark"))
    print(f'{bot.user.name} is online! ✨')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Error syncing commands: {e}")

    # Update server count immediately on startup
    await update_server_count()
    
    # Start the loop to update the server count every 30 minutes
    update_server_count.start()

@tasks.loop(minutes=60)  # Update every 60 minutes
async def update_server_count():
    url = f'https://top.gg/api/bots/{bot.user.id}/stats'
    headers = {
        'Authorization': f'Bearer {TOP_GG_API_TOKEN}',  # Ensure the token is correctly prefixed with 'Bearer'
        'Content-Type': 'application/json'
    }
    data = {
        'server_count': len(bot.guilds)
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as response:
            if response.status == 200:
                print('Successfully updated server count on Top.gg')
            else:
                print(f'Failed to update server count: {response.status} - {await response.text()}')

# Define the command categories here
security_commands = [
    ":octagonal_sign: **__Security Commands__** :octagonal_sign:",
    "\n🔹 ``/extra-owner`` - Extra owner will be able to use all commands in the bot",
    "\n🔹 ``/trusted-admin`` - Trusted admin will be able to use all commands except ***extra-owner and trusted-admin***",
    "\n🔹 ``/list`` - You will get a list of extra owners and trusted admins",
    "\n🔹 ``/security-alert`` - It will alert you immediately about any deletion of roles or channels",
    "\n🔹 ``/message-alert`` - Sets up alerts for message deletions and edits.",
    "\n🔹 ``/alert-off`` - Disables all alert notifications.",
    "\n🔹 ``/anti-spam`` - Enable or disable anti-spam for the server",
]

moderation_commands = [
    ":shield: **__Moderation Commands__** :shield:",
    "\n🔹 ``/warn`` - Warn a user",
    "\n🔹 ``/list-warn`` - Check a user's warning count.",
    "\n🔹 ``/reset-warn`` - Reset a user's warnings.",
    "\n🔹 ``/mute`` - Mute a user",
    "\n🔹 ``/unmute`` - Unmute a user",
    "\n🔹 ``/kick`` - Kick a user",
    "\n🔹 ``/ban`` - Ban a user",
    "\n🔹 ``/purge`` - Purge messages",
]

utility_commands = [
    "🔧 **__Utility Commands__** 🔧 ",
    "\n🔹 ``/rename-role`` - Rename a role",
    "\n🔹 ``/delete-role`` - Delete a role",
    "\n🔹 ``/give-role`` - Give a role to a user",
    "\n🔹 ``/embed-create`` - Create a custom embed",
    "\n🔹 ``/avatar`` - Show someone's profile picture",
    "\n🔹 ``/user-info`` - Get information about a member",
    "\n🔹 ``/server-info`` - Get information about the server",
    "\n🔹 ``/create-role`` - Create a role",
    "\n🔹 ``/role-all`` - Assign a role to all members",
    "\n🔹 ``/remove-role-all`` - Remove a role from all members",
]

ticket_commands = [
    "🎟️ **__Ticket Commands__** 🎟️ ",
    "\n🔹 ``/ticket-add-user:`` Add a user to an open ticket",
    "\n🔹 ``/ticket-remove-user:`` Remove a user from an open ticket",
    "\n🔹 ``/ticket-category:`` Set the category for ticket channels",
    "\n🔹 ``/ticket-close:`` Close a ticket",
    "\n🔹 ``/ticket-custom-message:`` Set custom messages for tickets",
    "\n🔹 ``/ticket-logs:`` Set ticket logs channel",
    "\n🔹 ``/ticket-setup:`` Setup a ticket panel",
    "\n🔹 ``/ticket-staff:`` Assign roles as ticket staff",
    "\n🔹 ``/ticket-staff-list:`` List all ticket staff roles",
]

special_commands = [
    ":dizzy: **__Special Commands__** :dizzy:",
    "\n🔹 ``/say`` - Admin only: Say anything through the bot",
    "\n🔹 ``/clear-dm`` - Clear the DM messages from the bot",
]

extra_commands = [
    ":mirror: **__Extra__** :mirror:",
    "\n🔹 ``/about`` - Show information about the bot",
    "\n🔹 ``/help`` - Get a list of available commands",
    "\n🔹 ``/ping`` - Check bot latency",
    "\n🔹 ``/support`` - Get the support server link",
    "\n🔹 ``/hosting`` - Get the bot hosting link",
    "\n🔹 ``/invite`` - Get the bot invite link",
]


# View for the help menu
class CommandView(View):
    def __init__(self, interaction: Interaction):
        super().__init__()
        self.interaction = interaction

    @discord.ui.select(
        placeholder="Select a command category...",
        options=[
            discord.SelectOption(label="🛡️ Security Commands", description="View security commands", value="security"),
            discord.SelectOption(label="🔨 Moderation Commands", description="View moderation commands", value="moderation"),
            discord.SelectOption(label="🔧 Utility Commands", description="View utility commands", value="utility"),
            discord.SelectOption(label="🎟️ Ticket Commands", description="View ticket commands", value="ticket"),
            discord.SelectOption(label="🌟 Special Commands", description="View special commands", value="special"),
            discord.SelectOption(label="🔮 Extra Commands", description="View extra commands", value="extra"),
        ]
    )
    async def select_category(self, interaction: Interaction, select: Select):
        category_value = select.values[0]
        embed = None

        # Map selected value to appropriate command list
        if category_value == "security":
            embed = self.create_embed("Security Commands", security_commands)
        elif category_value == "moderation":
            embed = self.create_embed("Moderation Commands", moderation_commands)
        elif category_value == "utility":
            embed = self.create_embed("Utility Commands", utility_commands)
        elif category_value == "ticket":
            embed = self.create_embed("Ticket Commands", ticket_commands)
        elif category_value == "special":
            embed = self.create_embed("Special Commands", special_commands)
        elif category_value == "extra":
            embed = self.create_embed("Extra Commands", extra_commands)

        # Update the message with the selected category's embed
        await interaction.response.edit_message(embed=embed, view=self)

    def create_embed(self, title, commands):
        embed = Embed(
            title=title,
            description="Here are the commands you can use:",
            color=Color.from_rgb(0, 0, 255)
        )
        commands_formatted = '\n'.join(commands)
        embed.add_field(name="Commands:", value=commands_formatted, inline=False)
        return embed

# /help command
@bot.tree.command(name="help", description="Get a list of available commands")
async def help(interaction: Interaction):
    embed = discord.Embed(
        title="Help Commands",
        description="Here are the list of command categories",
        color=0x000080
    )

    # Combine the values into a single string using line breaks for readability
    embed.add_field(
        name="Available Command Categories",
        value=(
            "> - 🛡️ **Security Commands** 🛡️\n\n"
            "> - 🔨 **Moderation Commands** 🔨\n\n"
            "> - 🔧 **Utility Commands** 🔧\n\n"
            "> - 🎟️ **Ticket Commands** 🎟️\n\n"
            "> - 🌟 **Special Commands** 🌟\n\n"
            "> - 🔮 **Extra Commands** 🔮"
        ),
        inline=False
    )

    # Create the initial view with a select menu and a home button
    view = CommandView(interaction)
    await interaction.response.send_message(embed=embed, view=view)

# /avatar command
@bot.tree.command(name="avatar", description="Show someone's profile picture")
@app_commands.describe(user="Pick a user to use this command on.")
async def avatar(interaction, user: discord.Member=None):
    if user is None:
        user = interaction.user

    avatar_url = user.avatar.url if user.avatar else user.default_avatar.url

    embed = discord.Embed(
        title=f"🖼 Avatar for {user.name}",
        color=0x0000FF
    )
    embed.set_thumbnail(url=avatar_url)  # Ensure this works properly
    embed.add_field(name="Full Image", value=f"[Click Here]({avatar_url})", inline=False)
    
    await interaction.response.send_message(embed=embed)

# /ping command
@bot.tree.command(name="ping", description="Check how fast the bot is at the moment! (Less ms means faster responses)")
async def ping(interaction: discord.Interaction):
    # Calculate the latency between the bot and Discord server
    latency = round(bot.latency * 1000)

    # Create an embed with blue color
    embed = discord.Embed(
        title="🏓 Pong! Ping Results",
        description="Here's how quick I am to respond! ⚡",
        color=0x0000FF
    )
    embed.add_field(name="Latency", value=f"{latency}ms", inline=False)
    embed.set_footer(text="")

    # Send the embed as a response to the interaction
    await interaction.response.send_message(embed=embed)

# /uptime command
@bot.tree.command(name="uptime", description="Check how long the bot has been online.")
async def uptime(interaction: Interaction):
    current_time = datetime.datetime.now()
    uptime_delta = current_time - bot.uptime
    uptime_str = str(uptime_delta).split(".")[0]

    embed = discord.Embed(title="{bot.user}BOT's Uptime", description=f"", color=0x0000FF)
    embed.add_field(name="{bot.user} has been online for", value=f"{uptime_str}", inline=False)
    embed.set_footer(text="")
    await interaction.response.send_message(embed=embed)

bot.uptime = datetime.datetime.now()

# /clear-dm command
@bot.tree.command(name="clear-dm", description="Clear the message that the bot has sent to you in DM.")
async def clear_dm(interaction: discord.Interaction):
    if isinstance(interaction.channel, discord.DMChannel):
        await interaction.response.send_message("Please wait while the bot clean up your DM!", ephemeral=True)
        total_messages_deleted = 0
        async for message in interaction.channel.history(limit=1000):
            if message.author == bot.user:
                await message.delete()
                total_messages_deleted += 1
                await asyncio.sleep(1)  # 1 second delay per message
        # Message removed as requested
    else:
        await interaction.response.send_message("This command can only be used in DM.", ephemeral=True)

# /about command
@bot.tree.command(name="about", description="Show information about the bot.")
async def about(interaction: discord.Interaction):
    # Create buttons
    button_support = Button(label="Support Server", url="https://discord.gg/NkekNtQfnb", style=discord.ButtonStyle.link)
    button_website = Button(label="hosting", url="https://bot-hosting.net/panel/", style=discord.ButtonStyle.link)
    button_invite = Button(label="Invite me!", url="https://discord.com/oauth2/authorize?client_id=1301923181287968899", style=discord.ButtonStyle.link)

    # Add buttons to a view
    view = View()
    view.add_item(button_support)
    view.add_item(button_website)
    view.add_item(button_invite)

    # Create the embed
    embed = discord.Embed(color=0x0000FF)  # Blue color
    embed.add_field(name="**__About me__**", value=(
        f"**I am {bot.user}, you can use me for many purposes like**\n\n"
        "> - security\n"
        "> - Moderation\n"
        "> - Utility\n"
        "> - Miscellaneous\n\n"
        "  **__Powered by .gg/EnvyNodes__**\n\n"
        "**Owners/founders**\n\n"
        "> - NOT SNOOZY\n"
        "> - SNOOZY JR.\n\n"
        "**__Support__**"
    ), inline=False)

    # Defer the response to acknowledge the interaction immediately
    await interaction.response.defer()

    # Ensure interaction response is valid
    try:
        await interaction.followup.send(embed=embed, view=view)
    except discord.errors.NotFound:
        await interaction.followup.send(content="Something went wrong while sending the message.")

# /invite command
@bot.tree.command(name="invite", description="Get the bot invite link, so you can put it in your server!")
async def invite(interaction: discord.Interaction):
    await interaction.response.send_message(f"[Click To Invite {bot.name} To Your Server](https://discord.com/oauth2/authorize?client_id=1301923181287968899)", ephemeral=True)

# /support command
@bot.tree.command(name="support", description="The bot will provide the support server link.")
async def support(interaction: discord.Interaction):

    await interaction.response.send_message(f"[Click To Join Support Server](https://discord.gg/NkekNtQfnb)")

# !hosting command
@bot.command(name="hosting", description="The bot will provide the hosting link.")
async def hosting(ctx):
    
    await ctx.send(f"[Click To Join the Best Hosting In Which This Bot Is Running In](https://bot-hosting.net/panel/)")

# /say command
@bot.tree.command(name="say", description="Make the bot say a message in a specified channel.")
@app_commands.describe(message="What should I say?", channel="Where should I say it?")
async def say(interaction: discord.Interaction, message: str, channel: TextChannel):
    # Get the user who invoked the command
    user = interaction.user
    guild_id = interaction.guild_id

    # Check if the user is an extra owner, trusted admin, or the guild owner
    if (
        user.id in [1288797573674569740]
        or user == interaction.guild.owner
        or user.id in extra_owners.get(str(guild_id), set())
    ):
        await channel.send(message)
        await interaction.response.send_message("✅ Message sent successfully!", ephemeral=True)
    else:
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)

# /kick command
@bot.tree.command(name="kick", description="Kick a member from the server.")
@app_commands.describe(user="The user you want to kick.", reason="reason")
async def kick(interaction: Interaction, user: Member, reason: str):
    invoker = interaction.user
    guild_id = interaction.guild_id

    # Check if the bot has permission to kick members
    if not interaction.guild.me.guild_permissions.kick_members:
        await interaction.response.send_message("❌ I don't have permission to kick that user. (Please ensure that the bot's role is at the top of the role hierarchy, as it needs to be highest to have the necessary permissions to kick members. Additionally, ensure that the bot have either the 'Administrator' permission or the 'Kick Members' permission.)", ephemeral=True)
        return

    # Check if the invoker has kick members permission, specific user IDs, or is an extra owner/trusted admin/guild owner
    if not (invoker.guild_permissions.kick_members or 
            invoker.id in [1288797573674569740] or 
            invoker == interaction.guild.owner or  # Add guild owner check
            invoker.id in extra_owners.get(str(guild_id), set()) or 
            invoker.id in trusted_admins.get(str(guild_id), set())):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return

    # Check if the user is trying to kick themselves
    if user == invoker:
        await interaction.response.send_message("❌ You can't kick yourself.", ephemeral=True)
        return

    # Check if the user is an extra owner, trusted admin, or guild owner
    if user.id in [1288797573674569740] or user == interaction.guild.owner or user.id in extra_owners.get(str(guild_id), set()) or user.id in trusted_admins.get(str(guild_id), set()):
        await interaction.response.send_message("❌ You cannot kick an extra owner, trusted admin, or the guild owner.", ephemeral=True)
        return

    # Kick the user
    try:
        await user.kick(reason=reason)
        # Send kick message as an embed with red color
        embed = discord.Embed(title="User Kicked", description=f"{user.name} has been kicked by {invoker.name}.", color=0xFF0000)  # Red color
        embed.add_field(name="Reason", value=reason)
        await interaction.response.send_message(embed=embed, ephemeral=False)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to kick that user.", ephemeral=True)
        return

    # Try to send a DM to the kicked user
    embed = discord.Embed(title="You've been kicked!", description=f"You've been kicked from {interaction.guild.name} by {invoker.name}.", color=0xFF0000)  # Red color
    embed.add_field(name="Reason", value=reason)
    try:
        await user.send(embed=embed)
    except discord.Forbidden:
        pass

# /ban command
@bot.tree.command(name="ban", description="Ban a member from the server.")
@app_commands.describe(user="The user you want to ban.", reason="Reason for banning")
async def ban(interaction: Interaction, user: discord.User, reason: str):
    invoker = interaction.user
    guild = interaction.guild
    guild_id = interaction.guild_id

    # Fetch the member object from the user
    member = guild.get_member(user.id)
    if member is None:
        await interaction.response.send_message("❌ User not found in the server.", ephemeral=True)
        return

    # Check if the bot has permission to ban members
    if not guild.me.guild_permissions.ban_members:
        await interaction.response.send_message("❌ I don't have permission to ban that user. (Please ensure that the bot's role is at the top of the role hierarchy, as it needs to be highest to have the necessary permissions to ban members. Additionally, ensure that the bot has either the 'Administrator' permission or the 'Ban Members' permission.)", ephemeral=True)
        return

    # Check if the invoker has ban members permission, specific user IDs, or is an extra owner/trusted admin/guild owner
    if not (invoker.guild_permissions.ban_members or 
            invoker.id in [1288797573674569740] or 
            invoker == interaction.guild.owner or  # Add guild owner check
            invoker.id in extra_owners.get(str(guild_id), set()) or 
            invoker.id in trusted_admins.get(str(guild_id), set())):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return

    # Check if the user is trying to ban themselves
    if member == invoker:
        await interaction.response.send_message("❌ You can't ban yourself.", ephemeral=True)
        return

    # Check if the user is an extra owner or trusted admin
    if member.id in extra_owners.get(str(guild_id), set()) or member.id in trusted_admins.get(str(guild_id), set()):
        await interaction.response.send_message("❌ You cannot ban an extra owner or a trusted admin.", ephemeral=True)
        return

    # Try to send a DM to the user
    embed = discord.Embed(title="You've been banned!", description=f"You've been banned from {guild.name} by {invoker.name}.", color=0xFF0000)  # Red color
    embed.add_field(name="Reason", value=reason)
    try:
        await member.send(embed=embed)
    except discord.Forbidden:
        pass

    # Ban the user
    try:
        await guild.ban(member, reason=reason)
        # Send ban message as an embed with red color
        embed = discord.Embed(title="User Banned", description=f"{member.name} has been banned by {invoker.name}.", color=0xFF0000)  # Red color
        embed.add_field(name="Reason", value=reason)
        await interaction.response.send_message(embed=embed, ephemeral=False)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to ban that user.", ephemeral=True)
        return


def parse_duration(duration: str) -> timedelta:
    unit = duration[-1]
    time = int(duration[:-1])
    if unit == 'm':
        return timedelta(minutes=time)
    elif unit == 'h':
        return timedelta(hours=time)
    elif unit == 'd':
        return timedelta(days=time)
    else:
        raise ValueError("Invalid duration unit. Use 'm', 'h', or 'd'.")

# /mute command
@bot.tree.command(name="mute", description="Mute a member.")
@app_commands.describe(user="Pick a user to use this command on.", reason="Reason", duration="Duration of the mute (e.g., 10m, 1h, 2d)")
async def mute(interaction: Interaction, user: discord.Member, reason: str, duration: str):
    invoker = interaction.user
    guild_id = interaction.guild_id
    bot_member = interaction.guild.get_member(bot.user.id)

    # Check if the invoker is an extra owner, trusted admin, or one of the specified user IDs
    if not (invoker.id in [1288797573674569740] or 
            invoker == interaction.guild.owner or  # Add guild owner check
            invoker.id in extra_owners.get(str(guild_id), set()) or 
            invoker.id in trusted_admins.get(str(guild_id), set())):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return
    
    if user == invoker:
        await interaction.response.send_message("❌ You cannot mute yourself.", ephemeral=True)
        return

    if user == interaction.guild.owner:
        await interaction.response.send_message("❌ You cannot mute the server owner.", ephemeral=True)
        return

    if bot_member.top_role <= user.top_role:
        await interaction.response.send_message("❌ I cannot mute this user. Make sure my role is above theirs.", ephemeral=True)
        return

    try:
        mute_duration = parse_duration(duration)
    except ValueError:
        await interaction.response.send_message("❌ Invalid duration format. Use 'm', 'h', or 'd'.", ephemeral=True)
        return

    mute_until = discord.utils.utcnow() + mute_duration
    await user.timeout(mute_until, reason=reason)

    embed = discord.Embed(title="User Muted", description=f"{user.name} has been muted by {invoker.name}.", color=0x0000FF)
    embed.add_field(name="Reason", value=reason)
    embed.add_field(name="Duration", value=duration)
    await interaction.response.send_message(embed=embed, ephemeral=False)

    dm_embed = discord.Embed(title="You've been muted!", description=f"You've been muted in {interaction.guild.name} by {invoker.name}.", color=0x0000FF)
    dm_embed.add_field(name="Reason", value=reason)
    dm_embed.add_field(name="Duration", value=duration)
    try:
        await user.send(embed=dm_embed)
    except discord.Forbidden:
        pass  # User has DMs disabled

# /unmute command
@bot.tree.command(name="unmute", description="Unmute a member.")
@app_commands.describe(user="Pick a user to use this command on.", reason="Reason")
async def unmute(interaction: Interaction, user: discord.Member, reason: str):
    invoker = interaction.user
    guild_id = interaction.guild_id

    # Check if the invoker is an extra owner, trusted admin, or one of the specified user IDs
    if not (invoker.id in [1288797573674569740] or 
            invoker == interaction.guild.owner or  # Add guild owner check
            invoker.id in extra_owners.get(str(guild_id), set()) or 
            invoker.id in trusted_admins.get(str(guild_id), set())):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return
    
    if user == invoker:
        await interaction.response.send_message("❌ You cannot unmute yourself.", ephemeral=True)
        return
    
    if bot_member.top_role <= user.top_role:
        await interaction.response.send_message("❌ I cannot unmute this user. Make sure my role is above theirs.", ephemeral=True)
        return

    if user.timed_out_until is None or user.timed_out_until <= discord.utils.utcnow():
        await interaction.response.send_message("❌ User is not muted.", ephemeral=True)
        return

    await user.edit(timed_out_until=None, reason=reason)

    embed = discord.Embed(title="User Unmuted", description=f"{user.name} has been unmuted by {invoker.name}.", color=0x0000FF)
    embed.add_field(name="Reason", value=reason)
    await interaction.response.send_message(embed=embed, ephemeral=False)

    dm_embed = discord.Embed(title="You've been unmuted!", description=f"You've been unmuted in {interaction.guild.name} by {invoker.name} for {reason}.", color=0x0000FF)
    try:
        await user.send(embed=dm_embed)
    except discord.Forbidden:
        pass  # User has DMs disabled

# /warn command
@bot.tree.command(name="warn", description="Warn a user")
@app_commands.describe(user="User to warn", reason="reason")
async def warn(interaction: Interaction, user: Member, reason: str):
    invoker = interaction.user
    guild_id = str(interaction.guild.id)

    if not (invoker.guild_permissions.manage_messages or invoker.id in [1288797573674569740]):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return

    if user.guild_permissions.manage_messages or user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Cannot warn a user with 'Manage Messages' permission or 'Administrator' permission.", ephemeral=True)
        return

    # Load warnings from file, handle the case where the file is empty or does not exist
    try:
        with open('warns.json', 'r') as f:
            warns = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        warns = {}

    # Update the warning count
    user_id = str(user.id)
    if guild_id not in warns:
        warns[guild_id] = {}
    if user_id in warns[guild_id]:
        warns[guild_id][user_id] += 1
    else:
        warns[guild_id][user_id] = 1

    # Save updated warnings to file
    with open('warns.json', 'w') as f:
        json.dump(warns, f)

    # Send a DM to the warned user
    dm_embed = Embed(
        title="You've been warned!",
        description=f"You've been warned in {interaction.guild.name} by {invoker.name}.",
        color=0x0000FF
    )
    dm_embed.add_field(name="Reason", value=reason)
    dm_embed.set_footer(text=f"You now have {warns[guild_id][user_id]} warning(s).")
    try:
        await user.send(embed=dm_embed)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to send a message to that user.", ephemeral=True)
        return

    # Send the warning message in the server
    server_embed = Embed(
        title="User Warned",
        description=f"{user.name} has been warned by {invoker.name}.",
        color=0x0000FF
    )
    server_embed.add_field(name="Reason", value=reason)
    server_embed.set_footer(text=f"{user.name} now has {warns[guild_id][user_id]} warning(s).")
    await interaction.response.send_message(embed=server_embed)

# /list-warn command
@bot.tree.command(name="list-warn", description="Check how many warnings a user has.")
@app_commands.describe(user="Pick a user to check warnings.")
async def list_warn(interaction: Interaction, user: Member):
    invoker = interaction.user
    guild_id = str(interaction.guild.id)

    if not (invoker.guild_permissions.manage_messages or invoker.id in [1288797573674569740]):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return

    # Load warnings from file, handle the case where the file is empty or does not exist
    try:
        with open('warns.json', 'r') as f:
            warns = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        warns = {}

    user_id = str(user.id)
    warn_count = warns.get(guild_id, {}).get(user_id, 0)

    if warn_count == 0:
        await interaction.response.send_message(f"✅ {user.name} has no warnings.", ephemeral=True)
    else:
        embed = Embed(
            title="Warning Count",
            description=f"{user.name} has {warn_count} warnings.",
            color=0x0000FF
        )
        await interaction.response.send_message(embed=embed)

# /reset-warn command
@bot.tree.command(name="reset-warn", description="Reset the warning count for a user to zero.")
@app_commands.describe(user="Pick a user to reset warnings.")
async def reset_warn(interaction: Interaction, user: Member):
    invoker = interaction.user
    guild_id = str(interaction.guild.id)

    if not (invoker.guild_permissions.manage_messages or invoker.id in [1288797573674569740]):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return

    # Load warnings from file, handle the case where the file is empty or does not exist
    try:
        with open('warns.json', 'r') as f:
            warns = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        warns = {}

    user_id = str(user.id)
    if guild_id in warns and user_id in warns[guild_id]:
        del warns[guild_id][user_id]
        if not warns[guild_id]:
            del warns[guild_id]
        with open('warns.json', 'w') as f:
            json.dump(warns, f)
        embed = Embed(
            title="Warnings Reset",
            description=f"{user.name} now has 0 warnings.",
            color=0x0000FF
        )
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message(f"✅ {user.name} has no warnings to reset.", ephemeral=True)

# /list command
@bot.tree.command(name="list", description="List all Extra Owners and Trusted Admins.")
async def list_roles(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    extra_owner_list = database["extra_owners"].get(guild_id, [])
    trusted_admin_list = database["trusted_admins"].get(guild_id, [])

    extra_owner_names = "\n".join([bot.get_user(owner_id).mention for owner_id in extra_owner_list]) if extra_owner_list else "None"
    trusted_admin_names = "\n".join([bot.get_user(admin_id).mention for admin_id in trusted_admin_list]) if trusted_admin_list else "None"

    embed = discord.Embed(
        title="📝 Role List",
        description="Here are the current Extra Owners and Trusted Admins in this server:",
        color=discord.Color.blue()
    )
    embed.add_field(name="Extra Owners", value=extra_owner_names, inline=False)
    embed.add_field(name="Trusted Admins", value=trusted_admin_names, inline=False)

    await interaction.response.send_message(embed=embed)

# /extra-owner command
@bot.tree.command(name="extra-owner", description="Assign an extra owner.")
@app_commands.describe(user="The user to assign as an extra owner.")
async def extra_owner(interaction: discord.Interaction, user: discord.User):
    guild = interaction.guild
    invoker = interaction.user

    if not has_permission(invoker, guild):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return

    guild_id = str(interaction.guild_id)
    extra_owners = {k: set(v) for k, v in database.get("extra_owners", {}).items()}  # Load from database

    if guild_id not in extra_owners:
        extra_owners[guild_id] = set()

    if user.id in extra_owners[guild_id]:
        extra_owners[guild_id].remove(user.id)
        await interaction.response.send_message(f"❌ {user.mention} is no longer an extra owner.", ephemeral=True)
    else:
        if len(extra_owners[guild_id]) >= 5:
            await interaction.response.send_message("❌ You cannot assign more than 5 extra owners. Please remove one to add another.", ephemeral=True)
        else:
            extra_owners[guild_id].add(user.id)
            await interaction.response.send_message(f"✅ {user.mention} has been assigned as an extra owner.", ephemeral=True)

    database["extra_owners"] = {k: list(v) for k, v in extra_owners.items()}
    save_database(database)

# /trusted-admin command
@bot.tree.command(name="trusted-admin", description="Assign or remove a trusted admin.")
@app_commands.describe(user="The user to assign or remove as a trusted admin.")
async def trusted_admin(interaction: discord.Interaction, user: discord.User):
    guild_id = str(interaction.guild_id)
    invoker_id = interaction.user.id

    extra_owners = {k: set(v) for k, v in database.get("extra_owners", {}).items()}  # Load from database
    trusted_admins = {k: set(v) for k, v in database.get("trusted_admins", {}).items()}  # Load from database

    if guild_id not in extra_owners:
        await interaction.response.send_message("❌ An extra owner has not been set yet.", ephemeral=True)
        return

    if invoker_id != interaction.guild.owner_id and invoker_id not in extra_owners[guild_id]:
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return

    if guild_id not in trusted_admins:
        trusted_admins[guild_id] = set()

    if user.id in trusted_admins[guild_id]:
        trusted_admins[guild_id].remove(user.id)
        await interaction.response.send_message(f"❌ {user.mention} is no longer a trusted admin.", ephemeral=True)
    else:
        if len(trusted_admins[guild_id]) >= 10:
            await interaction.response.send_message("❌ You cannot assign more than 10 trusted admins. Please remove one to add another.", ephemeral=True)
        else:
            trusted_admins[guild_id].add(user.id)
            await interaction.response.send_message(f"✅ {user.mention} has been assigned as a trusted admin.", ephemeral=True)

    database["trusted_admins"] = {k: list(v) for k, v in trusted_admins.items()}
    save_database(database)

# /alert command
@bot.tree.command(name="security-alert", description="Sets up alerts for channel and role creations and deletions.")
@app_commands.describe(channel="The channel to send alerts to.")
async def setup_alert(interaction: discord.Interaction, channel: discord.TextChannel):
    guild = interaction.guild
    invoker = interaction.user

    if not has_permission(invoker, guild):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return

    guild_id = str(guild.id)
    alert_channels[guild_id] = channel.id
    alerting_enabled[guild_id] = True

    database["alert_channels"] = alert_channels
    database["alerting_enabled"] = alerting_enabled
    save_database(database)

    embed = discord.Embed(
        title="🚨 Alert Setup",
        description=f"Alerts will be sent to {channel.mention} if a channel or role is deleted or created.",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed)

# /message-alert command
@bot.tree.command(name="message-alert", description="Sets up alerts for message deletions and edits.")
@app_commands.describe(channel="The channel to send alerts to.")
async def setup_message_alert(interaction: discord.Interaction, channel: discord.TextChannel):
    guild_id = str(interaction.guild_id)
    invoker = interaction.user

    if not has_permission(invoker, interaction.guild):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return

    message_alert_channels[guild_id] = channel.id
    message_alerting_enabled[guild_id] = True

    database["message_alert_channels"] = message_alert_channels
    database["message_alerting_enabled"] = message_alerting_enabled
    save_database(database)

    embed = discord.Embed(
        title="📩 Message Alert Setup",
        description=f"Message alerts will be sent to {channel.mention} for deletions and edits.",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed)

# /alert-off command
@bot.tree.command(name="alert-off", description="Disables all alert notifications.")
async def disable_alerts(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    invoker = interaction.user

    if not (invoker.id in [1288797573674569740] or
            invoker == interaction.guild.owner or
            invoker.id in database["extra_owners"].get(guild_id, set())):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return

    if not database["alerting_enabled"].get(guild_id, False) and not database["message_alerting_enabled"].get(guild_id, False):
        await interaction.response.send_message("🚫 Alerts are already disabled.", ephemeral=True)
        return

    database["alerting_enabled"][guild_id] = False
    database["message_alerting_enabled"][guild_id] = False

    save_database(database)

    embed = discord.Embed(
        title="🚨 Alerts Disabled",
        description="All alert notifications have been disabled. To enable them again, please use `/alert <channel>` or `/message-alert <channel>`.",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed)

# /vote command
@bot.tree.command(name="vote", description="Vote for {bot.user} on top.gg")
async def vote(interaction: Interaction):
    embed = Embed(
        title="",
        description="Vote for {bot.user} on Top.gg!",
        color=Color.from_rgb(0, 0, 255)
    )
    embed.set_author(name="{bot.user}", icon_url=bot.user.avatar.url)  # Set the bot's avatar next to the title

    button = Button(
        label="🗳️ Vote on Top.gg",
        url="https://top.gg/bot/1288135630408257598/vote",
        style=ButtonStyle.link
    )

    view = View()
    view.add_item(button)
    
    await interaction.response.send_message(embed=embed, view=view)

# /review command
@bot.tree.command(name="review", description="Review {bot.user} on top.gg")
async def review(interaction: Interaction):
    embed = Embed(
        title="",
        description="If you're enjoying {bot.user}, please consider leaving a review on Top.gg!",
        color=Color.from_rgb(0, 0, 255)
    )
    embed.set_author(name="{bot.user}", icon_url=bot.user.avatar.url)  # Set the bot's avatar next to the title

    button = Button(
        label="✍️ Leave a Review",
        url="https://top.gg/bot/1288135630408257598#reviews",
        style=ButtonStyle.link
    )

    view = View()
    view.add_item(button)
    
    await interaction.response.send_message(embed=embed, view=view)

# /purge command
@bot.tree.command(name="purge", description="Purge a specified number of messages.")
@app_commands.describe(amount="The number of messages to purge.")
async def purge(interaction: discord.Interaction, amount: int):
    invoker = interaction.user
    guild_id = str(interaction.guild_id)
    
    # Load extra_owners and trusted_admins from the database
    extra_owners = {k: set(v) for k, v in database.get("extra_owners", {}).items()}
    trusted_admins = {k: set(v) for k, v in database.get("trusted_admins", {}).items()}
    
    # Check if the invoker has permission
    if not (invoker.id in [1288797573674569740] or 
            invoker == interaction.guild.owner or
            invoker.id in extra_owners.get(guild_id, set()) or 
            invoker.id in trusted_admins.get(guild_id, set())):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message("❌ Please specify a positive number of messages to purge.", ephemeral=True)
        return

    if amount > 50:
        await interaction.response.send_message("❌ You can only purge up to 50 messages at a time.", ephemeral=True)
        return

    # Defer the response to avoid interaction timeout
    await interaction.response.defer()

    try:
        await interaction.channel.purge(limit=amount + 1)  # Adding 1 to account for the command message itself
        
        # No message sent for successful purges
    except discord.Forbidden:
        # Notify if the bot doesn't have permission to delete messages
        await interaction.response.send_message("❌ I do not have permission to delete messages.", ephemeral=True)
    except discord.HTTPException:
        # Handle HTTP exceptions silently without logging
        await interaction.response.send_message("❌ An error occurred while trying to purge messages.", ephemeral=True)
    except discord.NotFound:
        # Handle not found errors silently without logging
        await interaction.response.send_message("❌ Some messages were not found and could not be deleted.", ephemeral=True)
    except Exception:
        # Handle any other exceptions silently without logging
        await interaction.response.send_message("❌ An unexpected error occurred.", ephemeral=True)
        # Suppress the exception traceback

# /ticket-setup command
@bot.tree.command(name="ticket-setup", description="Setup the ticket panel in a specific channel")
@app_commands.describe(
    channel="The channel where the ticket panel will be set up.",
    title="Custom title for the ticket panel (optional).",
    description="Custom description for the ticket panel (optional).",
    button_text="The text that will appear on the button (optional)."
)
async def setup(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    title: str = "User Ticket",
    description: str = "To Create a ticket, react with 📩",
    button_text: str = "📩 Create Ticket"
):
    user_id = interaction.user.id

    # Check if the user has voted recently
    if user_id != EXEMPT_USER_ID:
        has_voted = await check_user_voted_recently(user_id)
        if not has_voted:
            try:
                await interaction.response.send_message(
                    "Please show {bot.user} some love by voting for him on Top.gg to unlock this command:\nhttps://top.gg/bot/1288135630408257598/vote 🛡️✨\nYour support means everything! 💖", 
                    ephemeral=True
                )
            except discord.errors.NotFound:
                # Handle the case where the interaction response is no longer valid
                pass
            return

    # Check if the user has the required permissions
    if not (interaction.user.guild_permissions.administrator or interaction.user.guild_permissions.manage_guild):
        try:
            await interaction.response.send_message("❌ You don't have permission to use this command. Admin or Manage Server permission required.", ephemeral=True)
        except discord.errors.NotFound:
            pass
        return

    # Check if the category has been set up
    category_path = "ticket-category.json"
    if not os.path.exists(category_path):
        try:
            await interaction.response.send_message("❌ You need to set the ticket category first using `/ticket-category`.", ephemeral=True)
        except discord.errors.NotFound:
            pass
        return

    with open(category_path, "r") as file:
        category_data = json.load(file)

    guild_id = str(interaction.guild.id)
    if guild_id not in category_data or "category_id" not in category_data[guild_id]:
        try:
            await interaction.response.send_message("❌ You need to set the ticket category first using `/ticket-category`.", ephemeral=True)
        except discord.errors.NotFound:
            pass
        return

    # Ensure the JSON file exists and is created if it does not exist
    file_path = "ticket-channel.json"
    if not os.path.exists(file_path):
        with open(file_path, "w") as file:
            json.dump({}, file)

    # Load the current data
    with open(file_path, "r+") as file:
        data = json.load(file)

        # Check if there's already a panel set up
        if guild_id in data and "channel_id" in data[guild_id]:
            old_channel_id = data[guild_id]["channel_id"]
            old_channel = interaction.guild.get_channel(old_channel_id)
            if old_channel:
                async for message in old_channel.history(limit=100):
                    if message.author == bot.user and message.embeds:
                        await message.delete()
                try:
                    await old_channel.send("❌ The ticket panel has been moved to a new channel.")
                except discord.errors.NotFound:
                    pass
            
            response_message = "Ticket panel has been set up in the new channel and the previous panel has been removed."
        else:
            response_message = "Ticket panel has been set up!"

        # Update the data with the new channel ID
        data[guild_id] = {
            "channel_id": channel.id
        }
        file.seek(0)
        json.dump(data, file, indent=4)
        file.truncate()

    # Create the new ticket panel
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.blue()
    )
    embed.set_footer(text="")

    view = discord.ui.View()
    button = discord.ui.Button(label=button_text, custom_id="create_ticket", style=discord.ButtonStyle.primary)
    view.add_item(button)

    try:
        await channel.send(embed=embed, view=view)
        await interaction.response.send_message(response_message, ephemeral=True)
    except discord.errors.NotFound:
        # Handle the case where the interaction response is no longer valid
        pass

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        if interaction.data['custom_id'] == "create_ticket":
            guild = interaction.guild

            # Load the ticket channel setup from the JSON file
            file_path = "ticket-channel.json"
            if not os.path.exists(file_path):
                try:
                    await interaction.response.send_message("❌ Ticket setup not found. Please run the setup command again.", ephemeral=True)
                except discord.errors.NotFound:
                    pass
                return

            with open(file_path, "r") as file:
                data = json.load(file)

            guild_id = str(interaction.guild.id)
            if guild_id not in data or "channel_id" not in data[guild_id]:
                try:
                    await interaction.response.send_message("❌ Ticket setup not found for this server. Please run the setup command again.", ephemeral=True)
                except discord.errors.NotFound:
                    pass
                return

            # Retrieve the setup channel ID
            setup_channel_id = data[guild_id]["channel_id"]
            setup_channel = interaction.guild.get_channel(setup_channel_id)
            if setup_channel is None:
                try:
                    await interaction.response.send_message("❌ Setup channel not found. Please run the setup command again.", ephemeral=True)
                except discord.errors.NotFound:
                    pass
                return

            # Load the ticket category from the JSON file
            category_path = "ticket-category.json"
            if not os.path.exists(category_path):
                try:
                    await interaction.response.send_message("❌ Ticket category not found. Please set it up using `/ticket-category`.", ephemeral=True)
                except discord.errors.NotFound:
                    pass
                return

            with open(category_path, "r") as file:
                category_data = json.load(file)

            if guild_id not in category_data or "category_id" not in category_data[guild_id]:
                try:
                    await interaction.response.send_message("❌ Ticket category not found. Please set it up using `/ticket-category`.", ephemeral=True)
                except discord.errors.NotFound:
                    pass
                return

            category_id = category_data[guild_id]["category_id"]
            category = interaction.guild.get_channel(category_id)
            if category is None or not isinstance(category, discord.CategoryChannel):
                try:
                    await interaction.response.send_message("❌ Invalid ticket category. Please set it up again using `/ticket-category`.", ephemeral=True)
                except discord.errors.NotFound:
                    pass
                return

            # Load custom title and description if set and enabled
            custom_message_path = "ticket-custom-message.json"
            title = "Welcome!"
            description = "Thank you for contacting support.\nPlease describe your issue and wait for a response."

            if os.path.exists(custom_message_path):
                with open(custom_message_path, "r") as file:
                    custom_message_data = json.load(file)
                    custom_message = custom_message_data.get(guild_id, {})

                    if custom_message.get("status") == "on":
                        title = custom_message.get("title", title)
                        description = custom_message.get("description", description).replace('\\n', '\n')

            # Load ticket staff roles from the JSON file
            ticket_staff_path = "ticket-staff.json"
            if not os.path.exists(ticket_staff_path):
                try:
                    await interaction.response.send_message("❌ Ticket staff roles not found. Please run the ticket staff command again.", ephemeral=True)
                except discord.errors.NotFound:
                    pass
                return

            with open(ticket_staff_path, "r") as file:
                staff_data = json.load(file)

            # Set up the channel overwrites
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(view_channel=True),
            }

            # Add ticket staff roles to overwrites
            server_roles = staff_data.get(str(interaction.guild.id), [])
            for role_id in server_roles:
                role = interaction.guild.get_role(role_id)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(view_channel=True)

            # Create the ticket channel under the specified category
            channel_name = f"ticket-{interaction.user.name}"
            channel_topic = f"Ticket {interaction.user.name} | {interaction.user.id}"
            channel = await category.create_text_channel(
                name=channel_name,
                topic=channel_topic,
                overwrites=overwrites
            )

            # Load the log channel
            logs_path = "ticket-logs.json"
            log_channel_id = None
            if os.path.exists(logs_path):
                with open(logs_path, "r") as file:
                    log_data = json.load(file)
                    log_channel_id = log_data.get(guild_id, {}).get("log_channel_id")

            if log_channel_id:
                log_channel = interaction.guild.get_channel(log_channel_id)
                if log_channel:
                    log_embed = discord.Embed(
                        title="Ticket Opened",
                        description=f"{interaction.user.mention} opened a new ticket {channel.mention}",
                        color=discord.Color.blue()
                    )
                    try:
                        await log_channel.send(embed=log_embed)
                    except discord.errors.NotFound:
                        pass

            # Create the "Close Ticket" button
            class CloseTicketView(View):
                def __init__(self):
                    super().__init__(timeout=None)

                @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket")
                async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
                    # Modal to ask for the reason to close the ticket
                    class CloseTicketModal(Modal, title="Close Ticket"):
                        reason = TextInput(label="Reason", style=discord.TextStyle.paragraph, required=True)

                        async def on_submit(self, interaction: discord.Interaction):
                            await interaction.response.defer()  # Defer the interaction response
                            if not interaction.channel.name.startswith("ticket-"):
                                await interaction.followup.send("❌ This is not a ticket channel.", ephemeral=True)
                                return

                            # Ensure user has permission to close the ticket
                            if not interaction.user.guild_permissions.administrator:
                                if not any(role.id in server_roles for role in interaction.user.roles):
                                    await interaction.followup.send("❌ You don't have permission to close this ticket.", ephemeral=True)
                                    return

                            embed = discord.Embed(
                                title=interaction.guild.name,  # Server name as the title
                                description="**Ticket Closed**",  # Subtitle
                                color=discord.Color.blue()
                            )
                            embed.add_field(
                                name="Summary",
                                value=f"Your ticket ({interaction.channel.name}) has been closed by {interaction.user.name}.",
                                inline=False
                            )
                            embed.add_field(
                                name="Reason",
                                value=self.reason.value,
                                inline=False
                            )
                            embed.set_footer(text="")

                            # Send embed to the user and delete the channel
                            user_name = interaction.channel.name.split("ticket-")[1]
                            member = discord.utils.get(interaction.guild.members, name=user_name)
                            if member:
                                await member.send(embed=embed)
                            await interaction.channel.delete()

                            # Send close ticket log if log channel is set
                            if log_channel_id:
                                log_channel = interaction.guild.get_channel(log_channel_id)
                                if log_channel:
                                    close_embed = discord.Embed(
                                        title="Ticket Closed",
                                        description=f"{interaction.user.mention} closed the ticket ({interaction.channel.name}) for the reason: {self.reason.value}",
                                        color=discord.Color.blue()
                                    )
                                    try:
                                        await log_channel.send(embed=close_embed)
                                    except discord.errors.NotFound:
                                        pass

                    await interaction.response.send_modal(CloseTicketModal())

            # Send the confirmation and ticket created messages with the button
            embed = discord.Embed(
                title="Ticket",
                description=f"Opened a new ticket: {channel.mention}",
                color=discord.Color.blue()
            )
            embed.set_footer(text="")

            try:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except discord.errors.NotFound:
                pass

            try:
                await channel.send(content=interaction.user.mention, embed=discord.Embed(
                    title=title,
                    description=description,
                    color=discord.Color.blue()
                ).set_footer(text=""), view=CloseTicketView())
            except discord.errors.NotFound:
                pass

# /ticket-add-user
@bot.tree.command(name="ticket-add-user", description="Add a user to an open ticket")
@app_commands.describe(user="The user you want to add to the ticket")
async def ticket_add_user(interaction: discord.Interaction, user: discord.Member):
    # Check if this is a ticket channel
    if not interaction.channel.name.startswith("ticket-"):
        await interaction.response.send_message("❌ This is not a ticket channel.", ephemeral=True)
        return

    # Load ticket staff roles from the JSON file
    ticket_staff_path = "ticket-staff.json"
    if not os.path.exists(ticket_staff_path):
        await interaction.response.send_message("❌ Ticket staff roles not found. Please set them up using the appropriate command.", ephemeral=True)
        return

    with open(ticket_staff_path, "r") as file:
        staff_data = json.load(file)

    # Verify if the user has a staff role
    server_roles = staff_data.get(str(interaction.guild.id), [])
    if not any(role.id in server_roles for role in interaction.user.roles):
        await interaction.response.send_message("❌ You don't have permission to add users to tickets.", ephemeral=True)
        return

    # Set up the permission overwrite for the user being added
    overwrites = interaction.channel.overwrites_for(user)
    overwrites.view_channel = True
    await interaction.channel.set_permissions(user, overwrite=overwrites)

    await interaction.response.send_message(f"✅ {user.mention} has been added to the ticket.", ephemeral=True)

# /ticket-remove-user commannd
@bot.tree.command(name="ticket-remove-user", description="Remove a user from an open ticket")
@app_commands.describe(user="The user you want to remove from the ticket")
async def ticket_remove_user(interaction: discord.Interaction, user: discord.Member):
    # Check if this is a ticket channel
    if not interaction.channel.name.startswith("ticket-"):
        await interaction.response.send_message("❌ This is not a ticket channel.", ephemeral=True)
        return

    # Load ticket staff roles from the JSON file
    ticket_staff_path = "ticket-staff.json"
    if not os.path.exists(ticket_staff_path):
        await interaction.response.send_message("❌ Ticket staff roles not found. Please set them up using the appropriate command.", ephemeral=True)
        return

    with open(ticket_staff_path, "r") as file:
        staff_data = json.load(file)

    # Verify if the user has a staff role
    server_roles = staff_data.get(str(interaction.guild.id), [])
    if not any(role.id in server_roles for role in interaction.user.roles):
        await interaction.response.send_message("❌ You don't have permission to remove users from tickets.", ephemeral=True)
        return

    # Remove the user's permission to view the ticket
    await interaction.channel.set_permissions(user, overwrite=None)

    await interaction.response.send_message(f"✅ {user.mention} has been removed from the ticket.", ephemeral=True)

# /ticket-logs command
@bot.tree.command(name="ticket-logs", description="Set the channel for ticket logs")
@app_commands.describe(channel="The channel to send ticket logs to")
async def ticket_logs(interaction: discord.Interaction, channel: discord.TextChannel):
    user_id = interaction.user.id

    # Check if the user has voted recently
    if user_id != EXEMPT_USER_ID:
        has_voted = await check_user_voted_recently(user_id)
        
        if not has_voted:
            await interaction.response.send_message(
                "Please show {bot.user} some love by voting for him on Top.gg to unlock this command:\nhttps://top.gg/bot/1288135630408257598/vote 🛡️✨\nYour support means everything! 💖", ephemeral=True
            )
            return

    logs_path = "ticket-logs.json"
    
    # Create the file if it does not exist
    if not os.path.exists(logs_path):
        with open(logs_path, "w") as file:
            json.dump({}, file, indent=4)

    # Load existing data
    with open(logs_path, "r") as file:
        data = json.load(file)

    guild_id = str(interaction.guild.id)
    if guild_id not in data:
        data[guild_id] = {}

    data[guild_id]["log_channel_id"] = channel.id

    # Save the updated data
    with open(logs_path, "w") as file:
        json.dump(data, file, indent=4)

    await interaction.response.send_message(f"✅ Ticket logs channel set to {channel.mention}.", ephemeral=True)

# /ticket-category command
@bot.tree.command(name="ticket-category", description="Select the category for ticket channels")
@app_commands.describe(category="The category where the ticket channels will be created.")
async def ticket_category(interaction: discord.Interaction, category: discord.CategoryChannel):
    user_id = interaction.user.id

    # Check if the user has voted recently
    if user_id != EXEMPT_USER_ID:
        has_voted = await check_user_voted_recently(user_id)
        
        if not has_voted:
            await interaction.response.send_message(
                "Please show {bot.user} some love by voting for him on Top.gg to unlock this command:\nhttps://top.gg/bot/1288135630408257598/vote 🛡️✨\nYour support means everything! 💖", ephemeral=True
            )
            return

    # Check if the user has the required permissions
    if not (interaction.user.guild_permissions.administrator or interaction.user.guild_permissions.manage_guild):
        await interaction.response.send_message("❌ You don't have permission to use this command. Admin or Manage Server permission required.", ephemeral=True)
        return

    # Ensure the JSON file exists and is created if it does not exist
    file_path = "ticket-category.json"
    if not os.path.exists(file_path):
        with open(file_path, "w") as file:
            json.dump({}, file)

    # Load the current data and update with the selected category
    with open(file_path, "r+") as file:
        data = json.load(file)
        guild_id = str(interaction.guild.id)

        data[guild_id] = {
            "category_id": category.id
        }
        file.seek(0)
        json.dump(data, file, indent=4)
        file.truncate()

    await interaction.response.send_message(f"Ticket channels will now be created under the `{category.name}` category.", ephemeral=True)

# /ticket-custom-message command
@bot.tree.command(name="ticket-custom-message", description="Enable or disable custom ticket messages, and set title/description if enabled")
@app_commands.describe(status="Enable or disable custom messages ('on' to enable, 'off' to disable).", title="Custom title for the ticket embed (optional).", description="Custom description for the ticket embed (optional).")
async def ticket_custom_message(interaction: discord.Interaction, status: str, title: str = None, description: str = None):
    user_id = interaction.user.id

    # Check if the user has voted recently
    if user_id != EXEMPT_USER_ID:
        has_voted = await check_user_voted_recently(user_id)
        
        if not has_voted:
            await interaction.response.send_message(
                "Please show {bot.user} some love by voting for him on Top.gg to unlock this command:\nhttps://top.gg/bot/1288135630408257598/vote 🛡️✨\nYour support means everything! 💖", ephemeral=True
            )
            return

    # Check if the user has the required permissions
    if not (interaction.user.guild_permissions.administrator or interaction.user.guild_permissions.manage_guild):
        await interaction.response.send_message("❌ You don't have permission to use this command. Admin or Manage Server permission required.", ephemeral=True)
        return

    file_path = "ticket-custom-message.json"
    
    # Ensure the JSON file exists
    if not os.path.exists(file_path):
        with open(file_path, "w") as file:
            json.dump({}, file)

    # Load the current data
    with open(file_path, "r+") as file:
        data = json.load(file)
        guild_id = str(interaction.guild.id)

        if status == "on":
            if not title or not description:
                await interaction.response.send_message("❌ When enabling custom messages, both title and description must be provided.", ephemeral=True)
                return
            data[guild_id] = {
                "status": "on",
                "title": title,
                "description": description.replace('\n', '\\n')
            }
            message = "✅ Custom ticket message enabled successfully!"
        else:
            if guild_id in data:
                # Remove the title and description when disabling custom messages
                data.pop(guild_id)
                message = "✅ Custom ticket message disabled. Default message will be used."
            else:
                message = "Custom ticket message was not set up for this server. Default message will be used."

        # Write the updated data back to the file
        file.seek(0)
        json.dump(data, file, indent=4)
        file.truncate()

    await interaction.response.send_message(message, ephemeral=True)

# /ticket-close command
@bot.tree.command(name="ticket-close", description="Close a ticket with a specific reason")
@app_commands.describe(reason="Reason for closing the ticket")
async def close(interaction: discord.Interaction, reason: str):
    # Check if the user has admin permissions
    if not interaction.user.guild_permissions.administrator:
        # Load the ticket-staff roles from the JSON file
        with open("ticket-staff.json", "r") as file:
            data = json.load(file)
        
        # Get the roles for the current guild
        server_roles = data.get(str(interaction.guild.id), [])
        
        # Check if the user has any of the ticket-staff roles
        if not any(role.id in server_roles for role in interaction.user.roles):
            await interaction.response.send_message("❌ You don't have permission to use this command. Admin permission or ticket-staff role required.", ephemeral=True)
            return

    # Ensure this is a ticket channel
    if not interaction.channel.name.startswith("ticket-"):
        await interaction.response.send_message("❌ This is not a ticket channel.", ephemeral=True)
        return
    
    user = interaction.channel.name.split("ticket-")[1]
    member = discord.utils.get(interaction.guild.members, name=user)

    if member:
        embed = discord.Embed(
            title=interaction.guild.name,  # Server name as the title
            description="**Ticket Closed**",  # Subtitle
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Summary",
            value=f"Your ticket ({interaction.channel.name}) has been closed by {interaction.user.name}.",
            inline=False
        )
        embed.add_field(
            name="Reason",
            value=reason,
            inline=False
        )
        embed.set_footer(text="")
        await member.send(embed=embed)

    await interaction.channel.delete()

# /ticket-staff command
@bot.tree.command(name="ticket-staff", description="Assign or remove a role as ticket staff")
@app_commands.describe(role="Role to assign or remove as ticket staff")
async def ticket_staff(interaction: discord.Interaction, role: discord.Role):
    user_id = interaction.user.id

    # Check if the user has voted recently
    if user_id != EXEMPT_USER_ID:
        has_voted = await check_user_voted_recently(user_id)
        
        if not has_voted:
            await interaction.response.send_message(
                "Please show {bot.user} some love by voting for him on Top.gg to unlock this command:\nhttps://top.gg/bot/1288135630408257598/vote 🛡️✨\nYour support means everything! 💖", ephemeral=True
            )
            return

    # Check if the user has administrator or manage_guild permissions
    if not (interaction.user.guild_permissions.administrator or interaction.user.guild_permissions.manage_guild):
        await interaction.response.send_message("❌ You don't have permission to use this command. Administrator or Manage Server permission required.", ephemeral=True)
        return
    
    file_path = "ticket-staff.json"
    
    # Ensure the JSON file exists
    if not os.path.exists(file_path):
        with open(file_path, "w") as file:
            json.dump({}, file)

    # Load the current data
    with open(file_path, "r+") as file:
        data = json.load(file)
        guild_id = str(interaction.guild.id)

        # Initialize the list if it doesn't exist
        if guild_id not in data:
            data[guild_id] = []
        
        # Check if the role is already assigned
        if role.id in data[guild_id]:
            # Remove the role from the list
            data[guild_id].remove(role.id)
            message = f"❌ {role.mention} has been removed as ticket staff."
        else:
            # Add the role to the list
            data[guild_id].append(role.id)
            message = f"✅ {role.mention} has been assigned as ticket staff."

        # Write the updated data back to the file
        file.seek(0)
        json.dump(data, file, indent=4)
        file.truncate()

    await interaction.response.send_message(message, ephemeral=True)

# /ticket-staff-list
@bot.tree.command(name="ticket-staff-list", description="List all roles assigned as ticket staff for this server")
@commands.has_permissions(administrator=True, manage_guild=True)
async def ticket_staff_list(interaction: discord.Interaction):
    file_path = "ticket-staff.json"
    
    # Ensure the JSON file exists
    if not os.path.exists(file_path):
        await interaction.response.send_message("❌ No ticket staff roles have been set for this server yet.", ephemeral=True)
        return
    
    # Load the current data
    with open(file_path, "r") as file:
        data = json.load(file)
        guild_id = str(interaction.guild.id)
        
        # Check if there are roles set for the server
        if guild_id not in data or not data[guild_id]:
            await interaction.response.send_message("❌ No ticket staff roles have been set for this server.", ephemeral=True)
            return
        
        # Get the roles from the data
        roles = [interaction.guild.get_role(role_id) for role_id in data[guild_id]]
        role_mentions = [role.mention for role in roles if role is not None]
        
        if not role_mentions:
            await interaction.response.send_message("❌ No valid ticket staff roles found.", ephemeral=True)
            return
        
        # Create and send the message with the list of roles
        roles_list = "\n".join(role_mentions)
        embed = discord.Embed(
            title=f"{interaction.guild.name}",
            description=f"**__Staff Roles:__**\n{roles_list}",
            color=discord.Color.pink()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.event
async def on_message_delete(message):
    guild_id = str(message.guild.id)
    database = load_database()

    if guild_id in database["message_alert_channels"] and database["message_alerting_enabled"].get(guild_id, False):
        alert_channel_id = database["message_alert_channels"][guild_id]
        alert_channel = bot.get_channel(alert_channel_id)
        if alert_channel:
            embed = discord.Embed(
                title="📩 Message Alert",
                description=f"A message from {message.author.mention} was deleted in <#{message.channel.id}>:\n{message.content}",
                color=discord.Color.blue()
            )
            await alert_channel.send(embed=embed)

@bot.event
async def on_message_edit(before, after):
    guild_id = str(before.guild.id)
    database = load_database()

    if guild_id in database["message_alert_channels"] and database["message_alerting_enabled"].get(guild_id, False):
        alert_channel_id = database["message_alert_channels"][guild_id]
        alert_channel = bot.get_channel(alert_channel_id)
        if alert_channel:
            embed = discord.Embed(
                title="📩 Message Alert",
                description=f"A message from {before.author.mention} was edited in <#{before.channel.id}>:",
                color=discord.Color.blue()
            )
            embed.add_field(name="Before", value=before.content, inline=False)
            embed.add_field(name="After", value=after.content, inline=False)
            await alert_channel.send(embed=embed)

# Updated bot events with permission check
@bot.event
async def on_guild_channel_delete(channel):
    guild = channel.guild
    guild_id = str(guild.id)

    # Load database
    database = load_database()

    if guild_id in database["alert_channels"] and database["alerting_enabled"].get(guild_id, False):
        alert_channel_id = database["alert_channels"][guild_id]
        alert_channel = bot.get_channel(alert_channel_id)

        if alert_channel:
            async for entry in guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=1):
                deleter = entry.user
                embed = discord.Embed(
                    title="🚨 Alert",
                    description=f"A {channel.type} channel '{channel.name}' was deleted by {deleter.mention}.",
                    color=discord.Color.blue()
                )
                await alert_channel.send(embed=embed)

                logger.debug(f"Deleter: {deleter}, Deleter's Roles: {deleter.roles}")
                logger.debug(f"Has Permission: {has_permission(deleter, guild)}")

                # Check if the deleter does not have permission
                if not has_permission(deleter, guild):
                    bot_member = guild.me
                    logger.debug(f"Bot Member Top Role: {bot_member.top_role}, Deleter Top Role: {deleter.top_role}")
                    
                    # Kick if the bot's role is higher than the deleter's
                    if bot_member.top_role > deleter.top_role:
                        await guild.kick(deleter, reason="Deleted a channel without permission")
                        logger.debug(f"Kicked User: {deleter}")
                    else:
                        logger.debug("Bot role is not higher than the deleter's role")

@bot.event
async def on_guild_channel_create(channel):
    guild = channel.guild
    guild_id = str(guild.id)

    # Load database
    database = load_database()

    if guild_id in database["alert_channels"] and database["alerting_enabled"].get(guild_id, False):
        alert_channel_id = database["alert_channels"][guild_id]
        alert_channel = bot.get_channel(alert_channel_id)

        if alert_channel:
            async for entry in guild.audit_logs(action=discord.AuditLogAction.channel_create, limit=1):
                creator = entry.user
                embed = discord.Embed(
                    title="🚨 Alert",
                    description=f"A {channel.type} channel '{channel.name}' was created by {creator.mention}.",
                    color=discord.Color.blue()
                )
                await alert_channel.send(embed=embed)

                logger.debug(f"Creator: {creator}, Creator's Roles: {creator.roles}")
                logger.debug(f"Has Permission: {has_permission(creator, guild)}")

                # Check if the creator does not have permission
                if not has_permission(creator, guild):
                    bot_member = guild.me
                    logger.debug(f"Bot Member Top Role: {bot_member.top_role}, Creator Top Role: {creator.top_role}")
                    
                    # Kick if the bot's role is higher than the creator's
                    if bot_member.top_role > creator.top_role:
                        await guild.kick(creator, reason="Created a channel without permission")
                        logger.debug(f"Kicked User: {creator}")
                    else:
                        logger.debug("Bot role is not higher than the creator's role")

@bot.event
async def on_guild_role_create(role):
    guild = role.guild
    guild_id = str(guild.id)

    # Load database
    database = load_database()

    if guild_id in database["alert_channels"] and database["alerting_enabled"].get(guild_id, False):
        alert_channel_id = database["alert_channels"][guild_id]
        alert_channel = bot.get_channel(alert_channel_id)

        if alert_channel:
            async for entry in guild.audit_logs(action=discord.AuditLogAction.role_create, limit=1):
                creator = entry.user
                embed = discord.Embed(
                    title="🚨 Alert",
                    description=f"A role '{role.name}' was created by {creator.mention}.",
                    color=discord.Color.blue()
                )
                await alert_channel.send(embed=embed)

                logger.debug(f"Creator: {creator}, Creator's Roles: {creator.roles}")
                logger.debug(f"Has Permission: {has_permission(creator, guild)}")

                # Check if the creator does not have permission
                if not has_permission(creator, guild):
                    bot_member = guild.me
                    logger.debug(f"Bot Member Top Role: {bot_member.top_role}, Creator Top Role: {creator.top_role}")
                    
                    # Kick if the bot's role is higher than the creator's
                    if bot_member.top_role > creator.top_role:
                        await guild.kick(creator, reason="Created a role without permission")
                        logger.debug(f"Kicked User: {creator}")
                    else:
                        logger.debug("Bot role is not higher than the creator's role")

@bot.event
async def on_guild_role_delete(role):
    guild = role.guild
    guild_id = str(guild.id)

    # Load database
    database = load_database()

    if guild_id in database["alert_channels"] and database["alerting_enabled"].get(guild_id, False):
        alert_channel_id = database["alert_channels"][guild_id]
        alert_channel = bot.get_channel(alert_channel_id)

        if alert_channel:
            async for entry in guild.audit_logs(action=discord.AuditLogAction.role_delete, limit=1):
                deleter = entry.user
                embed = discord.Embed(
                    title="🚨 Alert",
                    description=f"A role '{role.name}' was deleted by {deleter.mention}.",
                    color=discord.Color.blue()
                )
                await alert_channel.send(embed=embed)

                logger.debug(f"Deleter: {deleter}, Deleter's Roles: {deleter.roles}")
                logger.debug(f"Has Permission: {has_permission(deleter, guild)}")

                # Check if the deleter does not have permission
                if not has_permission(deleter, guild):
                    bot_member = guild.me
                    logger.debug(f"Bot Member Top Role: {bot_member.top_role}, Deleter Top Role: {deleter.top_role}")
                    
                    # Kick if the bot's role is higher than the deleter's
                    if bot_member.top_role > deleter.top_role:
                        await guild.kick(deleter, reason="Deleted a role without permission")
                        logger.debug(f"Kicked User: {deleter}")
                    else:
                        logger.debug("Bot role is not higher than the deleter's role")

@bot.event
async def on_member_join(member: discord.Member):
    guild = member.guild
    guild_id = str(guild.id)

    # Check if the new member is a bot
    if member.bot:
        # Load database
        database = load_database()

        if guild_id in database["alert_channels"] and database["alerting_enabled"].get(guild_id, False):
            alert_channel_id = database["alert_channels"][guild_id]
            alert_channel = bot.get_channel(alert_channel_id)

            if alert_channel:
                # Get the audit log entry for the bot addition
                async for entry in guild.audit_logs(action=discord.AuditLogAction.bot_add, limit=1):
                    adder = entry.user  # User who added the bot

                    embed = discord.Embed(
                        title="🚨 Alert",
                        description=f"A bot '{member.name}' was added by {adder.mention}.",
                        color=discord.Color.blue()
                    )
                    await alert_channel.send(embed=embed)

                    logger.debug(f"Adder: {adder}, Adder's Roles: {adder.roles}")
                    logger.debug(f"Has Permission: {has_permission(adder, guild)}")

                    # Check if the adder does not have permission
                    if not has_permission(adder, guild):
                        bot_member = guild.me
                        logger.debug(f"Bot Member Top Role: {bot_member.top_role}, Adder Top Role: {adder.top_role}")

                        # Kick the added bot
                        await guild.kick(member, reason="Bot added by user without permission")
                        logger.debug(f"Kicked Bot: {member}")
                    else:
                        logger.debug("User has permission to add the bot")

@bot.event
async def on_message(message):
    user_id = 1301923181287968899  # Replace with the specific user ID

    if any(mention.id == user_id for mention in message.mentions):
        response = (
            f"**Hello there! {bot.user} here!**\n"
            f"**Need any assistance or you don't know where to start from? Check the points given below!**\n\n"
            f"> \n"
            f"> - Bot Prefix `/`\n"
            f"> \n"
            f"> - Learn about all the commands `/help`\n"
            f"> \n\n"
            f"**Please report any bugs/glitches if found!**\n\n"
            f" **__Support:__**"
        )

        # Create buttons
        button_support = Button(label="Support Server", url="https://discord.gg/NkekNtQfnb", style=discord.ButtonStyle.link)
        button_website = Button(label="hosting", url="https://bot-hosting.net/panel/", style=discord.ButtonStyle.link)
        button_invite = Button(label="Invite Me", url="https://discord.com/oauth2/authorize?client_id=1255568682357362769", style=discord.ButtonStyle.link)

        # Add buttons to a view
        view = View()
        view.add_item(button_support)
        view.add_item(button_website)
        view.add_item(button_invite)

        # Reply to the message with buttons
        await message.reply(response, mention_author=False, view=view)

    await bot.process_commands(message)

@bot.event
async def on_guild_join(guild):
    response = (
        f" **Hello there! {bot.user} here!**\n"
        f"**Need any assistance or you don't know where to start from? Check the points given below!**\n\n"
        f"> \n"

        f"> - Bot Prefix `/`\n"
        f"> \n"
        f"> - Learn about all the commands `/help`\n"
        f"> \n\n"
        f"**Please report any bugs/glitches if found!**\n\n"
        f" **__Support:__**"
    )

    # Create buttons
    button_support = Button(label="Support Server", url="https://discord.gg/NkekNtQfnb", style=discord.ButtonStyle.link)
    button_website = Button(label="hosting", url="https://bot-hosting.net/panel/", style=discord.ButtonStyle.link)
    button_invite = Button(label="Invite me!", url="https://discord.com/oauth2/authorize?client_id=1301923181287968899", style=discord.ButtonStyle.link)

    # Add buttons to a view
    view = View()
    view.add_item(button_support)
    view.add_item(button_website)
    view.add_item(button_invite)

    # Send the message with buttons to the first available channel
    for channel in guild.text_channels:
        if channel.permissions_for(guild.default_role).send_messages and channel.permissions_for(guild.default_role).read_messages:
            await channel.send(response, view=view)
            break

# Load anti-spam data from file
def load_anti_spam_data():
    try:
        with open("anti-spam.json", "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

# Save anti-spam data to file
def save_anti_spam_data(data):
    with open("anti-spam.json", "w") as file:
        json.dump(data, file, indent=4)

# /anti-spam command
@bot.tree.command(name="anti-spam", description="Enable or disable anti-spam for the server")
@app_commands.choices(status=[
    app_commands.Choice(name="on", value="on"),
    app_commands.Choice(name="off", value="off")
])
async def anti_spam(interaction: discord.Interaction, status: app_commands.Choice[str]):
    guild_id_str = str(interaction.guild.id)

    # Check if the user has the required permissions
    if not has_permission(interaction.user, interaction.guild, check_roles=True):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return

    data = load_anti_spam_data()

    # Toggle the anti-spam feature on or off for the server
    if status.value == "on":
        data[guild_id_str] = True
        await interaction.response.send_message(f"Anti-spam is now enabled for {interaction.guild.name}.", ephemeral=True)
    else:
        data[guild_id_str] = False
        await interaction.response.send_message(f"Anti-spam is now disabled for {interaction.guild.name}.", ephemeral=True)

    save_anti_spam_data(data)

# Dictionary to keep track of message timestamps for users and their messages
user_message_timestamps = defaultdict(list)
user_messages = defaultdict(list)

# Event to check messages for spam
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    guild_id_str = str(message.guild.id)
    data = load_anti_spam_data()

    # Check if anti-spam is enabled for the server
    if data.get(guild_id_str, False):
        current_time = time.time()
        user_id = message.author.id

        # Keep only timestamps within the last 15 seconds
        user_message_timestamps[user_id] = [timestamp for timestamp in user_message_timestamps[user_id] if current_time - timestamp < 15]
        user_message_timestamps[user_id].append(current_time)
        user_messages[user_id].append(message)

        # Keep only messages within the last 15 seconds
        user_messages[user_id] = [msg for msg in user_messages[user_id] if (current_time - (msg.created_at.timestamp() if hasattr(msg, 'created_at') else 0)) < 15]

        # Check if the user has sent too many messages in less than 15 seconds
        if len(user_message_timestamps[user_id]) > 4:  # 5 messages in 15 seconds threshold
            # Check if the user has permission
            if not has_permission(message.author, message.guild):
                try:
                    # Timeout the user
                    timeout_duration = timedelta(minutes=1)
                    timeout_until = discord.utils.utcnow() + timeout_duration
                    await message.author.edit(timed_out_until=timeout_until, reason="Spamming")

                    # Notify the channel
                    await message.channel.send(f"{message.author.mention} has been timed out for spamming.", delete_after=5)

                    # Delete the last 5 messages of the user
                    for msg in user_messages[user_id][-5:]:
                        try:
                            await msg.delete()
                        except discord.Forbidden:
                            await message.channel.send("I do not have permission to delete this message.", delete_after=5)
                        except discord.HTTPException as e:
                            await message.channel.send(f"An error occurred: {e}", delete_after=1)

                except discord.Forbidden:
                    await message.channel.send("I do not have permission to timeout this user.", delete_after=5)
                except discord.HTTPException as e:
                    await message.channel.send(f"An error occurred: {e}", delete_after=1)

            else:
                # User has permission, so no timeout, but delete their last 5 messages
                try:
                    for msg in user_messages[user_id][-5:]:
                        try:
                            await msg.delete()
                        except discord.Forbidden:
                            await message.channel.send("I do not have permission to delete this message.", delete_after=5)
                        except discord.HTTPException as e:
                            await message.channel.send(f"An error occurred: {e}", delete_after=1)

                    # Notify the user to slow down
                    await message.channel.send(f"{message.author.mention}, please slow down with the messages!", delete_after=5)

                except discord.Forbidden:
                    await message.channel.send("I do not have permission to delete messages or notify this user.", delete_after=5)
                except discord.HTTPException as e:
                    await message.channel.send(f"An error occurred: {e}", delete_after=1)

    # Make sure the bot processes other commands
    await bot.process_commands(message)

# /give-role command
@bot.tree.command(name="give-role", description="Give a role to a user")
@app_commands.describe(user="Select the user", role="Select the role", role_id="Or enter the role ID")
async def give_role(interaction: discord.Interaction, user: discord.Member, role: Optional[discord.Role] = None, role_id: Optional[str] = None):
    # Check if the user has Manage Roles or Administrator permission
    if not (interaction.user.guild_permissions.manage_roles or interaction.user.guild_permissions.administrator):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return

    # Determine the role to assign
    if role is None and role_id is None:
        await interaction.response.send_message("❌ You must provide either a role or a role ID.", ephemeral=True)
        return

    if role is None:
        role = discord.utils.get(interaction.guild.roles, id=int(role_id))

    if role is None:
        await interaction.response.send_message("❌ No role found with the provided ID.", ephemeral=True)
        return

    # Check if the role is under the bot's role
    if role.position >= interaction.guild.me.top_role.position:
        await interaction.response.send_message("❌ I cannot assign a role that is equal to or above my role in the hierarchy.", ephemeral=True)
        return

    await user.add_roles(role)
    await interaction.response.send_message(f"✅ Gave {role.mention} to {user.mention}.", ephemeral=True)

# /create-role command choice
class RolePermissions(app_commands.Choice[str]):
    ALL = "all"
    NONE = "none"

# /create-role command
@bot.tree.command(name="create-role", description="Create a role with customizable permissions")
@app_commands.describe(
    name="The name of the role",
    color="The color of the role (enter role hex code # or color name like blue)",
    permissions="Choose 'all' for all permissions or 'none' for no permissions"
)
@app_commands.choices(permissions=[
    app_commands.Choice(name="All Permissions", value=RolePermissions.ALL),
    app_commands.Choice(name="No Permissions", value=RolePermissions.NONE)
])
async def create_role(interaction: discord.Interaction, name: str, color: str, permissions: app_commands.Choice[str]):
    # Check if the user has Manage Roles or Administrator permission
    if not (interaction.user.guild_permissions.manage_roles or interaction.user.guild_permissions.administrator):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return

    # Convert color input to discord.Color
    try:
        if color.startswith("#"):
            role_color = discord.Color(int(color[1:], 16))
        else:
            role_color = discord.Color.from_str(color.lower())
    except ValueError:
        await interaction.response.send_message("❌ Invalid color format. Please provide a valid hex code (e.g., #00ffff) or color name (e.g., blue).", ephemeral=True)
        return

    # Determine role permissions based on the user's choice
    if permissions.value == RolePermissions.ALL:
        role_permissions = discord.Permissions.all()  # Grants all permissions including Administrator
    else:
        role_permissions = discord.Permissions.none()  # No permissions granted

    # Create the role
    new_role = await interaction.guild.create_role(
        name=name,
        color=role_color,
        permissions=role_permissions
    )

    # Move the role directly under the bot's top role
    bot_role_position = interaction.guild.me.top_role.position
    await new_role.edit(position=bot_role_position - 1)

    await interaction.response.send_message(f"✅ Created the role **{new_role.name}** with `{permissions.value}` permissions.", ephemeral=True)

# /delete-role command
@bot.tree.command(name="delete-role", description="Delete a role")
@app_commands.describe(role="Select the role", role_id="Or enter the role ID")
async def delete_role(interaction: discord.Interaction, role: Optional[discord.Role] = None, role_id: Optional[str] = None):
    # Check if the user has Manage Roles or Administrator permission
    if not (interaction.user.guild_permissions.manage_roles or interaction.user.guild_permissions.administrator):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return

    # Determine the role to delete
    if role is None and role_id is None:
        await interaction.response.send_message("❌ You must provide either a role or a role ID.", ephemeral=True)
        return

    if role is None:
        role = discord.utils.get(interaction.guild.roles, id=int(role_id))

    if role is None:
        await interaction.response.send_message("❌ No role found with the provided ID.", ephemeral=True)
        return

    # Check if the role is under the bot's role
    if role.position >= interaction.guild.me.top_role.position:
        await interaction.response.send_message("❌ I cannot delete a role that is equal to or above my role in the hierarchy.", ephemeral=True)
        return

    await role.delete()
    await interaction.response.send_message(f"✅ Deleted the role **{role.name}**.", ephemeral=True)

# /rename-role command
@bot.tree.command(name="rename-role", description="Rename a role")
@app_commands.describe(role="Select the role or enter the role ID", new_name="New name for the role")
async def rename_role(interaction: discord.Interaction, role: Optional[discord.Role] = None, role_id: Optional[str] = None, new_name: Optional[str] = None):
    # Check if the user has Manage Roles or Administrator permission
    if not (interaction.user.guild_permissions.manage_roles or interaction.user.guild_permissions.administrator):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return

    # Determine the role to rename
    if role is None and role_id is None:
        await interaction.response.send_message("❌ You must provide either a role or a role ID.", ephemeral=True)
        return

    if role is None:
        try:
            role = discord.utils.get(interaction.guild.roles, id=int(role_id))
        except ValueError:
            await interaction.response.send_message("❌ Invalid role ID provided.", ephemeral=True)
            return

    if role is None:
        await interaction.response.send_message("❌ No role found with the provided ID.", ephemeral=True)
        return

    # Check if new_name is valid
    if not new_name:
        await interaction.response.send_message("❌ You must provide a new name for the role.", ephemeral=True)
        return

    if len(new_name) > 100:
        await interaction.response.send_message("❌ The new role name is too long. It must be 100 characters or less.", ephemeral=True)
        return

    # Check if the role is under the bot's top role
    if role.position >= interaction.guild.me.top_role.position:
        await interaction.response.send_message("❌ I cannot rename a role that is equal to or above my role in the hierarchy.", ephemeral=True)
        return

    # Rename the role
    await role.edit(name=new_name)
    await interaction.response.send_message(f"✅ Renamed the role to **{new_name}**.", ephemeral=True)

# /role-everyone command
@bot.tree.command(name="role-everyone", description="Assign a role to all members (humans and bots) in the server")
@app_commands.describe(role="Select the role to assign to everyone")
async def role_everyone(interaction: discord.Interaction, role: discord.Role):
    # Check if the user has Manage Roles or Administrator permission
    if not (interaction.user.guild_permissions.manage_roles or interaction.user.guild_permissions.administrator):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return

    members = interaction.guild.members
    total_members = len(members)
    estimated_time = (total_members * 1.1) // 60  # Approximate ETA (1.1 seconds per member)

    await interaction.response.send_message(f"⏳ Starting to assign the role **{role.name}** to {total_members} members. Estimated time: {estimated_time} minutes.", ephemeral=True)

    async def assign_role(member):
        try:
            await member.add_roles(role)
        except discord.Forbidden:
            pass  # Skip members where the bot lacks permission
        await asyncio.sleep(1.1)  # Delay to prevent rate limiting

    @tasks.loop(count=total_members)
    async def assign_roles():
        for member in members:
            await assign_role(member)
    
    assign_roles.start()

    await assign_roles.wait()  # Wait for the task to finish

    # Send the completion message in the same channel where the command was executed, mentioning the user
    await interaction.channel.send(f"✅ {interaction.user.mention}, finished assigning the role **{role.name}** to all members.")

#/role-all command choice
class MemberType(app_commands.Choice[str]):
    HUMANS = "humans"
    BOTS = "bots"

#/role-all command
@bot.tree.command(name="role-all", description="Assign a role to all humans or bots in the server")
@app_commands.describe(
    member_type="Select whether to assign the role to humans or bots",
    role="Select the role to assign"
)
@app_commands.choices(member_type=[
    app_commands.Choice(name="Humans", value=MemberType.HUMANS),
    app_commands.Choice(name="Bots", value=MemberType.BOTS)
])
async def role_all(interaction: discord.Interaction, member_type: app_commands.Choice[str], role: discord.Role):
    # Check if the user has Manage Roles or Administrator permission
    if not (interaction.user.guild_permissions.manage_roles or interaction.user.guild_permissions.administrator):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return

    if member_type.value == MemberType.HUMANS:
        members = [member for member in interaction.guild.members if not member.bot]
    else:
        members = [member for member in interaction.guild.members if member.bot]

    total_members = len(members)
    estimated_time = (total_members * 1.1) // 60  # Approximate ETA (1.1 seconds per member)

    await interaction.response.send_message(f"⏳ Starting to assign the role **{role.name}** to {total_members} {member_type.value}. Estimated time: {estimated_time} minutes.", ephemeral=True)

    async def assign_role(member):
        try:
            await member.add_roles(role)
        except discord.Forbidden:
            pass  # Skip members where the bot lacks permission
        await asyncio.sleep(1.1)  # Delay to prevent rate limiting

    @tasks.loop(count=total_members)
    async def assign_roles():
        for member in members:
            await assign_role(member)
    
    assign_roles.start()

    await assign_roles.wait()  # Wait for the task to finish

    # Send the completion message in the same channel where the command was executed, mentioning the user
    await interaction.channel.send(f"✅ {interaction.user.mention}, finished assigning the role **{role.name}** to all {member_type.value}.")

# /remove-role-all command choice
class MemberType(app_commands.Choice[str]):
    HUMANS = "humans"
    BOTS = "bots"

# /remove-role-all command
@bot.tree.command(name="remove-role-all", description="Remove a role from all humans or bots in the server")
@app_commands.describe(
    member_type="Select whether to remove the role from humans or bots",
    role="Select the role to remove"
)
@app_commands.choices(member_type=[
    app_commands.Choice(name="Humans", value=MemberType.HUMANS),
    app_commands.Choice(name="Bots", value=MemberType.BOTS)
])
async def remove_role_all(interaction: discord.Interaction, member_type: app_commands.Choice[str], role: discord.Role):
    # Check if the user has Manage Roles or Administrator permission
    if not (interaction.user.guild_permissions.manage_roles or interaction.user.guild_permissions.administrator):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return

    if member_type.value == MemberType.HUMANS:
        members = [member for member in interaction.guild.members if not member.bot]
    else:
        members = [member for member in interaction.guild.members if member.bot]

    total_members = len(members)
    estimated_time = (total_members * 1.1) // 60  # Approximate ETA (1.1 seconds per member)

    await interaction.response.send_message(f"⏳ Starting to remove the role **{role.name}** from {total_members} {member_type.value}. Estimated time: {estimated_time} minutes.", ephemeral=True)

    async def remove_role(member):
        try:
            await member.remove_roles(role)
        except discord.Forbidden:
            pass  # Skip members where the bot lacks permission
        await asyncio.sleep(1.1)  # Delay to prevent rate limiting

    @tasks.loop(count=total_members)
    async def remove_roles():
        for member in members:
            await remove_role(member)
    
    remove_roles.start()

    await remove_roles.wait()  # Wait for the task to finish

    # Send the completion message in the same channel where the command was executed, mentioning the user
    await interaction.channel.send(f"✅ {interaction.user.mention}, finished removing the role **{role.name}** from all {member_type.value}.")

# /user-info command
@bot.tree.command(name="user-info", description="Get information about a member")
@app_commands.describe(user="The member you want information about")
async def user_info(interaction: discord.Interaction, user: discord.Member):
    member = user or interaction.user  # Default to the command invoker if no member is specified

    embed = discord.Embed(title=f"User Info - {member}", color=0x0000FF)

    embed.set_thumbnail(url=member.avatar.url)
    embed.add_field(name="ID", value=member.id, inline=False)
    embed.add_field(name="Name", value=str(member), inline=False)
    embed.add_field(name="Nickname", value=member.nick if member.nick else "None", inline=False)
    
    account_created_timestamp = int(member.created_at.replace(tzinfo=timezone.utc).timestamp())
    joined_server_timestamp = int(member.joined_at.replace(tzinfo=timezone.utc).timestamp())
    
    embed.add_field(name="Account Created", value=f"<t:{account_created_timestamp}:R>", inline=False)
    embed.add_field(name="Joined Server", value=f"<t:{joined_server_timestamp}:R>", inline=False)

    await interaction.response.send_message(embed=embed)

# /server-info command
@bot.tree.command(name="server-info", description="Get information about the server")
async def serverinfo(interaction):
    guild = interaction.guild
    member_count = guild.member_count
    bot_count = sum(1 for member in guild.members if member.bot)
    human_count = member_count - bot_count

    # Count custom emojis and stickers
    emoji_count = len(guild.emojis)
    sticker_count = len(guild.stickers)

    embed = discord.Embed(title="Server Information", color=0x0000FF)
    if guild.icon:  # Check if guild has an icon
        embed.set_thumbnail(url=guild.icon.url)
    if guild.owner:  # Check if guild has an owner
        embed.add_field(name="Owner", value=guild.owner.name, inline=False)
    else:
        embed.add_field(name="Owner", value="None", inline=False)
    embed.add_field(name="Server Created", value=guild.created_at.strftime("%m/%d/%Y"), inline=False)
    embed.add_field(name="Total Roles", value=len(guild.roles), inline=False)
    embed.add_field(name="Members", value=f"{member_count} members\n{bot_count} bots, {human_count} humans", inline=False)
    embed.add_field(name="Total Channels", value=f"{len(guild.channels)} total channels:\n{len(guild.categories)} categories\n{len(guild.text_channels)} text, {len(guild.voice_channels)} voice", inline=False)
    embed.add_field(name="Custom Emojis", value=emoji_count, inline=False)
    embed.add_field(name="Custom Stickers", value=sticker_count, inline=False)
    embed.add_field(name="Boost Level", value=guild.premium_tier, inline=False)
    embed.add_field(name="Number of Boosts", value=guild.premium_subscription_count, inline=False)
    embed.set_footer(text=f"Server Name: {guild.name}\nServerID: {guild.id}")
    await interaction.response.send_message(embed=embed)

# /embed-create command
@bot.tree.command(name="embed-create", description="Create a custom embed")
@app_commands.describe(
    title="Title of the embed", 
    description="Description of the embed", 
    color="Color of the embed (Plz type the color hex code like #FFC0CB)", 
    channel="Channel to send the embed", 
    thumbnail="Thumbnail URL (optional)", 
    image="Image URL (optional)",
    button1_name="Button 1 Name (optional)", button1_link="Button 1 URL (optional)",
    button2_name="Button 2 Name (optional)", button2_link="Button 2 URL (optional)",
    button3_name="Button 3 Name (optional)", button3_link="Button 3 URL (optional)",
    button4_name="Button 4 Name (optional)", button4_link="Button 4 URL (optional)",
    button5_name="Button 5 Name (optional)", button5_link="Button 5 URL (optional)"
)
async def embed_create(
    interaction: discord.Interaction, 
    title: str, 
    description: str, 
    color: str, 
    channel: discord.TextChannel = None, 
    thumbnail: str = None, 
    image: str = None,
    button1_name: str = None, button1_link: str = None,
    button2_name: str = None, button2_link: str = None,
    button3_name: str = None, button3_link: str = None,
    button4_name: str = None, button4_link: str = None,
    button5_name: str = None, button5_link: str = None
):
    # Check if the user has the 'Manage Messages' permission
    if not (interaction.user.guild_permissions.manage_messages or interaction.user.id in [667372536400445441]):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return

    # Convert color code to a discord.Color object
    try:
        embed_color = discord.Color(int(color.replace("#", ""), 16))
    except ValueError:
        await interaction.response.send_message("Invalid color code. Please use a valid hex color.", ephemeral=True)
        return

    # Create the embed
    embed = discord.Embed(title=title, description=description, color=embed_color)
    embed.set_footer(text=f"Powered by {bot.user}")

    # Add thumbnail if a valid URL is provided
    if thumbnail:
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(thumbnail) as response:
                    if response.status == 200 and response.headers['Content-Type'].startswith('image/'):
                        embed.set_thumbnail(url=thumbnail)
                    else:
                        await interaction.response.send_message("Invalid thumbnail URL or the link is not an image.", ephemeral=True)
                        return
            except aiohttp.ClientError:
                await interaction.response.send_message("There was an error fetching the thumbnail URL. Please try again.", ephemeral=True)
                return

    # Add image if a valid URL is provided
    if image:
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(image) as response:
                    if response.status == 200 and response.headers['Content-Type'].startswith('image/'):
                        embed.set_image(url=image)
                    else:
                        await interaction.response.send_message("Invalid image URL or the link is not an image.", ephemeral=True)
                        return
            except aiohttp.ClientError:
                await interaction.response.send_message("There was an error fetching the image URL. Please try again.", ephemeral=True)
                return

    # Add buttons if names and links are provided
    buttons = []
    for i in range(1, 6):
        button_name = locals().get(f'button{i}_name')
        button_link = locals().get(f'button{i}_link')
        if button_name and button_link:
            buttons.append(discord.ui.Button(label=button_name, url=button_link))

        if channel == None:
            await ctx.send(embed=embed)
        else:
            message = await channel.send(embed=embed)

    # Add buttons to the message
    if buttons:
        view = discord.ui.View()
        for button in buttons:
            view.add_item(button)
        await message.edit(view=view)

    # Notify the user of success
    await interaction.response.send_message(f"✅ Successfully sent the embed to {channel.mention}.", ephemeral=True)

# Run the bot
bot.run(TOKEN)