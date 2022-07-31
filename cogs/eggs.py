import logging
import re
import random
import sys
import os
# import math

# import discord
from discord.ext import commands

import giphy_client


class Egg(commands.Cog):
	def __init__(self, bot, giphy_token):
		self.bot = bot
		self.logger = logging.getLogger('EggCog')
		self.GIPHY_TOKEN = giphy_token
		self.GIPHY_LIMIT = 25
		self.giphy = giphy_client.DefaultApi()
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
		# self.THE_LEGEND_REGEX = re.compile(r'show\s+(me\s+)?the\s+legend!*', re.I)
		# self.THE_LEGEND_DIR = Path('the_legend')
		# if self.THE_LEGEND_DIR.is_dir():
		# 	self.THE_LEGEND_FILES = [file for file in self.THE_LEGEND_DIR.iterdir() if file.is_file()]


	@commands.Cog.listener()
	async def on_message(self, message):
		msg = None
		if message.author.bot == False:
			if self.bot.user.mentioned_in(message) and len(message.mentions) == 1:
				if message.content == self.bot.user.mention:
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
		api_response = self.giphy.gifs_search_get(self.GIPHY_TOKEN, keyword, limit = self.GIPHY_LIMIT)
		url = api_response.data[random.randrange(self.GIPHY_LIMIT)].images.downsized_small.mp4
		self.logger.info(f'Grabbed random "{keyword}" image: {url}')
		return url

	def grab_specific_gif(self, gif_id):
		api_response = self.giphy.gifs_gif_id_get(self.GIPHY_TOKEN, gif_id)
		url = api_response.data.images.downsized_small.mp4
		self.logger.info(f'Grabbed "{gif_id}" image: {url}')
		return url


	# @commands.Cog.listener()
	# async def on_member_remove(self, member):
	# 	if self.GOODBYE_CHANNEL:
	# 		self.logger.info(f'{member.id} left the server')
	# 		gif = self.grab_random_gif('sassy')
	# 		channel = self.bot.get_channel(self.GOODBYE_CHANNEL)
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


async def setup(bot):
	try:
		giphy_token = os.environ['GIPHY_TOKEN']
	except KeyError:
		raise KeyError('Please make sure to pass the Giphy API token (GIPHY_TOKEN) as environmental variable!')
	await bot.add_cog(Egg(bot, giphy_token))
