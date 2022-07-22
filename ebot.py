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
SENTIENCE_REGEX = re.compile(r'[Aa]re\s+[Yy]ou\s+(.*)\?')

THE_LEGEND_REGEX = re.compile(r'show\s+(me\s+)?the\s+legend!*', re.I)
THE_LEGEND_DIR = Path('the_legend')
if THE_LEGEND_DIR.is_dir():
	THE_LEGEND_FILES = [file for file in THE_LEGEND_DIR.iterdir() if file.is_file()]

MONGO_SERVER = os.environ.get('MONGO_SERVER', None)
MONGO_PORT = os.environ.get('MONGO_PORT', 27017)
TACO_EMOJI = os.environ.get('TACO_EMOJI', '🍆')
TACO_REGEX = re.compile(fr'^\s*(<@[0-9]+>\s+)+{TACO_EMOJI}\s*')
try:
	NO_COOLDOWN_GROUPS = os.environ['NO_COOLDOWN_GROUPS']
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

bot = commands.Bot(intents = intents, command_prefix = commands.when_mentioned)

api_instance = giphy_client.DefaultApi()

mongo = pymongo.MongoClient(f'mongodb://{MONGO_SERVER}:{MONGO_PORT}')
try:
	mongo.admin.command('ping')
except:
	botlogger.error('Cannot connect to MongoDB')
	sys.exit(2)


def grab_random_gif(keyword):
	api_response = api_instance.gifs_search_get(GIPHY_TOKEN, keyword, limit = GIPHY_LIMIT)
	url = api_response.data[random.randrange(GIPHY_LIMIT)].images.downsized_small.mp4
	logging.info(f'Grabbed random "{keyword}" image: {url}')
	return url


def grab_random_pika_gif():
	return grab_random_gif('pikachu')


def grab_random_seagal_gif():
	return grab_random_gif('steven seagal')


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

	# logging.info('Adding Pika Cog...')
	# try:
	# 	await bot.add_cog(Pika(bot))
	# except commands.CommandError:
	# 	logging.error('Error while loading Pika Cog!')
	# else:
	# 	logging.info('Pika Cog is now running!')

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


@bot.command()
async def foo(ctx, arg = None):
	if arg is None:
		msg = 'What do you want dumdum?!'
	else:
		msg = arg
	await ctx.send(msg)


# @bot.event
# async def on_message(message):
# 	if message.author.bot == False:
# 		if bot.user.mentioned_in(message) and len(message.mentions) == 1:
# 			if message.content == bot.user.mention:
# 				await message.channel.send(f"Eeeey, what's up {message.author.mention}?")
# 			elif question := SENTIENCE_REGEX.search(message.clean_content):
# 				await message.channel.send(f'Indeed, I am {question.group(1)}!')
# 			else:
# 				await bot.process_commands(message)


###################################################################
class Taco(commands.Cog):
	def __init__(self, bot):
		self.init_cooldown()
		self.logger = logging.getLogger('TacoCog')

	@commands.Cog.listener()
	async def on_message(self, message):
		msg = None
		if message.author.bot == False:
			# breakpoint()
			try:
				if TACO_REGEX.search(message.content):
					self.logger.info('It\'s TACO time!!!')
					self.mongo_manage(message)
				else:
					self.logger.debug(f'"{message.author.name}" sent: {message.clean_content}')
			except ValueError as e:
				await message.reply(e)


	@commands.command()
	async def leaderboard(self, message):
		await self.print_leaderboard(message)


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


	async def print_leaderboard(self, message):
		db = mongo[f'{message.guild.id}']
		col = db['tacos']
		ranking = [d for d in col.find().sort('tacos', pymongo.DESCENDING)]
		embed = discord.Embed(title = f'Top 25 users with {TACO_EMOJI}', colour = discord.Colour.dark_purple())
		# embed = discord.Embed(title = 'Top 25 users with 🍆', colour = discord.Colour.dark_purple())
		for user in ranking[:25]:
			username = await bot.fetch_user(user['_id'])
			embed.add_field(name = username, value = user['tacos'], inline = False)
		await message.reply(embed = embed)
###################################################################


class Pika(commands.Cog):
	@commands.Cog.listener()
	async def on_message(self, message):
		msg = None
		if message.author.bot == False:
			if asking_for_the_legend := THE_LEGEND_REGEX.search(message.clean_content) and 'THE_LEGEND_FILES' in globals() and isinstance(THE_LEGEND_FILES, list):
				# Sending in multiple parts, as Discord only allows 10 images in one message
				number_of_images = len(THE_LEGEND_FILES)
				for batch in range(0, math.ceil(number_of_images / 10)):
					try:
						files = [discord.File(THE_LEGEND_FILES[i]) for i in range(10 * batch, 10 * batch + 10)]
					except IndexError:
						files = [discord.File(THE_LEGEND_FILES[i]) for i in range(10 * batch, number_of_images)]
					await message.channel.send(files = files)

			elif 'pikapika' in message.content.lower():
				msg = grab_random_pika_gif()

			elif 'cocoa' in message.content.lower():
				msg = grab_random_seagal_gif()

		if msg:
			await message.channel.send(msg)

	@commands.command()
	async def cocoa(self, ctx):
		msg = grab_random_seagal_gif()
		await ctx.send(msg)


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
