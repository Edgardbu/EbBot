import discord
import random
import utils
import discord

def init(tree: discord.app_commands.CommandTree, bot: discord.Client, config: dict, lang: dict):
    minesweeper_commands = discord.app_commands.Group(name="minesweeper", description=lang["command_description"])

    @minesweeper_commands.command(name="play", description=lang["play_command_description"])
    @discord.app_commands.describe(bombs=lang.get("bombs_description", "Number of bombs (4-9)"))
    async def minesweeper_play(interaction: discord.Interaction,
                               bombs: discord.app_commands.Range[int, 4, 9] = 6):
        """
        Start a Minesweeper game with a specified number of bombs or 6 by default.
        """
        em = discord.Embed(
            title=lang["embed"]["title"],
            description=lang["embed"]["description"],
            color=discord.Color.from_str(config["embed"]["color"])
        )
        em.set_footer(
            text=utils.replace_variables(lang["embed"]["footer"], member=interaction.user),
            icon_url=interaction.user.avatar.url
        )
        await interaction.response.send_message(embed=em, view=MinesweeperView(interaction.user, lang, bombs=bombs))

    tree.add_command(minesweeper_commands)

class MinesweeperView(discord.ui.View):
    """
    A view that represents a Minesweeper game.
    """
    def __init__(self, player: discord.Member, lang: dict, rows: int = 5, cols: int = 4, bombs: int = 6):
        super().__init__(timeout=300)
        self.player = player
        self.lang = lang
        self.rows = rows
        self.cols = cols
        self.bombs = bombs
        self.grid = [['' for _ in range(cols)] for _ in range(rows)]
        self.revealed = [[False for _ in range(cols)] for _ in range(rows)]
        self.flags = [[False for _ in range(cols)] for _ in range(rows)]
        self.game_over = False
        self.mode = 'Reveal'
        self.bombs_generated = False
        #bombs will be generated when the first cell is clicked so that the player can't lose on the first click
        self.add_buttons()
        self.add_item(ModeButton(self))

    def generate_board(self, first_click_x: int, first_click_y: int):
        available_positions = [
            (x, y) for x in range(self.rows) for y in range(self.cols)
            if not (x == first_click_x and y == first_click_y)
        ]
        bomb_positions = random.sample(available_positions, self.bombs)
        for x, y in bomb_positions:
            self.grid[x][y] = 'B'

        for x in range(self.rows):
            for y in range(self.cols):
                if self.grid[x][y] != 'B':
                    count = 0
                    for dx in (-1, 0, 1):
                        for dy in (-1, 0, 1):
                            if dx == 0 and dy == 0:
                                continue
                            nx, ny = x + dx, y + dy
                            if 0 <= nx < self.rows and 0 <= ny < self.cols and self.grid[nx][ny] == 'B':
                                count += 1
                    self.grid[x][y] = str(count) if count > 0 else '0'
        self.bombs_generated = True

    def add_buttons(self):
        for x in range(self.rows):
            for y in range(self.cols):
                button = MinesweeperButton(x, y)
                button.row = x
                self.add_item(button)

    def check_win(self):
        for x in range(self.rows):
            for y in range(self.cols):
                if self.grid[x][y] != 'B' and not self.revealed[x][y]:
                    return False
        return True

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user == self.player:
            return True
        else:
            await interaction.response.send_message(self.lang["not_your_game"], ephemeral=True)
            return False

class MinesweeperButton(discord.ui.Button):
    def __init__(self, x: int, y: int):
        super().__init__(style=discord.ButtonStyle.secondary, label='\u200b', row=x)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        view: MinesweeperView = self.view
        if interaction.user != view.player:
            await interaction.response.send_message(view.lang["not_your_game"], ephemeral=True)
            return
        if view.game_over:
            await interaction.response.send_message(view.lang["game_over"], ephemeral=True)
            return
        if view.mode == 'Reveal':
            await self.reveal_cell(interaction)
        else:
            await self.flag_cell(interaction)

    async def reveal_cell(self, interaction: discord.Interaction):
        view: MinesweeperView = self.view
        x, y = self.x, self.y

        if not view.bombs_generated:
            view.generate_board(x, y)

        if view.revealed[x][y]:
            await interaction.response.send_message(view.lang["already_revealed"], ephemeral=True)
            return
        if view.flags[x][y]:
            await interaction.response.send_message(view.lang["already_flagged"], ephemeral=True)
            return
        view.revealed[x][y] = True
        cell_value = view.grid[x][y]
        if cell_value == 'B':
            self.style = discord.ButtonStyle.danger
            self.label = '💣'
            view.game_over = True
            for child in view.children:
                if isinstance(child, MinesweeperButton):
                    cx, cy = child.x, child.y
                    if view.grid[cx][cy] == 'B':
                        child.style = discord.ButtonStyle.danger
                        child.label = '💣'
                    child.disabled = True
            em = discord.Embed(
                title=view.lang["game_over_embed"]["title"],
                description=view.lang["game_over_embed"]["description"],
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=em, view=view)
            view.stop()
        else:
            num = int(cell_value)
            if num == 0:
                self.label = '\u200b'
                self.style = discord.ButtonStyle.gray
                self.disabled = True
                await self.expand_zero(x, y)
            else:
                self.label = cell_value
                self.style = discord.ButtonStyle.gray
                self.disabled = True
            if view.check_win():
                em = discord.Embed(
                    title=view.lang["win_embed"]["title"],
                    description=view.lang["win_embed"]["description"],
                    color=discord.Color.green()
                )
                for child in view.children:
                    child.disabled = True
                await interaction.response.edit_message(embed=em, view=view)
                view.stop()
            else:
                await interaction.response.edit_message(view=view)

    async def expand_zero(self, x: int, y: int):
        view: MinesweeperView = self.view
        queue = [(x, y)]
        while queue:
            cx, cy = queue.pop(0)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < view.rows and 0 <= ny < view.cols and not view.revealed[nx][ny]:
                        if view.flags[nx][ny]:
                            continue
                        view.revealed[nx][ny] = True
                        button = next(
                            (child for child in view.children if isinstance(child, MinesweeperButton) and child.x == nx and child.y == ny),
                            None
                        )
                        if button:
                            cell_value = view.grid[nx][ny]
                            if cell_value == '0':
                                button.label = '\u200b'
                                button.style = discord.ButtonStyle.gray
                                button.disabled = True
                                queue.append((nx, ny))
                            else:
                                button.label = cell_value
                                button.style = discord.ButtonStyle.gray
                                button.disabled = True

    async def flag_cell(self, interaction: discord.Interaction):
        view: MinesweeperView = self.view
        x, y = self.x, self.y
        if view.revealed[x][y]:
            await interaction.response.send_message(view.lang["already_revealed"], ephemeral=True)
            return
        if view.flags[x][y]:
            # Unflag
            view.flags[x][y] = False
            self.label = '\u200b'
            self.style = discord.ButtonStyle.secondary
        else:
            # Flag
            view.flags[x][y] = True
            self.label = '🚩'
            self.style = discord.ButtonStyle.danger
        await interaction.response.edit_message(view=view)

class ModeButton(discord.ui.Button):
    def __init__(self, view: MinesweeperView):
        super().__init__(label=view.lang["reveal_mode"], style=discord.ButtonStyle.primary, row=4)
        self.mode_label = 'Reveal'

    async def callback(self, interaction: discord.Interaction):
        view: MinesweeperView = self.view
        if interaction.user != view.player:
            await interaction.response.send_message(view.lang["not_your_game"], ephemeral=True)
            return
        if view.mode == 'Reveal':
            view.mode = 'Flag'
            self.label = view.lang["flag_mode"]
            self.style = discord.ButtonStyle.danger
        else:
            view.mode = 'Reveal'
            self.label = view.lang["reveal_mode"]
            self.style = discord.ButtonStyle.primary
        await interaction.response.edit_message(view=view)
