from datetime import datetime
import discord
import utils


def init(tree: discord.app_commands.CommandTree, bot: discord.Client, config: dict, lang: dict):

    async def on_member_join(member: discord.Member):
        """
        This function is called when a member joins the server
        :param member: discord.Member the member that joined
        """
        channel = bot.get_channel(int(config["channel-id"]))
        if channel is not None:
            em = discord.Embed(title=utils.replace_variables(lang["title"]["text"], member, member.guild), url=utils.replace_variables(config["embed"]["title"]["url"], member, member.guild), description=utils.replace_variables(lang["description"], member, member.guild), color=discord.Color.from_str(config["embed"]["color"]))
            em.set_author(name=utils.replace_variables(lang["author"]["name"], member, member.guild), url=utils.replace_variables(config["embed"]["author"]["url"], member, member.guild), icon_url=utils.replace_variables(config["embed"]["author"]["icon_url"], member, member.guild))
            em.set_thumbnail(url=utils.replace_variables(config["embed"]["thumbnail_url"], member, member.guild))
            em.set_image(url=utils.replace_variables(config["embed"]["image_url"], member, member.guild))
            em.set_footer(text=utils.replace_variables(lang["footer"]["text"], member, member.guild), icon_url=utils.replace_variables(config["embed"]["footer"]["icon_url"], member, member.guild))
            if config["embed"]["footer"]["timestamp"]:
                em.timestamp = datetime.now()
            await channel.send(embed=em)

    if not hasattr(bot, "on_member_join_callbacks"):
        bot.on_member_join_callbacks = []
    bot.on_member_join_callbacks.append(on_member_join)