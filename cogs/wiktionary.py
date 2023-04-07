import logging

import requests
from bs4 import BeautifulSoup
import discord
from discord.ext import commands
from discord import app_commands


class WiktionaryCog(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		botlogger = logging.getLogger('ebot')
		self.logger = botlogger.getChild('WiktionaryCog')
		self.API = 'https://en.wiktionary.org/api/rest_v1'

	@app_commands.command(name = 'define', description = 'Get the definition of a word from Wiktionary.')
	@app_commands.describe(word = 'The word to define.')
	async def get_definition(self, interaction, word: str):
		await interaction.response.defer(thinking = True)
		ENDPOINT = 'page/definition'
		response = requests.get(f'{self.API}/{ENDPOINT}/{word}')
		self.logger.debug(f'The response of {response.url} was HTTP{response.status_code}.')
		if response.ok:
			descriptions = response.json()['en']
			embed = discord.Embed(title = f'The definition(s) of "{word}":', colour = discord.Colour.og_blurple(), url = f'https://en.wiktionary.org/wiki/{word}')
			embed.set_footer(text = f'asked by {interaction.user.name}\nsource: Wiktionary')
			for desc in descriptions:
				definitions = '\n\n'.join([_def['definition'].strip() for _def in desc['definitions'] if 'mw-reference-text' not in _def['definition']])
				soup = BeautifulSoup(definitions, 'html.parser')
				if len(soup.text) >= 1024:
					# Discord limits the text length for embed fields at 1024 characters
					end = soup.text[:1024].rfind('\n\n')
					text = soup.text[:end]
					self.logger.debug(f'Definitions contained {len(soup.text)} characters, trimmed it down to fit embed.')
				else:
					text = soup.text
				embed.add_field(name = desc['partOfSpeech'], value = text, inline = False)
				embed.add_field(name = '---', value = '')
			await interaction.followup.send(embed = embed)
		else:
			await interaction.followup.send('Ooops, something went wrong!\nTry a different word.', ephemeral = True)


async def setup(bot):
	await bot.add_cog(WiktionaryCog(bot))
