'''Main file for the mapcore discord faceit bot'''

import logging
#from logging.handlers import RotatingFileHandler
#from logging import handlers
import asyncio
from datetime import datetime
import sys
import functools
import typing  # For typehinting
#import requests
#import json
from discord.ext import commands, tasks

import discord
import pytz

import mapcore_functions as mapcorefunctions
from ongoing_notifier import OngoingNotifier
from map_fetcher import map_fetcher
import config
from webhook import mapcore_bot


import paginator

#get the bot setup object
bot_setup = mapcorefunctions.setup_processor(sys.argv)


#setup the logger
logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("debug2.log"),
        logging.StreamHandler()
    ]
)
logger  = logging.getLogger("")

logger.error('Started')

logger.error("Running version %s", bot_setup["version"])

intents = discord.Intents.default()
intents.message_content = True

# Change only the no_category default string
help_command = commands.DefaultHelpCommand(
    no_category='Commands'
)

#setup the base discord bot
bot = commands.Bot(intents=intents, command_prefix="!", help_command=help_command)

bot.queue_count_dict = mapcorefunctions.build_input_dict()
bot.map_fetcher = map_fetcher("*", logger)
bot.cest_timezone = pytz.timezone('Europe/Berlin')

bot.notifier_custom = OngoingNotifier(bot, bot.map_fetcher, logger)
bot.on_going_messages = {}
bot.webhooker = mapcore_bot()
bot.webhooker.start()
bot.timers = {}

if bot_setup["version"] == "main":
    bot.map_fetcher.build_map_list()
    print("db backfilled")


@bot.event
async def on_ready():
    '''generic function called when bot is logged in, gets us ready'''
    print(f'{bot.user} succesfully logged in!')

    # find all of the channels in the connected servers call CHANNEL_NAME that we auto post to
    # channels_to_post = []
    channels = []
    for server in bot.guilds:
        for channel in server.channels:
            if channel.name == config.CHANNEL_NAME:
                # channels_to_post.append(channel.id)
                temp = bot.get_channel(channel.id)
                channels.append(temp)


    bot.channels = channels
    game_watcher.start()
    queue_watcher.start()


@bot.command(aliases=['NAQ', 'naqueue', 'NAQueue', 'NAQUEUE', 'na', 'NA'])
async def naq(ctx, *arg):
    '''Returns status of NA mapcore hub queue. Also works with !NAQ, !NA, !na''' 
    
    message_string = f'Players in NA Queue: {bot.queue_count_dict["NA"]["players"]}\n'
    await ctx.send(message_string)


@bot.command(aliases=['EUQ', 'euqueue', 'EUQueue', 'EUQUEUE', 'EU', 'eu'])
async def euq(ctx, *arg):
    '''Returns status of EU mapcore hub queue. Also works with !EUQ, !EU, !eu'''

    message_string = f'Players in EU Queue: {bot.queue_count_dict["EU"]["players"]}\n'
    await ctx.send(message_string)


@bot.command(aliases=['Q', 'queue', 'Queue', 'QUEUE'])
async def q(ctx, *arg):
    '''Returns status of all hub queues, also response to !Q, !queue, !QUEUE'''
    message_string = ""

    for hub_name, data in bot.queue_count_dict.items():
        message_string = message_string + f'Players in {hub_name} Queue: {data["players"]}\n'

    await ctx.send(message_string)

@bot.command()
async def matchcount(ctx, *arg):
    '''Command to show total number of games per map in database'''

    #embeds = [discord.Embed(title="First embed")]
    try:
        games_dict = bot.map_fetcher.db.print_all("contest")

        # convert list of games into dict of maps and number of games for that map
        all_maps = [d['map_name'] for d in games_dict.values()]

        maps_counter = {}
        maps_list = []

        for map_key in all_maps:
            if map_key not in maps_counter.keys():
                map_name = map_key.replace("contest ", "")
                count_of_map_games = len([i for i in all_maps if i == map_key])
                maps_counter[map_key] = count_of_map_games
                maps_list.append(f"{map_name.capitalize()} has {count_of_map_games} games\n")
        sorted_map_list = sorted(maps_list)
        chunks_of_maps = mapcorefunctions.divide_chunks(sorted_map_list, 15)

        embeds = []
        for chunk in chunks_of_maps:
            string_out = ""
            for item in chunk:
                string_out = string_out + item

            embeds.append(discord.Embed(title="", description=string_out))
        
        logger.error(embeds)
        logger.error(len(embeds))

        await paginator.Simple().start(ctx, pages=embeds)

    except Exception as e:
        error_string = f'Error in new_match_count, {e}'
        logger.error(error_string, exc_info=True)  

@bot.command()
async def matchcountall(ctx, *arg):
    '''Command to show total number of games per map in database'''

    #embeds = [discord.Embed(title="First embed")]
    try:
        games_dict = bot.map_fetcher.db.print_all("*")

        # convert list of games into dict of maps and number of games for that map
        all_maps = [d['map_name'] for d in games_dict.values()]

        maps_counter = {}
        maps_list = []

        for map_key in all_maps:
            if map_key not in maps_counter.keys():
                map_name = map_key.replace("contest ", "")
                count_of_map_games = len([i for i in all_maps if i == map_key])
                maps_counter[map_key] = count_of_map_games
                maps_list.append(f"{map_name.capitalize()} has {count_of_map_games} games\n")
        sorted_map_list = sorted(maps_list)
        chunks_of_maps = mapcorefunctions.divide_chunks(sorted_map_list, 15)

        embeds = []
        for chunk in chunks_of_maps:
            string_out = ""
            for item in chunk:
                string_out = string_out + item

            embeds.append(discord.Embed(title="", description=string_out))
        
        logger.error(embeds)
        logger.error(len(embeds))

        await paginator.Simple().start(ctx, pages=embeds)

    except Exception as e:
        error_string = f'Error in new_match_count, {e}'
        logger.error(error_string, exc_info=True) 

@bot.command(aliases=["dbdata"])
async def dbdescribe(ctx, *arg):
    '''Command to show total number of games per map in database'''

    # get all games from db and count
    try:
        games_dict = bot.map_fetcher.db.print_all()
        number_of_games = len(games_dict)
        return_message1 = f"There are now {number_of_games} matches in the database\n"

        # convert list of games into dict of maps and number of games for that map
        all_maps = [d['map_name'] for d in games_dict.values()]

        maps_counter = {}

        for map_key in all_maps:
            if map_key not in maps_counter.keys():
                count_of_map_games = len([i for i in all_maps if i == map_key])
                maps_counter[map_key] = count_of_map_games
                #return_message = return_message + f"{map_key.capitalize()} has {count_of_map_games} games\n"

        await ctx.send(return_message1)
    except Exception as e:
        error_string = f'Error in dbdescribe, {e}'
        logger.error(error_string, exc_info=True)

@bot.command(aliases=["devbackfiller"])
async def backfiller(ctx, number_of_games=20, offset=0):
    '''Command to back fill last 20 games into database, does hang the bot so careful!'''
    try:
        await ctx.send(f"Back filling {number_of_games} for all hubs")
        # Pass the args and kwargs here
        r = await run_backfilling(backfilling_func, number_of_games, offset)
        #print(r)  # -> "some stuff"
        games_dict = bot.map_fetcher.db.print_all()
        number_of_games = len(games_dict)
        return_message = f"There are now {number_of_games} matches in the database\n"
        await ctx.send(return_message)
    except Exception as e:
        error_string = f'Error in backfiller, {e}'
        logger.error(error_string, exc_info=True)

async def run_backfilling(backfilling_func: typing.Callable, *args, **kwargs):
    '''function to try and stop back filler halting the heartbeat'''
    # `run_in_executor` doesn't support kwargs, `functools.partial` does
    func = functools.partial(backfilling_func, *args, **kwargs)
    return await bot.loop.run_in_executor(None, func)

def backfilling_func(number_of_games, offset):
    """A very blocking function"""
    bot.map_fetcher.backfiller(number_of_games, offset)
    return "some stuff"

@bot.command(aliases=['map', 'matches', 'maps'])
async def games(ctx, map_name: str, number_of_games=30, offset=0, *arg):
    '''Command to list games on map stored in the database with link to the match room.
        Format for command is:
        !games MAPNAME NUMBER_OF_GAMES OFFSET
        NUMBER_OF_GAMES and OFFSET are optional, without it will return the 15 most recent games
        example:
        !games mills 30 0
        will return the last 30 games on Mills (WIP) map'''
    try:
    # get all the games for map_name from db
        games_dict = bot.map_fetcher.db.print_all(map_name.lower())
        list_of_games = mapcorefunctions.process_games(games_dict)
        total_number_of_games = len(list_of_games)

        # make sure we arent trying to return more games than we have
        if  total_number_of_games < number_of_games:
            number_of_games == total_number_of_games

        # break into chunks of 15 games to stay within 2000 character limit
        list_of_games = list_of_games[offset:number_of_games + offset]
        chunks_of_games = mapcorefunctions.divide_chunks(list_of_games, 15)

        # message back as many chunks as we need
        embeds = []
        title_string = f"{map_name.capitalize()} - {total_number_of_games} saved in total"
        for chunk in chunks_of_games:
            return_chunk = "" # "# " + map_name.capitalize() + "\n"
            for message in chunk:
                return_chunk = return_chunk + message
            embeds.append(discord.Embed(title=title_string, description=return_chunk))

        await paginator.Simple().start(ctx, pages=embeds)
    except Exception as e:
        error_string = f'Error in games, {e}'
        logger.error(error_string, exc_info=True)


@bot.command()
async def recentgames(ctx, map_name: str, start_days=1, *arg):
    '''Command to get games from named map played in past x days \n
    "!recentgames coaline 1" will get games on coaline in the last day'''
    try:
    # initial message
        return_message = f"Going to get you the matches played on {map_name}, in the last {start_days} day(s)"
        await ctx.send(return_message)

        games_dict = bot.map_fetcher.db.table_dated_map(map_name, start_days)
        list_of_games = mapcorefunctions.process_games(games_dict)

        # break into chunks of 15 games to stay within 2000 character limit
        chunks_of_games = mapcorefunctions.divide_chunks(list_of_games, 15)

        # message back as many chunks as we need
        for chunk in chunks_of_games:
            return_chunk = "# " + map_name.capitalize() + "\n"
            for message in chunk:
                return_chunk = return_chunk + message

            await ctx.send(return_chunk)
    except Exception as e:
        error_string = f'Error in games, {e}'
        logger.error(error_string, exc_info=True)


@bot.command()
async def lastweek(ctx):
    '''Command to that returns a chart showing games per map for last 7 days'''
    games_data = bot.map_fetcher.db.last_week_matches()
    chart_file = mapcorefunctions.build_chart(games_data)
    image = discord.File(chart_file)
    await ctx.send(file=image)


@bot.command(aliases=['TODAY', 'Today'])
async def today(ctx):
    '''Command to that returns a chart showing games per map for last day'''
    games_data = bot.map_fetcher.db.chart_data_fetch('1')
    chart_file = mapcorefunctions.build_chart(games_data, "day")
    image = discord.File(chart_file)
    await ctx.send(file=image)


@bot.command(aliases=['Chart', 'CHART'])
async def chart(ctx, number_of_days=1):
    '''Command to that returns a chart showing games per map for x days, use !chart 2 for 2 days'''
    games_data = bot.map_fetcher.db.chart_data_fetch(number_of_days)
    title_string = f"{number_of_days} days"
    chart_file = mapcorefunctions.build_chart(games_data, title_string)
    image = discord.File(chart_file)
    await ctx.send(file=image)


async def friday_map_count(bot):
    '''function to post the last week map on a friday, triggered by ping'''
    # when called, make the channel chart
    games_data = bot.map_fetcher.db.last_week_matches()
    chart_file = mapcorefunctions.build_chart(games_data, 'week')

    # now find the friday channels
    channels_to_post_summary = []
    for server in bot.guilds:
        for channel in server.channels:
            # print(channel.name)
            if channel.name == config.FRIDAY_CHANNEL_NAME:
                channels_to_post_summary.append(channel.id)

    # setup the fridaychannels and post image
    channels_friday = []
    for channel in channels_to_post_summary:
        temp = bot.get_channel(channel)
        channels_friday.append(temp)
        image = discord.File(chart_file)
        await temp.send(file=image)

async def process_games_dict(bot, games_dict, pop_games_flag=False):

    processed_games = []

    for game_id, game in games_dict:

        embed_message = game.build_embedded_message()

        if len(game.discord_messages) == len(bot.channels):

            for message in game.discord_messages:
                await message.edit(embed=embed_message)

        else:
            for channel in bot.channels:
                new_message = await channel.send(embed=embed_message)
                game.discord_messages.append(new_message)

        processed_games.append(game_id)

    if pop_games_flag:
        for game_id in processed_games:    
            games_dict.pop(game_id)

    return games_dict

@tasks.loop(seconds=30)
async def game_watcher():
    '''function that runs every minute
    checks queue statuses, messages if less than '''
    
    '''processed_dict = process_games_dict(bot, bot.webhooker.ongoing_games)
    bot.webhooker.ongoing_games = processed_dict

    processed_dict = process_games_dict(bot, bot.webhooker.completed_games, True)
    bot.webhooker.completed_games = processed_dict
    
    processed_dict = process_games_dict(bot, bot.webhooker.cancelled_games, True)
    bot.webhooker.cancelled_games = processed_dict
    '''
    pop_games = []

    ongoing_games = bot.webhooker.ongoing_games
    for game_id, game in ongoing_games.items():

        embed_message = game.build_embedded_message()

        if len(game.discord_messages) == len(bot.channels):

            for message in game.discord_messages:
                await message.edit(embed=embed_message)

        else:
            for channel in bot.channels:
                new_message = await channel.send(embed=embed_message)
                bot.webhooker.ongoing_games[game_id].discord_messages.append(new_message)

        if game.cancelled or (game.finished and game.demoed):
            pop_games.append(game_id)
    #print(pop_games)
    logger.debug(f"popping from {ongoing_games}")
    #logger.error(bot.webhooker.ongoing_games)
    logger.debug(f"popping with {pop_games}")
    #logger.error(pop_games)
    for game_id in pop_games:    

        bot.webhooker.ongoing_games.pop(game_id)
    logger.debug(f"popping result {ongoing_games}")
    
        

    now_cest = datetime.now(bot.cest_timezone)
    if now_cest.weekday() == 4 and now_cest.hour == 18 and now_cest.minute == 0:
        await friday_map_count(bot)

@tasks.loop(seconds=60)
async def queue_watcher():

    # then we create a function that does what we need
    # note that this does not execute the blocking function,
    # it just wraps it into another function
    blocking_insert = lambda: mapcorefunctions.get_queue_counts(bot.queue_count_dict, logger)

    # we schedule this function to run on a thread,
    # and only come back here once that thread has completed
    bot.queue_count_dict = await asyncio.to_thread(blocking_insert)
    for queue_data in bot.queue_count_dict.values():

        if queue_data["test"] and (queue_data["timer"] == 2):  # or queue["timer"] % 10 == 0):
            for channel in bot.channels:
                await channel.send(queue_data["message"])

    bot_activity_string = mapcorefunctions.build_activity_string(bot.queue_count_dict)
    await bot.change_presence(activity=discord.CustomActivity(name=bot_activity_string))

try:
    bot.run(bot_setup["token"])

except Exception as e:
    error_string = f'Error in bot, {e}'
    logger.error(error_string, exc_info=True)
