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
import itertools
import math
from async_timeout import timeout
from functools import partial
import functools
from youtube_dl import YoutubeDL
import youtube_dl
from io import StringIO
import time
import dbkrpy
import urllib.request
from gtts import gTTS

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
access_dbkrtoken = os.environ["dbkrBOT_TOKEN"]

def init():
	global command
	global default_prefix
	global server_prefix

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

	default_prefix = "!"
	server_prefix = {}

	#print (command)

init()

#mp3 파일 생성함수(gTTS 이용, 남성목소리)
async def MakeSound(saveSTR, filename):
	
	tts = gTTS(saveSTR, lang = 'ko')
	tts.save('./' + filename + '.wav')
	'''
	try:
		encText = urllib.parse.quote(saveSTR)
		urllib.request.urlretrieve("https://clova.ai/proxy/voice/api/tts?text=" + encText + "%0A&voicefont=1&format=wav",filename + '.wav')
	except Exception as e:
		print (e)
		tts = gTTS(saveSTR, lang = 'ko')
		tts.save('./' + filename + '.wav')
		pass
	'''
#mp3 파일 재생함수	
async def PlaySound(voiceclient, filename):
	source = discord.FFmpegPCMAudio(filename)
	try:
		voiceclient.play(source)
	except discord.errors.ClientException:
		while voiceclient.is_playing():
			await asyncio.sleep(1)
	while voiceclient.is_playing():
		await asyncio.sleep(1)
	voiceclient.stop()
	source.cleanup()

# Silence useless bug reports messages
youtube_dl.utils.bug_reports_message = lambda: ''


class VoiceError(Exception):
	pass


class YTDLError(Exception):
	pass


class YTDLSource(discord.PCMVolumeTransformer):
	YTDL_OPTIONS = {
		'format': 'bestaudio/best',
		'extractaudio': True,
		'audioformat': 'mp3',
		'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
		'restrictfilenames': True,
		'noplaylist': True,
		'nocheckcertificate': True,
		'ignoreerrors': False,
		'logtostderr': False,
		'quiet': True,
		'no_warnings': True,
		'default_search': 'auto',
		'source_address': '0.0.0.0',
		'force-ipv4' : True,
    		'-4': True
	}

	FFMPEG_OPTIONS = {
		'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
		'options': '-vn',
	}

	ytdl = youtube_dl.YoutubeDL(YTDL_OPTIONS)

	def __init__(self, ctx: commands.Context, source: discord.FFmpegPCMAudio, *, data: dict, volume: float = 0.5):
		super().__init__(source, volume)

		self.requester = ctx.author
		self.channel = ctx.channel
		self.data = data

		self.uploader = data.get('uploader')
		self.uploader_url = data.get('uploader_url')
		date = data.get('upload_date')
		self.upload_date = date[6:8] + '.' + date[4:6] + '.' + date[0:4]
		self.title = data.get('title')
		self.thumbnail = data.get('thumbnail')
		self.description = data.get('description')
		self.duration = self.parse_duration(int(data.get('duration')))
		self.tags = data.get('tags')
		self.url = data.get('webpage_url')
		self.views = data.get('view_count')
		self.likes = data.get('like_count')
		self.dislikes = data.get('dislike_count')
		self.stream_url = data.get('url')

	def __str__(self):
		return '**{0.title}** by **{0.uploader}**'.format(self)

	@classmethod
	async def create_source(cls, ctx: commands.Context, search: str, *, loop: asyncio.BaseEventLoop = None):
		loop = loop or asyncio.get_event_loop()

		partial = functools.partial(cls.ytdl.extract_info, f"ytsearch5:{search}", download=False, process=False)
		data = await loop.run_in_executor(None, partial)

		if data is None:
			raise YTDLError('Couldn\'t find anything that matches `{}`'.format(search))

		emoji_list : list = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
		song_list_str : str = ""
		cnt : int = 0
		song_index : int = 0

		for data_info in data["entries"]:
			cnt += 1
			song_list_str += f"`{cnt}.` [**{data_info['title']}**](https://www.youtube.com/watch?v={data_info['url']})\n"

		embed = discord.Embed(description= song_list_str)
		embed.set_footer(text=f"10초 안에 미선택시 1번 노래가 선택됩니다.")

		song_list_message = await ctx.send(embed = embed)

		for emoji in emoji_list:
			await song_list_message.add_reaction(emoji)

		def reaction_check(reaction, user):
			return (reaction.message.id == song_list_message.id) and (user.id == ctx.author.id) and (str(reaction) in emoji_list)
		try:
			reaction, user = await bot.wait_for('reaction_add', check = reaction_check, timeout = 5)
		except asyncio.TimeoutError:
			reaction = "1️⃣"
		
		if str(reaction) == "1️⃣":
			song_index = 0
		elif str(reaction) == "2️⃣":
			song_index = 1
		elif str(reaction) == "3️⃣":
			song_index = 2
		elif str(reaction) == "4️⃣":
			song_index = 3
		else:
			song_index = 4

		webpage_url = f"https://www.youtube.com/watch?v={data['entries'][song_index]['url']}"
		partial = functools.partial(cls.ytdl.extract_info, webpage_url, download=False)
		processed_info = await loop.run_in_executor(None, partial)

		if processed_info is None:
			raise YTDLError('Couldn\'t fetch `{}`'.format(webpage_url))

		if 'entries' not in processed_info:
			info = processed_info
		else:
			info = None
			while info is None:
				try:
					info = processed_info['entries'].pop(0)
				except IndexError:
					raise YTDLError('Couldn\'t retrieve any matches for `{}`'.format(webpage_url))

		return cls(ctx, discord.FFmpegPCMAudio(info['url'], **cls.FFMPEG_OPTIONS), data=info)

	@staticmethod
	def parse_duration(duration: int):
		return time.strftime('%H:%M:%S', time.gmtime(duration))


class Song:
	__slots__ = ('source', 'requester')

	def __init__(self, source: YTDLSource):
		self.source = source
		self.requester = source.requester

	def create_embed(self):
		embed = (discord.Embed(title='Now playing',
							description='```css\n{0.source.title}\n```'.format(self),
							color=discord.Color.blurple())
				.add_field(name='Duration', value=self.source.duration)
				.add_field(name='Requested by', value=self.requester.mention)
				.add_field(name='Uploader', value='[{0.source.uploader}]({0.source.uploader_url})'.format(self))
				.add_field(name='URL', value='[Click]({0.source.url})'.format(self))
				.set_thumbnail(url=self.source.thumbnail))

		return embed


class SongQueue(asyncio.Queue):
	def __getitem__(self, item):
		if isinstance(item, slice):
			return list(itertools.islice(self._queue, item.start, item.stop, item.step))
		else:
			return self._queue[item]

	def __iter__(self):
		return self._queue.__iter__()

	def __len__(self):
		return self.qsize()

	def clear(self):
		self._queue.clear()

	def shuffle(self):
		random.shuffle(self._queue)

	def remove(self, index: int):
		del self._queue[index]


class VoiceState:
	def __init__(self, bot: commands.Bot, ctx: commands.Context):
		self.bot = bot
		self._ctx = ctx
		self._cog = ctx.cog

		self.current = None
		self.voice = None
		self.next = asyncio.Event()
		self.songs = SongQueue()

		self._loop = False
		self._volume = 0.5
		self.skip_votes = set()

		self.audio_player = bot.loop.create_task(self.audio_player_task())

	def __del__(self):
		self.audio_player.cancel()

	@property
	def loop(self):
		return self._loop

	@loop.setter
	def loop(self, value: bool):
		self._loop = value

	@property
	def volume(self):
		return self._volume

	@volume.setter
	def volume(self, value: float):
		self._volume = value

	@property
	def is_playing(self):
		return self.voice and self.current

	async def audio_player_task(self):
		while True:
			self.next.clear()

			if self.loop and self.current is not None:
				source1 = await YTDLSource.create_source(self._ctx, self.current.source.url, loop=self.bot.loop)
				song1 = Song(source1)
				await self.songs.put(song1)
			else:
				pass

			try:
				async with timeout(180):  # 3 minutes
					self.current = await self.songs.get()
			except asyncio.TimeoutError:
				self.bot.loop.create_task(self.stop())
				return

			self.current.source.volume = self._volume
			self.voice.play(self.current.source, after=self.play_next_song)
			play_info_msg = await self.current.source.channel.send(embed=self.current.create_embed())
			await play_info_msg.delete(delay = 20)
			
			await self.next.wait()

	def play_next_song(self, error=None):
		if error:
			raise VoiceError(str(error))

		self.next.set()

	def skip(self):
		self.skip_votes.clear()

		if self.is_playing:
			self.voice.stop()

	async def stop(self):
		self.songs.clear()

		if self.voice:
			await self.voice.disconnect()
			self.voice = None

		self.bot.loop.create_task(self._cog.cleanup(self._ctx))

class Music(commands.Cog):
	def __init__(self, bot: commands.Bot):
		self.bot = bot
		self.voice_states = {}

	def get_voice_state(self, ctx: commands.Context):
		state = self.voice_states.get(ctx.guild.id)
		if not state:
			state = VoiceState(self.bot, ctx)
			self.voice_states[ctx.guild.id] = state

		return state

	def cog_unload(self):
		for state in self.voice_states.values():
			self.bot.loop.create_task(state.stop())

	def cog_check(self, ctx: commands.Context):
		if not ctx.guild:
			raise commands.NoPrivateMessage('This command can\'t be used in DM channels.')

		return True

	async def cog_before_invoke(self, ctx: commands.Context):
		ctx.voice_state = self.get_voice_state(ctx)

	async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
		await ctx.send('에러 : {}'.format(str(error)))
	'''
	@commands.command(name='join', invoke_without_subcommand=True)
	async def _join(self, ctx: commands.Context):
		destination = ctx.author.voice.channel
		if ctx.voice_state.voice:
			await ctx.voice_state.voice.move_to(destination)
			return
		ctx.voice_state.voice = await destination.connect()
	'''
	async def cleanup(self, ctx: commands.Context):
		del self.voice_states[ctx.guild.id]

	@commands.command(name=command[0][0], aliases=command[0][1:])
	#@commands.has_permissions(manage_guild=True)
	async def _summon(self, ctx: commands.Context, *, channel: discord.VoiceChannel = None):
		if not channel and not ctx.author.voice:
			raise VoiceError(':no_entry_sign: 현재 접속중인 음악채널이 없습니다.')

		destination = channel or ctx.author.voice.channel
		if ctx.voice_state.voice:
			await ctx.voice_state.voice.move_to(destination)
			return

		ctx.voice_state.voice = await destination.connect()

	@commands.command(name=command[1][0], aliases=command[1][1:])
	#@commands.has_permissions(manage_guild=True)
	async def _leave(self, ctx: commands.Context):
		if not ctx.voice_state.voice:
			return await ctx.send(':no_entry_sign: 현재 접속중인 음악채널이 없습니다.')

		await ctx.voice_state.stop()
		del self.voice_states[ctx.guild.id]

	@commands.command(name=command[8][0], aliases=command[8][1:])
	async def _volume(self, ctx: commands.Context, *, volume: int):
		vc = ctx.voice_client

		if not ctx.voice_state.is_playing:
			return await ctx.send(':mute: 현재 재생중인 음악이 없습니다.')

		if not 0 < volume < 101:
			return await ctx.send('```볼륨은 1 ~ 100 사이로 입력 해주세요.```')

		if vc.source:
			vc.source.volume = volume / 100

		ctx.voice_state.volume = volume / 100
		await ctx.send(':loud_sound: 볼륨을 {}%로 조정하였습니다.'.format(volume))

	@commands.command(name=command[7][0], aliases=command[7][1:])
	async def _now(self, ctx: commands.Context):
		await ctx.send(embed=ctx.voice_state.current.create_embed())

	@commands.command(name=command[3][0], aliases=command[3][1:])
	#@commands.has_permissions(manage_guild=True)
	async def _pause(self, ctx: commands.Context):
		if ctx.voice_state.is_playing and ctx.voice_state.voice.is_playing():
			ctx.voice_state.voice.pause()
			await ctx.message.add_reaction('⏸')

	@commands.command(name=command[4][0], aliases=command[4][1:])
	#@commands.has_permissions(manage_guild=True)
	async def _resume(self, ctx: commands.Context):
		if ctx.voice_state.is_playing and ctx.voice_state.voice.is_paused():
			ctx.voice_state.voice.resume()
			await ctx.message.add_reaction('⏯')

	@commands.command(name=command[9][0], aliases=command[9][1:])
	#@commands.has_permissions(manage_guild=True)
	async def _stop(self, ctx: commands.Context):
		ctx.voice_state.songs.clear()

		if ctx.voice_state.is_playing:
			ctx.voice_state.voice.stop()
			await ctx.message.add_reaction('⏹')

	@commands.command(name=command[5][0], aliases=command[5][1:])
	async def _skip(self, ctx: commands.Context):
		if not ctx.voice_state.is_playing:
			return await ctx.send(':mute: 현재 재생중인 음악이 없습니다.')

		await ctx.message.add_reaction('⏭')
		ctx.voice_state.skip()
		'''	
		voter = ctx.message.author
		if voter == ctx.voice_state.current.requester:
			await ctx.message.add_reaction('⏭')
			ctx.voice_state.skip()
		elif voter.id not in ctx.voice_state.skip_votes:
			ctx.voice_state.skip_votes.add(voter.id)
			total_votes = len(ctx.voice_state.skip_votes)
			if total_votes >= 3:
				await ctx.message.add_reaction('⏭')
				ctx.voice_state.skip()
			else:
				await ctx.send('Skip vote added, currently at **{}/3**'.format(total_votes))
		else:
			await ctx.send('```이미 투표하셨습니다.```')
		'''
	@commands.command(name=command[6][0], aliases=command[6][1:])
	async def _queue(self, ctx: commands.Context, *, page: int = 1):

		if len(ctx.voice_state.songs) == 0:
			return await ctx.send(':mute: 재생목록이 없습니다.')

		items_per_page = 10
		pages = math.ceil(len(ctx.voice_state.songs) / items_per_page)

		start = (page - 1) * items_per_page
		end = start + items_per_page

		queue = ''
		for i, song in enumerate(ctx.voice_state.songs[start:end], start=start):
			queue += '`{0}.` [**{1.source.title}**]({1.source.url})\n'.format(i + 1, song)

		embed = (discord.Embed(description='**{} tracks:**\n\n{}'.format(len(ctx.voice_state.songs), queue))
				.set_footer(text='Viewing page {}/{}'.format(page, pages)))
		await ctx.send(embed=embed)

	@commands.command(name=command[11][0], aliases=command[11][1:])
	async def _shuffle(self, ctx: commands.Context):
		if len(ctx.voice_state.songs) == 0:
			return await ctx.send(':mute: 재생목록이 없습니다.')

		ctx.voice_state.songs.shuffle()
		result = await ctx.send('셔플 완료!')
		await result.add_reaction('🔀')

	@commands.command(name=command[10][0], aliases=command[10][1:])
	async def _remove(self, ctx: commands.Context, index: int):
		if len(ctx.voice_state.songs) == 0:
			return await ctx.send(':mute: 재생목록이 없습니다.')
		
		remove_result = '`{0}.` [**{1.source.title}**] 삭제 완료!\n'.format(index, ctx.voice_state.songs[index - 1])
		result = await ctx.send(remove_result)
		ctx.voice_state.songs.remove(index - 1)
		await result.add_reaction('✅')
		

	@commands.command(name=command[14][0], aliases=command[14][1:])
	async def _loop(self, ctx: commands.Context):
		if not ctx.voice_state.is_playing:
			return await ctx.send(':mute: 현재 재생중인 음악이 없습니다.')

		# Inverse boolean value to loop and unloop.
		ctx.voice_state.loop = not ctx.voice_state.loop
		if ctx.voice_state.loop :
			result = await ctx.send('반복재생이 설정되었습니다!')
		else:
			result = await ctx.send('반복재생이 취소되었습니다!')
		await result.add_reaction('🔁')

	@commands.command(name=command[2][0], aliases=command[2][1:])
	async def _play(self, ctx: commands.Context, *, search: str):
		if not ctx.voice_state.voice:
			await ctx.invoke(self._summon)

		async with ctx.typing():
			try:
				source = await YTDLSource.create_source(ctx, search, loop=self.bot.loop)
			except YTDLError as e:
				await ctx.send('에러가 발생했습니다 : {}'.format(str(e)))
			else:
				song = Song(source)

				await ctx.voice_state.songs.put(song)
				await ctx.send('재생목록 추가 : {}'.format(str(source)))
				
	@commands.command(name=command[13][0], aliases=command[13][1:])
	async def race_(self, ctx: commands.Context, *, msg: str):
		#msg = ctx.message.content[len(ctx.invoked_with)+1:]
		race_info = []
		fr = []
		racing_field = []
		str_racing_field = []
		cur_pos = []
		race_val = []
		random_pos = []
		racing_result = []
		output = ':camera: :camera: :camera: 신나는 레이싱! :camera: :camera: :camera:\n'
		#racing_unit = [':giraffe:', ':elephant:', ':tiger2:', ':hippopotamus:', ':crocodile:',':leopard:',':ox:', ':sheep:', ':pig2:',':dromedary_camel:',':dragon:',':rabbit2:'] #동물스킨
		racing_unit = [':red_car:', ':taxi:', ':bus:', ':trolleybus:', ':race_car:', ':police_car:', ':ambulance:', ':fire_engine:', ':minibus:', ':truck:', ':articulated_lorry:', ':tractor:', ':scooter:', ':manual_wheelchair:', ':motor_scooter:', ':auto_rickshaw:', ':blue_car:', ':bike:', ':helicopter:', ':steam_locomotive:']  #탈것스킨
		random.shuffle(racing_unit) 
		racing_member = msg.split(" ")

		'''
		racing_unit = []
		emoji = discord.Emoji
		emoji = ctx.message.guild.emojis
		for j in range(len(tmp_racing_unit)):
			racing_unit.append(':' + tmp_racing_unit[j] + ':')
			for i in range(len(emoji)):
				if emoji[i].name == tmp_racing_unit[j].strip(":"):
					racing_unit[j] = '<:' + tmp_racing_unit[j] + ':' + str(emoji[i].id) + '>'
		random.shuffle(racing_unit)
		'''
		field_size = 60
		tmp_race_tab = 35 - len(racing_member)
		if len(racing_member) <= 1:
			await ctx.send('레이스 인원이 2명보다 작습니다.')
			return
		elif len(racing_member) >= 13:
			await ctx.send('레이스 인원이 12명 초과입니다.')
			return
		else :
			race_val = random.sample(range(tmp_race_tab, tmp_race_tab+len(racing_member)), len(racing_member))
			random.shuffle(race_val)
			for i in range(len(racing_member)):
				fr.append(racing_member[i])
				fr.append(racing_unit[i])
				fr.append(race_val[i])
				race_info.append(fr)
				fr = []
				for i in range(field_size):
					fr.append(" ")
				racing_field.append(fr)
				fr = []

			for i in range(len(racing_member)):
				racing_field[i][0] = "|"
				racing_field[i][field_size-2] = race_info[i][1]
				if len(race_info[i][0]) > 5:
					racing_field[i][field_size-1] = "| " + race_info[i][0][:5] + '..'
				else:
					racing_field[i][field_size-1] = "| " + race_info[i][0]
				str_racing_field.append("".join(racing_field[i]))
				cur_pos.append(field_size-2)

			for i in range(len(racing_member)):
				output +=  str_racing_field[i] + '\n'

			result_race = await ctx.send(output + ':traffic_light: 3초 후 경주가 시작됩니다!')
			await asyncio.sleep(1)
			await result_race.edit(content = output + ':traffic_light: 2초 후 경주가 시작됩니다!')
			await asyncio.sleep(1)
			await result_race.edit(content = output + ':traffic_light: 1초 후 경주가 시작됩니다!')
			await asyncio.sleep(1)
			await result_race.edit(content = output + ':checkered_flag:  경주 시작!')								

			for i in range(len(racing_member)):
				test = random.sample(range(2,field_size-2), race_info[i][2])
				while len(test) != tmp_race_tab + len(racing_member)-1 :
					test.append(1)
				test.append(1)
				test.sort(reverse=True)
				random_pos.append(test)

			for j in range(len(random_pos[0])):
				if j%2 == 0:
					output =  ':camera: :camera_with_flash: :camera: 신나는 레이싱! :camera_with_flash: :camera: :camera_with_flash:\n'
				else :
					output =  ':camera_with_flash: :camera: :camera_with_flash: 신나는 레이싱! :camera: :camera_with_flash: :camera:\n'
				str_racing_field = []
				for i in range(len(racing_member)):
					temp_pos = cur_pos[i]
					racing_field[i][random_pos[i][j]], racing_field[i][temp_pos] = racing_field[i][temp_pos], racing_field[i][random_pos[i][j]]
					cur_pos[i] = random_pos[i][j]
					str_racing_field.append("".join(racing_field[i]))

				await asyncio.sleep(1) 

				for i in range(len(racing_member)):
					output +=  str_racing_field[i] + '\n'

				await result_race.edit(content = output + ':checkered_flag:  경주 시작!')

			for i in range(len(racing_field)):
				fr.append(race_info[i][0])
				fr.append((race_info[i][2]) - tmp_race_tab + 1)
				racing_result.append(fr)
				fr = []

			result = sorted(racing_result, key=lambda x: x[1])

			result_str = ''
			for i in range(len(result)):
				if result[i][1] == 1:
					result[i][1] = ':first_place:'
				elif result[i][1] == 2:
					result[i][1] = ':second_place:'
				elif result[i][1] == 3:
					result[i][1] = ':third_place:'
				elif result[i][1] == 4:
					result[i][1] = ':four:'
				elif result[i][1] == 5:
					result[i][1] = ':five:'
				elif result[i][1] == 6:
					result[i][1] = ':six:'
				elif result[i][1] == 7:
					result[i][1] = ':seven:'
				elif result[i][1] == 8:
					result[i][1] = ':eight:'
				elif result[i][1] == 9:
					result[i][1] = ':nine:'
				elif result[i][1] == 10:
					result[i][1] = ':keycap_ten:'
				else:
					result[i][1] = ':x:'
				result_str += result[i][1] + "  " + result[i][0] + "  "

			#print(result)
			await asyncio.sleep(1)
			await result_race.edit(content = output + ':tada: 경주 종료!\n' + result_str)

	@commands.command(name="!hellothisisverification")
	async def verification_(self, ctx: commands.Context, *, msg: str=None):
		await ctx.send('일상#7025(chochul12@gmail.com')

	@commands.command(name=command[15][0], aliases=command[15][1:])
	async def change_prefix_(self, ctx: commands.Context, *, msg: str=None):
		server_prefix[ctx.guild.id] = msg.split()
		await ctx.send(f"```명령어 [{msg}]로 변경완료!```")
		
	@_summon.before_invoke
	@_play.before_invoke
	async def ensure_voice_state(self, ctx: commands.Context):
		if not ctx.author.voice or not ctx.author.voice.channel:
			raise commands.CommandError('음성채널에 접속 후 사용해주십시오.')

		if ctx.voice_client:
			if ctx.voice_client.channel != ctx.author.voice.channel:
				raise commands.CommandError('봇이 이미 음성채널에 접속해 있습니다.')
				
	@commands.command(name="채팅청소")
	async def clear_channel_(self, ctx: commands.Context, *, msg: int = 1):
		try:
			msg = int(msg)
		except:
			await ctx.send(f"```지우고 싶은 줄수는 [숫자]로 입력해주세요!```")
		await ctx.channel.purge(limit = msg)

	@commands.command(name=command[12][0], aliases=command[12][1:])   #도움말
	async def menu_(self, ctx):
		if ctx.guild.id in server_prefix:
			curr_prefix = ', '.join(server_prefix[ctx.guild.id])
		else:
			curr_prefix = default_prefix
		command_list = '```현재 설정된 접두어 : ' + curr_prefix + '\n```'
		command_list += '```'
		command_list += '접두어 + ' + '인중 : 봇상태가 안좋을 때 쓰세요!\n'     #!
		command_list += '접두어 + ' + ','.join(command[0]) + '\n'     #!들어가자
		command_list += '접두어 + ' + ','.join(command[1]) + '\n'     #!나가자
		command_list += '접두어 + ' + ','.join(command[2]) + ' [검색어] or [url]\n'     #!재생
		command_list += '접두어 + ' + ','.join(command[3]) + '\n'     #!일시정지
		command_list += '접두어 + ' + ','.join(command[4]) + '\n'     #!다시재생
		command_list += '접두어 + ' + ','.join(command[5]) + '\n'     #!스킵
		command_list += '접두어 + ' + ','.join(command[6]) + ' 혹은 [명령어] + [숫자]\n'     #!목록
		command_list += '접두어 + ' + ','.join(command[7]) + '\n'     #!현재재생
		command_list += '접두어 + ' + ','.join(command[8]) + ' [숫자 1~100]\n'     #!볼륨
		command_list += '접두어 + ' + ','.join(command[9]) + '\n'     #!정지
		command_list += '접두어 + ' + ','.join(command[10]) + '\n'     #!삭제
		command_list += '접두어 + ' + ','.join(command[11]) + '\n'     #!섞기
		command_list += '접두어 + ' + ','.join(command[14]) + '\n'     #!
		command_list += '접두어 + ' + ','.join(command[15]) + ' + 원하는 접두어(! @ # $ 빈칸으로 여러개 가능)\n'     #접두어
		command_list += '접두어 + ' + ','.join(command[13]) + ' 아이디1 아이디2 아이디3 ....\n```'     #!경주
		command_list += "```기본 접두어 : !\n※ 개인설정한 접두어는 봇 재시작시 초기화됩니다.```"     #!경주
		embed = discord.Embed(
				title = "----- 명령어 -----",
				description = command_list,
				color=0xff00ff
				)
		await ctx.send( embed=embed, tts=False)
	################ 음성파일 생성 후 재생 ################ 			
	@commands.command(name="인중")
	async def playText_(self, ctx):
		#msg = ctx.message.content[len(ctx.invoked_with)+1:]
		#sayMessage = msg
		await MakeSound('뮤직봇이 마이 아파요. 잠시 후 사용해주세요.', './say' + str(ctx.guild.id))
		await ctx.send("```뮤직봇이 마이 아파요. 잠시 후 사용해주세요.```", tts=False)
		
		if not ctx.voice_state.voice:
			await ctx.invoke(self._summon)
			
		if ctx.voice_state.is_playing:
			ctx.voice_state.voice.stop()
		
		await PlaySound(ctx.voice_state.voice, './say' + str(ctx.guild.id) + '.wav')

		await ctx.voice_state.stop()
		del self.voice_states[ctx.guild.id]

def get_prefix(bot, msg):
	if msg.author.bot: #만약 메시지를 보낸사람이 봇일 경우에는
		return None #동작하지 않고 무시합니다.
	
	if msg.guild.id in server_prefix:
		return commands.when_mentioned_or(*server_prefix[msg.guild.id])(bot, msg)

	return commands.when_mentioned_or(*default_prefix)(bot, msg)

bot = commands.Bot(command_prefix=get_prefix, help_command = None, description='해성뮤직봇')
bot.add_cog(Music(bot))

@bot.event
async def on_ready():
	print("Logged in as ") #화면에 봇의 아이디, 닉네임이 출력됩니다.
	print(bot.user.name)
	print(bot.user.id)
	print("===========")
	
	await bot.change_presence(status=discord.Status.dnd, activity=discord.Game(name=command[12][0], type=1), afk = False)

@bot.event 
async def on_command_error(ctx, error):
	if isinstance(error, CommandNotFound):
		return
	elif isinstance(error, discord.ext.commands.MissingRequiredArgument):
		return
	raise error

dbkrpy.UpdateGuilds(bot, access_dbkrtoken)
bot.run(access_token)
