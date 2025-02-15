import discord
import typing
import io
import colorama
import utils

def init(tree: discord.app_commands.CommandTree, bot: discord.Client, config: dict, lang: dict):
    # We assume config is already a dictionary that includes 'TicketSystem' key.
    # If needed, uncomment the line below to directly refer to TicketSystem config:
    # config = config["TicketSystem"]

    ticket_commands = discord.app_commands.Group(name="ticket", description=lang["command_description"])

    @ticket_commands.command(name="setup", description=lang["setup_command_description"])
    async def ticket_setup(interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(lang["no_permission"], ephemeral=True)
            return

        # Start the setup wizard
        view = SetupWizardView(config, lang, interaction.guild)
        await interaction.response.send_message(lang["setup_welcome_detailed"], view=view, ephemeral=True)

    @ticket_commands.command(name="add", description=lang["add_command_description"])
    @discord.app_commands.describe(member=lang["member_description"])
    async def ticket_add(interaction: discord.Interaction, member: discord.Member):
        if not is_ticket_channel(interaction.channel):
            await interaction.response.send_message(lang["not_in_ticket_channel"], ephemeral=True)
            return

        if config.get("require_staff_approval_for_add_user", False):
            await request_staff_approval_for_add(interaction, member, config, lang)
        else:
            await interaction.channel.set_permissions(member, read_messages=True, send_messages=True)
            await interaction.response.send_message(lang["user_added"].format(member=member.mention), ephemeral=True)

    @ticket_commands.command(name="close", description=lang["close_command_description"])
    async def ticket_close(interaction: discord.Interaction):
        if not is_ticket_channel(interaction.channel):
            await interaction.response.send_message(lang["not_in_ticket_channel"], ephemeral=True)
            return

        if not await can_close_ticket(interaction.user, interaction.channel, config):
            await interaction.response.send_message(lang["no_permission_close"], ephemeral=True)
            return

        await close_ticket(interaction.channel, interaction.user, config, lang)
        await interaction.response.send_message(lang["ticket_closed"], ephemeral=True)

    tree.add_command(ticket_commands)

    async def on_ready():
        channel_id = config.get("ticket_panel_channel_id")
        if channel_id is None:
            print(colorama.Fore.YELLOW + "[!] TicketSystem: Ticket panel channel ID not set.")
            return
        channel = bot.get_channel(channel_id)
        if channel is None:
            print(colorama.Fore.YELLOW + f"[!] TicketSystem: Cannot find channel with ID {channel_id}")
            return

        if config.get("ticket_panel_message_id") is None:
            print(colorama.Fore.YELLOW + "[!] TicketSystem: 'ticket_panel_message_id' not set. After completing setup and adding the placeholder message_id, restart the bot.")
        else:
            try:
                message_id = config["ticket_panel_message_id"]
                message = await channel.fetch_message(message_id)
                # Edit this message to the actual open ticket message
                embed = get_ticket_panel_embed(config, lang)
                view = TicketPanelView(config, lang)
                await message.edit(content=None, embed=embed, view=view)

                # Register the view so the button works after restart
                bot.add_view(view)
                print(colorama.Fore.GREEN + "[+] TicketSystem: Ticket panel message updated and persistent view registered!")
            except discord.NotFound:
                print(colorama.Fore.YELLOW + "[!] TicketSystem: Ticket panel message not found. Check 'ticket_panel_message_id' in config.")
            except Exception as e:
                print(colorama.Fore.RED + f"[-] TicketSystem: Error fetching ticket panel message: {e}")

    if not hasattr(bot, "on_ready_callbacks"):
        bot.on_ready_callbacks = []
    bot.on_ready_callbacks.append(on_ready)

    class TicketPanelView(discord.ui.View):
        def __init__(self, conf, lang):
            super().__init__(timeout=None)
            self.config = conf
            self.lang = lang

            if conf.get("enable_categories", False):
                categories = conf.get("categories", {})
                for category_name in categories:
                    button = discord.ui.Button(
                        label=category_name,
                        style=discord.ButtonStyle.primary,
                        custom_id=f"ticket_panel_{category_name}"
                    )
                    button.callback = self.create_ticket_callback(category_name)
                    self.add_item(button)
            else:
                button = discord.ui.Button(
                    label=lang["open_ticket_button"],
                    style=discord.ButtonStyle.primary,
                    custom_id="ticket_panel_open"
                )
                button.callback = self.create_ticket_callback(None)
                self.add_item(button)

        def create_ticket_callback(self, category_name):
            async def callback(interaction: discord.Interaction):
                await create_ticket(interaction, category_name, self.config, lang)
            return callback

    async def create_ticket(interaction: discord.Interaction, category_name: typing.Optional[str], conf, lang):
        guild = interaction.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }

        support_role_ids = conf.get("support_roles", [])
        for role_id in support_role_ids:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        if category_name and conf.get("enable_categories", False):
            category_id = conf.get("categories", {}).get(category_name)
            if category_id:
                category = guild.get_channel(category_id)
            else:
                await interaction.response.send_message(lang["category_not_found"], ephemeral=True)
                return
        else:
            category_id = conf.get("ticket_category_id")
            category = guild.get_channel(category_id)

        if category is None:
            await interaction.response.send_message(lang["category_not_found"], ephemeral=True)
            return

        channel_name = f"ticket-{interaction.user.name.lower()}"
        ticket_channel = await guild.create_text_channel(channel_name, overwrites=overwrites, category=category)

        embed = discord.Embed(title=lang["ticket_created_title"], description=lang["ticket_created_description"].format(user=interaction.user.mention), color=discord.Color.green())
        channel_id = ticket_channel.id
        close_button_id = f"ticket_close_button_{channel_id}"
        view = TicketChannelView(conf, lang, close_button_id)
        await ticket_channel.send(embed=embed, view=view)

        # Register the ticket channel view
        bot.add_view(view)

        await interaction.response.send_message(lang["ticket_opened"].format(channel=ticket_channel.mention), ephemeral=True)

    class TicketChannelView(discord.ui.View):
        def __init__(self, conf, lang, close_button_id: str):
            super().__init__(timeout=None)
            self.config = conf
            self.lang = lang

            button = discord.ui.Button(
                label=lang["close_ticket_button"],
                style=discord.ButtonStyle.danger,
                custom_id=close_button_id
            )
            self.add_item(button)

    def is_ticket_channel(channel: discord.TextChannel) -> bool:
        return channel.name.startswith("ticket-")

    async def can_close_ticket(user: discord.Member, channel: discord.TextChannel, conf) -> bool:
        if channel.name.startswith(f"ticket-{user.name.lower()}"):
            return True
        support_role_ids = conf.get("support_roles", [])
        for role_id in support_role_ids:
            role = user.guild.get_role(role_id)
            if role in user.roles:
                return True
        return False

    async def close_ticket(channel: discord.TextChannel, closed_by: discord.Member, conf, lang):
        messages = [msg async for msg in channel.history(limit=None, oldest_first=True)]
        transcript = ""
        for message in messages:
            timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
            if message.embeds:
                index = 1
                for embed in message.embeds:
                    content = f"EMBED {index}: {embed.title} \n ------> {'------>'.join(s + '\n' for s in embed.description.splitlines())}"
                    content += f"Fields: ------------> {'------------>'.join(f.name + ': ' + f.value + '\n' for f in embed.fields)}"
                    if embed.image:
                        content += f"Image: {embed.image.url}"
                    if embed.thumbnail:
                        content += f"Thumbnail: {embed.thumbnail.url}"
                    if embed.footer:
                        content += f"Footer: {embed.footer.text}"
                    index += 1
            else:
                content = message.content
            transcript += f"[{timestamp}] {message.author.name}: {content}\n"
        transcript = transcript.encode('utf-8').decode('utf-8')

        log_channel_id = conf.get("ticket_log_channel_id")
        log_channel = channel.guild.get_channel(log_channel_id)
        if log_channel:
            transcript_file = discord.File(fp=io.StringIO(transcript), filename=f"transcript-{channel.name}.txt")
            await log_channel.send(content=lang["ticket_transcript_log"].format(channel=channel.name, closed_by=closed_by.mention), file=transcript_file)

        await channel.delete()

    async def request_staff_approval_for_add(interaction: discord.Interaction, member: discord.Member, conf, lang):
        support_role_ids = conf.get("support_roles", [])
        support_roles = [interaction.guild.get_role(role_id) for role_id in support_role_ids if interaction.guild.get_role(role_id)]
        if not support_roles:
            await interaction.response.send_message(lang["no_support_roles_configured"], ephemeral=True)
            return
        support_roles_mentions = ' '.join(role.mention for role in support_roles)
        embed = discord.Embed(title=lang["add_member_request_title"], description=lang["add_member_request_description"].format(requester=interaction.user.mention, member=member.mention), color=discord.Color.blue())
        await interaction.channel.send(content=support_roles_mentions, embed=embed, view=AddMemberApprovalView(member, interaction.user, conf, lang))
        await interaction.response.send_message(lang["add_member_request_sent"], ephemeral=True)

    class AddMemberApprovalView(discord.ui.View):
        def __init__(self, member_to_add: discord.Member, requester: discord.Member, conf, lang):
            super().__init__(timeout=60)
            self.member_to_add = member_to_add
            self.requester = requester
            self.config = conf
            self.lang = lang

        @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, custom_id="approve_add_member")
        async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not is_support_staff(interaction.user, self.config):
                await interaction.response.send_message(self.lang["no_permission_approve"], ephemeral=True)
                return
            await interaction.channel.set_permissions(self.member_to_add, read_messages=True, send_messages=True)
            await interaction.response.send_message(self.lang["member_added_approved"].format(member=self.member_to_add.mention))
            self.stop()

        @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, custom_id="deny_add_member")
        async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not is_support_staff(interaction.user, self.config):
                await interaction.response.send_message(self.lang["no_permission_deny"], ephemeral=True)
                return
            await interaction.response.send_message(self.lang["member_add_denied"].format(member=self.member_to_add.mention))
            self.stop()

        async def on_timeout(self):
            await self.requester.send(self.lang["add_member_request_timeout"])

    def is_support_staff(member: discord.Member, conf) -> bool:
        support_role_ids = conf.get("support_roles", [])
        for role_id in support_role_ids:
            role = member.guild.get_role(role_id)
            if role in member.roles:
                return True
        return False

    def get_ticket_panel_embed(conf, lang):
        embed = discord.Embed(title=lang["ticket_panel_title"], description=lang["ticket_panel_description"], color=discord.Color.blue())
        return embed

    def get_config_instructions(enable_categories: bool, categories: dict, ticket_category_id: int, support_roles: list, ticket_panel_channel_id: int, ticket_log_channel_id: int, require_staff_approval_for_add_user: bool):
        categories_yaml = ""
        if enable_categories and categories:
            categories_yaml = "  categories:\n"
            for name, cid in categories.items():
                categories_yaml += f"    '{name}': {cid}\n"

        roles_yaml = ""
        for rid in support_roles:
            roles_yaml += f"    - {rid}\n"

        instructions = f"""ticket_system:
  enable_categories: {str(enable_categories).lower()}
{categories_yaml if enable_categories else ''}
  ticket_category_id: {ticket_category_id if not enable_categories else '# Not needed when enable_categories is true'}
  support_roles:
{roles_yaml if support_roles else '    # Add support role IDs here'}
  ticket_panel_channel_id: {ticket_panel_channel_id}
  ticket_log_channel_id: {ticket_log_channel_id}
  require_staff_approval_for_add_user: {str(require_staff_approval_for_add_user).lower()}
  # After sending the placeholder message below, please copy its ID into ticket_panel_message_id:
  # ticket_panel_message_id: <PUT_MESSAGE_ID_HERE>
"""
        return instructions

    #####################
    # Setup Wizard Code #
    #####################

    class SetupWizardView(discord.ui.View):
        def __init__(self, config, lang, guild: discord.Guild):
            super().__init__(timeout=600)
            self.config = config
            self.lang = lang
            self.guild = guild

            # Temporary storage of user choices
            self.enable_categories = False
            self.categories = {}
            self.ticket_category_id = None
            self.support_roles = []
            self.ticket_panel_channel_id = None
            self.ticket_log_channel_id = None
            self.require_staff_approval_for_add_user = False

            self.add_item(EnableCategoriesButton(lang))
            self.add_item(NextStepButton(lang, lang["skip_categories_button"], self.skip_categories))

        async def skip_categories(self, interaction: discord.Interaction):
            await interaction.response.edit_message(
                content=self.lang["select_ticket_category"] + "\n\nYou selected to skip categories.",
                view=SelectChannelView(self, self.lang, self.guild, "ticket_category_id", is_category=True)
            )

        def all_steps_done(self):
            if self.enable_categories:
                if not self.categories:
                    return False
            else:
                if not self.ticket_category_id:
                    return False
            if not self.support_roles:
                return False
            if not self.ticket_panel_channel_id:
                return False
            if not self.ticket_log_channel_id:
                return False
            return True

        async def show_final_instructions(self, interaction: discord.Interaction, additional_info: str = ""):
            instructions = get_config_instructions(
                enable_categories=self.enable_categories,
                categories=self.categories,
                ticket_category_id=self.ticket_category_id if not self.enable_categories else 0,
                support_roles=self.support_roles,
                ticket_panel_channel_id=self.ticket_panel_channel_id,
                ticket_log_channel_id=self.ticket_log_channel_id,
                require_staff_approval_for_add_user=self.require_staff_approval_for_add_user
            )

            # Send a placeholder message in the selected panel channel
            panel_channel = self.guild.get_channel(self.ticket_panel_channel_id)
            if panel_channel:
                placeholder_message = await panel_channel.send(self.lang["ticket_panel_placeholder"])
                instructions += f"\n# ticket_panel_message_id: {placeholder_message.id}"

                await interaction.response.edit_message(
                    content=self.lang["setup_done"].format(instructions=instructions) + f"\n\n{additional_info}\n\n" + self.lang["update_message_id_in_config"].format(message_id=placeholder_message.id),
                    view=None
                )
            else:
                await interaction.response.edit_message(
                    content=self.lang["setup_done"].format(instructions=instructions) + f"\n\n{additional_info}\n\n" + self.lang["panel_channel_not_found"],
                    view=None
                )

    class EnableCategoriesButton(discord.ui.Button):
        def __init__(self, lang):
            super().__init__(label=lang["enable_categories_button"], style=discord.ButtonStyle.primary)

        async def callback(self, interaction: discord.Interaction):
            view: SetupWizardView = self.view
            explanation = view.lang["enable_categories_explanation_detailed"]
            await interaction.response.edit_message(content=explanation, view=EnableCategoriesView(view, view.lang))

    class YesNoCategoriesSelect(discord.ui.Select):
        def __init__(self, wizard_view, lang):
            self.wizard_view = wizard_view
            self.lang = lang
            options = [
                discord.SelectOption(label=lang["yes_option"], value="yes"),
                discord.SelectOption(label=lang["no_option"], value="no")
            ]
            super().__init__(placeholder=lang["select_yes_no"], options=options)

        async def callback(self, interaction: discord.Interaction):
            user_choice = self.values[0]
            if user_choice == "yes":
                self.wizard_view.enable_categories = True
                await interaction.response.edit_message(
                    content=self.lang["select_categories_now"] + f"\n\nYou selected: **Enable categories**",
                    view=SelectCategoriesView(self.wizard_view, self.lang, self.wizard_view.guild)
                )
            else:
                self.wizard_view.enable_categories = False
                await interaction.response.edit_message(
                    content=self.lang["select_ticket_category"] + f"\n\nYou selected: **Disable categories**",
                    view=SelectChannelView(self.wizard_view, self.lang, self.wizard_view.guild, "ticket_category_id", is_category=True)
                )

    class EnableCategoriesView(discord.ui.View):
        def __init__(self, wizard_view: SetupWizardView, lang):
            super().__init__(timeout=600)
            self.wizard_view = wizard_view
            self.lang = lang
            self.add_item(YesNoCategoriesSelect(wizard_view, lang))

        async def on_timeout(self):
            pass

    class CategoriesSelect(discord.ui.Select):
        def __init__(self, wizard_view, lang, guild: discord.Guild):
            self.wizard_view = wizard_view
            self.lang = lang
            self.guild = guild
            categories = [c for c in guild.channels if isinstance(c, discord.CategoryChannel)]
            if categories:
                options = [discord.SelectOption(label=c.name, value=str(c.id)) for c in categories]
            else:
                options = []
            super().__init__(placeholder=lang["select_one_or_more_categories"], options=options, min_values=1, max_values=len(options) if options else 1)

        async def callback(self, interaction: discord.Interaction):
            if not self.values:
                await interaction.response.send_message(self.wizard_view.lang["no_categories_selected"], ephemeral=True)
                return
            chosen_categories = []
            for cid_str in self.values:
                cid = int(cid_str)
                cat = self.guild.get_channel(cid)
                if cat:
                    self.wizard_view.categories[cat.name] = cid
                    chosen_categories.append(cat.name)
            chosen_list_str = ", ".join(chosen_categories)
            await interaction.response.edit_message(
                content=self.lang["select_support_roles"] + f"\n\nYou selected categories: **{chosen_list_str}**",
                view=SelectRolesView(self.wizard_view, self.lang, self.guild, "support_roles")
            )

    class SelectCategoriesView(discord.ui.View):
        def __init__(self, wizard_view: SetupWizardView, lang, guild: discord.Guild):
            super().__init__(timeout=600)
            self.wizard_view = wizard_view
            self.lang = lang
            self.guild = guild
            self.add_item(CategoriesSelect(wizard_view, lang, guild))

        async def on_timeout(self):
            pass

    class ChannelSelect(discord.ui.Select):
        def __init__(self, wizard_view, lang, guild, field_name: str, is_category: bool):
            self.wizard_view = wizard_view
            self.lang = lang
            self.guild = guild
            self.field_name = field_name
            self.is_category = is_category

            if self.is_category:
                channels = [c for c in guild.channels if isinstance(c, discord.CategoryChannel)]
            else:
                channels = [c for c in guild.channels if isinstance(c, discord.TextChannel)]

            options = [discord.SelectOption(label=c.name, value=str(c.id)) for c in channels] if channels else []
            placeholder = lang["select_a_channel"]
            super().__init__(placeholder=placeholder, options=options, min_values=1, max_values=1)

        async def callback(self, interaction: discord.Interaction):
            if not self.values:
                await interaction.response.send_message(self.lang["no_channel_selected"], ephemeral=True)
                return
            cid = int(self.values[0])
            selected_channel = self.guild.get_channel(cid)
            selected_name = selected_channel.name if selected_channel else f"ID {cid}"

            if self.field_name == "ticket_category_id":
                self.wizard_view.ticket_category_id = cid
                await interaction.response.edit_message(
                    content=self.lang["select_support_roles"] + f"\n\nYou selected category: **{selected_name}**",
                    view=SelectRolesView(self.wizard_view, self.lang, self.guild, "support_roles")
                )
            elif self.field_name == "ticket_panel_channel_id":
                self.wizard_view.ticket_panel_channel_id = cid
                await interaction.response.edit_message(
                    content=self.lang["select_log_channel"] + f"\n\nYou selected panel channel: **{selected_name}**",
                    view=SelectChannelView(self.wizard_view, self.lang, self.guild, "ticket_log_channel_id")
                )
            elif self.field_name == "ticket_log_channel_id":
                self.wizard_view.ticket_log_channel_id = cid
                await interaction.response.edit_message(
                    content=self.lang["require_staff_approval_question"] + f"\n\nYou selected log channel: **{selected_name}**",
                    view=RequireStaffApprovalView(self.wizard_view, self.lang)
                )
            else:
                await interaction.response.send_message("Unknown field. Please report this issue.", ephemeral=True)

    class SelectChannelView(discord.ui.View):
        def __init__(self, wizard_view: SetupWizardView, lang, guild: discord.Guild, field_name: str, is_category=False):
            super().__init__(timeout=600)
            self.wizard_view = wizard_view
            self.lang = lang
            self.guild = guild
            self.field_name = field_name
            self.is_category = is_category
            self.add_item(ChannelSelect(wizard_view, lang, guild, field_name, is_category=is_category))

        async def on_timeout(self):
            pass

    class RolesSelect(discord.ui.Select):
        def __init__(self, wizard_view, lang, guild):
            self.wizard_view = wizard_view
            self.lang = lang
            self.guild = guild
            roles = [r for r in guild.roles if not r.is_default()]
            options = [discord.SelectOption(label=r.name, value=str(r.id)) for r in roles]
            super().__init__(placeholder=lang["select_one_or_more_roles"], options=options, min_values=1, max_values=len(options) if options else 1)

        async def callback(self, interaction: discord.Interaction):
            if not self.values:
                await interaction.response.send_message(self.lang["no_roles_selected"], ephemeral=True)
                return
            self.wizard_view.support_roles = [int(rid) for rid in self.values]
            chosen_roles = []
            for rid in self.values:
                role_obj = self.guild.get_role(int(rid))
                if role_obj:
                    chosen_roles.append(role_obj.name)
            chosen_roles_str = ", ".join(chosen_roles)
            await interaction.response.edit_message(
                content=self.lang["select_panel_channel"] + f"\n\nYou selected support roles: **{chosen_roles_str}**",
                view=SelectChannelView(self.wizard_view, self.lang, self.guild, "ticket_panel_channel_id")
            )

    class SelectRolesView(discord.ui.View):
        def __init__(self, wizard_view: SetupWizardView, lang, guild: discord.Guild, field_name: str):
            super().__init__(timeout=600)
            self.wizard_view = wizard_view
            self.lang = lang
            self.guild = guild
            self.field_name = field_name
            self.add_item(RolesSelect(wizard_view, lang, guild))

        async def on_timeout(self):
            pass

    class YesNoStaffApprovalSelect(discord.ui.Select):
        def __init__(self, wizard_view, lang):
            self.wizard_view = wizard_view
            self.lang = lang
            options = [
                discord.SelectOption(label=lang["yes_option"], value="yes"),
                discord.SelectOption(label=lang["no_option"], value="no")
            ]
            super().__init__(placeholder=lang["select_yes_no"], options=options)

        async def callback(self, interaction: discord.Interaction):
            user_choice = self.values[0]
            chosen_text = "Require staff approval" if user_choice == "yes" else "Do not require staff approval"
            if user_choice == "yes":
                self.wizard_view.require_staff_approval_for_add_user = True
            else:
                self.wizard_view.require_staff_approval_for_add_user = False

            if self.wizard_view.all_steps_done():
                await self.wizard_view.show_final_instructions(interaction, additional_info=f"You selected: **{chosen_text}**")
            else:
                await interaction.response.send_message("An error occurred: not all steps are done. Please report this issue.", ephemeral=True)

    class RequireStaffApprovalView(discord.ui.View):
        def __init__(self, wizard_view: SetupWizardView, lang):
            super().__init__(timeout=600)
            self.wizard_view = wizard_view
            self.lang = lang
            self.add_item(YesNoStaffApprovalSelect(wizard_view, lang))

        async def on_timeout(self):
            pass

    class NextStepButton(discord.ui.Button):
        def __init__(self, lang, label_text: str, callback_function):
            super().__init__(label=label_text, style=discord.ButtonStyle.secondary)
            self.callback_function = callback_function
            self.lang = lang

        async def callback(self, interaction: discord.Interaction):
            await self.callback_function(interaction)

    async def on_interaction(interaction: discord.Interaction):
        if not isinstance(interaction, discord.Interaction):
            return

        # Only process component interactions
        if interaction.type != discord.InteractionType.component:
            return

        component = interaction.data
        if component.get("component_type") != 2: # Buttons have component_type 2
            return

        custom_id = component["custom_id"]
        # Handle close button logic here
        if custom_id.startswith("ticket_close_button_"):
            channel = interaction.channel
            if not isinstance(channel, discord.TextChannel):
                return

            # Check if user can close
            if not await can_close_ticket(interaction.user, channel, config):
                await interaction.response.send_message(lang["no_permission_close"], ephemeral=True)
                return

            await interaction.response.send_message(lang["ticket_closed"], ephemeral=True)
            await close_ticket(channel, interaction.user, config, lang)

    if not hasattr(bot, "on_interaction_callbacks"):
        bot.on_interaction_callbacks = []
    bot.on_interaction_callbacks.append(on_interaction)
