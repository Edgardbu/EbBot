import base64
import json
import discord
import aiohttp
import utils
import math
import io
import Commands.Fivem.helper as helper

def init(tree: discord.app_commands.CommandTree, bot: discord.Client, config: dict, lang: dict):
    """
    sets up the on_message callback for '!ip'.
    """

    fivem_config = config
    server_ip = "https://" if fivem_config.get("ssl", "false") == "true" else "http://" + fivem_config.get("server_ip", "127.0.0.1:30120")
    embed_color = fivem_config.get("embed", {}).get("color", "#FF5733")
    # Endpoint for player listing (common for FiveM is "players.json" or e.g. "info.json")
    players_endpoint = fivem_config.get("players_endpoint", "players.json")
    info_endpoint = fivem_config.get("info_endpoint", "info.json")

    # This is the text command you want: "!ip"
    async def on_message(message: discord.Message):
        if message.author.bot:
            return
        content = message.content.strip()
        if content.lower() == "!ip":
            await handle_ip_command(message, server_ip, embed_color, players_endpoint, info_endpoint)

    if not hasattr(bot, "on_message_callbacks"):
        bot.on_message_callbacks = []
    bot.on_message_callbacks.append(on_message)


async def handle_ip_command(message: discord.Message, server_ip: str, embed_color: str, players_endpoint: str, info_endpoint: str):
    """
    Responds to '!ip' with an embed showing:
    - The server's IP/Port
    - The connected players / max players
    """
    # Build the embed(s)
    players, status_ok, error_reason = await helper.get_player_data(server_ip, players_endpoint)
    color = discord.Color.from_str(embed_color) if embed_color else discord.Color.blue()
    server_name = "FiveM Server"
    if not status_ok:
        # Could not fetch the data
        embed_fail = discord.Embed(
            title=server_name,
            description=f"**Server IP:** `connect {server_ip.split("://")[1]}`\n**Status:** Could not retrieve player data.\nReason: {error_reason}",
            color=discord.Color.red()
        )
        return await message.channel.send(embed=embed_fail)

    # Get server info (info.json)
    info, status_ok, error_reason = await helper.get_server_info(server_ip, info_endpoint)
    if not status_ok or not info or not info.get("vars") or not info.get("vars").get("sv_maxClients"):
        # Could not fetch the data
        embed_fail = discord.Embed(
            title=server_name,
            description=f"**Server IP:** `connect {server_ip.split("://")[1]}`\n**Status:** Could not retrieve server info.\nReason: {error_reason}",
            color=discord.Color.red()
        )
        return await message.channel.send(embed=embed_fail)
    server_name = info.get("vars", {}).get("sv_projectName", server_name)
    if server_name.startswith("^"): # Remove color codes
        server_name = server_name[2:]
    main_embed = discord.Embed(
        title=server_name,
        description=f"**Server IP:** `connect {server_ip.split("://")[1]}`\n**Online Players:** `{len(players)}` / `{info['vars']['sv_maxClients']}`",
        color=color
    )

    image_file = None
    if info.get("icon"):
        base64_icon = info["icon"]
        image_data = base64.b64decode(base64_icon)
        image_file = discord.File(io.BytesIO(image_data), filename="icon.png")
        main_embed.set_thumbnail(url="attachment://icon.png")

    await message.channel.send(embed=main_embed, file=image_file)
