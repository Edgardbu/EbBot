import discord
from discord.ext.commands import IDConverter, EmojiNotFound
import re
import string
from ruamel.yaml import YAML


def replace_variables(text: str, member: discord.Member = None, guild: discord.Guild = None) -> str | None:
    """
    This function replaces the variables in the text with the actual values
    {{user}} - mention the user
    {{user.name}} - the name of the user
    {{user.id}} - the id of the user
    {{user.icon}} - the avatar of the user
    {{server.name}} - the name of the guild
    {{server.id}} - the id of the guild
    {{server.icon}} - the icon of the guild
    {{server.memberCount}} - the member count of the guild without bots!

    :param text: str the text to replace the variables in
    :param member: discord.Member the member to replace the variables with
    :param guild: discord.Guild the guild to replace the variables with
    :return:
    """
    if text is None:
        return None

    if member is not None:
        text = text.replace("{{user}}", member.mention)
        text = text.replace("{{user.name}}", member.name)
        text = text.replace("{{user.id}}", str(member.id))
        if member.avatar is not None:
            text = text.replace("{{user.icon}}", str(member.avatar.url))
    if guild is not None:
        text = text.replace("{{server.name}}", guild.name)
        text = text.replace("{{server.id}}", str(guild.id))
        if guild.icon is not None:
            text = text.replace("{{server.icon}}", str(guild.icon.url))
        text = text.replace("{{server.memberCount}}", str(sum(1 for member in guild.members if not member.bot)))
    return text


async def get_command_mention(bot: discord.Client, tree: discord.app_commands.CommandTree, guild_id: int, cmd_name: str) -> str:
    commands = await tree.fetch_commands()  # I know this looks weird, but it's the best way to get the commands until discord will give us a better way to do it
    cmd_lst = cmd_name.split(" ")
    for command in commands:
        if cmd_lst[0] == command.name:
            return command.mention.replace(cmd_lst[0], cmd_name)
    return f"/{cmd_name}"


def base64_decode(encoded):
    encoded = encoded.rstrip('=') # Remove padding characters
    base64_chars = string.ascii_uppercase + string.ascii_lowercase + string.digits + '+/'
    base64_values = {char: idx for idx, char in enumerate(base64_chars)}
    encoded = encoded.replace('-', '+').replace('_', '/') # Replace URL-safe characters with base64 characters
    padding = len(encoded) % 4
    if padding != 0:
        encoded += '=' * (4 - padding)
    binary_string = ''.join([format(base64_values[char], '06b') for char in encoded]) # base64 to binary
    byte_chunks = [binary_string[i:i + 8] for i in range(0, len(binary_string), 8)] # split into 8-bit chunks
    decoded_bytes = bytes([int(byte, 2) for byte in byte_chunks if len(byte) == 8])
    return decoded_bytes.decode('utf-8') # convert to string


class CustomButtons(discord.ui.View):
    def __init__(self, buttons: list):
        super().__init__()
        for button in buttons:
            self.add_item(button)


class EmojiConverter(IDConverter[discord.Emoji]):
    """Converts to a :class:`~discord.Emoji`.

    All lookups are done for the local guild first, if available. If that lookup
    fails, then it checks the client's global cache.

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by extracting ID from the emoji.
    3. Lookup by name
    .. versionchanged:: 1.5
         Raise :exc:`.EmojiNotFound` instead of generic :exc:`.BadArgument`
    """

    async def convert(self, inter: discord.Interaction, argument: str, bot: discord.Client) -> discord.Emoji:
        match = self._get_id_match(argument) or re.match(r'<a?:[a-zA-Z0-9\_]{1,32}:([0-9]{15,20})>$', argument)
        result = None
        guild = inter.guild
        emoji_pattern = re.compile("["
                                   u"\U0001F600-\U0001F64F"  # emoticons
                                   u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                                   u"\U0001F680-\U0001F6FF"  # transport & map symbols
                                   u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                                   "]+", flags=re.UNICODE)
        if emoji_pattern.search(argument) is not None:
            return argument
        if match is None:
            # Try to get the emoji by name. Try local guild first.
            if guild:
                result = discord.utils.get(guild.emojis, name=argument)

            if result is None:
                result = discord.utils.get(bot.emojis, name=argument)
        else:
            emoji_id = int(match.group(1))

            # Try to look up emoji by id.
            result = bot.get_emoji(emoji_id)

        if result is None:
            raise EmojiNotFound(argument)

        return result




