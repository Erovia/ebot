#!/usr/bin/env python

import logging
import os
import sys
from pathlib import Path

import discord
from discord.ext import commands

from emoji import demojize


logging.basicConfig(format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s', level = logging.INFO)
botlogger = logging.getLogger('ebot')


###########################################
#
try:
	DISCORD_TOKEN = os.environ['DISCORD_TOKEN']
except KeyError:
	botlogger.error('Please make sure to pass the Discord API token (DISCORD_TOKEN) as environmental variables!')
	sys.exit(1)
#
###########################################


class eBot(commands.Bot):
	# Custom Bot class so we can load our cogs before the bot logs in
	async def setup_hook(self):
		botlogger.info('Loading cogs...')
		for cog in [cog.stem for cog in Path('cogs').iterdir() if cog.is_file() and cog.suffix == '.py']:
			try:
				botlogger.info(f'Adding "{cog}" Cog...')
				await bot.load_extension(f'cogs.{cog}')
			except commands.errors.ExtensionFailed as e:
				botlogger.error(f'Error while loading "{cog}" Cog!\n{e}')
			else:
				botlogger.info(f'"{cog}" Cog is now running!')


intents = discord.Intents.default()
intents.message_content = True
# intents.members = True

bot = eBot(intents = intents, command_prefix = commands.when_mentioned)


@bot.event
async def on_ready():
	botlogger.info(f'We have logged in as {bot.user}')
	sync = await bot.tree.sync()
	botlogger.info(f'Synced {len(sync)} commands')


@bot.event
async def on_command_error(ctx, error):
	# We don't want to care about "commands" that are simply emojis sent to the bot
	command = demojize(ctx.invoked_with)
	if command.startswith('<:') or command.startswith(':'):
		return

	if isinstance(error, commands.errors.CommandNotFound):
		await ctx.reply('Are you trying to initiate a standard human connection, fellow human?')
	else:
		raise error


try:
	bot.run(DISCORD_TOKEN)
except discord.errors.LoginFailure as e:
	botlogger.error(e)
