import discord
import yt_dlp
from discord.ext import commands
import asyncio
from concurrent.futures import ThreadPoolExecutor
import argparse


# ArgParser to get and use YT-DLP's --cookies, if preferred by the user.
# The correct usage can be found at: https://github.com/yt-dlp/yt-dlp#filesystem-options
parser = argparse.ArgumentParser()
parser.add_argument(
    "-c", "--cookies",
    type=str,
    help="Path to the cookies.txt file (optional).",
    default=None
)
args = parser.parse_args()

path_to_cookies = args.cookies # Receives 'None', if no path is specified.


intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)

#globals because i'm lazy
queue = []

actual_url = []

thumb_url = []

embed_msg = None

thumb = None

bot.play_status = False

bot.in_chat = None

bot.doom = False

executor = ThreadPoolExecutor(max_workers=4)


async def embeded(ctx, msg, thumbna):
    embed= discord.Embed(
        colour=discord.Colour.brand_green(),
        title='Playing Now:',
        description=f'{msg}'
            )      
    embed.set_author(name='Tocador') 

    embed.set_image(url=thumbna)
    
    await ctx.send(embed=embed)


async def search_video(ctx, urlq):  
    yt_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'default_search': 'auto',
                'noplaylist': True,
                'verbose': True,
                'cookiefile': path_to_cookies # 'None', if blank.
    }
    yt_search = yt_dlp.YoutubeDL(yt_opts)
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(executor, lambda: yt_search.extract_info(url=urlq, download=False))
    if 'entries' in data:
        data = data['entries'][0]       
        data1 = [data['title'], data['url']]
        data2 = data['webpage_url']
        data3 = data['thumbnail']
    else:
        data1 = [data['title'], data['url']]
        data2 = [data['webpage_url']]
        data3 = [data['thumbnail']]
    return data1, data2, data3


async def playlist(ctx, urlq):
    pl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'default_search': 'auto',     
            'noplaylist': False,
            'ignoreerrors': True,
            'flat_playlist': True,
            'verbose': True,
            'cookiefile': path_to_cookies # 'None', if blank.
}
    playlist_search = yt_dlp.YoutubeDL(pl_opts)
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(executor, lambda: playlist_search.extract_info(url=urlq, download=False))
    if 'entries' in data:
        data1 =[[entry['title'], entry['url']] for entry in data['entries']]
        data2 = [entry['webpage_url'] for entry in data['entries']]
        data3 = [entry['thumbnail'] for entry in data['entries']]
    return data1, data2, data3


async def join(ctx):
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if not voice_client:
        if ctx.author.voice:
            voice_channel = ctx.author.voice.channel
            voice_client = await voice_channel.connect()
            bot.in_chat = voice_channel  
            
        elif not voice_client:
            embed = discord.Embed(title='Error', description='You are not in a voice channel', colour=discord.Colour.brand_red())
            await ctx.send(embed=embed)
        
    elif ctx.author.voice.channel != bot.in_chat:
        embed = discord.Embed(title='Error', description='We are not in the same voice channel', colour=discord.Colour.brand_red())
        await ctx.send(embed=embed)
        return
    
    return voice_client



@bot.listen()
async def on_voice_state_update(member, before, after):
    if not member.id == bot.user.id:
        return

    elif before.channel is None:
        voice = after.channel.guild.voice_client
        time = 0
        while True:
            await asyncio.sleep(1)
            time = time + 1
            if voice.is_playing() and not voice.is_paused():
                time = 0
            if time == 600:
                await voice.disconnect()
            if not voice.is_connected():
                break



@bot.command(name='play', help='Command for searching videos and Playlist: !play Leno Brega')# note: for playlist use only playlist urls like: https://www.youtube.com/playlist?list=PLCbw7XKNtw1iZsT7-VHj1JJKhFlgOVHNB
@commands.cooldown(1, 2, commands.BucketType.user)
async def play(ctx, *, search_query):
    global queue, actual_url, thumb_url
    voice_client = await join(ctx)
    if not voice_client:
        return
    
    bot.doom = False
    if '&list=' in search_query or '&start_radio=' in search_query:
        embed = (discord.Embed(title='Error', description='Url format not supported', colour=discord.Colour.dark_orange()))
        
        await ctx.send(embed=embed)
        return
    
    elif '/playlist?' in search_query and not '/watch?' in search_query:
        embed = discord.Embed(title='Warning:', description='getting information from the playlist, it may take a while, if you use "!play" again, the song may be queued before the playlist...',
                              colour=discord.Colour.yellow())
        await ctx.send(embed=embed)
        data1, url, tn = await playlist(ctx, search_query)
            
        data = data1.copy()
        actual_url.extend(url)
        thumb_url.extend(tn)
    
        if bot.doom: #lazy check to make sure no thread task aren't sent to queue after using !stop
            data = None
            actual_url.clear()
            thumb_url.clear()
            queue.clear()
            return
    
        if bot.play_status or len(queue) > 0:
            queue.extend(data)
            embed = discord.Embed(title='Added to queue', colour= discord.Colour.blue())
            await ctx.send(embed=embed)      
        else:
            queue.extend(data)
            await play_now(ctx, url=queue.pop(0))     
                                       
    elif '/watch?' in search_query and not '/playlist?' in search_query:
        data1, url, tn = await search_video(ctx, search_query)
        
        data = data1.copy()
        actual_url.extend(url)
        thumb_url.extend(tn)
        
        if bot.play_status or len(queue) > 0:
            queue.append(data)
            embed = discord.Embed(title='Added to queue', colour= discord.Colour.blue())
            await ctx.send(embed=embed)
        else:
            queue.append(data)
            await play_now(ctx, url=queue.pop(0))
    else:
        data1, url, tn = await search_video(ctx, search_query)

        data = data1.copy()
        actual_url.append(url)
        thumb_url.append(tn)

        if bot.play_status or len(queue) > 0:
            queue.append(data)
            embed = discord.Embed(title='Added to queue', colour= discord.Colour.blue())
            await ctx.send(embed=embed)
        else:
            queue.append(data)
            await play_now(ctx, url=queue.pop(0))
     
        
        
async def play_now(ctx, url):
    global embed_msg, thumb
    voice_client = await join(ctx)
    if not voice_client:
        return
        
    ffmpeg_options = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}
    bot.play_status = True    
    def after(error):
        if error:
            print(error)
                
        if bot.play_status and len(queue) > 0:
            next_song = queue.pop(0)
            embed_msg = f'{next_song[0]}  {actual_url.pop(0)}'
            thumb = f'{thumb_url.pop(0)}'
            asyncio.run_coroutine_threadsafe(embeded(ctx, embed_msg, thumb), bot.loop)
            voice_client.play(discord.FFmpegPCMAudio(next_song[1], **ffmpeg_options), after=lambda e: after(e))
        else:
            bot.play_status = False
            
    embed_msg = f'{url[0]}  {actual_url.pop(0)}'
    thumb = f'{thumb_url.pop(0)}'
    await embeded(ctx, embed_msg, thumb)          
    voice_client.play(discord.FFmpegPCMAudio(url[1], **ffmpeg_options), after=lambda e: after(e))
        
 
        
@bot.command(name='next', help='skips the song that is currently playing or paused.')
@commands.cooldown(1, 2, commands.BucketType.user)
async def next(ctx):
    voice_client = await join(ctx)
    if not voice_client:
        return
    
    if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
        voice_client.stop()
    else:
        embed = discord.Embed(title="Error", description="No songs playing.", color=discord.Colour.brand_red())
        await ctx.send(embed=embed)          
    
                

@bot.command(name='pause', help='pause the current song.')
@commands.cooldown(1, 2, commands.BucketType.user)
async def pause(ctx):
    voice_client = await join(ctx)
    if not voice_client:
        return
        
    if voice_client.is_playing():
        voice_client.pause()
        embed = discord.Embed(title='Paused', color=discord.Colour.blue())
        await ctx.send(embed=embed)
        return
    else:
        embed = discord.Embed(title="Error", description="No songs playing.", color=discord.Colour.brand_red())
        await ctx.send(embed=embed) 
        return

      
        
@bot.command(name='continue', help='continue the song that is paused.')
@commands.cooldown(1, 2, commands.BucketType.user)
async def Continue(ctx):
    voice_client = await join(ctx)
    if not voice_client:
        return
        
    if voice_client.is_paused():
        voice_client.resume()
        embed = discord.Embed(title='Resuming', colour= discord.Colour.brand_green())
        await ctx.send(embed=embed)
        return
    else:
        embed = discord.Embed(title='Error', description='No songs paused.', colour=discord.Colour.brand_red())
        await ctx.send(embed=embed)

        
           
@bot.command(name='stop', help='command used to stop the bot and clear the music queue')
@commands.cooldown(1, 2, commands.BucketType.user)
async def stop(ctx):
    voice_client = await join(ctx)
    if not voice_client:
        return

    bot.doom = True
    if bot.play_status or voice_client.is_paused():
        queue.clear()
        actual_url.clear()
        thumb_url.clear()
        voice_client.stop()
        bot.play_status = False
        embed = discord.Embed(title='Stopped', description='All songs have been removed from the queue', colour=discord.Colour.brand_red())
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(title='Error', description="i'm not playing anything.", colour=discord.Colour.brand_red())
        await ctx.send(embed=embed)
        


class MyHelp(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        embed = discord.Embed(title="Help", colour=discord.Colour.gold())
        for command in self.context.bot.commands:
            embed.add_field(name=f"{command.name}", value=command.help, inline=False)
        await self.get_destination().send(embed=embed)
        
    async def send_command_help(self, command):
        embed = discord.Embed(title=f"Help to: {command.qualified_name}", description=command.help, colour=discord.Colour.gold())
        await self.get_destination().send(embed=embed)
        
bot.help_command = MyHelp()

# Run the bot with your token
bot.run('Your_bot_key_here')