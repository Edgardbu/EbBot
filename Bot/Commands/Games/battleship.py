# battleship.py
import discord
import random
import utils

def init(tree: discord.app_commands.CommandTree, bot: discord.Client, config: dict, lang: dict):
    battleship_commands = discord.app_commands.Group(name="battleship", description=lang["command_description"])

    @battleship_commands.command(name="play", description=lang["play_command_description"])
    async def battleship_play(interaction: discord.Interaction):
        """
        Start a Battleship game
        """
        em = discord.Embed(
            title=lang["embed_before_game"]["title"],
            description=utils.replace_variables(lang["embed_before_game"]["description"]),
            color=discord.Color.from_str(config["embed"]["color"])
        )
        em.set_footer(
            text=utils.replace_variables(lang["embed_before_game"]["footer"], member=interaction.user),
            icon_url=interaction.user.avatar.url
        )
        await interaction.response.send_message(embed=em, view=BattleshipWaitingView(interaction.user, lang, config))

    tree.add_command(battleship_commands)


class BattleshipWaitingView(discord.ui.View):
    def __init__(self, player1: discord.Member, lang: dict, config: dict):
        super().__init__(timeout=300)
        self.player1 = player1
        self.player2 = None
        self.lang = lang
        self.config = config
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.gray, label=player1.name, disabled=True, row=3))
        self.add_item(JoinGameButton(lang, config))


class JoinGameButton(discord.ui.Button):
    def __init__(self, lang: dict, config: dict):
        super().__init__(style=discord.ButtonStyle.gray, label=lang["embed_before_game"]["join_button"], row=3)
        self.lang = lang
        self.config = config

    async def callback(self, interaction: discord.Interaction):
        view: BattleshipWaitingView = self.view
        if view.player1 == interaction.user:
            return await interaction.response.send_message(self.lang["embed_before_game"]["play_with_yourself"], ephemeral=True)
        if view.player2 is not None:
            return await interaction.response.send_message(self.lang["embed_before_game"]["game_full"], ephemeral=True)
        view.player2 = interaction.user
        starting_player = random.choice([view.player1, view.player2]) # Randomly choose who will start
        em = interaction.message.embeds[0]
        em.description = self.lang["embed_in_game"]["description"].replace("{{c_player}}", starting_player.mention).replace("{{player1}}", view.player1.mention).replace("{{player2}}", view.player2.mention)
        em.set_footer(text=None, icon_url=None)
        await interaction.response.edit_message(embed=em, view=None)
        # Start the game
        game = BattleshipGame(view.player1, view.player2, starting_player, self.lang, self.config)
        await game.start_game()


class BattleshipGame:
    active_games = {}

    def __init__(self, player1: discord.Member, player2: discord.Member, current_player: discord.Member, lang: dict, config: dict):
        self.player1 = player1
        self.player2 = player2
        self.current_player = current_player
        self.other_player = player2 if current_player == player1 else player1
        self.lang = lang
        self.config = config
        self.player_data = {
            player1.id: {'board': self.create_board(), 'ships': [], 'hits': set(), 'misses': set(), 'logs': [], 'attack_board': self.create_board()},
            player2.id: {'board': self.create_board(), 'ships': [], 'hits': set(), 'misses': set(), 'logs': [], 'attack_board': self.create_board()}
        }
        self.player_messages = {}  # Store the last message sent to each player
        self.game_over = False
        # Place ships for both players
        self.place_ships(player1.id)
        self.place_ships(player2.id)
        # Store the game instance
        BattleshipGame.active_games[player1.id] = self
        BattleshipGame.active_games[player2.id] = self

    def create_board(self):
        # Create a 10x10 board
        return [[' ' for _ in range(10)] for _ in range(10)]

    def place_ships(self, player_id):
        ships = {
            'Carrier': 5,
            'Battleship': 4,
            'Cruiser': 3,
            'Submarine': 3,
            'Destroyer': 2
        }
        board = self.player_data[player_id]['board']
        ship_positions = []
        for ship_name, ship_size in ships.items():
            placed = False
            while not placed:
                orientation = random.choice(['H', 'V'])
                if orientation == 'H':
                    row = random.randint(0, 9)
                    col = random.randint(0, 9 - ship_size)
                    if all(board[row][col + i] == ' ' for i in range(ship_size)):
                        positions = []
                        for i in range(ship_size):
                            board[row][col + i] = 'S'
                            positions.append((row, col + i))
                        ship_positions.append({'name': ship_name, 'positions': positions, 'hits': set()})
                        placed = True
                else:
                    row = random.randint(0, 9 - ship_size)
                    col = random.randint(0, 9)
                    if all(board[row + i][col] == ' ' for i in range(ship_size)):
                        positions = []
                        for i in range(ship_size):
                            board[row + i][col] = 'S'
                            positions.append((row + i, col))
                        ship_positions.append({'name': ship_name, 'positions': positions, 'hits': set()})
                        placed = True
        self.player_data[player_id]['ships'] = ship_positions

    async def start_game(self):
        # Send the initial game state to both players
        await self.send_game_state(self.player1)
        await self.send_game_state(self.player2)

    async def send_game_state(self, player: discord.Member):
        player_id = player.id
        opponent_id = self.player1.id if player_id == self.player2.id else self.player2.id
        # First embed: Game info
        em1 = discord.Embed(
            title=self.lang["embed_in_game"]["title"],
            description=self.get_game_info(player_id),
            color=discord.Color.green()
        )
        em1.set_footer(text=self.lang["embed_in_game"]["your_turn_footer"] if self.current_player.id == player_id else self.lang["embed_in_game"]["opponent_turn_footer"])
        # Second embed: Player's own board
        em2 = discord.Embed(
            title=self.lang["your_board_title"],
            description=self.get_player_board_str(player_id),
            color=discord.Color.blue()
        )
        # Third embed: Player's attack board
        em3 = discord.Embed(
            title=self.lang["your_attack_board_title"],
            description=self.get_attack_board_str(player_id),
            color=discord.Color.orange()
        )
        view = AttackView(self, player) if self.current_player.id == player_id and not self.game_over else None
        if player.id in self.player_messages: # Send or edit the message to the player
            try:
                await self.player_messages[player.id].edit(embeds=[em1, em3, em2], view=view)
            except discord.NotFound:
                self.player_messages[player.id] = await player.send(embeds=[em1, em3, em2], view=view)
        else:
            self.player_messages[player.id] = await player.send(embeds=[em1, em3, em2], view=view)

    def get_game_info(self, player_id):
        # Return a string with game info, ships remaining, logs, etc.
        opponent_id = self.player1.id if player_id == self.player2.id else self.player2.id
        opponent = self.player1 if player_id == self.player2.id else self.player2
        ships_left = len([ship for ship in self.player_data[opponent_id]['ships'] if len(ship['hits']) < len(ship['positions'])])
        logs = self.player_data[player_id]['logs']
        log_str = '\n'.join(logs[-5:]) if logs else self.lang["no_attacks_yet"]
        info = self.lang["game_info"].format(
            opponent=opponent.display_name,
            ships_left=ships_left,
            logs=log_str
        )
        return info

    def get_player_board_str(self, player_id):
        """
        A B C D E F G H I J
        1 x x x x x x x x x
        2 x x x x x x x x x
        3 x x x x x x x x x
        4 x x x x x x x x x
        5 x x x x x x x x x
        6 x x x x x x x x x
        7 x x x x x x x x x
        8 x x x x x x x x x
        9 x x x x x x x x x
       10 x x x x x x x x x

        M - Miss
        H - Hit
        S - Ship
        everything else - Water
        :param player_id:
        :return: ASCII representation of the player's attack board
        """
        # Return the ASCII representation of the player's own board
        board = self.player_data[player_id]['board']
        board_str = "      A    B     C     D     E     F     G     H     I     J\n"
        for idx, row in enumerate(board):
            row_str = f"{idx+1:2}  "
            for cell in row:
                if cell == 'S':
                    row_str += self.config["icons"]["Ship"] + ' '
                elif cell == 'H':
                    row_str += self.config["icons"]["Hit"] + ' '
                elif cell == 'M':
                    row_str += self.config["icons"]["Miss"] + ' '
                else:
                    row_str += self.config["icons"]["Water"] + ' '
            board_str += row_str + '\n'
        return f"```\n{board_str}```"

    def get_attack_board_str(self, player_id):
        """
        similar to get_player_board_str but for the attack board
        :param player_id:
        :return: ASCII representation of the player's attack board
        """
        attack_board = self.player_data[player_id]['attack_board']
        board_str = "      A    B     C     D     E     F     G     H     I     J\n"
        for idx, row in enumerate(attack_board):
            row_str = f"{idx+1:2}  "
            for cell in row:
                if cell == 'H':
                    row_str += self.config["icons"]["Hit"] + ' '
                elif cell == 'M':
                    row_str += self.config["icons"]["Miss"] + ' '
                else:
                    row_str += self.config["icons"]["Water"] + ' '
            board_str += row_str + '\n'
        return f"```\n{board_str}```"

    async def handle_attack(self, player: discord.Member, column: int, row: int, interaction: discord.Interaction):
        attacker_id = player.id
        defender_id = self.player1.id if attacker_id == self.player2.id else self.player2.id
        defender_board = self.player_data[defender_id]['board']
        defender_ships = self.player_data[defender_id]['ships']
        attacker_attack_board = self.player_data[attacker_id]['attack_board']

        # Check if already attacked
        attack_pos = (row, column)
        if attack_pos in self.player_data[attacker_id]['hits'] or attack_pos in self.player_data[attacker_id]['misses']:
            await interaction.response.send_message(self.lang["already_attacked"], ephemeral=True)
            await self.send_game_state(player) # Restart attack process without switching turns
            return

        hit = False
        sunk_ship_name = None
        if defender_board[row][column] == 'S':
            defender_board[row][column] = 'H'
            self.player_data[attacker_id]['hits'].add(attack_pos)
            attacker_attack_board[row][column] = 'H'
            # Update defender's ships
            for ship in defender_ships:
                if attack_pos in ship['positions']:
                    ship['hits'].add(attack_pos)
                    if len(ship['hits']) == len(ship['positions']):
                        sunk_ship_name = ship['name']
            hit = True
        else:
            defender_board[row][column] = 'M'
            self.player_data[attacker_id]['misses'].add(attack_pos)
            attacker_attack_board[row][column] = 'M'
            hit = False

        # Logs
        col_letter = chr(65 + column)
        row_number = row + 1
        if hit:
            if sunk_ship_name:
                log_entry = self.lang["attack_sunk"].format(col=col_letter, row=row_number, ship=sunk_ship_name)
            else:
                log_entry = self.lang["attack_hit"].format(col=col_letter, row=row_number)
        else:
            log_entry = self.lang["attack_miss"].format(col=col_letter, row=row_number)
        self.player_data[attacker_id]['logs'].append(log_entry)

        await interaction.response.send_message(log_entry, ephemeral=True) # Send response to the attacker

        if all(len(ship['hits']) == len(ship['positions']) for ship in defender_ships): # Check for game over
            self.game_over = True
            await self.end_game()
        else:
            if not hit: # Switch turns because the attack missed
                self.current_player, self.other_player = self.other_player, self.current_player
            await self.update_game_state() # Update game state for both players

    async def update_game_state(self):
        # Send new game state to both players
        await self.send_game_state(self.player1)
        await self.send_game_state(self.player2)

    async def end_game(self):
        winner = self.current_player
        em = discord.Embed(
            title=self.lang["game_over_title"],
            description=self.lang["game_over_description"].format(winner=winner.display_name),
            color=discord.Color.red()
        )
        await self.player1.send(embed=em)
        await self.player2.send(embed=em)
        # Remove game from active games
        del BattleshipGame.active_games[self.player1.id]
        del BattleshipGame.active_games[self.player2.id]


class AttackView(discord.ui.View):
    def __init__(self, game: BattleshipGame, player: discord.Member):
        super().__init__(timeout=300)
        self.game = game
        self.player = player
        self.column_g = None
        self.row_g = None
        # Add column buttons (A-J) split into two rows (A-E and F-J)
        for i in range(10):
            label = chr(65 + i)  # A-J
            button = ColumnButton(label, i)
            button.row = 0 if i < 5 else 1 # Assign rows: first 5 buttons in row 0, next 5 in row 1
            self.add_item(button)

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user != self.player:
            await interaction.response.send_message(self.game.lang["not_your_turn"], ephemeral=True)
            return False
        return True


class ColumnButton(discord.ui.Button):
    def __init__(self, label: str, value: int):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.value = value

    async def callback(self, interaction: discord.Interaction):
        view: AttackView = self.view
        view.column_g = self.value
        # Disable all column buttons after selection
        for item in view.children:
            if isinstance(item, ColumnButton):
                item.disabled = True
                item.style = discord.ButtonStyle.grey
        await interaction.response.edit_message(view=view)
        await interaction.followup.send(view.game.lang["select_row_prompt"], view=RowSelectionView(view.game, view.player, view.column_g)) # Send row selection prompt as a regular message


class RowSelectionView(discord.ui.View):
    def __init__(self, game: BattleshipGame, player: discord.Member, column: int):
        super().__init__(timeout=300)
        self.game = game
        self.player = player
        self.column_g = column
        self.message = None  # To store the row selection prompt message
        for i in range(10): # Add row buttons (1-10) split into two rows (1-5 and 6-10)
            label = str(i + 1)  # 1-10
            button = RowButton(label, i)
            button.row = 0 if i < 5 else 1 # Assign rows: first 5 buttons in row 0, next 5 in row 1
            self.add_item(button)

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user != self.player:
            await interaction.response.send_message(self.game.lang["not_your_turn"], ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            await self.message.delete()


class RowButton(discord.ui.Button):
    def __init__(self, label: str, value: int):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.value = value

    async def callback(self, interaction: discord.Interaction):
        view: RowSelectionView = self.view
        row = self.value
        # Disable all row buttons after selection
        for item in view.children:
            if isinstance(item, RowButton):
                item.disabled = True
                item.style = discord.ButtonStyle.grey
        await interaction.response.edit_message(view=view)
        # Ask for confirmation
        col_letter = chr(65 + view.column_g)
        row_number = row + 1
        confirm_view = ConfirmAttackView(view.game, view.player, view.column_g, row)
        prompt = view.game.lang["confirm_attack_prompt"].format(col=col_letter, row=row_number)
        confirm_message = await interaction.followup.send(prompt, view=confirm_view)
        confirm_view.message = confirm_message  # Assign the confirmation message to the view for later deletion
        confirm_view.row_selection_message = interaction.message  # interaction.message is the row selection prompt message


class ConfirmAttackView(discord.ui.View):
    def __init__(self, game: BattleshipGame, player: discord.Member, column_g: int, row_g: int):
        super().__init__(timeout=300)
        self.game = game
        self.player = player
        self.column_g = column_g
        self.row_g = row_g
        self.message = None  # To store the confirmation message
        self.row_selection_message = None  # To store the row selection prompt message
        self.add_item(ConfirmAttackButton(self.game.lang["confirm_button_label"], discord.ButtonStyle.green, self.game, self.player, self.column_g, self.row_g))
        self.add_item(ConfirmAttackButton(self.game.lang["cancel_button_label"], discord.ButtonStyle.red, self.game, self.player, None, None))

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user != self.player:
            await interaction.response.send_message(self.game.lang["not_your_turn"], ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        # Disable all buttons when the view times out and delete the games from the active games
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.delete()
            except discord.NotFound:
                pass
        if self.row_selection_message:
            try:
                await self.row_selection_message.delete()
            except discord.NotFound:
                pass
        del BattleshipGame.active_games[self.game.player1.id]
        del BattleshipGame.active_games[self.game.player2.id]


class ConfirmAttackButton(discord.ui.Button):
    def __init__(self, label: str, style: discord.ButtonStyle, game: BattleshipGame, player: discord.Member, column_g: int, row_g: int):
        super().__init__(label=label, style=style)
        self.game = game
        self.player = player
        self.column_g = column_g
        self.row_g = row_g

    async def callback(self, interaction: discord.Interaction):
        confirm_view: ConfirmAttackView = self.view
        if self.label == self.game.lang["confirm_button_label"]:
            await self.game.handle_attack(self.player, self.column_g, self.row_g, interaction) # Confirm attack
        else:
            # Cancel
            await interaction.response.send_message(self.game.lang["attack_cancelled"], ephemeral=True)
            await self.game.send_game_state(self.player) # Restart attack process without switching turns
        # Delete the confirmation message and the row selection message
        if confirm_view.message:
            try:
                await confirm_view.message.delete()
            except discord.NotFound:
                pass
        if confirm_view.row_selection_message:
            try:
                await confirm_view.row_selection_message.delete()
            except discord.NotFound:
                pass
        self.view.stop() # Stop the view to prevent further interactions
