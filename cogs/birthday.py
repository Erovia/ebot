import logging
import os
import json
from datetime import time, datetime, timezone
from enum import IntEnum, auto

import discord
from discord import app_commands
from discord.ext import commands, tasks

import pymongo

POST_TIME = time(hour = 7, tzinfo = timezone.utc)


class Months(IntEnum):
	January = auto()
	February = auto()
	March = auto()
	April = auto()
	May = auto()
	June = auto()
	July = auto()
	August = auto()
	September = auto()
	October = auto()
	November = auto()
	December = auto()


class Birthday(commands.Cog):
	def __init__(self, bot, mongo, channel_ids):
		self.bot = bot
		self.mongo = mongo
		botlogger = logging.getLogger('ebot')
		self.logger = botlogger.getChild('BirthdayCog')
		self.channel_ids = channel_ids
		self.post_task.start()


	def cog_unload(self):
		self.post_task.cancel()


	@tasks.loop(time = POST_TIME)
	async def post_task(self):
		await self.post()


	async def post(self):
		# Check if we have to post today
		today = datetime.now(timezone.utc)
		current_month = today.month
		current_day = today.day

		for guild in self.bot.guilds:
			db = self.mongo[str(guild.id)]
			if 'birthdays' not in db.list_collection_names():
				# Skip this server if no birthdays are configured
				continue
			col = db['birthdays']
			users = col.find({'$and': [{'month': current_month}, {'day': current_day}]})

			embed = discord.Embed(title = ':birthday_cake: Today\'s birthdays :partying_face:', colour = discord.Colour.og_blurple())
			for user in users:
				user_obj = await get_user(self.bot, user['_id'])
				if user_obj is not False:
					self.logger.debug(f'Birthday today: {user_obj.display_name}')
					embed.add_field(name = user_obj.display_name, value = '', inline = False)

			if len(embed.fields) == 0:
				# No users have birthday today
				continue

			channel = await get_channel(self.bot, self.channel_ids[str(guild.id)])
			if channel:
				self.logger.debug(f'Sending birthday embed to channel {channel.id} on server {guild.id}')
				await channel.send(embed = embed)
			else:
				self.logger.debug(f'Invalid channel ID: {self.channel_ids[str(guild.id)]}')


	@app_commands.command(description = 'Set the date of your birthday.')
	@app_commands.describe(year = 'Only used for validation, not saved')
	@app_commands.describe(month = 'Month')
	@app_commands.describe(day = 'Day')
	@commands.guild_only()
	async def birthday(self, interaction, year: int, month: Months, day: int):
		if not self.validate_date(year, month, day):
			await interaction.response.send_message('That date seems to be invalid!')
		else:
			await interaction.response.defer(ephemeral = True, thinking = True)
			mongo_manage(self, interaction.guild_id, interaction.user.id, month, day)
			await interaction.followup.send('Saved', ephemeral = True)

	def validate_date(self, year, month, day):
		try:
			datetime.strptime(f'{year}-{month}-{day}', '%Y-%m-%d')
			return True
		except ValueError:
			return False


async def get_channel(bot, channel_id):
	try:
		channel = await bot.fetch_channel(channel_id)
		return channel
	except discord.NotFound:
		# The channel does not exist
		return False
	except discord.HTTPException:
		# Something is wrong with the ID
		return False
	except discord.InvalidData:
		# Discord returned an unknown channel type
		return False
	except discord.Forbidden:
		# The bot has no permissions to fetch the channel
		return False


async def get_user(bot, user_id):
	try:
		user = await bot.fetch_user(user_id)
		return user
	except discord.NotFound:
		# The user does not exist
		return False
	except discord.HTTPException:
		# Something is wrong with the ID
		return False


def mongo_manage(self, guild_id, user_id, month, day):
	db = self.mongo[str(guild_id)]
	col = db['birthdays']
	self.logger.debug(f'Updating birthday for user {user_id} on server {guild_id} to {month}/{day}')
	resp = col.update_one({'_id': user_id}, {'$set': {'month': month, 'day': day}})
	if resp.modified_count != 1:
		self.logger.debug(f'First time setting a birthday for user {user_id} on server {guild_id}')
		resp = col.insert_one({'_id': user_id, 'month': month, 'day': day})


async def setup(bot):
	try:
		channel_ids = os.environ['BIRTHDAY_CHANNEL_IDS'].strip("'")
		channel_ids = json.loads(channel_ids)
	except KeyError:
		# No "BIRTHDAY_CHANNEL_IDS" environmental variable was provided, no birthdays will be posted
		channel_ids = set()
	except json.decoder.JSONDecodeError:
		raise KeyError('The provided "BIRTHDAY_CHANNEL_IDS" environmental variable is an invalid JSON. The format is "BIRTHDAY_CHANNEL_IDS=\'{"server1_id": "channel1_id", "server2_id": "channel2_id"}\'"')

	try:
		MONGO_SERVER = os.environ.get('MONGO_SERVER', None)
		MONGO_PORT = os.environ.get('MONGO_PORT', 27017)

		mongo = pymongo.MongoClient(f'mongodb://{MONGO_SERVER}:{MONGO_PORT}')
		mongo.admin.command('ping')
	except:
		raise KeyError('Cannot connect to MongoDB')
	await bot.add_cog(Birthday(bot, mongo, channel_ids))
