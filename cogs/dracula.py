import json
from pathlib import Path
from datetime import time, datetime, timezone
import logging
import textwrap

import discord
from discord import app_commands
from discord.ext import commands, tasks


DD_FILE = 'data/daily_dracula.json'
POST_TIME = time(hour = 7, tzinfo = timezone.utc)
CHAR_LIMIT = 2000    # Discord limit


class DailyDraculaCog(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		botlogger = logging.getLogger('ebot')
		self.logger = botlogger.getChild('DailyDraculaCog')
		self.DRACULA = json.loads(Path(DD_FILE).read_text())
		self.CHANNEL_ID = None
		self.post_task.start()

	def cog_unload(self):
		self.post_task.cancel()

	async def post(self, interaction = None, date = ''):
		if self.CHANNEL_ID is None:
			msg = 'Feature not configured yet!'
			if interaction is not None:
				await interaction.followup.send(msg, ephemeral = True)
			self.logger.error(msg)
		else:
			if date != '':
				today = datetime.fromisoformat(f'{datetime.now(timezone.utc).year}-{date}')
				day = date.strip()
			else:
				today = datetime.now(timezone.utc)
				day = f'{today:%m}-{today:%d}'
			header = f'--- Post start for {today:%b} {today.day} ---'
			footer = f'--- Post end for {today:%b} {today.day} ---'
			try:
				dracula = self.DRACULA[day]
				message = [header]
				message += textwrap.wrap(dracula, width = CHAR_LIMIT, replace_whitespace = False, drop_whitespace = False)
				message += [footer]
				channel = self.bot.get_channel(self.CHANNEL_ID)
				self.logger.debug(f'Posting for {today}')
				for msg in message:
					await channel.send(msg)
			except KeyError:
				msg = f'No post for {day}'
				if interaction is not None:
					await interaction.followup.send(msg, ephemeral = True)
				self.logger.debug(msg)

	@tasks.loop(time = POST_TIME)
	async def post_task(self):
		await self.post()

	@app_commands.command()
	@app_commands.describe(date = 'The entry for which date should be posted? (Format is MM-DD)')
	async def daily_dracula_force_post(self, interaction, date: str = ''):
		is_owner = await self.bot.is_owner(interaction.user)
		if is_owner:
			await interaction.response.send_message('Working on it...', ephemeral = True, delete_after = 10)
			await self.post(interaction, date)
		else:
			await interaction.response.send_message("Ah ah ah! You didn't say the magic word!", ephemeral = True, delete_after = 30)

	@app_commands.command()
	async def daily_dracula_init(self, interaction):
		is_owner = await self.bot.is_owner(interaction.user)
		if is_owner:
			self.CHANNEL_ID = interaction.channel_id
			self.logger.debug(f'Feature is configured to use channel: {self.CHANNEL_ID}')
			await interaction.response.send_message('Feature configured successfully!', ephemeral = True)
		else:
			await interaction.response.send_message("Ah ah ah! You didn't say the magic word!", ephemeral = True, delete_after = 30)


async def setup(bot):
	if not Path(DD_FILE).is_file():
		raise Exception("No daily Dracula file was found or it's not readable!")
	await bot.add_cog(DailyDraculaCog(bot))
