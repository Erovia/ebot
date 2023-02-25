from datetime import datetime, timezone
import os
import sys

import discord
from discord.channel import DMChannel
from discord.ext import commands
from discord.ext.tasks import loop


class ElizaCog(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.SESSIONS = dict()
		self._session_cleanup.start()

	@commands.command()
	@commands.dm_only()
	async def doctor(self, message):
		if message.author.bot == False:
			view = self._prep_ui(message)
			if self.SESSIONS.get(message.author.id, False):
				await message.send(self.SESSIONS[message.author.id]['eliza'].final())
				self.SESSIONS.pop(message.author.id)
				await message.send(view = view)
			else:
				await message.send(view = view)
				self.SESSIONS[message.author.id] = {'last_activity': datetime.now(timezone.utc)}
				self.SESSIONS[message.author.id]['context'] = message
				# The module's availability was checked and it was imported in the setup function,
				# so at this point it's already cached.
				eliza = sys.modules['eliza']
				self.SESSIONS[message.author.id]['eliza'] = eliza.Eliza()
				self.SESSIONS[message.author.id]['eliza'].load('./eliza/doctor.txt')
				await message.send(self.SESSIONS[message.author.id]['eliza'].initial())

	@doctor.error
	async def doctor_error(self, ctx, error):
		if isinstance(error, commands.errors.PrivateMessageOnly):
			await ctx.reply('This command only works in DMs.')


	def _prep_ui(self, message):
		if message is None:
			item = discord.ui.Button(label = 'This session has timed out due to inactivity.', style = discord.ButtonStyle.red, disabled = True)
		elif self.SESSIONS.get(message.author.id, False):
			item = discord.ui.Button(label = 'The session has been stopped.', style = discord.ButtonStyle.red, disabled = True)
		else:
			item = discord.ui.Button(label = 'A new session has been started!', style = discord.ButtonStyle.green, disabled = True)
		view = discord.ui.View()
		view.add_item(item)
		return view


	@loop(minutes = 15)
	async def _session_cleanup(self):
		# Timeout sessions after 1 hour of inactivity
		MAX_TIME = 60 * 60
		NOW = datetime.now(timezone.utc)
		expired_sessions = [[_id, session] for _id, session in self.SESSIONS.items() if (NOW - session['last_activity']).seconds >= MAX_TIME]
		for _id, session in expired_sessions:
				await session['context'].send(session['eliza'].final())
				view = self._prep_ui(None)
				await session['context'].send(view = view)
				self.SESSIONS.pop(_id)


	@commands.Cog.listener()
	async def on_message(self, message):
		if message.author.bot == False and isinstance(message.channel, DMChannel):
			if not self.bot.user.mentioned_in(message):
				if self.SESSIONS.get(message.author.id, False):
					self.SESSIONS[message.author.id]['last_activity'] = datetime.now(timezone.utc)
					await message.reply(self.SESSIONS[message.author.id]['eliza'].respond(message.clean_content))


async def setup(bot):
	if os.path.isdir('./eliza'):
		sys.path.append('./eliza')
		import eliza
		await bot.add_cog(ElizaCog(bot))
	else:
		raise ModuleNotFoundError('The eliza module is not available. Eliza Cog will not start.')
