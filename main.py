"""
BOT CREATED BY VNCET
PLEASE HELP ME IMPROVE IT
SORRY FOR THE MESS

"""

from libs.utilities import *
from libs.generate import *
import discord
from discord import app_commands
from discord.ext import commands
import requests
import math
from datetime import datetime
import asyncio
import re
import firebase_admin
from firebase_admin import credentials, db
import time
from dotenv import load_dotenv
import os


load_dotenv() # Loading environment variables

# -- Global variables
TOKEN = os.getenv("USER_TOKEN") # Your Discord user token

QUERIES = [
    'scammer',
    'trust',
    'fraud',
    'scam',
    'cheat',
    'steal',
    'liar',
    'griefer'
]

ADMIN = [1043429252789452801] # UserIds of admins, they don't have cooldown

server_activity = 0
cooldowns = {}


# -- Database setup
cred = credentials.Certificate("credentials.json") # Service accounts key found in firebase settings
firebase_admin.initialize_app(cred, {"databaseURL": os.getenv("DATABASE_URL")}) # Google firebase realtime database url
ref = db.reference("/")



# -- Bot setup
bot = commands.Bot(command_prefix='!', intents=discord.Intents.all()) # Turn on all intents when configuring bot

@bot.event
async def on_ready(): # Syncing commands
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)



# -- Functions
def getMessages(guild_id, search, offset, after=None): # Will search messages using user token
    headers = {'authorization': TOKEN}
    after_filter = ''
    if after:
        after_snowflake = timestampToSnowflake(int(after) * 1000)
        after_filter = f'min_id={after_snowflake}&'
    return requests.get(f'https://discord.com/api/v9/guilds/{guild_id}/messages/search?{after_filter}content={search}&offset={offset}', headers=headers).json()


def getReplies(guild_id, mentions, search, offset, after=None): # Will search reply messages using user token
    headers = {'authorization': TOKEN}
    after_filter = ''
    if after: # If a message has been cached it will search for messages after that date
        after_snowflake = timestampToSnowflake(int(after) * 1000)
        after_filter = f'min_id={after_snowflake}&'
    return requests.get(f'https://discord.com/api/v9/guilds/{guild_id}/messages/search?{after_filter}mentions={mentions}&content={search}&offset={offset}', headers=headers).json()


def findEarlierCache(player_cache, query, reply_to): # Looking for latest cache message
    reply_prefix = 'mention' if reply_to else 'no_mention'

    if not reply_prefix in player_cache or query not in player_cache[reply_prefix]:
        return None
    
    if player_cache[reply_prefix][query] != {}:
        sorted_caches = sorted(player_cache[reply_prefix][query].keys(), key=lambda x: int(x), reverse=True) # Sorting by epoch
        latest_date = sorted_caches[0]
        return latest_date


def getCaches(player_cache, query, all_messages, reply_to): # Getting cache
    reply_prefix = 'mention' if reply_to else 'no_mention'

    if reply_prefix not in player_cache or query not in player_cache[reply_prefix]:
        return all_messages
    
    if player_cache[reply_prefix][query] != {}:
        for x in player_cache[reply_prefix][query]:
            all_messages.append(player_cache[reply_prefix][query][x])

    return all_messages


def findFalsePositives(messages_list): # Filtering false accusations, spam
    time_threshold = 900
    temp_msg_list = sorted(messages_list, key=lambda x: x['epoch'], reverse=True)

    clusters = []
    current_cluster = []
    previous_msg_time = None

    filtered_temp_msg_list = []
    unique_messages = {}

    for msg in temp_msg_list:
        if int(msg['channel_id']) == 1303096047698182164: # Bot's forum post, will automatically ignore all messages here
            continue

        msg_key = (msg['content'], msg['author'])
        msg_time = datetime.fromtimestamp(msg['epoch'])

        if msg_key in unique_messages:
            last_time = unique_messages[msg_key]
            time_diff = (msg_time - last_time).total_seconds()

            if time_diff < 3600:
                continue

        unique_messages[msg_key] = msg_time
        filtered_temp_msg_list.append(msg)

    for msg in filtered_temp_msg_list: # Finding message clusters
        msg_time = datetime.fromtimestamp(msg['epoch'])

        if previous_msg_time is not None:
            time_diff = (previous_msg_time - msg_time).total_seconds()

            if time_diff > time_threshold:
                if current_cluster:
                    if len(current_cluster) > 5:
                        clusters.append(current_cluster)
                current_cluster = []

        current_cluster.append(msg)
        previous_msg_time = msg_time

    if current_cluster:
        if len(current_cluster) > 5:
            clusters.append(current_cluster)

    fake_accusations = []
    for cluster in clusters:
        if len(cluster) >= 4: # If there are more than 4 messages in cluster, messages are fake
            for msg in cluster:
                fake_accusations.append(msg)

    return [item for item in filtered_temp_msg_list if item not in fake_accusations]


async def FindMessages(batch_updates, messages_list, player_cache, username, guild_id, reply_to, player_id=None): # Finding messages related to username
    username_key = stringToNumbers(username)

    for query in QUERIES: # Going through all queries
        latest_date = findEarlierCache(player_cache, query, reply_to) # Finding latest message date thats cached
        all_messages = []
        while True:
            offset = 0
            if reply_to:
                page_object = getReplies(guild_id, player_id, query, offset, after=latest_date) # Searching for replies
            else:
                search = f'{username}%20{query}'
                page_object = getMessages(guild_id, search, offset, after=latest_date) # Searching for messages
            if 'total_results' in page_object:
                messages_amount = page_object['total_results']
                if messages_amount > 0:
                    all_messages.append(page_object)

                page_object = page_object
                break
            elif 'retry_after' in page_object: # Discord rate limited us, retrying
                await asyncio.sleep(page_object['retry_after'])
            else:
                print(page_object)
                break

        all_messages = getCaches(player_cache, query, all_messages, reply_to) # Adding cached messages to list

        pages_amount = int(math.ceil(messages_amount / 25)) # Calculating how many requests are necessary
        for _ in range(pages_amount - 1):
            offset += 25
            while True:
                if reply_to:
                    page_object = getReplies(guild_id, player_id, query, offset, after=latest_date)
                else:
                    search = f'{username}%20{query}'
                    page_object = getMessages(guild_id, search, offset, after=latest_date)
                
                if 'retry_after' not in page_object:  
                    all_messages.append(page_object)
                    break
                else:
                    await asyncio.sleep(page_object['retry_after'])

        seen_msg_ids = set() # No duplicate ids
        for page_object in all_messages:
            if 'messages' not in page_object: # If page is empty, continue
                continue

            latest_date = sorted(page_object['messages'], key=lambda x: int(datetime.fromisoformat(x[0]['timestamp']).timestamp()), reverse=True)[0] # Sort list to find latest date
            for msg in page_object['messages']:
                if msg[0]['author']['username'] == 'Shatty': # Ignoring messages from bot
                    continue

                reply_prefix = f"[Reply to {username}] " if reply_to else ""
                message = reply_prefix + msg[0]['content'].replace('\_', '_')
    
                msg_id = msg[0]['id']
                if msg_id in seen_msg_ids: # Continue if msg_id isnt unique
                    continue

                seen_msg_ids.add(msg_id)

                dt = datetime.fromisoformat(msg[0]['timestamp'])
                epoch = int(dt.timestamp())

                msg_data = {'content': message, 'author': msg[0]['author']['username'], 'epoch': epoch, 'id': msg_id, 'channel_id': msg[0]['channel_id']}

                messages_list.append(msg_data)

            key_epoch = int(datetime.fromisoformat(latest_date[0]['timestamp']).timestamp())
            if reply_to: # Adding to cache
                batch_updates[f'player_cache/{username_key}/mention/{query}/{key_epoch}'] = {'messages': page_object['messages']}
            else:
                batch_updates[f'player_cache/{username_key}/no_mention/{query}/{key_epoch}'] = {'messages': page_object['messages']}

    return messages_list, batch_updates


async def searchMessages(username, guild_id, interaction, player_id): # Full scanning process
    cache = db.reference('message_cache/').get() or {} # Getting caches from database
    
    full_player_cache = db.reference(f'player_cache/').get() or {}

    accusers_cache = db.reference(f'accusers_cache/').get() or {}

    username_key = stringToNumbers(username)

    player_cache = full_player_cache[username_key] if username_key in full_player_cache else {} # Finding player specific cache in response

    estimate = int(player_cache['innocence']) if 'innocence' in player_cache else None

    batch_updates = {} # This will define all changes we want applied to the database

    messages_list = []
    if player_id: # If we have a player id, we can find messages connected to it
        messages_list, batch_updates = await FindMessages(batch_updates, messages_list, player_cache, username, guild_id, reply_to=True, player_id=player_id)

    await interaction.edit_original_response(embed=newEmbed(username, loadingBar(4), value="Loading more...", estimate=estimate)) # Updating loading bar

    messages_list, batch_updates = await FindMessages(batch_updates, messages_list, player_cache, username, guild_id, reply_to=False) # Finding messsages that only require username

    await interaction.edit_original_response(embed=newEmbed(username, loadingBar(6), value="Collecting evidence...", estimate=estimate))

    messages_list_len = len(messages_list) # Getting length now, for a full idea of how many messages were processed

    messages_list = findFalsePositives(messages_list) # Remove abrupt chains of accusations 

    players = {}
    for msg in messages_list: # Getting the author of the message, and trying to find any other players
        message = msg['content']
        if ':' in message and not ' :' in message: # The ingame chat's messages start with <author>: <message>, trying to extract author
            player = message.split(':')[0].strip()
            message = message.split(':')[1].strip()
        else: # No author found means the message came directly from discord
            player = msg['author'].strip()

        if player.lower() not in players: # Defining list if it doesn't already exist
            players[player.lower()] = []

        def replace(match): # Quick function to find match
            temp_user_id = match.group(1)

            if temp_user_id == player_id:
                return f"@({username})"
            else:
                return f"@(unknown user)"

        message = re.sub(r"<@(\d+)>", replace, message) # Replacing <@userid> with username or unknown user

        msg_data = {'content': message, 'epoch': msg['epoch'], 'id': msg['id']}

        # if msg_data not in players[player.lower()]: # Removing duplicates
        players[player.lower()].append(msg_data)

    await interaction.edit_original_response(embed=newEmbed(username, loadingBar(7), value="Counting evidence...", estimate=estimate))

    for player in list(players.copy().keys()): # Getting rid of duplicate players
        players_temp = list(players.copy().keys()) # Converting the keys of players to a list

        if player not in players_temp:
            continue

        players_temp.remove(player)

        if not players_temp:
            continue

        closest_string, closest_distance = findClosestPlayer(player, players_temp) # Similar author names will be turned into one author
        if closest_distance <= 2:
            if characterDifference(player, closest_string) < len(player) / 2: # If difference in characters is less than half of the name
                for msg in players[closest_string]:
                    players[player].append(msg)
                    
                del players[closest_string]

    await interaction.edit_original_response(embed=newEmbed(username, loadingBar(8), value="Reading...", estimate=estimate))

    total_players = len(players.keys()) # Getting amount of authors/players

    for player, messages in players.items(): # Sorting player messages by date and time
        players[player] = sorted(messages, key=lambda x: x['epoch'], reverse=True)

    accusations, cache, batch_updates, blacklist_compensation = await getScammer(players, cache, full_player_cache, batch_updates, username, accusers_cache) # Get guilty and innocent counts from messages

    await interaction.edit_original_response(embed=newEmbed(username, loadingBar(9), value="Finalizing...", estimate=estimate))

    guilty = 0
    innocent = blacklist_compensation
    for item in accusations: # Change weight of accusation based on how reliable the source is
        if item['conclusion'] == 'guilty':
            guilty += 1 * item['rel']
        elif item['conclusion'] == 'innocent':
            innocent += 1 * item['rel']

    if [item['conclusion'] for item in accusations if item['conclusion'] == 'confession']:
        guilty *= 2

    innocent_prob, guilty_prob = innocenceProb(innocent, guilty) # Get innocence percentage

    batch_updates[f'player_cache/{username_key}/innocence'] = round(innocent_prob, 2)
    if batch_updates != {}:
        db.reference('/').update(batch_updates) # Applying changes to database in one request

    return round(innocent_prob, 2), total_players, messages_list_len


def newEmbed(username, loading_status, color=discord.Color.blue(), no_notice=False, value=None, estimate=None):
    embed = discord.Embed(title=discord.utils.escape_markdown(username) + " :mag_right:", color=color)

    notice = ''
    if server_activity > 1 and not no_notice: # If there are at least 2 commands running, add server is busy warning
        notice += f"\n(server is busy: {server_activity} commands)"
        
    if estimate and not no_notice: # Show estimate, if available
        if server_activity > 1:
            notice += f"(est. {estimate}%)"
        else:
            notice += f"\n(est. {estimate}%)"

    embed.set_footer(text=loading_status + notice)

    if value:
        embed.add_field(name="", value=value, inline=False)

    return embed # Returning built embed


async def tempEmbed(title, footer, field, interaction, edit_only=False): # Command to quickly setup message that dissapears after 1 second
    embed = discord.Embed(title=title, color=discord.Color.red())

    if footer:
        embed.set_footer(text=footer)
    embed.add_field(name="", value=field, inline=False)

    if not edit_only:
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        await interaction.edit_original_response(embed=embed)

    await asyncio.sleep(2)
    return await interaction.delete_original_response()


@app_commands.allowed_installs(guilds=True, users=True) # Allow command to be used when user installed
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@bot.tree.command(name="scan", description="Check if user is a scammer")
@app_commands.describe(discord_user="Discord user", username="User's most used name", visible="Make response visible to others")
async def scanCommand(interaction: discord.Interaction, discord_user: discord.User=None, username: str=None, visible: bool=None):
    global server_activity, cooldowns

    if interaction.user.id not in ADMIN and visible == None:
        visible = True
    elif visible == None:
        visible = False

    visible = not visible

    await interaction.response.defer(ephemeral=visible) # Telling Discord we're processing the command

    epoch_now = int(time.time())
    if str(interaction.user.id) in cooldowns and interaction.user.id not in ADMIN:
        difference = epoch_now - cooldowns[str(interaction.user.id)]
        if difference < 60:
            return await tempEmbed(title='ERROR', footer=None, field=f'Cooldown! {60 - difference} seconds left.', interaction=interaction)
    
    cooldowns[str(interaction.user.id)] = epoch_now
    
    if not username and not discord_user: # If no arguments set, sending temporary error message
        return await tempEmbed(title='ERROR', footer=None, field='No player specified.\nDeleting message...', interaction=interaction)

    discord_ids = db.reference(f'discord_cache/').get() or {}

    player_id = discord_user.id if discord_user else None # Setting player_id if discord_user is defined
    username = discord_user.display_name if not username else username # Setting username

    if username and not player_id: # Getting userid from cache
        if username.lower() in discord_ids:
            player_id = discord_ids[username.lower()]
    elif username.lower() not in discord_ids:
        db.reference(f'discord_cache/{username.lower()}').set(discord_user.id)

    print(f"{interaction.user.name} used /scan {username}")
    server_activity += 1

    await interaction.edit_original_response(embed=newEmbed(username, loadingBar(1), value="Loading messages...")) # Starting loading bar

    try: # Try to search messages
        innocence_prob, total_players, total_messages = await searchMessages(username=username.lower(), guild_id='219863747248914433', interaction=interaction, player_id=player_id)
    except Exception: # Catch failed attempts/errors
        server_activity -= 1 # Not working on command anymore, so removing from activity
        return await tempEmbed(title='ERROR', footer=None, field='Deleting message...', edit_only=True, interaction=interaction)

    color = discord.Color.green() if innocence_prob >= 50 or total_players <= 2 else discord.Color.red() # Setting color of embed (red for scam, green for no scam)
    
    embed = newEmbed(username, f'scanned {total_messages} messages from {total_players} different players', color=color, no_notice=True) # Getting final embed

    server_activity -= 1 # Got the results, now removing from command acitivty

    if total_players <= 2:
        embed.add_field(name="Result", value=f"Not enough information.", inline=False)
        return await interaction.edit_original_response(embed=embed)
    
    embed.add_field(name="Result", value=f"This player is probably {'not ' if innocence_prob >= 50 else ''}a scammer.", inline=False)

    embed.add_field(name="", value=f"``Innocence probability: {innocence_prob}%``", inline=False)
    await interaction.edit_original_response(embed=embed) # Editing original message



# -- Start
if __name__ == "__main__":
    bot.run(os.getenv("BOT_TOKEN")) # Start bot
