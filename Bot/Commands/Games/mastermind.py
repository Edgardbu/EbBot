# mastermind.py
import discord
import random
import utils
from discord import app_commands

# Available colors for Mastermind. Each item has an 'emoji' and a short 'id'.
COLOR_OPTIONS = [
    {"id": "R", "emoji": "🟥"},
    {"id": "B", "emoji": "🟦"},
    {"id": "G", "emoji": "🟩"},
    {"id": "Y", "emoji": "🟨"},
    {"id": "P", "emoji": "🟪"},
    {"id": "O", "emoji": "🟧"},
]

CODE_LENGTH = 4
MAX_ATTEMPTS = 10

def init(tree: app_commands.CommandTree, bot: discord.Client, config: dict, lang: dict):
    """
    Initializes the Mastermind command.
    """
    mastermind_group = app_commands.Group(name="mastermind", description=lang["command_description"])

    @mastermind_group.command(name="play", description=lang["play_command_description"])
    async def mastermind_play(interaction: discord.Interaction):
        """
        Start a Mastermind game session.
        """
        mastermind_config = config
        code_length = mastermind_config["settings"]["code_length"]
        max_attempts = mastermind_config["settings"]["max_attempts"]

        color_list = " ".join(mastermind_config["icons"].values())

        embed = discord.Embed(
            title=lang["embed_title"],
            description=lang["embed_description"].replace("{{code_length}}", str(code_length)).replace("{{max_attempts}}", str(max_attempts)).replace("{{color_list}}", color_list),
            color=discord.Color.from_str(mastermind_config["embed"]["color"])
        )
        embed.set_footer(
            text=utils.replace_variables(lang["embed_footer"], member=interaction.user)
        )

        game = MastermindGame(interaction.user, mastermind_config, lang)
        view = MastermindView(game)

        await interaction.response.send_message(embed=embed, view=view)
        message = await interaction.original_response()
        game.message = message

    tree.add_command(mastermind_group)


class MastermindGame:
    def __init__(self, player: discord.Member, config: dict, lang: dict):
        self.player = player
        self.config = config
        self.lang = lang
        self.code_length = config["settings"]["code_length"]
        self.max_attempts = config["settings"]["max_attempts"]
        self.secret_code = self.generate_code()
        self.attempts = 0
        self.guesses = []
        self.solved = False
        self.message: discord.Message = None

    def generate_code(self):
        color_keys = list(self.config["icons"].keys())
        return [random.choice(color_keys) for _ in range(self.code_length)]

    def check_guess(self, guess):
        secret_copy = self.secret_code[:]
        guess_copy = guess[:]

        exact = 0
        color = 0
        matched_indexes = []

        # First pass: Check for exact matches
        for i in range(self.code_length):
            if guess_copy[i] == secret_copy[i]:
                exact += 1
                matched_indexes.append(i)

        # Remove exact matches before checking for color matches
        for i in reversed(matched_indexes):  # Remove from the back to avoid index shifting
            del secret_copy[i]
            del guess_copy[i]

        # Second pass: Check for color-only matches (correct color, wrong position)
        for g in guess_copy:
            if g in secret_copy:
                color += 1
                secret_copy.remove(g)  # Remove only one occurrence

        return exact, color

    def add_guess(self, guess):
        result = self.check_guess(guess)
        self.attempts += 1
        self.guesses.append({"guess": guess, "result": result})
        if result[0] == self.code_length:
            self.solved = True
        return result

    def is_over(self):
        return self.solved or (self.attempts >= self.max_attempts)

    def get_embed(self):
        desc = []
        desc.append(self.lang["attempts_text"].replace("{{max}}", str(self.max_attempts)).replace("{{current}}", str(self.attempts)))

        for i, ginfo in enumerate(self.guesses, start=1):
            guess_str = " ".join([self.config["icons"][c] for c in ginfo["guess"]])
            exact, color = ginfo["result"]
            desc.append(self.lang["attempt_history"].replace("{{num}}", str(i)).replace("{{guess}}", guess_str).replace("{{exact}}", str(exact)).replace("{{color}}", str(color)))


        if self.is_over():
            if self.solved:
                desc.append(self.lang["solved_message"])
            else:
                secret_str = " ".join([self.config["icons"][c] for c in self.secret_code])
                desc.append(self.lang["game_over_message"].replace("{{secret_code}}", str(secret_str)))

        else:
            desc.append(self.lang["select_next_guess"].replace("{{code_length}}", str(self.code_length)))

        embed = discord.Embed(title=self.lang["game_progress_title"], description="\n".join(desc), color=discord.Color.green())
        return embed


def color_id_to_emoji(cid):
    """
    Converts a color ID (R, B, G, etc.) to the matching emoji from COLOR_OPTIONS.
    """
    for c in COLOR_OPTIONS:
        if c["id"] == cid:
            return c["emoji"]
    return "?"


class MastermindView(discord.ui.View):
    """
    The main game view that shows color selection, remove last, and submit buttons.
    We track the in-progress guess in self.current_guess.
    """
    def __init__(self, game: MastermindGame):
        super().__init__(timeout=None)  # No auto-timeout, game ends when solved or attempts exhausted
        self.game = game
        self.current_guess = []

        # Add color buttons (for each color in COLOR_OPTIONS)
        row_index = 0
        self.color_buttons = []
        for i, copt in enumerate(COLOR_OPTIONS):
            btn = SelectColorButton(copt["id"], copt["emoji"], row=row_index, lang=game.lang)
            self.color_buttons.append(btn)
            self.add_item(btn)
            if (i+1) % 3 == 0:
                row_index += 1

        # Add "Remove Last" and "Submit" buttons
        self.add_item(RemoveLastButton(label=self.game.lang["remove_button_label"], style=discord.ButtonStyle.danger, row=row_index, lang=game.lang))
        self.add_item(SubmitGuessButton(label=self.game.lang["confirm_button_label"], style=discord.ButtonStyle.success, row=row_index, lang=game.lang))

    async def interaction_check(self, interaction: discord.Interaction):
        """
        Only allow the original player to interact.
        """
        if interaction.user != self.game.player:
            await interaction.response.send_message(self.game.lang["not_your_game"], ephemeral=True)
            return False
        return True

    async def update_embed(self):
        """
        Updates the main embed with the current game progress.
        """
        # If the game is over, disable all buttons
        if self.game.is_over():
            for item in self.children:
                item.disabled = True

        embed = self.game.get_embed()
        if self.game.is_over():
            # Once the game is over, reveal the code in the embed
            pass

        # Also show the user's in-progress guess at the bottom if the game is not over
        if not self.game.is_over():
            guess_str = " ".join(map(color_id_to_emoji, self.current_guess))
            embed.add_field(
                name=self.game.lang["current_guess"],
                value=guess_str if guess_str else self.game.lang["no_colors_selected"],
                inline=False
            )

        await self.game.message.edit(embed=embed, view=self)

    def reset_guess(self):
        """
        Clears the current guess array so the user can pick anew.
        """
        self.current_guess = []


class SelectColorButton(discord.ui.Button):
    """
    A button representing a single color choice.
    """
    def __init__(self, color_id: str, emoji: str, row: int, lang: dict):
        super().__init__(label="", emoji=emoji, style=discord.ButtonStyle.secondary, row=row)
        self.color_id = color_id
        self.lang = lang

    async def callback(self, interaction: discord.Interaction):
        view: MastermindView = self.view
        # If the game is over, do nothing
        if view.game.is_over():
            await interaction.response.send_message(self.lang["game_over"], ephemeral=True)
            return
        # If the guess is already 4, ignore
        if len(view.current_guess) >= CODE_LENGTH:
            await interaction.response.send_message(self.lang["max_colors_reached"], ephemeral=True)
            return

        # Add this color to the guess
        view.current_guess.append(self.color_id)
        await view.update_embed()
        await interaction.response.defer()


class RemoveLastButton(discord.ui.Button):
    """
    Removes the last color from the current guess.
    """
    def __init__(self, label: str, style: discord.ButtonStyle, row: int, lang: dict):
        super().__init__(label=label, style=style, row=row)
        self.lang = lang

    async def callback(self, interaction: discord.Interaction):
        view: MastermindView = self.view
        if view.game.is_over():
            await interaction.response.send_message(self.lang["game_over"], ephemeral=True)
            return
        if len(view.current_guess) > 0:
            view.current_guess.pop()
            await view.update_embed()
            await interaction.response.defer()
        else:
            await interaction.response.send_message(self.lang["no_colors_to_remove"], ephemeral=True)


class SubmitGuessButton(discord.ui.Button):
    """
    Submits the current guess if it has exactly CODE_LENGTH colors.
    """
    def __init__(self, label: str, style: discord.ButtonStyle, row: int, lang: dict):
        super().__init__(label=label, style=style, row=row)
        self.lang = lang

    async def callback(self, interaction: discord.Interaction):
        view: MastermindView = self.view
        game = view.game
        if game.is_over():
            await interaction.response.send_message(self.lang["game_over"], ephemeral=True)
            return

        if len(view.current_guess) < CODE_LENGTH:
            await interaction.response.send_message(self.lang["guess_incomplete"].replace("{{code_length}}", str(CODE_LENGTH)), ephemeral=True)
            return

        # Process the guess
        result = game.add_guess(view.current_guess)
        # If solved or attempts exhausted, game ends
        # If not, user can pick next guess
        view.reset_guess()
        await view.update_embed()
        await interaction.response.defer()

        # Check if game ended
        if game.is_over():
            await view.update_embed()
