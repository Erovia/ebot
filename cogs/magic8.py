import random

import discord
from discord import app_commands
from discord.ext import commands


class Magic8Cog(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.ANSWERS = ('It is certain.', 'It is decidedly so.', 'Without a doubt.', 'Yes definitely.', 'You may rely on it.',
                    'As I see it, yes.', 'Most likely.', 'Outlook good.', 'Yes.', 'Signs point to yes.',
                    'Reply hazy, try again.', 'Ask again later.', 'Better not tell you now.', 'Cannot predict now.', 'Concentrate and ask again.',
                    'Don\'t count on it.', 'My reply is no.', 'My sources say no.', 'Outlook not so good.', 'Very doubtful.')

	@app_commands.command(description = 'Get answers to life\'s biggest questions.')
	@app_commands.describe(question = 'Your question')
	async def magic8(self, interaction, question: str):
		embed = discord.Embed(colour = discord.Colour.dark_blue())
		embed.add_field(name = f'{interaction.user.name} asked:', value = question, inline = False)
		embed.add_field(name = 'The magic 8 ball says:', value = random.choice(self.ANSWERS), inline = False)
		embed.set_thumbnail(url = 'https://upload.wikimedia.org/wikipedia/commons/thumb/e/eb/Magic_eight_ball.png/240px-Magic_eight_ball.png')
		await interaction.response.send_message(embed = embed)


async def setup(bot):
	await bot.add_cog(Magic8Cog(bot))
