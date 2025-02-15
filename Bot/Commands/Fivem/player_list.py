import asyncio
import json
import colorama
import discord
import aiohttp
import utils
import math
import io
from discord.ext import tasks
import Commands.Fivem.helper as helper
from requests.utils import resolve_proxies


def init(tree: discord.app_commands.CommandTree, bot: discord.Client, config: dict, lang: dict):
    """
    sets up the
    """
    fivem_config = config
    server_ip = fivem_config.get("server_ip", "127.0.0.1:30120")
    embed_color = fivem_config.get("embed", {}).get("color", "#FF5733")
    server_name = fivem_config.get("server_name", "FiveM Server")
    # Endpoint for player listing (common for FiveM is "players.json")
    players_endpoint = fivem_config.get("players_endpoint", "players.json")

    @tasks.loop(seconds=config.get("loop_seconds", 60))
    async def handle_player_list_loop_command(server_ip: str, embed_color: str, server_name: str, fivem_config: dict):
        """
        # The base URL for requesting player data
        # Usually for FiveM: e.g. http://server_ip/players.json
        # We strip the port from server_ip if needed
        # For example: "127.0.0.1:30120" => "127.0.0.1" + port = "30120"
        # But the common approach is "http://<ip>/players.json"
        # If you have a custom port, you can do that too.
        """
        try:
            ip_part, port_part = server_ip.split(":") # Attempt to split the server_ip by colon
            base_url = "https://" if fivem_config.get("ssl", "false") == "true" else "http://" + f"{ip_part}:{port_part}"
        except ValueError:
            base_url = "https://" if fivem_config.get("ssl", "false") == "true" else "http://" + f"{server_ip}" # If we cannot split, assume all is in ip_part | NOTE: it's not recommended and not tested!

        color = discord.Color.from_str(embed_color) if embed_color else discord.Color.blue()
        info_endpoint = fivem_config.get("info_endpoint", "info.json")
        players_endpoint = fivem_config.get("players_endpoint", "players.json")

        main_message = bot.get_channel(fivem_config.get("channel_id"))
        if not main_message:
            return print(colorama.Fore.RED + "[-] Fivem: player list channel not found")
        main_message = await main_message.fetch_message(fivem_config.get("message_id"))
        if not main_message:
            return print(colorama.Fore.RED + "[-] Fivem: player list message not found | use the /player_list command to create it")

        # Get server info (info.json)
        info, status_ok, error_reason = await helper.get_server_info(base_url, info_endpoint)
        if not status_ok or not info or not info.get("vars") or not info.get("vars").get("sv_maxClients"):
            # Could not fetch the data
            embed_fail = discord.Embed(
                title=server_name,
                description=f"**Server IP:** `connect {server_ip}`\n**Status:** Could not retrieve server info.\nReason: {error_reason}",
                color=discord.Color.red()
            )
            return await main_message.edit(embed=embed_fail, content=None)
        server_name = info.get("vars", {}).get("sv_projectName", server_name)
        if server_name.startswith("^"): # Remove color codes
            server_name = server_name[2:]

        # Get player data (players.json)
        players, status_ok, error_reason = await helper.get_player_data(base_url, players_endpoint)
        if not status_ok:
            # Could not fetch the data
            embed_fail = discord.Embed(
                title=server_name,
                description=f"**Server IP:** `connect {server_ip}`\n**Status:** Could not retrieve player data.\nReason: {error_reason}",
                color=discord.Color.red()
            )
            return await main_message.edit(embed=embed_fail, content=None)

        # Build the embed(s)
        color = discord.Color.from_str(embed_color) if embed_color else discord.Color.blue()
        if not status_ok:
            # Could not fetch the data
            embed_fail = discord.Embed(
                title=server_name,
                description=f"**Server IP:** `{server_ip}`\n**Status:** Could not retrieve player data.\nReason: {error_reason}",
                color=discord.Color.red()
            )
            await main_message.edit(embed=embed_fail, content=None)
            return

        # We have players data
        # Usually players is a list of dict with "id", "name", "ping" etc.
        # We'll display them in one or more embeds, chunking if we exceed the embed limit.

        # Example structure:
        # players = [
        #   {"id": 1, "name": "PlayerOne", "ping": 42, ...},
        #   ...
        # ]

        # Convert to a list of strings
        player_strings = []
        for p in players:
            pid = p.get("id", "?")
            name = p.get("name", "Unknown")
            ping = p.get("ping", "?")
            # Customize as needed
            player_strings.append(f"**[{pid}]** \\{name} (ping: {ping})")

        # We'll create a primary embed with server info
        main_embed = discord.Embed(
            title=server_name,
            description=f"**Server IP:** `{server_ip}`\n**Online Players:** {len(players)}",
            color=color
        )

        # If no players, we can just say "No players online."
        if not player_strings:
            main_embed.add_field(name="Players", value="No players online.", inline=False)
            await main_message.edit(embed=main_embed, content=None)
            return

        # If players exist, chunk them to fit in embed(s)
        # embed descriptions have a 4096 char limit, fields have 1024 limit, total embed limit ~6000
        # We'll store each player's line in a big text, chunk by ~1024 chars for each field or
        # we can do multiple embeds if we want. Let's do multiple fields in the same embed if possible.

        # We'll store as strings until we reach ~900-1000 chars, then make a new field
        chunk_size = 900
        current_chunk = ""
        field_counter = 1

        for ps in player_strings:
            line = ps + "\n"
            if len(current_chunk) + len(line) > chunk_size:
                # add field
                main_embed.add_field(name=f"Players {field_counter}", value=current_chunk, inline=False)
                field_counter += 1
                current_chunk = line
            else:
                current_chunk += line

        # Add the last chunk if not empty
        if current_chunk.strip():
            main_embed.add_field(name=f"Players {field_counter}", value=current_chunk, inline=False)

        # Check if the embed size exceeds Discord's limit
        if len(main_embed) > 5900:
            split_embeds = []
            current_embed = discord.Embed(
                title=server_name,
                color=color
            )
            total_chars = 0
            # Split fields among multiple embeds
            for field in main_embed.fields:
                field_chars = len(field.name) + len(field.value)

                # If adding this field exceeds the limit, store current embed and create a new one
                if total_chars + field_chars > 5900:
                    split_embeds.append(current_embed)
                    current_embed = discord.Embed(
                        title=server_name,
                        color=color)
                    total_chars = 0  # Reset character count for new embed
                current_embed.add_field(name=field.name, value=field.value, inline=False)
                total_chars += field_chars

            # Store the last embed if it contains any fields
            if len(current_embed.fields) > 0:
                split_embeds.append(current_embed)

            # Send the first embed as an edit
            await main_message.edit(embed=split_embeds[0], content=None)
            for split_embed in split_embeds[1:]: # Send the remaining embeds as new messages
                await main_message.channel.send(embed=split_embed)
        else:
            await main_message.edit(embed=main_embed, content=None) # Safe to send without splitting

        # Delete old messages (if any) that were sent by the bot
        async for message in main_message.channel.history(limit=1000):
            if message.id != main_message.id and message.author == bot.user:
                await message.delete()
                await asyncio.sleep(0.5)  # Prevent rate-limiting

    @tree.command(name="player_list", description=lang["command_description"])
    async def player_list_command(interaction: discord.Interaction, channel: discord.TextChannel = None):
        """
        send placeholder message
        sends ephemeral message with the data to put inside the config file
        """
        ch = channel
        if not ch:
            ch = interaction.channel
        if not ch.permissions_for(interaction.user).administrator:
            await interaction.response.send_message(lang["not_administrator"], ephemeral=True)
            return
        msg = await ch.send(lang["placeholder"])
        embed = discord.Embed(
            title=lang["command_embed_title"],
            description=lang["command_embed_description"].replace("{{ch_id}}", str(ch.id)).replace("{{msg_id}}", str(msg.id)),
            color=discord.Color.random())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def on_ready():
        ch = bot.get_channel(fivem_config.get("channel_id"))
        if ch:
            try:
                await ch.fetch_message(fivem_config.get("message_id"))
            except discord.NotFound:
                print(colorama.Fore.RED + "[-] Fivem: player list message not found | use the /player_list command to create it")
                return
            handle_player_list_loop_command.start(server_ip, embed_color, server_name, fivem_config)
            print(colorama.Fore.GREEN + "[+] Fivem: player list message updated and registered loop")

    if not hasattr(bot, "on_ready_callbacks"):
        bot.on_ready_callbacks = []
    bot.on_ready_callbacks.append(on_ready)