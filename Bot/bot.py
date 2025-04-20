import asyncio
import logging
import os
import signal
import sys
import subprocess
import importlib.util
import inspect
import traceback
import re
import discord
import colorama
import ruamel.yaml
import sqlite3


#Global variables
CONFIG = None # We put the config here, so I can access it from everywhere similar to other languages like C++
LANG = None


class EbClient(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.all())
        self.synced = False
        self.bot_ready = False
        self.commands = {}
        self.on_ready_callbacks = []
        self.on_message_callbacks = []
        self.on_interaction_callbacks = []
        self.on_member_join_callbacks = []

    async def on_connect(self):
        asyncio.create_task(monitor_shutdown())

    async def on_interaction(self, interaction):
        if self.on_interaction_callbacks:
            for callback in self.on_interaction_callbacks:
                try:
                    await callback(interaction)
                except Exception as e:
                    print(colorama.Fore.RED + 'Error: ' + colorama.Fore.CYAN + f"{e.__class__.__name__}: {e}")
                    print(colorama.Fore.YELLOW + "[!] Traceback details:")
                    print(colorama.Fore.YELLOW + colorama.Fore.YELLOW.join(re.split(r'(\r?\n)', traceback.format_exc())[:-2]))

    async def on_message(self, message):
        if message.author.bot:
            return
        if self.on_message_callbacks:
            for callback in self.on_message_callbacks:
                try:
                    await callback(message)
                except Exception as e:
                    print(colorama.Fore.RED + 'Error: ' + colorama.Fore.CYAN + f"{e.__class__.__name__}: {e}")
                    print(colorama.Fore.YELLOW + "[!] Traceback details:")
                    print(colorama.Fore.YELLOW + colorama.Fore.YELLOW.join(re.split(r'(\r?\n)', traceback.format_exc())[:-2]))

    async def on_member_join(self, member):
        if self.on_member_join_callbacks:
            for callback in self.on_member_join_callbacks:
                try:
                    await callback(member)
                except Exception as e:
                    print(colorama.Fore.RED + 'Error: ' + colorama.Fore.CYAN + f"{e.__class__.__name__}: {e}")
                    print(colorama.Fore.YELLOW + "[!] Traceback details:")
                    print(colorama.Fore.YELLOW + colorama.Fore.YELLOW.join(re.split(r'(\r?\n)', traceback.format_exc())[:-2]))

    async def on_ready(self):
        await tree.sync()
        self.synced = True
        self.bot_ready = True
        print(colorama.Fore.CYAN + f"{colorama.Fore.YELLOW}[!] Tip: You can use the following link to invite the bot to your server: {colorama.Fore.CYAN}https://discord.com/oauth2/authorize?client_id={self.user.id}&permissions=8&scope=bot%20applications.commands")
        if self.on_ready_callbacks:
            print(colorama.Fore.CYAN + "[!] Running on_ready callbacks from your commands packages...")
            for callback in self.on_ready_callbacks:
                try:
                    await callback()
                except Exception as e:
                    print(colorama.Fore.RED + 'Error: ' + colorama.Fore.CYAN + f"{e.__class__.__name__}: {e}")
                    print(colorama.Fore.YELLOW + "[!] Traceback details:")
                    print(colorama.Fore.YELLOW + colorama.Fore.YELLOW.join(re.split(r'(\r?\n)', traceback.format_exc())[:-2]))
            print(colorama.Fore.GREEN + "[+] Finished running on_ready callbacks from your commands packages!")
        print(f"{colorama.Fore.GREEN}[+] Logged in as {colorama.Fore.MAGENTA}{self.user}")
        print(colorama.Fore.CYAN + "-" * 50)

    async def close(self):
        await super().close()

    async def shutdown(self):
        print(f"{colorama.Fore.RED}Shutting down the bot...")
        await self.change_presence(status=discord.Status.offline)
        await self.close()

    async def reload_configs(self):
        global CONFIG, LANG, config
        print(colorama.Fore.CYAN + "-" * 50)
        print(colorama.Fore.CYAN + "[-] Found config changes!")
        print(colorama.Fore.YELLOW + "[-] For the changes to take effect, You need to restart the bot!")
        print(colorama.Fore.CYAN + "-" * 50)

    def load_specific_config(self, package: str, file:str):
        global CONFIG
        with open(f"Configs/{package}.yml", "r") as f:
            yaml = ruamel.yaml.YAML()
            CONFIG[package][file].clear() # Clear the current config without losing the reference
            CONFIG[package][file].update(yaml.load(f)[file]) # Update the config with the new values


bot = EbClient()
tree = discord.app_commands.CommandTree(bot)
config = None # This config represents the config file called 'general.yml' which is the base config file

def start_bot():
    global CONFIG, LANG, config
    #loading extra modules
    print(colorama.Fore.CYAN + "-" * 50)
    print(colorama.Fore.CYAN + "[-] Loading extra modules...")
    with open("../requirements.txt", "r") as f:
        required_modules = set(f.read().splitlines())
    for filename in os.listdir("Commands"):
        if os.path.isdir(os.path.join("Commands", filename)):
            path = os.path.join("Commands", filename)
            flag = False
            for sub_filename in os.listdir(os.path.join("Commands", filename)):
                sub_path = os.path.join(os.path.join(path), sub_filename)
                if sub_filename == "requirements.txt":
                    required_modules = required_modules.union(set(open(sub_path, "r").read().splitlines()))
                    flag = True
            if flag:
                print(colorama.Fore.YELLOW + f"[-] Loaded {colorama.Fore.MAGENTA}{filename} {colorama.Fore.YELLOW}package!")
    subprocess.run(f"pip install {' '.join(required_modules)}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(colorama.Fore.GREEN + "[+] Loaded extra modules!")
    #config loading
    print(colorama.Fore.CYAN + "-" * 50)
    print(colorama.Fore.CYAN + "[-] Loading config files...")
    for filename in os.listdir("Configs"):
        if filename.endswith(".yml"):
            filename_clear = filename[:-4]
            with open(os.path.join("Configs", filename), "r", encoding="utf-8") as f:
                loaded_yaml = ruamel.yaml.YAML(typ="safe").load(f)
                if loaded_yaml is None:
                    loaded_yaml = {}
                if CONFIG is None:
                    CONFIG = {filename_clear: loaded_yaml}
                else:
                    CONFIG[filename_clear] = loaded_yaml
            for key in CONFIG[filename_clear]:
                if CONFIG[filename_clear][key] is None:
                    CONFIG[filename_clear][key] = {}
            print(colorama.Fore.YELLOW + f"[-] Loaded {colorama.Fore.MAGENTA}{filename} {colorama.Fore.YELLOW}config file!")
    if 'general' not in CONFIG:
        print(colorama.Fore.RED + "Error: " + colorama.Fore.CYAN + f"general.yml{colorama.Fore.RED} config file not found!")
        print(colorama.Fore.RED + "Exiting...")
        exit()
    config = CONFIG['general']
    print(colorama.Fore.GREEN + "[+] Loaded base config file!")
    print(colorama.Fore.CYAN + "-" * 50)
    #language loading
    print(colorama.Fore.CYAN + "[-] Loading language files...")
    for filename in os.listdir("Commands"):
        if os.path.isdir(os.path.join("Commands", filename)):
            path = os.path.join("Commands", filename)
            flag = False
            for sub_filename in os.listdir(os.path.join("Commands", filename)):
                sub_path = os.path.join(os.path.join(path), sub_filename)
                if os.path.isdir(sub_path) and sub_filename == "lang":
                    language = CONFIG["general"]["bot"]["language"]
                    if os.path.exists(os.path.join(sub_path, f"{language}.json")):
                        with open(os.path.join(sub_path, f"{language}.json"), "r", encoding="utf-8") as f:
                            flag = True
                            LANG = {**LANG, **{filename: ruamel.yaml.YAML(typ="safe").load(f)}} if LANG is not None else {filename: ruamel.yaml.YAML(typ="safe").load(f)}
                        print(colorama.Fore.YELLOW + f"[-] Selected {colorama.Fore.MAGENTA}{language} {colorama.Fore.YELLOW}for {colorama.Fore.MAGENTA}{filename} {colorama.Fore.YELLOW}package!")
                    elif os.path.exists(os.path.join(sub_path, f"default.txt")):
                        with open(os.path.join(sub_path, f"default.txt"), "r") as f:
                            language = f.read()
                            with open(os.path.join(sub_path, f"{language}.json"), "r") as f:
                                flag = True
                                LANG = {**LANG, **{filename: ruamel.yaml.YAML(typ="safe").load(f)}} if LANG is not None else {filename: ruamel.yaml.YAML(typ="safe").load(f)}
                            print(colorama.Fore.YELLOW + f"[-] Selected {colorama.Fore.MAGENTA}{language} {colorama.Fore.YELLOW}for {colorama.Fore.MAGENTA}{filename} {colorama.Fore.YELLOW}package!")
                    else:
                        print(colorama.Fore.YELLOW + f"[!] can't find {colorama.Fore.MAGENTA}{language}{colorama.Fore.YELLOW} language file found for {colorama.Fore.MAGENTA}{filename}{colorama.Fore.YELLOW}! and there is no default.txt file!")
            if not flag:
                # check if there is a language file
                for sub_filename in os.listdir(os.path.join("Commands", filename)):
                    sub_path = os.path.join(os.path.join(path), sub_filename)
                    if os.path.isdir(sub_path) and sub_filename == "lang":
                        if len(os.listdir(sub_path)) > 0 and os.path.exists(os.path.join(sub_path, os.listdir(sub_path)[0])):
                            with open(os.path.join(sub_path, os.listdir(sub_path)[0]), "r", encoding="utf-8") as f:
                                LANG = {**LANG, **{filename: ruamel.yaml.YAML(typ="safe").load(f)}} if LANG is not None else {filename: ruamel.yaml.YAML(typ="safe").load(f)}
                            print(colorama.Fore.YELLOW + f"[!] Using first language file that can be found for {colorama.Fore.MAGENTA}{filename} {colorama.Fore.YELLOW}package!")
                            print(colorama.Fore.YELLOW + f"[-] Selected {colorama.Fore.MAGENTA}{os.listdir(sub_path)[0][:-5]} {colorama.Fore.YELLOW}for {colorama.Fore.MAGENTA}{filename} {colorama.Fore.YELLOW}package!")
                            flag = True
                            break
                if not flag:
                    print(colorama.Fore.YELLOW + f"[!] No language file found for {colorama.Fore.MAGENTA}{filename}{colorama.Fore.YELLOW} package!")

    print(colorama.Fore.GREEN + "[+] Loaded language files!")
    print(colorama.Fore.CYAN + "-" * 50)

    #database loading
    if not os.path.exists('data.db'):
        print(colorama.Fore.RED + "[!] Warning: " + colorama.Fore.CYAN + "Database file not found! Creating a new one...")
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    print(colorama.Fore.GREEN + "[+] Connected to the database!")
    #command loading
    print(colorama.Fore.CYAN + "[-] Loading command packages...")
    temp = 0
    try:
        for filename in os.listdir("Commands"):
            if os.path.isdir(os.path.join("Commands", filename)):
                for sub_filename in os.listdir(os.path.join("Commands", filename)):
                    if sub_filename.endswith(".py"):
                        module_name = sub_filename[:-3]  # Remove the '.py' extension
                        file_path = os.path.join(os.path.join("Commands", filename), sub_filename)
                        spec = importlib.util.spec_from_file_location(module_name, file_path)
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        for name, command in inspect.getmembers(module, inspect.isfunction): # Find the 'init' func in the module
                            if name != 'init':
                                continue
                            temp += 1
                            try:
                                sig = inspect.signature(command)
                                parametrs = []
                                for param in sig.parameters:
                                    match param:
                                        case 'tree':
                                            parametrs.append(tree)
                                        case 'bot':
                                            parametrs.append(bot)
                                        case 'config':
                                            if not filename in CONFIG:
                                                print(colorama.Fore.RED + "Error: " + colorama.Fore.CYAN + f"{filename}{colorama.Fore.RED} file config not found!")
                                                print(colorama.Fore.RED + "Exiting...")
                                                exit()
                                            if not module_name in CONFIG[filename]:
                                                print(f"{colorama.Fore.RED}Error: {colorama.Fore.CYAN}{filename}{colorama.Fore.RED} config has been found but {colorama.Fore.CYAN}{module_name}.py{colorama.Fore.RED} config not found!")
                                                print(colorama.Fore.RED + "Exiting...")
                                                exit()
                                            parametrs.append(CONFIG[filename][module_name])
                                        case 'lang':
                                            if not filename in LANG:
                                                print(colorama.Fore.RED + "Error: " + colorama.Fore.CYAN + f"{filename}{colorama.Fore.RED} file lang not found!")
                                                print(colorama.Fore.RED + "Exiting...")
                                                exit()
                                            if not module_name in LANG[filename]:
                                                print(f"{colorama.Fore.RED}Error: {colorama.Fore.CYAN}{filename}{colorama.Fore.RED} lang has been found but {colorama.Fore.CYAN}{module_name}.py{colorama.Fore.RED} lang not found!")
                                                print(colorama.Fore.RED + "Exiting...")
                                                exit()
                                            parametrs.append(LANG[filename][module_name])
                                        case 'db':
                                            parametrs.append(conn)
                                if not parametrs:
                                    print(colorama.Fore.RED + "Error: " + colorama.Fore.CYAN + "The 'init' function must have at least one parameter!")
                                    print(colorama.Fore.RED + f"[!] Hint: The {file_path} probably corrupted!")
                                    print(colorama.Fore.RED + "Exiting...")
                                    exit()
                                command(*parametrs)
                            except Exception as e:
                                if isinstance(e, discord.app_commands.errors.CommandAlreadyRegistered):
                                    print(colorama.Fore.RED + "Error: " + colorama.Fore.CYAN + "one or more commands of your commands conflict!")
                                    print(colorama.Fore.RED + "[-] It means that you have two or more commands with the same name!")
                                    print(colorama.Fore.YELLOW + f"[!] Hint: Most likely '{file_path}' has a command with the same name as another command in another file!")
                                    print(colorama.Fore.RED + "Exiting... due to command conflict!")
                                    exit()
                                else:
                                    print(colorama.Fore.RED + 'Error: ' + colorama.Fore.CYAN + f"{e.__class__.__name__}: {e}")
                                    print(colorama.Fore.YELLOW + "[!] Traceback details:")
                                    print(colorama.Fore.YELLOW + colorama.Fore.YELLOW.join(re.split(r'(\r?\n)', traceback.format_exc())[:-2]))
                                    print(colorama.Fore.RED + "Exiting...")
                                    exit()
                            print(colorama.Fore.GREEN + f"[-] Loaded {colorama.Fore.MAGENTA}{module_name} {colorama.Fore.GREEN}package!")
                            break
    except FileNotFoundError:
        print(colorama.Fore.RED + "Error: " + colorama.Fore.CYAN + "Commands folder not found!")
        print(colorama.Fore.RED + "Exiting...")
        exit()
    if temp == 0:
        print(colorama.Fore.RED + "Error: " + colorama.Fore.CYAN + "No commands found! | Check the 'Commands' folder and make sure that there is at least one command!")
        print(colorama.Fore.RED + "Exiting...")
        exit()
    print(colorama.Fore.GREEN + "[+] Loaded command packages!")
    print(colorama.Fore.CYAN + "-" * 50)
    print(colorama.Fore.CYAN + "[-] Connecting to Discord API...")
    print(colorama.Fore.YELLOW + "[!] Some commands are not working yet wait for the bot to completely start up!")
    try:
        bot.run(config["bot"]["token"], log_level=logging.NOTSET) # Even though I set the log level to NOTSET it still prints some ERRORS messages, I did it for better user experience for people who are not familiar with python but if you know what you are doing you can remove it
    except Exception as e:
        if isinstance(e, discord.errors.PrivilegedIntentsRequired):
            print(colorama.Fore.RED + "Error: " + colorama.Fore.CYAN + "The bot do not have the privileged intents!")
            print(colorama.Fore.YELLOW + "[!] Hint: " + colorama.Fore.MAGENTA + "go to " + colorama.Fore.CYAN + f"https://discord.com/developers/applications/{bot.user.id}/bot" + colorama.Fore.MAGENTA + " and enable the privileged intents!")
            print(colorama.Fore.YELLOW + "[!] Hint: PRESENCE INTENT and SERVER MEMBERS INTENT and MESSAGE CONTENT INTENT are required!")
            print(colorama.Fore.RED + "Exiting... due luck of privileged intents!")
            exit()
        else:
            print(colorama.Fore.RED + "Error: " + colorama.Fore.CYAN + f"{e.__class__.__name__}: {e}")
            print(colorama.Fore.YELLOW + "[!] Traceback details:")
            print(colorama.Fore.YELLOW + colorama.Fore.YELLOW.join(re.split(r'(\r?\n)', traceback.format_exc())[:-2]))


# Handle Stop Signal
def handle_shutdown_signal(signum, frame):
    asyncio.create_task(bot.shutdown())

signal.signal(signal.SIGTERM, handle_shutdown_signal)

async def monitor_shutdown():
    while True:
        if os.path.exists("shutdown_signal.txt"):
            os.remove("shutdown_signal.txt")
            await bot.shutdown()
            break
        elif os.path.exists("reload_config.txt"):
            await bot.reload_configs()
            os.remove("reload_config.txt")
        await asyncio.sleep(1)


if __name__ == "__main__":
    colorama.init()
    if len(sys.argv) > 1 and sys.argv[1] == "IknowWhatImDoing":
        start_bot()
    else:
        print(colorama.Fore.CYAN + "-" * 50)
        print(colorama.Fore.CYAN + "[!] Please use the web interface to use the bot!")
        print(colorama.Fore.CYAN + "[-] To start the bot use the following command:")
        print(colorama.Fore.CYAN + "-" * 50)