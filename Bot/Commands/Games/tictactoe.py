import discord
import random
import utils


def init(tree: discord.app_commands.CommandTree, bot: discord.Client, config: dict, lang: dict):
    tictactoe_commands = discord.app_commands.Group(name="tictactoe", description=lang["command_description"])

    @tictactoe_commands.command(name="friend", description=lang["friend_command_description"])
    async def tictactoe_friend(interaction: discord.Interaction):
        """
        Play tictactoe with a friend
        :param interaction: discord.Interaction the interaction
        :return: None
        """
        em = discord.Embed(title=lang["friend"]["embed_before_game"]["title"], description=utils.replace_variables(lang["friend"]["embed_before_game"]["description"]), color=discord.Color.from_str(config["embed"]["color"]))
        em.set_footer(text=utils.replace_variables(lang["friend"]["embed_before_game"]["footer"], member=interaction.user), icon_url=interaction.user.avatar.url)
        await interaction.response.send_message(embed=em, view=TicTacToe_wating_view(interaction.user, lang))

    tree.add_command(tictactoe_commands)


class TicTacToe_view(discord.ui.View):
    def __init__(self, player1: discord.Member, player2: discord.Member, x: discord.Member, lang: dict):
        super().__init__(timeout=300)
        self.lang = lang
        self.player1 = player1
        self.player2 = player2
        self.x = x
        self.o = player1 if self.x == player2 else player2
        self.current_player = x
        self.board = [["" for _ in range(3)] for _ in range(3)]
        self.add_buttons()
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.gray, label=player1.name, disabled=True, row=3))
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.gray, label=player2.name, disabled=True, row=3))

    def add_buttons(self):
        for x in range(3):
            for y in range(3):
                button = TicTacToe_button(x, y)
                self.add_item(button)

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user == self.current_player:
            return True
        elif interaction.user == self.player1 or interaction.user == self.player2:
            await interaction.response.send_message(self.lang["wrong_turn"], ephemeral=True)
        else:
            await interaction.response.send_message(self.lang["not_allowed"], ephemeral=True)
        return False


class TicTacToe_button(discord.ui.Button):
    def __init__(self, x: int, y: int):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=x)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        view: TicTacToe_view = self.view
        if view.current_player == view.player1:
            self.style = discord.ButtonStyle.blurple
            self.label = "X"
            self.disabled = True
            view.board[self.x][self.y] = "X"
            view.current_player = view.player2
        else:
            self.style = discord.ButtonStyle.blurple
            self.label = "O"
            self.disabled = True
            view.board[self.x][self.y] = "O"
            view.current_player = view.player1
        if (check_for_winner := await self.check_for_winner(view.board)) is None:
            if all(all(x != "" for x in y) for y in view.board):
                for child in view.children:
                    if child.type == discord.ComponentType.button:
                        child.disabled = True
                        if child.style == discord.ButtonStyle.secondary and child.label == "\u200b":
                            child.style = discord.ButtonStyle.red
                em = interaction.message.embeds[0]
                em.description = view.lang["friend"]["embed_after_game"]["description"].replace("{{winner}}", view.lang["tie"])
                await interaction.response.edit_message(view=view, embed=em, content=f"")
                view.stop()
                return
            em = interaction.message.embeds[0]
            em.description = view.lang["friend"]["embed_in_game"]["description"].replace("{{c_player}}", view.current_player.mention).replace("{{player1}}", view.player1.mention).replace("{{player2}}", view.player2.mention)
            await interaction.response.edit_message(view=view, embed=em, content=f"{view.current_player.mention}")
        else:
            for x, y in check_for_winner:
                view.children[x * 3 + y].style = discord.ButtonStyle.green
            for child in view.children:
                if child.type == discord.ComponentType.button:
                    child.disabled = True
                    if child.style == discord.ButtonStyle.secondary and child.label == "\u200b":
                        child.style = discord.ButtonStyle.red
            em = interaction.message.embeds[0]
            em.description = view.lang["friend"]["embed_after_game"]["description"].replace("{{winner}}", view.player1.mention if view.current_player == view.player2 else view.player2.mention)
            await interaction.response.edit_message(view=view, embed=em, content=f"")
            view.stop()

    async def on_timeout(self):
        self.style = discord.ButtonStyle.red
        self.label = "\u200b"
        self.disabled = True
        await self.view.message.edit(view=self.view)

    async def check_for_winner(self, board: list):
        for i in range(3):
            if board[i][0] == board[i][1] == board[i][2] != "":
                return [(i, 0), (i, 1), (i, 2)]
            if board[0][i] == board[1][i] == board[2][i] != "":
                return [(0, i), (1, i), (2, i)]
        if board[0][0] == board[1][1] == board[2][2] != "":
            return [(0, 0), (1, 1), (2, 2)]
        if board[0][2] == board[1][1] == board[2][0] != "":
            return [(0, 2), (1, 1), (2, 0)]
        return None


class TicTacToe_wating_view(discord.ui.View):
    def __init__(self, player1: discord.Member, lang: dict):
        super().__init__()
        self.player1 = player1
        self.player2 = None
        self.lang = lang
        for i in range(0, 3):
            for j in range(3):
                if i % 2 == 0:
                    if j % 2 == 0:
                        self.add_item(discord.ui.Button(style=discord.ButtonStyle.red, label="\u200b", disabled=True, row=i))
                    else:
                        self.add_item(discord.ui.Button(style=discord.ButtonStyle.green, label="\u200b", disabled=True, row=i))
                else:
                    if j % 2 == 0:
                        self.add_item(discord.ui.Button(style=discord.ButtonStyle.green, label="\u200b", disabled=True, row=i))
                    else:
                        self.add_item(discord.ui.Button(style=discord.ButtonStyle.red, label="\u200b", disabled=True, row=i))
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.gray, label=player1.name, disabled=True, row=3))
        self.add_item(TicTacToe_wating_button(self.lang))


class TicTacToe_wating_button(discord.ui.Button):
    def __init__(self, lang: dict):
        self.lang = lang
        super().__init__(style=discord.ButtonStyle.gray, label=self.lang["friend"]["embed_before_game"]["join_button"], row=3)

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        view: TicTacToe_wating_view = self.view
        if view.player1 == interaction.user:
            return await interaction.response.send_message(self.lang["friend"]["embed_before_game"]["play_with_yourself"], ephemeral=True)
        view.player2 = interaction.user
        x = random.choice([view.player1, view.player2])
        em = interaction.message.embeds[0]
        em.description = self.lang["friend"]["embed_in_game"]["description"].replace("{{c_player}}", x.mention).replace("{{player1}}", view.player1.mention).replace("{{player2}}", view.player2.mention)
        em.set_footer(text=None, icon_url=None)
        await interaction.response.edit_message(embed=em, view=TicTacToe_view(view.player1, view.player2, x, self.lang), content=f"{x.mention}")
        view.stop()