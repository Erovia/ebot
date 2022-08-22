import logging

from discord.ext import commands


class Admin(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.botlogger = logging.getLogger('ebot')
		self.logger = self.botlogger.getChild('AdminCog')

	@commands.command()
	@commands.is_owner()
	async def manage(self, ctx, topic, *args):
		topic = topic.casefold()
		if topic == 'logging':
			await self._logging(ctx, args)
		elif topic in ['cog', 'cogs' , 'extension', 'extensions']:
			await self._extensions(ctx, args)

	@manage.error
	async def manage_error(self, ctx, error):
		if isinstance(error, commands.errors.NotOwner):
			#TODO: Figure out why traceback is still printed on console for exceptions
			#      Found only this relevant thread, but did not help: https://stackoverflow.com/a/58713699
			self.logger.warning(f'"{ctx.author.name}-{ctx.author.id}" is trying to be smart and run admin commands!')
		else:
			raise error


	async def _logging(self, ctx, verbosity):
		options = ['INFO', 'DEBUG']
		if verbosity:
			verbosity = verbosity[0].upper()
			if verbosity not in options:
				self.logger.debug(f'The valid options for logging verbosity are {options}.')
				await ctx.reply(f'The valid options for logging verbosity are {options}.')
			else:
				if verbosity == 'INFO':
					self.botlogger.setLevel(logging.INFO)
				else:
					self.botlogger.setLevel(logging.DEBUG)
			await ctx.reply(f'Set log level to {verbosity}!')
		await ctx.reply(f'Effective log level is {self.logger.getEffectiveLevel()}')
		self.logger.debug(f'Effective log level is {self.logger.getEffectiveLevel()}')


	async def _extensions(self, ctx, args):
		msg = ''
		try:
			subcommand = args[0].lower()
			extensions = self.bot.extensions.keys()
			if subcommand == 'list':
				extensions = '\n'.join([ext.removeprefix('cogs.') for ext in extensions])
				await ctx.reply(f'The currently loaded extensions are: \n{extensions}')
			elif subcommand == 'remove':
				try:
					ext = args[1]
					if ext == 'admin':
						await self.bot.reload_extension(f'cogs.{ext}')
						msg = f'Admin extension should not be removed, reloading it instead!'
					else:
						await self.bot.unload_extension(f'cogs.{ext}')
						msg = f'Extension "{ext}" had been removed.'
				except IndexError:
					msg = 'No extension name was provided!'
				except commands.ExtensionNotLoaded:
					msg = f'Extension "{ext}" was not found. Not doing anything.'
				await ctx.reply(msg)
				self.logger.debug(msg)
			elif subcommand == 'add':
				try:
					ext = args[1]
					await self.bot.load_extension(f'cogs.{ext}')
					msg = f'Extension "{ext}" had been added.'
				except IndexError:
					msg = 'No extension name was provided!'
				except (commands.errors.ExtensionFailed, commands.errors.ExtensionNotFound) as e:
					self.logger.error(f'Error while loading "{ext}" extension!\n{e}')
				await ctx.reply(msg)
				self.logger.debug(msg)
			else:
				msg = 'Unknown subcommand'
				await ctx.reply(msg)
		except IndexError:
			msg = 'No subcommand was provided!'
			await ctx.reply(msg)
			self.logger.debug(f'Extensions: {msg}')


async def setup(bot):
	await bot.add_cog(Admin(bot))
