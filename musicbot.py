# -*- coding: utf-8 -*- 

import os
import discord
from discord.ext import commands
from discord.ext.commands import CommandNotFound
import logging
import asyncio
import itertools
import sys
import traceback
import random
from async_timeout import timeout
from functools import partial
from youtube_dl import YoutubeDL
from io import StringIO
import time

##################### 로깅 ###########################
log_stream = StringIO()    
logging.basicConfig(stream=log_stream, level=logging.WARNING)

#ilsanglog = logging.getLogger('discord')
#ilsanglog.setLevel(level = logging.WARNING)
#handler = logging.StreamHandler()
#handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
#ilsanglog.addHandler(handler)
#####################################################

access_token = os.environ["BOT_TOKEN"]	

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

	#print (command)

init()

ytdlopts = {
	'format': 'bestaudio/best',
	'outtmpl': 'downloads/%(extractor)s-%(id)s-%(title)s.%(ext)s',
	'restrictfilenames': True,
	'noplaylist': True,
	'nocheckcertificate': True,
	'ignoreerrors': False,
	'logtostderr': False,
	'quiet': True,
	'no_warnings': True,
	'default_search': 'auto',
	'source_address': '0.0.0.0'  # ipv6 addresses cause issues sometimes
}

ffmpegopts = {
	'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 60',
	'options': '-vn'
}

ytdl = YoutubeDL(ytdlopts)


class VoiceConnectionError(commands.CommandError):
	"""Custom Exception class for connection errors."""


class InvalidVoiceChannel(VoiceConnectionError):
	"""Exception for cases of invalid Voice Channels."""


class YTDLSource(discord.PCMVolumeTransformer):

	def __init__(self, source, *, data, requester):
		super().__init__(source)
		self.requester = requester

		self.title = data.get('title')
		self.web_url = data.get('webpage_url')
		self.duration = data.get('duration')
		self.thumbnail = data.get('thumbnail')

	def __getitem__(self, item: str):
		"""Allows us to access attributes similar to a dict.
		This is only useful when you are NOT downloading.
		"""
		return self.__getattribute__(item)

	@classmethod
	async def create_source(cls, ctx, search: str, *, loop, download=False):
		loop = loop or asyncio.get_event_loop()

		to_run = partial(ytdl.extract_info, url=search, download=download)
		data = await loop.run_in_executor(None, to_run)

		if 'entries' in data:
			# take first item from a playlist
			data = data['entries'][0]
	
		#await ctx.send(f'```ini\n[재생목록에 "{data["title"]}" 를 추가했습니다.]\n```', delete_after=15)
		embed = discord.Embed(title="[재생목록 추가]", description="제목 : " + data["title"] + "\n재생시간 : " + time.strftime('%H:%M:%S', time.gmtime(data['duration'])), color=0x62c1cc)
		embed.set_thumbnail(url=data['thumbnail'])
		embed.set_footer(text= 'requested by  ' f'`{ctx.author}`')
		await ctx.send(embed=embed, delete_after=15)

		if download:
			source = ytdl.prepare_filename(data)
		else:
			return {'webpage_url': data['webpage_url'], 'requester': ctx.author, 'title': data['title'], 'duration' : data['duration'], 'thumbnail' : data['thumbnail']}

		return cls(discord.FFmpegPCMAudio(source, **ffmpegopts), data=data, requester=ctx.author)

	@classmethod
	async def regather_stream(cls, data, *, loop):
		"""Used for preparing a stream, instead of downloading.
		Since Youtube Streaming links expire."""
		loop = loop or asyncio.get_event_loop()
		requester = data['requester']

		to_run = partial(ytdl.extract_info, url=data['webpage_url'], download=False)
		data = await loop.run_in_executor(None, to_run)

		return cls(discord.FFmpegPCMAudio(data['url'], **ffmpegopts), data=data, requester=requester)


class MusicPlayer:
	"""A class which is assigned to each guild using the bot for Music.
	This class implements a queue and loop, which allows for different guilds to listen to different playlists
	simultaneously.
	When the bot disconnects from the Voice it's instance will be destroyed.
	"""

	__slots__ = ('bot', '_guild', '_channel', '_cog', 'queue', 'next', 'current', 'np', 'volume')

	def __init__(self, ctx):
		self.bot = ctx.bot
		self._guild = ctx.guild
		self._channel = ctx.channel
		self._cog = ctx.cog

		self.queue = asyncio.Queue()
		self.next = asyncio.Event()

		self.np = None  # Now playing message
		self.volume = .5
		self.current = None

		ctx.bot.loop.create_task(self.player_loop())

	async def player_loop(self):
		"""Our main player loop."""
		await self.bot.wait_until_ready()

		while True:
			self.next.clear()

			
			try:
				# Wait for the next song. If we timeout cancel the player and disconnect...
				async with timeout(60):  # 5 minutes...
					source = await self.queue.get()
			except asyncio.TimeoutError:
				return self.destroy(self._guild)
			
			#play_duration = source['duration']
			#url_thumbnail = source['thumbnail']

			#del source['duration']
			#del source['thumbnail']

			if not isinstance(source, YTDLSource):
				# Source was probably a stream (not downloaded)
				# So we should regather to prevent stream expiration
				try:
					source = await YTDLSource.regather_stream(source, loop=self.bot.loop)
				except Exception as e:
					await self._channel.send(f'There was an error processing your song.\n'
											f'```css\n[{e}]\n```')
					continue

			source.volume = self.volume
			self.current = source

			self._guild.voice_client.play(source, after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set))
			embed = discord.Embed(title=source.title, description="재생시간 : " + time.strftime('%H:%M:%S', time.gmtime(source['duration'])), color=0x62c1cc)
			embed.set_thumbnail(url=source['thumbnail'])
			embed.set_footer(text= 'requested by  ' f'`{source.requester}`')
			self.np = await self._channel.send(embed=embed)
			#self.np = await self._channel.send(f'**Now Playing : **  `{source.title}`  requested by  ' f'`{source.requester}`')
			await self.next.wait()

			# Make sure the FFmpeg process is cleaned up.
			source.cleanup()
			self.current = None

			try:
				# We are no longer playing this song...
				await self.np.delete()
			except discord.HTTPException:
				pass

	def destroy(self, guild):
		"""Disconnect and cleanup the player."""
		return self.bot.loop.create_task(self._cog.cleanup(guild))


class Music(commands.Cog):
	"""Music related commands."""

	__slots__ = ('bot', 'players')

	def __init__(self, bot):
		self.bot = bot
		self.players = {}

	async def cleanup(self, guild):
		try:
			await guild.voice_client.disconnect()
		except AttributeError:
			pass

		try:
			del self.players[guild.id]
		except KeyError:
			pass

	async def __local_check(self, ctx):
		"""A local check which applies to all commands in this cog."""
		if not ctx.guild:
			raise commands.NoPrivateMessage
		return True

	async def __error(self, ctx, error):
		"""A local error handler for all errors arising from commands in this cog."""
		if isinstance(error, commands.NoPrivateMessage):
			try:
				return await ctx.send('This command can not be used in Private Messages.')
			except discord.HTTPException:
				pass
		elif isinstance(error, InvalidVoiceChannel):
			await ctx.send('Error connecting to Voice Channel. '
						'Please make sure you are in a valid channel or provide me with one')

		print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
		traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

	def get_player(self, ctx):
		"""Retrieve the guild player, or generate one."""
		try:
			player = self.players[ctx.guild.id]
		except KeyError:
			player = MusicPlayer(ctx)
			self.players[ctx.guild.id] = player

		return player

	@commands.command(name=command[0][0], aliases=command[0][1:])   #채널 접속
	async def connect_(self, ctx, *, channel: discord.VoiceChannel=None):

		if not channel:
			try:
				channel = ctx.author.voice.channel
			except AttributeError:
				await ctx.send(':no_entry_sign: 음성채널에 접속하고 사용해주세요.', delete_after=20)
				#raise InvalidVoiceChannel(':no_entry_sign: 음성채널에 접속하고 사용해주세요.')
				return False

		vc = ctx.voice_client

		if vc:
			if vc.channel.id == channel.id:
				return True
			try:
				await vc.move_to(channel)
			except asyncio.TimeoutError:
				await ctx.send(f':no_entry_sign: 채널 이동 : <{channel}> 시간 초과. 좀 있다 시도해주세요.', delete_after=20)
				#raise VoiceConnectionError(f':no_entry_sign: 채널 이동 : <{channel}> 시간 초과.')
				return False
		else:
			try:
				await channel.connect(reconnect=True)
			except asyncio.TimeoutError:
				await ctx.send(f':no_entry_sign: 채널 접속: <{channel}> 시간 초과. 좀 있다 시도해주세요.', delete_after=20)
				#raise VoiceConnectionError(f':no_entry_sign: 채널 접속: <{channel}> 시간 초과.')
				return False

		await ctx.send(f'Connected to : **{channel}**', delete_after=20)
		return True

	@commands.command(name=command[1][0], aliases=command[1][1:])     #재생
	async def play_(self, ctx, *, search: str):
		"""음악을 재생합니다. !재생 URL 또는 검색어"""
		await ctx.trigger_typing()

		vc = ctx.voice_client

		if not vc:
			connenct_result = await ctx.invoke(self.connect_)
			if connenct_result == False:
				return
			#return await ctx.send(':mute: 음성채널에 접속후 사용해주세요.', delete_after=20)

		player = self.get_player(ctx)

		# If download is False, source will be a dict which will be used later to regather the stream.
		# If download is True, source will be a discord.FFmpegPCMAudio with a VolumeTransformer.
		source = await YTDLSource.create_source(ctx, search, loop=self.bot.loop, download=False)

		await player.queue.put(source)

	@commands.command(name=command[2][0], aliases=command[2][1:])    #일시정지
	async def pause_(self, ctx):
		"""현재 재생중인 곡을 일시정지 합니다."""
		vc = ctx.voice_client

		if not vc or not vc.is_playing():
			return await ctx.send(':mute: 현재 재생중인 음악이 없습니다.', delete_after=20)
		elif vc.is_paused():
			return

		vc.pause()
		await ctx.send(f'**`{ctx.author}`**: 음악 정지!')

	@commands.command(name=command[3][0], aliases=command[3][1:])   #다시재생
	async def resume_(self, ctx):
		"""현재 재생중인 곡을 다시 재생 합니다."""
		vc = ctx.voice_client

		if not vc or not vc.is_connected():
			return await ctx.send(':mute: 현재 재생중인 음악이 없습니다.', delete_after=20)
		elif not vc.is_paused():
			return

		vc.resume()
		await ctx.send(f'**`{ctx.author}`**: 음악 다시 재생!')

	@commands.command(name=command[4][0], aliases=command[4][1:])   #스킵
	async def skip_(self, ctx):
		"""현재 재생중인 곡을 스킵합니다."""
		vc = ctx.voice_client

		if not vc or not vc.is_connected():
			return await ctx.send(':mute: 현재 재생중인 음악이 없습니다.', delete_after=20)

		if vc.is_paused():
			pass
		elif not vc.is_playing():
			return

		vc.stop()
		await ctx.send(f'**`{ctx.author}`**: 음악 스킵!')

	@commands.command(name=command[5][0], aliases=command[5][1:])   #재생목록
	async def queue_info(self, ctx):
		"""등록된 플레이리스트를 보여줍니다."""
		vc = ctx.voice_client

		if not vc or not vc.is_connected():
			return await ctx.send(':mute: 현재 재생중인 음악이 없습니다.', delete_after=20)

		player = self.get_player(ctx)
		if player.queue.empty():
			return await ctx.send(':mute: 더 이상 재생할 곡이 없습니다.')

		# Grab up to 5 entries from the queue...
		upcoming = list(itertools.islice(player.queue._queue, 0, 10))
		fmt = ''
		for i in range(len(upcoming)):
			fmt += '**' + str(i+1) + ' : ' + upcoming[i]['title'] + '**\n      재생시간 : ' + time.strftime('%H:%M:%S', time.gmtime(upcoming[i]['duration'])) + '\n'
		
		#fmt = '\n'.join(f'**`{_["title"]}`**' for _ in upcoming)
		embed = discord.Embed(title=f'Upcoming - Next {len(upcoming)}', description=fmt, color=0xff00ff)

		await ctx.send(embed=embed)

	@commands.command(name=command[6][0], aliases=command[6][1:])   #현재 재생음악
	async def now_playing_(self, ctx):
		"""현재 재생중인 곡 정보입니다."""
		vc = ctx.voice_client

		if not vc or not vc.is_connected():
			return await ctx.send(':no_entry_sign: 현재 접속중인 음악채널이 없습니다.', delete_after=20)

		player = self.get_player(ctx)
		if not player.current:
			return await ctx.send(':mute: 현재 재생중인 음악이 없습니다.')

		try:
			# Remove our previous now_playing message.
			await player.np.delete()
		except discord.HTTPException:
			pass

		embed = discord.Embed(title=vc.source.title, description="재생시간 : " + time.strftime('%H:%M:%S', time.gmtime(vc.source['duration'])), color=0x62c1cc)
		embed.set_thumbnail(url= vc.source['thumbnail'])
		embed.set_footer(text= 'requested by  ' f'`{vc.source.requester}`')
		player.np = await ctx.send(embed=embed, delete_after=20)

		#player.np = await ctx.send(f'**Now Playing : ** `{vc.source.title}` 'f'  requested by  `{vc.source.requester}`')

	@commands.command(name=command[7][0], aliases=command[7][1:])   #볼륨조정
	async def change_volume(self, ctx, *, vol: float):
		"""볼륨을 조절합니다. (1~100)"""
		vc = ctx.voice_client

		if not vc or not vc.is_connected():
			return await ctx.send(':no_entry_sign: 현재 접속중인 음악채널이 없습니다.', delete_after=20)

		if not 0 < vol < 101:
			return await ctx.send('볼륨은 1 ~ 100 사이로 입력 해주세요.')

		player = self.get_player(ctx)

		if vc.source:
			vc.source.volume = vol / 100

		player.volume = vol / 100
		await ctx.send(f'**`{ctx.author}`**: 님이 볼륨을 **{vol}%** 로 조정하였습니다.')

	@commands.command(name=command[8][0], aliases=command[8][1:])   #정지
	async def stop_(self, ctx):
		"""재생중인 음악을 정지하고 플레이리스트를 초기화 시킵니다."""
		vc = ctx.voice_client

		if not vc or not vc.is_connected():
			return await ctx.send(':no_entry_sign: 현재 접속중인 음악채널이 없습니다.', delete_after=20)

		await self.cleanup(ctx.guild)

	@commands.command(name=command[9][0], aliases=command[9][1:])   #삭제
	async def remove_(self, ctx, *, msg : int):
		"""플레이리스트에 있는 곡을 삭제합니다. ex) !삭제 1"""
		player = self.get_player(ctx)

		# If download is False, source will be a dict which will be used later to regather the stream.
		# If download is True, source will be a discord.FFmpegPCMAudio with a VolumeTransformer.
		if len(player.queue._queue) < msg :
			await ctx.send(':mute: 재생목록에 등록되어 있지 않은 번호 입니다. 다시 입력해주세요.')
			return
				       
		tmp = player.queue._queue[msg-1]

		player.queue._queue.remove(tmp)

		await ctx.send(f'**`{ctx.author}`**: 님이 **`{str(tmp["title"])}`** 을/를 재생목록에서 삭제하였습니다.')

	@commands.command(name=command[10][0], aliases=command[10][1:])   #도움말
	async def menu_(self, ctx):
		command_list = ''
		command_list += ','.join(command[0]) + '\n'     #!입장
		command_list += ','.join(command[1]) + ' [검색어] or [url]\n'     #!재생
		command_list += ','.join(command[2]) + '\n'     #!일시정지
		command_list += ','.join(command[3]) + '\n'     #!다시재생
		command_list += ','.join(command[4]) + '\n'     #!스킵
		command_list += ','.join(command[5]) + '\n'     #!목록
		command_list += ','.join(command[6]) + '\n'     #!현재재생
		command_list += ','.join(command[7]) + '\n'     #!볼륨
		command_list += ','.join(command[8]) + '\n'     #!정지
		command_list += ','.join(command[9]) + '\n'     #!삭제
		embed = discord.Embed(
				title = "----- 명령어 -----",
				description= '```' + command_list + '```',
				color=0xff00ff
				)
		await ctx.send( embed=embed, tts=False)

bot = commands.Bot(command_prefix="", help_command = None, description='일상뮤직봇')

@bot.event
async def on_ready():
	print("Logged in as ") #화면에 봇의 아이디, 닉네임이 출력됩니다.
	print(bot.user.name)
	print(bot.user.id)
	print("===========")
	
	await bot.change_presence(status=discord.Status.dnd, activity=discord.Game(name=command[10][0], type=1), afk = False)

@bot.event
async def on_command_error(ctx, error):
	if isinstance(error, CommandNotFound):
		return
	elif isinstance(error, discord.ext.commands.MissingRequiredArgument):
		return
	raise error

			       
bot.add_cog(Music(bot))
bot.run(access_token)

