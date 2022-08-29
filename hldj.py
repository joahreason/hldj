# --------------------------------------------------------------------------- #
#                                                                             #
#                           Music Bot For Discord                             #
#                               Joah Reason                                   #
#                              8 / 23 / 2022                                  #
#                                                                             #
# --------------------------------------------------------------------------- #

import asyncio
import os
import discord
import youtube_dl
from discord.ext import commands
from discord import FFmpegPCMAudio
from requests import get
from dotenv import load_dotenv
from youtube_dl import YoutubeDL

load_dotenv()

TOKEN = os.environ['DISCORD_TOKEN']
MOTD = "nothing... !play [link]"

YDL_OPTIONS = {'format': 'bestaudio',
               'noplaylist': 'True',
               'cookiefile': 'cookies.txt'}

FFMPEG_OPTIONS = {'before_options':
                  '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                  'options': '-vn'}

SONG_ALIASES = ["currentsong",
                "current",
                "whatamilisteningto",
                "songlist",
                "playlist",
                "showqueue",
                "whatsnext"]

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
bot = commands.Bot(command_prefix="!", intents=intents)

voice_client = None
stopping = False
queue = []
current_info = None
ffmpeg = None


# Start bot presence as the MOTD
@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(name=MOTD))


# Start playing queue of songs
async def play_queue(ctx):
    global current_info, voice_client, ffmpeg

    # While we have songs in queue
    while queue:
        # Grab next song in queue
        current_info = queue.pop(0)

        # Notify what song is being played and update presence
        await ctx.send(f"Playing **\"{current_info['title']}\"**")
        await bot.change_presence(
            activity=discord.Game(name=current_info['title'])
        )

        # Grab file from URL and play
        ffmpeg = FFmpegPCMAudio(current_info['url'], **FFMPEG_OPTIONS)
        voice_client.play(ffmpeg)

        # Hold until song is finished
        while voice_client and \
                (voice_client.is_playing() or voice_client.is_paused()):
            await asyncio.sleep(1)

    # No more songs in queue, disconnect from voice
    await disconnect_voice()


# Notify what song is currently playing or what is in queue
@bot.command(name="song", aliases=SONG_ALIASES)
async def song(ctx):
    global current_info
    output = ""

    # Basically a switch statement, checking which command alias we used
    match ctx.invoked_with:
        # All the commands to check the current song
        case "song" | "currentsong" | "current" | "whatamilisteningto":
            if current_info:
                output = f"Currently playing **\"{current_info['title']}\"**"
            else:
                output = "Nothing currently playing"

        # All the commands to check the queue of songs
        case "songlist" | "playlist" | "showqueue" | "whatsnext":
            if queue:
                output = "__Song Queue:__\n"
                for i in range(len(queue)):
                    info = queue[i]
                    output += f"\n**{i+1}.** *\"{info['title']}\"*"
            else:
                output = "Nothing currently in queue"

    # Display results
    await ctx.send(output)

# Returns who queued current song
@bot.command(name="who")
async def who(ctx):
    global current_info

    if current_info:
        title = current_info['title']
        user = current_info['played by']

        await ctx.send(
            f"**\' {title} \'** was requested by **{user}**"
        )


# Connects to voice channel user who called command is currently
# Grabs the URL to play given their !play link
# Adds to queue and starts queue if it isn't currently active
# Unpauses if not given a link and currently paused
@bot.command(name="play", aliases=["queue", "q"])
async def play(ctx, *, arg):
    global voice_client

    # Grabs user and voice channel
    user = ctx.message.author
    voice_channel = user.voice.channel

    if voice_channel:
        # Connects to voice channel if not already connected
        if not voice_client:
            voice_client = await voice_channel.connect()

        if arg:
            # Grabs video info from youtube
            with YoutubeDL(YDL_OPTIONS) as ydl:
                try:
                    get(arg)
                except:
                    try:
                        info = ydl.extract_info(f"ytsearch:{arg}", download=False)['entries'][0]
                    except:
                        ydl.params['format'] = None
                        info = ydl.extract_info(f"ytsearch:{arg}", download=False)['entries'][0]
                else:
                    info = ydl.extract_info(arg, download=False)

            # Grabs formatted URL from info
            URL = info['url']

            # Adds entry to track who requested the song
            info.update({"played by": user})

        if URL:
            # If something already playing, add to queue and notify
            queue.append(info)

            if voice_client.is_playing():
                await ctx.send(f"Queuing up **\"{info['title']}\"**")

        # Start queue if it isn't currently playing
        if not voice_client.is_playing():
            await play_queue(ctx)
        # Unpause if paused and no link was given
        elif voice_client.is_paused() and arg:
            await unpause.invoke(ctx)


# Skip to next song in queue
@bot.command(name="skip", aliases=["next"])
async def skip(ctx):
    global voice_client, ffmpeg

    # Checks that user is connected to voice
    if not is_user_connected(ctx):
        return

    # If bot is connected, stop current song and continue with queue
    if voice_client:
        voice_client.stop()
        await play_queue(ctx)


# Stops playing song, clears queue, and disconnects from voice
@bot.command(name="stop", aliases=["s", "end", "kick"])
async def stop(ctx):
    global voice_client

    # Checks that user is connected to voice
    if not is_user_connected(ctx):
        return

    # If bot is connected, disconnect from voice
    if voice_client:
        await disconnect_voice()


# Pauses the current song
# Unpauses if already paused
@bot.command(name="pause", aliases=["p"])
async def pause(ctx):
    global voice_client

    # Checks that user is connected to voice
    if not is_user_connected(ctx):
        return

    # If bot is connected
    if voice_client:
        # Pause song if one is playing and not paused
        if voice_client.is_playing() and not voice_client.is_paused():
            voice_client.pause()
            user = ctx.message.author.name
            title = current_info['title']
            await ctx.send(f"{user} paused **\"{title}\"**")

        # Unpause song if already paused
        elif voice_client.is_paused():
            await unpause.invoke(ctx)


# Unpauses the current song
@bot.command(name="unpause", aliases=["resume", "continue"])
async def unpause(ctx):
    global voice_client

    # Checks that user is connected to voice
    if not is_user_connected(ctx):
        return

    # If bot is connected and song is paused, resume song
    if voice_client:
        if voice_client.is_paused():
            voice_client.resume()
            user = ctx.message.author.name
            title = current_info['title']
            await ctx.send(f"{user} unpaused **\"{title}\"**")


# Hands disconnect and cleanup
async def disconnect_voice():
    global voice_client, current_info, queue

    # Cleanly kills current FFmpeg process
    FFmpegPCMAudio._kill_process(ffmpeg)

    # If bot is connected to voice, disconnect and clear reference
    if voice_client:
        await voice_client.disconnect()
        voice_client = None

    # Clears queue and current song info
    queue.clear()
    current_info = None

    # Reverts presence to MOTD
    await bot.change_presence(activity=discord.Game(name=MOTD))


# Checks if user is currently connected
def is_user_connected(ctx):
    return ctx.message.author.voice is not None


# Starts bot
bot.run(TOKEN)
