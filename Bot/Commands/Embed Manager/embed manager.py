import base64
import binascii
import json
from typing import Literal
import discord
import utils
import requests
import colorama


def init(tree: discord.app_commands.CommandTree, bot: discord.Client, config: dict, lang: dict):
    def has_permission():
        async def predicate(interaction: discord.Interaction):
            for role in config["access role"]:
                if role in [role.id for role in interaction.user.roles]:
                    return True
            await interaction.response.send_message(lang["no_permission_ephemeral"], ephemeral=True)
            return False

        return discord.app_commands.check(predicate)

    embed_manager_commands = discord.app_commands.Group(name="embed",
                                                        description=lang["embed_manager_commands_description"])

    @embed_manager_commands.command(name="setup", description=lang["setup_command_description"])
    @has_permission()
    async def embed_setup(interaction: discord.Interaction):
        """
        Setup the embed for the button role system
        :param interaction: discord.Interaction the interaction
        :return: None
        """
        await interaction.response.send_message(lang["how_to_setup"].replace("{{commandping}}", await utils.get_command_mention(bot, tree, interaction.guild_id, "embed button add")), ephemeral=True)
        await interaction.channel.send(embed=discord.Embed(title=lang["embed_title_placeholder"], description=lang["embed_description_placeholder"]))

    @embed_manager_commands.error
    async def embed_manager_commands_error(interaction: discord.Interaction, error):
        if isinstance(error, discord.app_commands.errors.CheckFailure):
            pass
        elif isinstance(error, discord.app_commands.errors.CommandInvokeError) and "raised an exception: EmojiNotFound: Emoji" in str(error):
            await interaction.followup.send(lang["emoji_not_found"], ephemeral=True)
        elif isinstance(error, discord.app_commands.errors.CommandInvokeError) and "Component custom id cannot be duplicated" in str(error):
            await interaction.followup.send(lang["button_existing"], ephemeral=True)
        else:
            print(colorama.Fore.RED + "Error: " + colorama.Fore.GREEN + f"{error.__class__.__name__}: {error}" + colorama.Fore.MAGENTA + f" at line {error.__traceback__.tb_lineno}")

    button_commands = discord.app_commands.Group(name="button", description=lang["button_commands_description"])

    @button_commands.command(name="add", description=lang["add_command_description"])
    @has_permission()
    async def button_add(interaction: discord.Interaction, color: Literal["red", "green", "blue", "grey"], role: discord.Role, text: str = "", emoji: str = None, toggleable: bool = False):
        await interaction.response.send_message(lang["select_message"], ephemeral=True)
        msg = await bot.wait_for("message", check=lambda m: m.author.id == interaction.user.id and m.content == "*select", timeout=60)
        await msg.delete()
        if not msg.reference:
            return await interaction.followup.send(lang["select_no_reference"], ephemeral=True)
        msg = msg.reference.resolved
        colors = {
            "red": discord.ButtonStyle.red,
            "green": discord.ButtonStyle.green,
            "blue": discord.ButtonStyle.blurple,
            "grey": discord.ButtonStyle.grey
        }
        if emoji is not None and emoji.startswith("<") and emoji.endswith(">"):
            emoji = await utils.EmojiConverter().convert(interaction, emoji, bot)
        if toggleable:
            buttons = [discord.ui.Button(style=colors[color], label=text, custom_id=f"toggle_button_role_{role.id}", emoji=emoji)]
        else:
            buttons = [discord.ui.Button(style=colors[color], label=text, custom_id=f"button_role_{role.id}", emoji=emoji)]
        for ar in msg.components:
            if isinstance(ar, discord.components.ActionRow):
                for btn in ar.children:
                    if isinstance(btn, discord.components.Button):
                        buttons.append(discord.ui.Button(style=btn.style, label=btn.label, custom_id=btn.custom_id, emoji=btn.emoji))
        view = utils.CustomButtons(buttons)
        await msg.edit(view=view)

    embed_manager_commands.add_command(button_commands)
    tree.add_command(embed_manager_commands)

    async def on_message(message: discord.Message):
        if message.author.bot:
            return
        if message.content.startswith("*edit embed"):
            await message.delete()
            for role in config["access role"]:
                if not role in [role.id for role in message.author.roles]:
                    return await message.channel.send(lang["no_permission_message"], delete_after=5)
            args = message.content.split(" ")[2:]
            if len(args) > 1:
                return await message.channel.send(lang["edit_embed_too_many_args"])
            if len(args) == 0:
                return await message.channel.send(lang["edit_embed_no_args"])
            if not args[0].startswith("https://share.discohook.app/go"):
                return await message.channel.send(lang["edit_embed_invalid_url"])
            msg = message.reference.resolved
            response = requests.get(args[0])
            base64_json = response.url.replace("https://discohook.org/?data=", "")
            try:
                embed_json = json.loads(base64.b64decode(base64_json).decode("utf-8"))["messages"][0]["data"]
            except binascii.Error:
                embed_json = json.loads(base64.urlsafe_b64decode(base64_json + '=' * (-len(base64_json) % 4)).decode("utf-8"))["messages"][0]["data"]  # fix padding sometimes it is missing
            embeds = []
            for em in embed_json["embeds"]:
                if em['color'] is None:
                    em['color'] = discord.Color.from_str("#2b2d31").value
                embeds.append(discord.Embed.from_dict(em))
            await msg.edit(embeds=embeds, content=embed_json["content"])
    if not hasattr(bot, "on_ready_callbacks"):
        bot.on_message_callbacks = []
    bot.on_message_callbacks.append(on_message)

    async def on_interaction(interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component:
            if interaction.data["component_type"] == 2:
                if "custom_id" in interaction.data and interaction.data["custom_id"].startswith("button_role_"):
                    role = discord.utils.get(interaction.guild.roles, id=int(interaction.data["custom_id"].replace("button_role_", "")))
                    if role in interaction.user.roles:
                        return await interaction.response.send_message(lang["role_already_added"].replace("{{role}}", role.mention), ephemeral=True)
                    try:
                        await interaction.user.add_roles(role)
                    except Exception as e:
                        if isinstance(e, discord.Forbidden):
                            return await interaction.response.send_message(lang["missing_permission"], ephemeral=True)
                        else:
                            print(colorama.Fore.RED + "Error: " + colorama.Fore.GREEN + f"{e.__class__.__name__}: {e}" + colorama.Fore.MAGENTA + f" at line {e.__traceback__.tb_lineno}")
                            return await interaction.response.send_message(lang["error_occurred"], ephemeral=True)
                    await interaction.response.send_message(lang["role_added"].replace("{{role}}", role.mention), ephemeral=True)
                elif "custom_id" in interaction.data and interaction.data["custom_id"].startswith("toggle_button_role_"):
                    role = discord.utils.get(interaction.guild.roles,id=int(interaction.data["custom_id"].replace("toggle_button_role_", "")))
                    if role in interaction.user.roles:
                        await interaction.user.remove_roles(role)
                        return await interaction.response.send_message(lang["role_removed"].replace("{{role}}", role.mention), ephemeral=True)
                    try:
                        await interaction.user.add_roles(role)
                    except Exception as e:
                        if isinstance(e, discord.Forbidden):
                            return await interaction.response.send_message(lang["missing_permission"], ephemeral=True)
                        else:
                            print(colorama.Fore.RED + "Error: " + colorama.Fore.GREEN + f"{e.__class__.__name__}: {e}" + colorama.Fore.MAGENTA + f" at line {e.__traceback__.tb_lineno}")
                            return await interaction.response.send_message(lang["error_occurred"], ephemeral=True)
                    await interaction.response.send_message(lang["role_added"].replace("{{role}}", role.mention), ephemeral=True)
    if not hasattr(bot, "on_interaction_callbacks"):
        bot.on_interaction_callbacks = []
    bot.on_interaction_callbacks.append(on_interaction)

    @tree.command(name="test")
    async def test(interaction: discord.Interaction):
        print(config)
        await interaction.response.send_message("Test", ephemeral=True)
