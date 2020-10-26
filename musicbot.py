# -*- coding: utf-8 -*- 
import asyncio
import datetime
import discord
import humanize
import itertools
import re
import sys
import traceback
import wavelink
import time
import math
import random
import dbkrpy
from discord.ext import commands
from discord.ext.commands import CommandNotFound
from typing import Union

access_token = os.environ["BOT_TOKEN"]
access_dbkrtoken = os.environ["dbkrBOT_TOKEN"]
access_IP = os.environ["ACCESS_IP"]
access_PW = os.environ["ACCESS_PW"]

RURL = re.compile('https?:\/\/(?:www\.)?.+')

def init():
    global command

    command = []
    fc = []

    command_inidata = open('command.ini', 'r', encoding = 'utf-8')
    command_inputData = command_inidata.readlines()

    ############## 뮤직봇 명령어 리스트 #####################
    for i in range(len(command_inputData)):
        tmp_command = command_inputData[i][12:].rstrip('\n')
        fc = tmp_command.split(', ')
        command.append(fc)
        fc = []

    del command[0]

    command_inidata.close()

init()

class Bot(commands.AutoShardedBot):

    def __init__(self):
        super(Bot, self).__init__(command_prefix='', help_command = None, description='해성뮤직봇')

        self.add_cog(Music(self))

    async def on_ready(self):
        print("Logged in as ") #화면에 봇의 아이디, 닉네임이 출력됩니다.
        print(bot.user.name)
        print(bot.user.id)
        print("===========")

    async def on_command_error(self, ctx, error):
        if isinstance(error, CommandNotFound):
            return
        elif isinstance(error, discord.ext.commands.MissingRequiredArgument):
            return
        raise error

class MusicController:

    def __init__(self, bot, guild_id):
        self.bot = bot
        self.guild_id = guild_id
        self.channel = None

        self.next = asyncio.Event()
        self.queue = asyncio.Queue()

        self.volume = 40
        self.now_playing = None

        self.bot.loop.create_task(self.controller_loop())

    def shuffle(self):
        random.shuffle(self.queue._queue)

    def remove(self, index: int):
        del self.queue._queue[index]

    async def controller_loop(self):
        await self.bot.wait_until_ready()

        player = self.bot.wavelink.get_player(self.guild_id)
        await player.set_volume(self.volume)

        while True:
            if self.now_playing:
                await self.now_playing.delete()

            self.next.clear()

            song = await self.queue.get()
            await player.play(song)
            self.now_playing = await self.channel.send(f'Now playing: `{song}`')

            await self.next.wait()


class Music(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.controllers = {}

        if not hasattr(bot, 'wavelink'):
            self.bot.wavelink = wavelink.Client(bot=self.bot)

        self.bot.loop.create_task(self.start_nodes())

    def create_embed(self, track):
        curr_play_time = time.strftime('%H:%M:%S', time.gmtime(track.position/1000))
        total_duration = time.strftime('%H:%M:%S', time.gmtime(track.current.duration/1000))
        embed = (discord.Embed(title=f'Now playing ({curr_play_time}/{total_duration})',
                            description=f'**```fix\n{track.current.title}\n```**',
                            color=discord.Color.blurple())
                .add_field(name='Duration', value=total_duration)
                # .add_field(name='Requested by', value=self.requester.mention)
                .add_field(name='Uploader', value=f'{track.current.author}')
                .add_field(name='URL', value=f'[Click]({track.current.uri})')
                .set_thumbnail(url=track.current.thumb))

        return embed

    async def start_nodes(self):
        await self.bot.wait_until_ready()

        # Initiate our nodes. For this example we will use one server.
        # Region should be a discord.py guild.region e.g sydney or us_central (Though this is not technically required)
        node  = await self.bot.wavelink.initiate_node(host=access_IP,
                                                    port=80,
                                                    rest_uri=f'http://{access_IP}:80',
                                                    password=access_PW,
                                                    identifier='MAIN',
                                                    region='us_central')


        # Set our node hook callback
        node.set_hook(self.on_event_hook)

    async def on_event_hook(self, event):
        """Node hook callback."""
        if isinstance(event, (wavelink.TrackEnd, wavelink.TrackException)):
            controller = self.get_controller(event.player)
            controller.next.set()

    def get_controller(self, value: Union[commands.Context, wavelink.Player]):
        if isinstance(value, commands.Context):
            gid = value.guild.id
        else:
            gid = value.guild_id

        try:
            controller = self.controllers[gid]
        except KeyError:
            controller = MusicController(self.bot, gid)
            self.controllers[gid] = controller

        return controller

    async def cog_check(self, ctx):
        """A local check which applies to all commands in this cog."""
        if not ctx.guild:
            raise commands.NoPrivateMessage
        return True

    async def cog_command_error(self, ctx, error):
        """A local error handler for all errors arising from commands in this cog."""
        if isinstance(error, commands.NoPrivateMessage):
            try:
                return await ctx.send('This command can not be used in Private Messages.')
            except discord.HTTPException:
                pass

        print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    @commands.command(name=command[0][0], aliases=command[0][1:]) # 들어가자
    async def connect_(self, ctx, *, channel: discord.VoiceChannel=None):
        if not channel:
            try:
                channel = ctx.author.voice.channel
            except AttributeError:
                raise discord.DiscordException(':no_entry_sign: 음성채널에 접속 후 명령어를 사용해주세요.')

        player = self.bot.wavelink.get_player(ctx.guild.id)
        await ctx.send(f'Connecting to **`{channel.name}`**', delete_after=15)
        await player.connect(channel.id)

        controller = self.get_controller(ctx)
        controller.channel = ctx.channel

    @commands.command(name=command[1][0], aliases=command[1][1:])
    async def play(self, ctx, *, query: str = None):
        if not query:
            return await ctx.send('`검색어`를 입력해주세요.')
        if not RURL.match(query):
            query = f'ytsearch:{query}'

        tracks = await self.bot.wavelink.get_tracks(f'{query}')

        if not tracks:
            return await ctx.send('`검색 조건`에 `만족`하는 `노래`가 없습니다.')

        player = self.bot.wavelink.get_player(ctx.guild.id)
        if not player.is_connected:
            await ctx.invoke(self.connect_)

        emoji_list : list = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "🚫"]
        song_list_str : str = ""
        cnt : int = 0
        song_index : int = 0
        
        for i in range(5):
            cnt += 1
            song_list_str += f"`{cnt}.` [**{tracks[i].title}**]({tracks[i].uri})\n"
        
        embed = discord.Embed(description= song_list_str)
        embed.set_footer(text=f"10초 안에 미선택시 취소됩니다.")

        song_list_message = await ctx.send(embed = embed)

        for emoji in emoji_list:
            await song_list_message.add_reaction(emoji)

        def reaction_check(reaction, user):
            return (reaction.message.id == song_list_message.id) and (user.id == ctx.author.id) and (str(reaction) in emoji_list)
        try:
            reaction, user = await bot.wait_for('reaction_add', check = reaction_check, timeout = 10)
        except asyncio.TimeoutError:
            reaction = "🚫"

        for emoji in emoji_list:
            await song_list_message.remove_reaction(emoji, bot.user)

        await song_list_message.delete(delay = 10)

        if str(reaction) == "1️⃣":
            song_index = 0
        elif str(reaction) == "2️⃣":
            song_index = 1
        elif str(reaction) == "3️⃣":
            song_index = 2
        elif str(reaction) == "4️⃣":
            song_index = 3
        elif str(reaction) == "5️⃣":
            song_index = 4
        else:
            return await ctx.send('`노래 재생`이 `취소`되었습니다.')

        track = tracks[song_index]

        controller = self.get_controller(ctx)
        await controller.queue.put(track)
        await ctx.send(f'재생목록 추가 : `{str(track)}`', delete_after=15)

    @commands.command(name=command[2][0], aliases=command[2][1:])
    async def pause(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id)
        if not player.is_playing:
            return await ctx.send(':mute: 현재 재생중인 음악이 없습니다.', delete_after=15)

        await ctx.message.add_reaction('⏸')
        await player.set_pause(True)

    @commands.command(name=command[3][0], aliases=command[3][1:])
    async def resume(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id)
        if not player.paused:
            return await ctx.send(':mute: 현재 일시정지된 음악이 없습니다.', delete_after=15)

        await ctx.message.add_reaction('⏯')
        await player.set_pause(False)

    @commands.command(name=command[4][0], aliases=command[4][1:])
    async def skip(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id)

        if not player.is_playing:
            return await ctx.send(':mute: 현재 재생중인 음악이 없습니다.', delete_after=15)

        await ctx.message.add_reaction('⏭')
        await player.stop()

    @commands.command(name=command[5][0], aliases=command[5][1:])
    async def queue(self, ctx, *, page: int = 1):
        player = self.bot.wavelink.get_player(ctx.guild.id)
        controller = self.get_controller(ctx)

        if not player.current or not controller.queue._queue:
            return await ctx.send(':mute: 재생목록이 없습니다.', delete_after=20)

        items_per_page = 10
        pages = math.ceil(len(controller.queue._queue) / items_per_page)

        start = (page - 1) * items_per_page
        end = start + items_per_page

        upcoming = list(itertools.islice(controller.queue._queue, start, end))

        queue = ''
        for i, song in enumerate(upcoming):
            queue += f'`{i + 1}.` [**{song.title}**]({song.uri})\n'

        embed = discord.Embed(title = f"Now playing ({time.strftime('%H:%M:%S', time.gmtime(player.position/1000))}/{time.strftime('%H:%M:%S', time.gmtime(player.current.duration/1000))})",
                            description=f'**```fix\n{player.current.title}\n```**')
        embed.add_field(name =f'\u200B\n**{len(controller.queue._queue)} tracks:**\n', value = f"\u200B\n{queue}")
        embed.set_thumbnail(url=player.current.thumb)
        embed.set_footer(text='Viewing page {}/{}'.format(page, pages))

        await ctx.send(embed=embed)

    @commands.command(name=command[6][0], aliases=command[6][1:])
    async def now_playing(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id)

        if not player.current:
            return await ctx.send(':mute: 현재 재생중인 음악이 없습니다.', delete_after=15)

        controller = self.get_controller(ctx)
        await controller.now_playing.delete()

        controller.now_playing = await ctx.send(embed = self.create_embed(player))

    @commands.command(name=command[7][0], aliases=command[7][1:])
    async def volume(self, ctx, *, vol: int):
        if not 0 < vol < 101:
            return await ctx.send('```볼륨은 1 ~ 100 사이로 입력 해주세요.```')

        player = self.bot.wavelink.get_player(ctx.guild.id)
        controller = self.get_controller(ctx)       

        if not player.is_playing:
            return await ctx.send(':mute: 현재 재생중인 음악이 없습니다.', delete_after=15)

        vol = max(min(vol, 1000), 0)
        controller.volume = vol
        
        await ctx.send(f':loud_sound: 볼륨을 {vol}%로 조정하였습니다.')
        await player.set_volume(vol)

    @commands.command(name=command[8][0], aliases=command[8][1:])
    async def stop(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id)

        try:
            del self.controllers[ctx.guild.id]
        except KeyError:
            await player.disconnect()
            return await ctx.send(':mute: 현재 재생중인 음악이 없습니다.', delete_after=20)

        await player.disconnect()
        await ctx.message.add_reaction('⏹')

    @commands.command(name=command[9][0], aliases=command[9][1:])
    async def remove(self, ctx: commands.Context, index: int):
        player = self.bot.wavelink.get_player(ctx.guild.id)
        controller = self.get_controller(ctx)
        
        if not player.current or not controller.queue._queue:
            return await ctx.send(':mute: 재생목록이 없습니다.', delete_after=20)
        
        remove_result = f'`{index}.` [**{controller.queue._queue[index-1].title}**] 삭제 완료!\n'
        result = await ctx.send(remove_result)
        controller.remove(index - 1)
        await result.add_reaction('✅')

    @commands.command(name=command[10][0], aliases=command[10][1:])
    async def shuffle(self, ctx: commands.Context):
        player = self.bot.wavelink.get_player(ctx.guild.id)
        controller = self.get_controller(ctx)

        if not player.current or not controller.queue._queue:
            return await ctx.send(':mute: 재생목록이 없습니다.', delete_after=20)

        controller.shuffle()
        result = await ctx.send('셔플 완료!')
        await result.add_reaction('🔀')

    @commands.command(name=command[11][0], aliases=command[11][1:])   #도움말
    async def menu_(self, ctx):
        command_list += '```'
        command_list += ','.join(command[0]) + '\n'     #!들어가자
        command_list += ','.join(command[1]) + ' [검색어] or [url]\n'     #!재생
        command_list += ','.join(command[2]) + '\n'     #!일시정지
        command_list += ','.join(command[3]) + '\n'     #!다시재생
        command_list += ','.join(command[4]) + ' (숫자)\n'     #!스킵
        command_list += ','.join(command[5]) + ' 혹은 [명령어] + [숫자]\n'     #!목록
        command_list += ','.join(command[6]) + '\n'     #!현재재생
        command_list += ','.join(command[7]) + ' [숫자 1~100]\n'     #!볼륨
        command_list += ','.join(command[8]) + '\n'     #!정지
        command_list += ','.join(command[9]) + '\n'     #!삭제
        command_list += ','.join(command[10]) + '\n'     #!섞기
        embed = discord.Embed(
                title = "----- 명령어 -----",
                description = command_list,
                color=0xff00ff
                )
        await ctx.send(embed=embed)

    @commands.command(name="해성정보")
    async def info(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id)
        node = player.node

        used = humanize.naturalsize(node.stats.memory_used)
        total = humanize.naturalsize(node.stats.memory_allocated)
        free = humanize.naturalsize(node.stats.memory_free)
        cpu = node.stats.cpu_cores

        fmt = f'**WaveLink:** `{wavelink.__version__}`\n\n' \
              f'Connected to `{len(self.bot.wavelink.nodes)}` nodes.\n' \
              f'Best available Node `{self.bot.wavelink.get_best_node().__repr__()}`\n' \
              f'`{len(self.bot.wavelink.players)}` players are distributed on nodes.\n' \
              f'`{node.stats.players}` players are distributed on server.\n' \
              f'`{node.stats.playing_players}` players are playing on server.\n\n' \
              f'Server Memory: `{used}/{total}` | `({free} free)`\n' \
              f'Server CPU: `{cpu}`\n\n' \
              f'Server Uptime: `{datetime.timedelta(milliseconds=node.stats.uptime)}`'
        await ctx.send(fmt)

bot = Bot()
dbkrpy.UpdateGuilds(bot, access_dbkrtoken)
bot.run(access_token)
