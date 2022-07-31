import logging
import re
import os
import json

import discord
from discord.ext import commands

import pymongo


class Taco(commands.Cog):
	def __init__(self, bot, mongo, taco_emoji, no_cooldown_groups):
		self.bot = bot
		self.mongo = mongo
		self.NO_COOLDOWN_GROUPS = no_cooldown_groups
		self.init_cooldown()
		self.logger = logging.getLogger('TacoCog')
		self.TACO_EMOJI = taco_emoji
		self.TACO_REGEX = re.compile(fr'(^|\s+)(<@[0-9]+>\s+)+<?{self.TACO_EMOJI}([0-9]+>)?\s*')


	@commands.Cog.listener('on_message')
	async def watching_out_for_tacos(self, message):
		msg = None
		if message.author.bot == False:
			try:
				if self.TACO_REGEX.search(message.content):
					self.logger.info('It\'s TACO time!!!')
					self.mongo_manage(message)
					await self.notify_sender(message)
					await self.notify_recepients(message)
				else:
					self.logger.debug(f'"{message.author.name}" sent: {message.clean_content}')
			except ValueError as e:
				await message.reply(e)


	@commands.command()
	async def leaderboard(self, message, limit = 5):
		if limit < 1:
			raise commands.errors.BadArgument
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
	def init_cooldown(self):
		db = self.mongo['system']
		if 'cooldown' in db.list_collection_names():
			col = db['cooldown']
			col.drop()
		col = db['cooldown']
		col.create_index('last_used', expireAfterSeconds = 15*60)

	def check_if_user_has_cooldown(self, author):
		author_groups = {group.id for group in author.roles}
		if author_groups.intersection(self.NO_COOLDOWN_GROUPS):
			self.logger.info(f'{author.id} is in a group with no cooldown!')
			return False
		self.logger.info(f'Checking if {author.id} is in cooldown...')
		if [d for d in self.mongo['system']['cooldown'].find({'_id': author.id})]:
			raise ValueError('You recently used this feature, sit in a corner for a little...')
		return True

	def add_user_to_cooldown(self, author):
		self.logger.info(f'Giving {author} a cooldown...')
		self.mongo['system']['cooldown'].insert_one({'_id': author, 'last_used': datetime.utcnow()})


	def get_users(self, message):
		for user in message.mentions:
			yield user.id


	def mongo_manage(self, message):
		db = self.mongo[f'{message.guild.id}']
		col = db['tacos']
		self.check_if_self_ping(message)
		self.check_for_bots(message)
		cooldown = self.check_if_user_has_cooldown(message.author)
		for user in self.get_users(message):
			self.logger.info(f'Adding 1 tacos to {user}...')
			resp = col.update_one({'_id': user, 'tacos': {'$gte': 1}}, {'$inc': {'tacos': 1}})
			if resp.modified_count != 1:
				self.logger.info(f'First taco for {user}!')
				resp = col.insert_one({'_id': user, 'tacos': 1})
		if cooldown:
			self.add_user_to_cooldown(message.author.id)


	def check_if_self_ping(self, message):
		if message.author in message.mentions:
			raise ValueError('Are you kidding me?')


	def check_for_bots(self, message):
		for user in message.mentions:
			if user.bot:
				raise ValueError('Leave the bots out of your games!')


	async def print_leaderboard(self, message, limit):
		db = self.mongo[f'{message.guild.id}']
		col = db['tacos']
		ranking = [d for d in col.find().sort('tacos', pymongo.DESCENDING)]
		embed = discord.Embed(title = f'Top {limit} users with {self.TACO_EMOJI}', colour = discord.Colour.dark_purple())
		for user in ranking[:limit]:
			username = await self.bot.fetch_user(user['_id'])
			embed.add_field(name = username, value = user['tacos'], inline = False)
		await message.reply(embed = embed)


	async def notify_sender(self, message):
		self.logger.info(f'Sending taco confirmation to sender: {message.author.id}')
		recepient_list = ', '.join([user.mention for user in message.mentions])
		await message.author.send(f'You\'ve sent a token of appreciation to: {recepient_list}!\nIt all happened here: {message.jump_url}')


	async def notify_recepients(self, message):
		for recepient in message.mentions:
			self.logger.info(f'Sending taco confirmation to recepient: {recepient.id}')
			await recepient.send(f'You\'ve received a token of appreciation from {message.author.mention}!\nIt all happened here: {message.jump_url}')


async def setup(bot):
	try:
		no_cooldown_groups = os.environ['NO_COOLDOWN_GROUPS'].strip("'")
		no_cooldown_groups = json.loads(no_cooldown_groups)
	except KeyError:
		# No "NO_COOLDOWN_GROUPS" environmental variable was provided, applying cooldowns to everyone'
		no_cooldown_groups = set()
	except json.decoder.JSONDecodeError:
		raise KeyError('The provided "NO_COOLDOWN_GROUPS" environmental variable is an invalid JSON. The format is "NO_COOLDOWN_GROUPS=\'[1111, 2222]\'"')

	try:
		MONGO_SERVER = os.environ.get('MONGO_SERVER', None)
		MONGO_PORT = os.environ.get('MONGO_PORT', 27017)
		taco_emoji = os.environ.get('TACO_EMOJI', '🍆').strip("'")

		mongo = pymongo.MongoClient(f'mongodb://{MONGO_SERVER}:{MONGO_PORT}')
		mongo.admin.command('ping')
	except:
		raise KeyError('Cannot connect to MongoDB')
	await bot.add_cog(Taco(bot, mongo, taco_emoji, no_cooldown_groups))
