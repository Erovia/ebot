#!/usr/bin/env python

import logging
import random
from datetime import datetime
import os
import sys
import re
from pathlib import Path
import math
import json

import requests

import discord
from discord.ext import commands, tasks

import giphy_client

import pymongo


logging.basicConfig(format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s', level = logging.INFO)
botlogger = logging.getLogger('ebot')


###########################################
#
try:
	DISCORD_TOKEN = os.environ['DISCORD_TOKEN']
	GIPHY_TOKEN = os.environ['GIPHY_TOKEN']
except KeyError:
	botlogger.error('Please make sure to pass the Discord API token (DISCORD_TOKEN) and the Giphy API token (G_TOKEN) as environmental variables!')
	sys.exit(1)
#
LIDL_CHANNEL_ID = os.environ.get('LIDL_CHANNEL_ID', None)
FIRST_RUN = os.environ.get('FIRST_RUN', False)
GIPHY_LIMIT = 25
#

THE_LEGEND_REGEX = re.compile(r'show\s+(me\s+)?the\s+legend!*', re.I)
THE_LEGEND_DIR = Path('the_legend')
if THE_LEGEND_DIR.is_dir():
	THE_LEGEND_FILES = [file for file in THE_LEGEND_DIR.iterdir() if file.is_file()]

MONGO_SERVER = os.environ.get('MONGO_SERVER', None)
MONGO_PORT = os.environ.get('MONGO_PORT', 27017)
TACO_EMOJI = os.environ.get('TACO_EMOJI', '🍆').strip("'")
TACO_REGEX = re.compile(fr'(^|\s+)(<@[0-9]+>\s+)+<?{TACO_EMOJI}([0-9]+>)?\s*')
try:
	NO_COOLDOWN_GROUPS = os.environ['NO_COOLDOWN_GROUPS'].strip("'")
	NO_COOLDOWN_GROUPS = json.loads(NO_COOLDOWN_GROUPS)
except KeyError:
	# No "NO_COOLDOWN_GROUPS" environmental variable was provided, applying cooldowns to everyone'
	NO_COOLDOWN_GROUPS = set()
except json.decoder.JSONDecodeError:
	botlogger.error('The provided "NO_COOLDOWN_GROUPS" environmental variable is an invalid JSON. The format is "NO_COOLDOWN_GROUPS=\'[1111, 2222]\'"')
	sys.exit(3)
###########################################


intents = discord.Intents.default()
intents.message_content = True
# intents.members = True

bot = commands.Bot(intents = intents, command_prefix = commands.when_mentioned)

api_instance = giphy_client.DefaultApi()

mongo = pymongo.MongoClient(f'mongodb://{MONGO_SERVER}:{MONGO_PORT}')
try:
	mongo.admin.command('ping')
except:
	botlogger.error('Cannot connect to MongoDB')
	sys.exit(2)


@bot.event
async def on_ready():
	botlogger.info(f'We have logged in as {bot.user}')

	if MONGO_SERVER:
		botlogger.info('Adding Taco Cog...')
		try:
			await bot.add_cog(Taco(bot))
		except commands.CommandError:
			botlogger.error('Error while loading Taco Cog!')
		else:
			botlogger.info('Taco Cog is now running!')
	else:
		botlogger.info('"MONGO_SERVER" env was not provided, skipping Taco Cog...')

	botlogger.info('Adding Egg Cog...')
	try:
		await bot.add_cog(Egg(bot))
	except commands.CommandError:
		botlogger.error('Error while loading Egg Cog!')
	else:
		botlogger.info('Egg Cog is now running!')

	# if LIDL_CHANNEL_ID:
	# 	logging.info('Adding LidlPromo Cog...')
	# 	try:
	# 		await bot.add_cog(LidlPromo(bot))
	# 	except commands.CommandError:
	# 		logging.error('Error while loading LidlPromo Cog!')
	# 	else:
	# 		logging.info('LidlPromo Cog is now running!')
	# else:
	# 	logging.info('LIDL_CHANNEL_ID was not provided, skipping LidlPromo Cog...')


@bot.event
async def on_command_error(ctx, error):
	if isinstance(error, commands.errors.CommandNotFound):
		await ctx.reply('Are you trying to initiate a standard human connection, fellow human?')
	else:
		raise error


###################################################################
class Taco(commands.Cog):
	def __init__(self, bot):
		self.init_cooldown()
		self.logger = logging.getLogger('TacoCog')

	@commands.Cog.listener()
	async def on_message(self, message):
		msg = None
		if message.author.bot == False:
			try:
				if TACO_REGEX.search(message.content):
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
	async def leaderboard_error(self, message, error):
		if isinstance(error, commands.errors.BadArgument):
			await message.reply(f'"{message.current_argument}" is a positive integer since when?!')


#### Taco's helper functions
	def init_cooldown(self):
		db = mongo['system']
		if 'cooldown' in db.list_collection_names():
			col = db['cooldown']
			col.drop()
		col = db['cooldown']
		col.create_index('last_used', expireAfterSeconds = 15*60)

	def check_if_user_has_cooldown(self, author):
		author_groups = {group.id for group in author.roles}
		if author_groups.intersection(NO_COOLDOWN_GROUPS):
			self.logger.info(f'{author.id} is in a group with no cooldown!')
			return False
		self.logger.info(f'Checking if {author.id} is in cooldown...')
		if [d for d in mongo['system']['cooldown'].find({'_id': author.id})]:
			raise ValueError('You recently used this feature, sit in a corner for a little...')
		return True

	def add_user_to_cooldown(self, author):
		self.logger.info(f'Giving {author} a cooldown...')
		mongo['system']['cooldown'].insert_one({'_id': author, 'last_used': datetime.utcnow()})


	def get_users(self, message):
		for user in message.mentions:
			yield user.id

	def mongo_manage(self, message):
		db = mongo[f'{message.guild.id}']
		col = db['tacos']
		self.check_if_self_ping(message)
		cooldown = self.check_if_user_has_cooldown(message.author)
		self.check_for_bots(message)
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
		db = mongo[f'{message.guild.id}']
		col = db['tacos']
		ranking = [d for d in col.find().sort('tacos', pymongo.DESCENDING)]
		embed = discord.Embed(title = f'Top {limit} users with {TACO_EMOJI}', colour = discord.Colour.dark_purple())
		for user in ranking[:limit]:
			username = await bot.fetch_user(user['_id'])
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
###################################################################


###################################################################
class Egg(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.logger = logging.getLogger('EggCog')
		# self.YUGE_REGEX = re.compile(r'[h|y]u+ge', re.IGNORECASE)
		# self.MAYBE_REGEX = re.compile(r'ma+ybe', re.IGNORECASE)
		self.COCOA_REGEX = re.compile(r'(^|\s)cocoa', re.IGNORECASE)
		# self.BAN_REGEX = re.compile(r'(^|\s)ban(\s|$)', re.IGNORECASE)
		self.SENTIENCE_REGEX = re.compile(r'[Aa]re\s+[Yy]ou\s+(.*)\?')
		# self.YUGE_ID = 'l0HefZY0mFfLS9AFa'
		# self.MAYBE_ID = 'gZGlQX3wWAV1u'
		self.SEAGAL_IDS = ('EjFx0jioOoMZq', 'CeMJ1CHY7CJMI', '53JRR3jD18vCw',
                       'fs9BuKuLs7CQWerV1q', '3oz8xyu5a15nCQafq8', 'RxzDe6KVv9SJW',
                       '26gJzhfjTvrFu4JuE', '3o6ZsYxFRLqno054GI', 'l0HlxPSpyojsTLjqM',
                       'l0HlwcbDDfN8I9vhK', 'l0HlPhK8pemiFgF4k', '95wZBAoDFCNYQ',
                       'l0HlJXtvGLbMQYjNS', '11BkowkONO4qGc', 'wcG2ivAWvpQs0',
                       '13FOmRwAHCqLp6', '3o6Ztqb8VuN88HvI0o', 'l0HlJXtvGLbMQYjNS')
		# self.TIT_ID = 'uSGDIb6hP458c'
		# self.BOOBY_ID = 'EExgR4RJV0CM6nfeKQ'
		# self.BAN_IDS= ['CybZqG4etuZsA', '8FJCnrkqkyRzIswceT', 'HXcALJVPgaR4A',
                   # 'C51woXfgJdug', 'fe4dDMD2cAU5RfEaCU']
		# self.GOODBYE_CHANNEL = os.environ.get('GOODBYE_CHANNEL', None)
		# if self.GOODBYE_CHANNEL:
		# 	try:
		# 		self.GOODBYE_CHANNEL = int(self.GOODBYE_CHANNEL)
		# 	except ValueError:
		# 		self.GOODBYE_CHANNEL = None
		# 		self.logger.error('The provide ID for "GOODBYE_CHANNEL" was not its numeric ID!')


	@commands.Cog.listener()
	async def on_message(self, message):
		msg = None
		if message.author.bot == False:
			if bot.user.mentioned_in(message) and len(message.mentions) == 1:
				if message.content == bot.user.mention:
					await message.reply(f"Eeeey, what's up {message.author.mention}?")
				elif question := self.SENTIENCE_REGEX.search(message.clean_content):
					await message.reply(f'Indeed, I am {question.group(1)}!')
			# if asking_for_the_legend := THE_LEGEND_REGEX.search(message.clean_content) and 'THE_LEGEND_FILES' in globals() and isinstance(THE_LEGEND_FILES, list):
			# 	# Sending in multiple parts, as Discord only allows 10 images in one message
			# 	number_of_images = len(THE_LEGEND_FILES)
			# 	for batch in range(0, math.ceil(number_of_images / 10)):
			# 		try:
			# 			files = [discord.File(THE_LEGEND_FILES[i]) for i in range(10 * batch, 10 * batch + 10)]
			# 		except IndexError:
			# 			files = [discord.File(THE_LEGEND_FILES[i]) for i in range(10 * batch, number_of_images)]
			# 		await message.channel.send(files = files)

			if self.COCOA_REGEX.search(message.content):
				msg = self.grab_specific_gif(random.choice(self.SEAGAL_IDS))
			# elif self.YUGE_REGEX.search(message.content):
			# 	msg = self.grab_specific_gif(self.YUGE_ID)
			# elif self.MAYBE_REGEX.search(message.content):
			# 	msg = self.grab_specific_gif(self.MAYBE_ID)
			# elif 'tits' in message.clean_content or 'titties' in message.clean_content:
			# 	msg = self.grab_specific_gif(self.TIT_ID)
			# elif 'boobs' in message.clean_content or 'booby' in message.clean_content or 'boobies' in message.clean_content:
			# 	msg = self.grab_specific_gif(self.BOOBY_ID)
			# elif self.BAN_REGEX.search(message.content):
			# 	msg = self.grab_specific_gif(random.choice(self.BAN_IDS))

		if msg:
			await message.channel.send(msg)


	def grab_random_gif(self, keyword):
		api_response = api_instance.gifs_search_get(GIPHY_TOKEN, keyword, limit = GIPHY_LIMIT)
		url = api_response.data[random.randrange(GIPHY_LIMIT)].images.downsized_small.mp4
		self.logger.info(f'Grabbed random "{keyword}" image: {url}')
		return url

	def grab_specific_gif(self, gif_id):
		api_response = api_instance.gifs_gif_id_get(GIPHY_TOKEN, gif_id)
		url = api_response.data.images.downsized_small.mp4
		self.logger.info(f'Grabbed "{gif_id}" image: {url}')
		return url


	# @commands.Cog.listener()
	# async def on_member_remove(self, member):
	# 	if self.GOODBYE_CHANNEL:
	# 		self.logger.info(f'{member.id} left the server')
	# 		gif = self.grab_random_gif('sassy')
	# 		channel = self.bot.get_channel(self.GOODBYE_CHANNEL)
	# 		# breakpoint()
	# 		if channel:
	# 			await channel.send(f'Buh-bye, {member.name}!')
	# 			await channel.send(gif)
	# 		else:
	# 			self.logger.error(f'Channel "{self.GOODBYE_CHANNEL}" was not found!')
	# 	else:
	# 		self.logger.info('A member left, but no "GOODBYE_CHANNEL" was configured.')


	@commands.command()
	async def foo(self, ctx, arg = None):
		if arg is None:
			msg = 'What do you want dumdum?! Here is a :chocolate_bar:.'
			await ctx.reply(msg)

	# @commands.command()
	# async def cocoa(self, ctx):
	# 	msg = grab_random_seagal_gif()
	# 	await ctx.send(msg)
###################################################################


class LidlPromo(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.channel = bot.get_channel(int(LIDL_CHANNEL_ID))
		if self.channel is None:
			logging.error(f"Couldn't find channel with id '{LIDL_CHANNEL_ID}'")
		else:
			self.apicheck.start()

	def cog_unload(self):
		self.apicheck.cancel()

	@tasks.loop(hours = 1.0)
	async def apicheck(self):
		current_date = datetime.now()
		should_run = True if current_date.hour >= 6 and current_date.hour < 7 else False
		if should_run or FIRST_RUN:
			logging.info('Querying the Lidl Plus API...')
			lidl = LidlDeals()
			lidl.update()
			for deal in lidl:
				embed = discord.Embed(title = deal['title'], color=discord.Color.dark_red())
				embed.add_field(name = deal['offer'], value = deal['offer_desc'])
				embed.set_image(url = deal['image'])

				await self.channel.send(embed = embed)
		else:
			logging.info('API query goes back to sleep...')


class LidlDeals(object):
	def __init__(self, country_code = 'IE'):
		self.country_code = country_code.upper()
		self.url = f'https://coupons.lidlplus.com/api/v1/{self.country_code}/public'
		logging.info(f'Will be using {self.url}')
		self.deals = list()

	def __iter__(self):
		yield from self.deals

	def update(self):
		r = requests.get(self.url)
		if r.ok:
			deals = r.json()
			today = datetime.today().date()
			for deal in deals:
				start_date = datetime.fromisoformat(deal['startValidityDate'].rstrip('Z')).date()
				global FIRST_RUN
				if start_date == today or FIRST_RUN:
					logging.info(f'Found deal: {deal["title"]}')
					self.deals.append({'image': deal['image'], 'title': deal['title'], 'offer': deal['offerTitle'], 'offer_desc': deal['offerDescriptionShort']})
			FIRST_RUN = False
		else:
			logging.error(f'Failed to fetch LidlPLus API: HTTP-{r.status-_code}: {r.reason}')


try:
	bot.run(DISCORD_TOKEN)
except discord.errors.LoginFailure as e:
	botlogger.error(e)
