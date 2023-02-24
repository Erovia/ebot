import logging
import re
import os
import json
from random import choice
from datetime import datetime, timezone

import discord
from discord.ext import commands

import pymongo


class Taco(commands.Cog):
	def __init__(self, bot, mongo, emojis, no_cooldown_groups, sassy_reply_users):
		self.bot = bot
		self.mongo = mongo
		self.NO_COOLDOWN_GROUPS = no_cooldown_groups
		self.SASSY_REPLY_USERS = sassy_reply_users
		botlogger = logging.getLogger('ebot')
		self.logger = botlogger.getChild('TacoCog')
		self.EMOJI_MAP = self._emoji_mapper(emojis)
		self.SASSY_RESPONSES = ('Bruh...', 'My creator gave on up the idea of explaining this to you, so let me give it a try:\n\n@name <placeholder_for_emoji> Any optional message', 'Let\'s give this another shot, shall we?', 'Seriously?', '(‡ಠ╭╮ಠ)')


	@commands.Cog.listener('on_message')
	async def watching_out_for_tacos(self, message):
		if message.author.bot == False and not isinstance(message.channel, discord.channel.DMChannel):
			msg = None
			server = message.guild.id
			try:
				regex = self.EMOJI_MAP[server]['regex'] if server in self.EMOJI_MAP else self.EMOJI_MAP['default']['regex']
				if regex.search(message.content):
					self.logger.debug('It\'s TACO time!!!')
					self.mongo_manage(message)
					await self.notify_sender(message)
					await self.notify_recepients(message)
				elif self.SASSY_REPLY_USERS and message.author.id in self.SASSY_REPLY_USERS and len(message.mentions) > 0 and self.EMOJI_MAP[server]['emoji'] in message.content:
					self.logger.debug('It\'s sassyness time!!!')
					await self.send_sassy_reply(message)
				else:
					self.logger.debug(f'"{message.author.name}" sent: {message.clean_content}')
			except ValueError as e:
				await message.reply(e)


	@commands.command()
	async def leaderboard(self, message, limit = 5):
		if limit < 1:
			raise commands.errors.BadArgument
		if limit > 50:
			limit = 50
		await self.print_leaderboard(message, limit)

	@leaderboard.error
	async def leaderboard_error(self, ctx, error):
		if isinstance(error, commands.errors.BadArgument):
			#TODO: Figure out why traceback is still printed on console for BadArgument exceptions
			#      Found only this relevant thread, but did not help: https://stackoverflow.com/a/58713699
			await ctx.reply(f'"{ctx.current_argument}" is a positive integer since when?!')
		else:
			raise error


#### Taco's helper functions
	def _emoji_mapper(self, emojis):
		emoji_map = dict()
		emojis['default'] = '🍆'
		for server, emoji in emojis.items():
			regex = re.compile(fr'(^|\s+)(<@[0-9]+>\s+)+<?{emoji}([0-9]+>)?\s*')
			server = int(server) if server.isnumeric() else server
			emoji_map[server] = {'emoji': emoji, 'regex': regex}
		return emoji_map

	def _init_cooldown(self, db):
		if 'cooldown' not in db.list_collection_names():
			col = db['cooldown']
			col.create_index('last_used', expireAfterSeconds = 15*60)

	def check_if_user_has_cooldown(self, db, author):
		author_groups = {group.id for group in author.roles}
		if author_groups.intersection(self.NO_COOLDOWN_GROUPS):
			self.logger.debug(f'{author.id} is in a group with no cooldown!')
			return False
		self.logger.debug(f'Checking if {author.id} is in cooldown...')
		if [d for d in db['cooldown'].find({'_id': author.id})]:
			raise ValueError('You recently used this feature, sit in a corner for a little...')
		return True

	def add_user_to_cooldown(self, db, author):
		self.logger.debug(f'Giving {author} a cooldown...')
		db['cooldown'].insert_one({'_id': author, 'last_used': datetime.now(timezone.utc)})


	def get_users(self, message):
		for user in message.mentions:
			yield user.id


	def mongo_manage(self, message):
		self.check_if_self_ping(message)
		self.check_for_bots(message)
		db = self.mongo[f'{message.guild.id}']
		self._init_cooldown(db)
		col = db['tacos']
		cooldown = self.check_if_user_has_cooldown(db, message.author)
		for user in self.get_users(message):
			self.logger.debug(f'Adding 1 tacos to {user}...')
			resp = col.update_one({'_id': user, 'tacos': {'$gte': 1}}, {'$inc': {'tacos': 1}})
			if resp.modified_count != 1:
				self.logger.debug(f'First taco for {user}!')
				resp = col.insert_one({'_id': user, 'tacos': 1})
		if cooldown:
			self.add_user_to_cooldown(db, message.author.id)


	def check_if_self_ping(self, message):
		if message.author in message.mentions:
			raise ValueError('Are you kidding me?')


	def check_for_bots(self, message):
		if any([user.bot for user in message.mentions]):
			raise ValueError('Leave the bots out of your games!')


	async def print_leaderboard(self, message, limit):
		server = message.guild.id
		db = self.mongo[f'{server}']
		col = db['tacos']
		ranking = [d for d in col.find().sort('tacos', pymongo.DESCENDING)]
		emoji = self.EMOJI_MAP[server]['emoji'] if server in self.EMOJI_MAP else self.EMOJI_MAP['default']['emoji']
		embed = discord.Embed(title = f'Top {limit} users with {emoji}', colour = discord.Colour.dark_purple())
		for user in ranking[:limit]:
			username = await self.bot.fetch_user(user['_id'])
			embed.add_field(name = username, value = user['tacos'], inline = False)
		await message.reply(embed = embed)


	async def notify_sender(self, message):
		self.logger.debug(f'Sending taco confirmation to sender: {message.author.id}')
		recepient_list = ', '.join([user.mention for user in message.mentions])
		await message.author.send(f'You\'ve sent a token of appreciation to: {recepient_list}!\nIt all happened here: {message.jump_url}', silent = True)


	async def notify_recepients(self, message):
		for recepient in message.mentions:
			self.logger.debug(f'Sending taco confirmation to recepient: {recepient.id}')
			await recepient.send(f'You\'ve received a token of appreciation from {message.author.mention}!\nIt all happened here: {message.jump_url}', silent = True)


	async def send_sassy_reply(self, message):
		self.logger.debug(f'User {message.author.id} did not use the correct taco sending format, sending sassy response.')
		await message.reply(choice(self.SASSY_RESPONSES))


async def setup(bot):
	try:
		no_cooldown_groups = os.environ['NO_COOLDOWN_GROUPS'].strip("'")
		no_cooldown_groups = json.loads(no_cooldown_groups)
	except KeyError:
		# No "NO_COOLDOWN_GROUPS" environmental variable was provided, applying cooldowns to everyone
		no_cooldown_groups = set()
	except json.decoder.JSONDecodeError:
		raise KeyError('The provided "NO_COOLDOWN_GROUPS" environmental variable is an invalid JSON. The format is "NO_COOLDOWN_GROUPS=\'[1111, 2222]\'"')

	try:
		sassy_reply_users = os.environ['SASSY_REPLY_USERS'].strip("'")
		sassy_reply_users = json.loads(sassy_reply_users)
	except KeyError:
		# No "SASSY_REPLY_USERS" environmental variable was provided, not using sassyness
		sassy_reply_users = set()
	except json.decoder.JSONDecodeError:
		raise KeyError('The provided "SASSY_REPLY_USERS" environmental variable is an invalid JSON. The format is "SASSY_REPLY_USERS=\'[1111, 2222]\'"')

	try:
		emojis = os.environ['EMOJIS'].strip("'")
		emojis = json.loads(emojis)
	except KeyError:
		# No "EMOJIS" environmental variable was provided, the default will be used for every server
		emojis = dict()
	except json.decoder.JSONDecodeError:
		raise KeyError('The provided "EMOJIS" environmental variable is an invalid JSON. The format is "\'{"server1_id": "emoji1", "server2_id": "emoji2"}\'"')
	

	try:
		MONGO_SERVER = os.environ.get('MONGO_SERVER', None)
		MONGO_PORT = os.environ.get('MONGO_PORT', 27017)

		mongo = pymongo.MongoClient(f'mongodb://{MONGO_SERVER}:{MONGO_PORT}')
		mongo.admin.command('ping')
	except:
		raise KeyError('Cannot connect to MongoDB')
	await bot.add_cog(Taco(bot, mongo, emojis, no_cooldown_groups, sassy_reply_users))
