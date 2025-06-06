import json
import flask
import requests
from flask import session
from flask_apscheduler import APScheduler
import pyotp
import os
import datetime
import ruamel.yaml
import jinja2
import psutil
import logging
import subprocess
import pathlib
import importlib.util
from extensions import turbo

class App(flask.Flask):
    def __init__(self, *args, **kwargs):
        super(App, self).__init__(*args, **kwargs)
        self.bot_running = False
        self.bot_status_updated = False # Tracks if the bot status was updated (started/stopped)
        self.bot_console_process = None # This is the process that runs the bot
        self.server_console = None # This is a list of previous console outputs
        self.up_time = 0
        self.error_count = 0


app = App(__name__)
app.secret_key = os.urandom(24)
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(hours=1)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True if using HTTPS
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

#logging.basicConfig(filename='error.log', level=logging.NOTSET)


turbo.init_app(app)
totp = pyotp.TOTP(pyotp.random_base32())


scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()
logging.getLogger('apscheduler').setLevel(logging.ERROR)


class Config:
    SCHEDULER_API_ENABLED = True

def get_allowed_users():
    with open(r'Bot/Configs/allowed_users.yml') as f:
        loaded_yaml = ruamel.yaml.YAML(typ="safe").load(f)
    return [str(user) for user in loaded_yaml.get('allowed_users', [])]


@app.before_request
def make_session_permanent():
    session.permanent = True


@app.context_processor
def inject_sidebar_items():
    default_items = [
        {"label": "Dashboard", "url": "/dashboard", "icon": "fas fa-tachometer-alt"},
        {"label": "Configs", "url": "/configs", "icon": "fas fa-pencil-square-o"},
        {"label": "Languages", "url": "/languages", "icon": "fas fa-language"},
        {"label": "Allowed Users", "url": "/allowed_users", "icon": "fas fa-user-shield"},
    ]
    extra = app.config.get("EXTRA_SIDEBAR_ITEMS", [])
    return {"sidebar_items": default_items + extra}



@app.route('/login', methods=['GET', 'POST'])
@app.route('/welcome', methods=['GET', 'POST'])
@app.route('/', methods=['GET'])
def login():
    if flask.request.method == 'POST':
        discord_id = flask.request.form.get('discord_id')
        if discord_id is not None:
            try:
                with open(r'Bot/Configs/general.yml') as f:
                    loaded_yaml = ruamel.yaml.YAML(typ="safe").load(f)
                config = loaded_yaml['bot']
                if not discord_id in get_allowed_users():
                    return turbo.stream(turbo.prepend(f'<div class="alert alert-danger" role="alert" id="error">You are not allowed to use the bot!</div>', target="description"))
                session['user_id'] = discord_id
                token = config['token']
                headers = {
                    'Authorization': f'Bot {token}',
                    'Content-Type': 'application/json'
                }
                dm_channel_response = requests.post(f"https://discord.com/api/v10/users/@me/channels", headers=headers, json={"recipient_id": discord_id})
                if dm_channel_response.status_code != 200:
                    return turbo.stream(turbo.prepend(f'<div class="alert alert-danger" role="alert" id="error">An error occurred while trying to send the OTP code!</div>',target="description"))
                dm_channel_id = dm_channel_response.json()['id']
                dm_message_response = requests.post(f"https://discord.com/api/v10/channels/{dm_channel_id}/messages", headers=headers, json={"content": f"Your OTP code is: ||{totp.now()}||"})
                return turbo.stream(turbo.append(f'<script>$("#otpModal").modal("show");</script>', 'otpModal'))
            except Exception as e:
                return {"status": "error", "message": str(e)}

        token = flask.request.form.get('token')
        if token is not None:
            session['token'] = token
            return flask.render_template('login.html', input_name="user_id", type="text", title="Please enter your user Id", body="Please enter your user id, you can get it by right clicking your name and clicking 'Copy ID'", placeholder="Enter user id here", footer="NOTE: You must be in the server!", btn_text="Continue", custom_js="history.pushState({}, '', '/login');", method="POST", show_otp_popup=False)
        user_id = flask.request.form.get('user_id')
        if user_id is not None:
            if "token" not in session:
                return turbo.stream(flask.abort(400))
            with open(r'Bot/Configs/general.yml') as f:
                loaded_yaml = ruamel.yaml.YAML(typ="safe").load(f)
                loaded_yaml['bot']['token'] = session['token']
                session.pop('token')
                with open(r'Bot/Configs/allowed_users.yml', 'w') as f:
                    ruamel.yaml.YAML().dump({"allowed_users": [user_id]}, f)
            with open(r'Bot/Configs/general.yml', 'w') as f:
                ruamel.yaml.YAML().dump(loaded_yaml, f)
            return flask.redirect(flask.url_for('dashboard'))
        return turbo.stream(flask.abort(400))

    # /login?otp=123456
    otp = flask.request.args.get('otp')
    if otp is not None and otp != "":
        if otp == totp.now():
            session['otp_verified'] = True
            return flask.redirect(flask.url_for('dashboard'))
        with open(r'Bot/Configs/general.yml') as f:
            loaded_yaml = ruamel.yaml.YAML(typ="safe").load(f)
            config = loaded_yaml['bot']
        user_id = session['user_id']
        token = config['token']
        headers = {
            'Authorization': f'Bot {token}',
            'Content-Type': 'application/json'
        }
        dm_channel_response = requests.post(f"https://discord.com/api/v10/users/@me/channels", headers=headers, json={"recipient_id": user_id})
        if dm_channel_response.status_code != 200:
            return turbo.stream(turbo.prepend(f'<div class="alert alert-danger" role="alert" id="error">An error occurred while trying to send the OTP code!</div>',target="description"))
        dm_channel_id = dm_channel_response.json()['id']
        dm_message_response = requests.post(f"https://discord.com/api/v10/channels/{dm_channel_id}/messages", headers=headers, json={"content": f"Your OTP code is: ||{totp.now()}||"})

        return turbo.stream(turbo.append(f'<div class="alert alert-danger" role="alert" id="error">Invalid OTP code!</div>', target="modal-error"))

    # /Dashboard
    if 'otp_verified' in session and session['otp_verified']:
        return turbo.replace(flask.render_template('index.html'), 'html')

    # /Welcome
    with open(r'Bot/Configs/general.yml') as f:
        loaded_yaml = ruamel.yaml.YAML(typ="safe").load(f)
        config = loaded_yaml['bot']
    with open(r'Bot/Configs/allowed_users.yml') as f:
        loaded_yaml = ruamel.yaml.YAML(typ="safe").load(f)
        allowed_users = loaded_yaml.get('allowed_users', [])
    if config['token'] is None or config['token'] == "" or not allowed_users:
        return flask.render_template('login.html', type="password", input_name="token", title="Welcome to EB-bot",
                                     body="This is your first time running the bot! <br/> please enter your bot token so we can continue...",
                                     placeholder="Enter the token here",
                                     footer="NOTE: dont share your token with anyone!", btn_text="Continue",
                                     custom_css="""
#next{
    transition: all 0.5s ease;
}

#back{
    transition: all 0.5s ease;
}

#confirm{
    transition: all 0.5s ease;
}

.shrinked {
    width: 50% !important;
}
.hidden-div {
    display: none;
}

.button-container {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px; 
}
            """,
                                     custom_js="""
history.pushState({}, '', '/welcome');

document.querySelector(".button-container").addEventListener("click", function(event) {
    event.preventDefault();
    if (event.target.id === "confirm") {
        document.forms[0].submit();
    }
    else if (event.target.id === "next") {
        event.preventDefault();
        fetch('https://discord.com/api/v10/users/@me', {
            method: 'GET',
            headers: {
                'Authorization': `Bot ${document.getElementById("input_form").getElementsByTagName("input")[0].value}`
            }
        })
        .then(response => response.json())
        .then(data => {
                if (data.message === "401: Unauthorized") {
                    if (document.getElementById("error") === null) {
                        const error = document.createElement("div");
                        error.className = "alert alert-danger";
                        error.role = "alert";
                        error.id = "error";
                        error.textContent = "Wrong token!";
                        document.getElementById("description").insertBefore(error, document.getElementById("description").firstChild);
                        return;
                    } else {
                        if (document.getElementById("error").textContent.includes("x")) {
                            const number = parseInt(document.getElementById("error").textContent[document.getElementById("error").textContent.length - 1]) + 1;
                            document.getElementById("error").textContent = `Wrong token! x${number}`;
                        }
                        else {
                            document.getElementById("error").textContent = "Wrong token! x2";
                        }
                        return;
                    }
                }
                
                const button = event.target;
                button.classList.add("shrinked");
                button.textContent = "Confirm";
                button.id = "confirm";
                button.name = "confirm";
        
        
                document.getElementById("description").classList.add("hidden-div");
                document.getElementById("input_form").classList.add("hidden-div");

                const titleText = document.getElementById("title_text");
                const imgElement = document.createElement("img");
                imgElement.id = "bot_avatar";
                if (data.avatar === null) {
                    const discriminator = data.discriminator;
                    const index = parseInt(discriminator) % 5;
                    imgElement.src = `https://cdn.discordapp.com/embed/avatars/${index}.png`;
                } else {
                    imgElement.src = `https://cdn.discordapp.com/avatars/${data.id}/${data.avatar}.png`;
                }
                imgElement.style.borderRadius = "50%";
                imgElement.style.width = "100px";
                imgElement.style.height = "100px";
                const br1 = document.createElement("br")
                br1.id = "br1";
                const br2 = document.createElement("br")
                br2.id = "br2";
                titleText.insertBefore(br1, titleText.firstChild);
                titleText.insertBefore(br2, titleText.firstChild);
                titleText.insertBefore(imgElement, titleText.firstChild);
                document.getElementById("title_text").getElementsByTagName("span")[0].textContent = `Is this your bot? ${data.username}#${data.discriminator}`;
                
                var new_btn = document.createElement("button");
                new_btn.innerHTML = 'Back';
                new_btn.name = 'back';
                new_btn.id = 'back';
                new_btn.className = 'btn btn-primary btn-user';
                new_btn.style.background = 'rgb(14,15,18)';
                new_btn.style.borderWidth = '1px';
                new_btn.style.borderColor = 'rgb(0,0,0)';
                new_btn.style.width = '50%';
                new_btn.type = 'button';
        
                var buttonContainer = document.querySelector(".button-container");
                buttonContainer.insertBefore(new_btn, buttonContainer.firstChild);
        })
        .catch(error => {
            console.error('Error:', error);
            console.log('An error occurred while trying to verify the token! Most likely its an internet connection issue!');
            if (document.getElementById("error") === null) {
                const error = document.createElement("div");
                error.className = "alert alert-danger";
                error.role = "alert";
                error.id = "error";
                error.textContent = "An error occurred while trying to verify the token! Check the console for more information! ";
                document.getElementById("description").insertBefore(error, document.getElementById("description").firstChild);
                return;
            } else {
                if (document.getElementById("error").textContent.includes("x")) {
                    const number = parseInt(document.getElementById("error").textContent[document.getElementById("error").textContent.length - 1]) + 1;
                    document.getElementById("error").textContent = `An error occurred while trying to verify the token! Check the console for more information! x${number}`;
                }
                else {
                    document.getElementById("error").textContent = "An error occurred while trying to verify the token! Check the console for more information! x2";
                }
                return;
            }
        });
    }
    else if (event.target.id === "back") {
        event.target.remove();
        const button = document.getElementById("confirm");
        button.classList.remove("shrinked");
        button.textContent = "Continue";
        button.id = "next";
        button.name = "next";

        document.getElementById("description").classList.remove("hidden-div");
        document.getElementById("input_form").classList.remove("hidden-div");

        document.getElementById("bot_avatar").remove();
        document.getElementById("br1").remove();
        document.getElementById("br2").remove();

        document.getElementById("title_text").getElementsByTagName("span")[0].textContent = "Welcome to EB-bot";
    }
});""",
                                     method="POST", show_otp_popup=False)

    # /Login
    return flask.render_template('login.html', type="text", input_name="discord_id", title="Please enter your discord user id",
                                 body="You can get it by right clicking your name and clicking 'Copy ID'",
                                 placeholder="Enter user id here",
                                 footer="NOTE: You must been given access to the bot by the owner!",
                                 btn_text="send OTP code",
                                 custom_js="history.pushState({}, '', '/login');",
                                 method="POST", show_otp_popup=True)


@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'otp_verified' in session and session['otp_verified']:
        return flask.render_template('index.html', console_content=app.server_console if app.server_console else [])
    return flask.redirect(flask.url_for('login'))

@app.route('/configs', methods=['GET', 'POST'])
def configs():
    if 'otp_verified' in session and session['otp_verified']:
        configs_folder = os.path.join('Bot', 'Configs')
        if flask.request.method == 'POST':
            # Handle saving updated configs
            for filename in os.listdir(configs_folder):
                if filename.endswith('.yml'):
                    form_field_name = f'config_{filename}'
                    updated_content = flask.request.form.get(form_field_name)
                    if updated_content is not None:
                        file_path = os.path.join(configs_folder, filename)
                        # Validate the YAML content before saving
                        try:
                            yaml = ruamel.yaml.YAML()
                            loaded_yaml = yaml.load(updated_content)
                            # If valid, save to file
                            with open(file_path, 'w', encoding='utf-8') as f:
                                yaml.dump(loaded_yaml, f)
                        except ruamel.yaml.YAMLError as e:
                            # Handle YAML parsing error
                            flask.flash(f"Error parsing YAML in {filename}: {e}")
                            return flask.redirect(flask.url_for('configs'))
            with open(os.path.join('Bot', 'reload_config.txt'), 'w') as f:
                f.write('reload')
            flask.flash('Configurations saved successfully.')
            return flask.redirect(flask.url_for('configs'))
        else:
            # GET method
            if flask.request.args.get('reload') is None:
                return flask.render_template('wating.html')

            configs_data = {}
            for filename in os.listdir(configs_folder):
                if filename.endswith('.yml'):
                    file_path = os.path.join(configs_folder, filename)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        configs_data[filename] = content
            return flask.render_template('configs.html', configs_data=configs_data)
    else:
        return flask.redirect(flask.url_for('login'))

@app.context_processor
def inject_bot_status():
    return {'bot_running': app.bot_running}

@app.route('/bot_start', methods=['POST'])
def bot_start():
    if app.bot_running:
        turbo.push(turbo.prepend(f'<div class="alert alert-danger" role="alert" id="error-running">The bot is already running!</div><script>setTimeout(() => document.getElementById("error-running").remove(), 5000);</script>', target="btn&error"))
        return {"status": "error"}

    app.bot_running = True
    app.server_console = []
    app.up_time = 0

    process = subprocess.Popen(
        ['python3' if os.name == 'posix' else 'python', 'bot.py', 'IknowWhatImDoing'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        cwd='Bot'
    )
    app.bot_console_process = process
    turbo.push(turbo.replace(f'<span id="bot-status-indicator" style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: green; margin-left: 8px;"></span>', "bot-status-indicator"))
    turbo.push(turbo.replace(f'<a class="btn btn-primary btn-sm disabled d-none d-sm-inline-block" role="button" id="start-btn" style="background: rgb(47,137,32);border-color: rgb(51,136,44);width: 40%;"><i class="fas fa-play fa-sm text-white-50"></i>&nbsp;Start</a>', 'start-btn'))
    turbo.push(turbo.replace(f'<a class="btn btn-primary btn-sm d-none d-sm-inline-block" role="button" onclick="stopBot()" id="stop-btn" style="background: rgb(137,38,32);margin-left: 5%;width: 40%;border-color: rgb(137,38,32);"><i class="fas fa-stop fa-sm text-white-50"></i>&nbsp;Stop</a>', 'stop-btn'))
    tick1console()

    return {"status": "success"}

@app.route('/bot_stop', methods=['POST'])
def bot_stop():
    if not app.bot_running:
        turbo.push(turbo.prepend(f'<div class="alert alert-danger" role="alert" id="error-running">The bot is not running!</div><script>setTimeout(() => document.getElementById("error-running").remove(), 5000);</script>', target="btn&error"))
        return {"status": "error"}
    with open("Bot/shutdown_signal.txt", "w") as f:
        f.write("shutdown")
    try:
        app.bot_console_process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        # Force kill if the bot didn't shut down
        print("Bot didn't shut down in time, force killing it")
        kill_process_and_children(app.bot_console_process.pid)
        os.remove("Bot/shutdown_signal.txt")

    app.bot_console_process = None
    app.bot_running = False
    turbo.push(turbo.replace(f'<span id="bot-status-indicator" style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: red; margin-left: 8px;"></span>', target="bot-status-indicator"))
    turbo.push(turbo.replace(f'<a class="btn btn-primary btn-sm d-none d-sm-inline-block" onclick="startBot()" role="button" id="start-btn" style="background: rgb(47,137,32);border-color: rgb(51,136,44);width: 40%;"><i class="fas fa-play fa-sm text-white-50"></i>&nbsp;Start</a>', 'start-btn'))
    turbo.push(turbo.replace(f'<a class="btn btn-primary btn-sm disabled d-none d-sm-inline-block" role="button" id="stop-btn" style="background: rgb(137,38,32);margin-left: 5%;width: 40%;border-color: rgb(137,38,32);"><i class="fas fa-stop fa-sm text-white-50"></i>&nbsp;Stop</a>', 'stop-btn'))

    return {"status": "success"}

def tick1console():
    with app.app_context():
        if app.bot_running:
            if app.bot_console_process is not None:
                for line in iter(app.bot_console_process.stdout.readline, b''):
                    if not app.bot_running:
                        break
                    line_to_add = console_colors_into_span(line)
                    if line_to_add == '<span style="color: white;"></span>':
                        break
                    app.server_console.append(line_to_add)
                    turbo.push(turbo.append(line_to_add + '\n', 'console-content-pre'))
                    if line_to_add == '<span style="color: red;">Shutting down the bot...</span>' or  line_to_add == '<span style="color: white;">Shutting down the bot...</span>':
                        break
                    elif line_to_add.startswith('<span style="color: red;">Error: </span>') or line_to_add.startswith('<span style="color: white;">Error: </span>'):
                        app.error_count += 1
                        continue
                    elif line_to_add == '<span style="color: red;">Exiting...</span>':
                        app.bot_running = False
                        kill_process_and_children(app.bot_console_process.pid)
                        turbo.push(turbo.replace(f'<span id="bot-status-indicator" style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: red; margin-left: 8px;"></span>', target="bot-status-indicator"))
                        turbo.push(turbo.replace(f'<a class="btn btn-primary btn-sm d-none d-sm-inline-block" onclick="startBot()" role="button" id="start-btn" style="background: rgb(47,137,32);border-color: rgb(51,136,44);width: 40%;"><i class="fas fa-play fa-sm text-white-50"></i>&nbsp;Start</a>', 'start-btn'))
                        turbo.push(turbo.replace(f'<a class="btn btn-primary btn-sm disabled d-none d-sm-inline-block" role="button" id="stop-btn" style="background: rgb(137,38,32);margin-left: 5%;width: 40%;border-color: rgb(137,38,32);"><i class="fas fa-stop fa-sm text-white-50"></i>&nbsp;Stop</a>', 'stop-btn'))
                        break


def kill_process_and_children(pid):
    try:
        parent = psutil.Process(pid)
        for child in parent.children(recursive=True):  # Kill all child processes
            child.terminate()
        parent.terminate()  # Kill the main process
    except psutil.NoSuchProcess:
        pass

def add_zero(number: int):
    return f"0{number}" if number < 10 else number

def seconds_to_time(seconds: int):
    # dd:hh:mm:ss
    days = seconds // 86400
    seconds %= 86400
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    return f"{add_zero(days)}:{add_zero(hours)}:{add_zero(minutes)}:{add_zero(seconds)}"


@scheduler.task('interval', id='tick1', seconds=1)
def tick1():
    if app.bot_running:
        app.up_time += 1
    with app.app_context():
        ram_usage_percentage = int(psutil.virtual_memory().percent)
        turbo.push(turbo.replace(f'<div class="progress-bar bg-info" aria-valuenow="{ram_usage_percentage}" aria-valuemin="0" aria-valuemax="100" id="ram_usage_percentage_bar" style="width: {ram_usage_percentage}%;"><span class="visually-hidden">{ram_usage_percentage}%</span></div>', 'ram_usage_percentage_bar'))
        turbo.push(turbo.replace(f'<span id="ram_usage_percentage_number">{ram_usage_percentage}%</span>', 'ram_usage_percentage_number'))
        turbo.push(turbo.replace(f'<span id="ram_usege_title">RAM usage ({psutil.virtual_memory().used / 1024 / 1024:.2f}/{psutil.virtual_memory().total / 1024 / 1024:.2f} MB)</span>', 'ram_usege_title'))
        turbo.push(turbo.replace(f'<span id="bot_uptime">{seconds_to_time(app.up_time)}</span>', 'bot_uptime'))
        turbo.push(turbo.replace(f'<span id="error_count">{app.error_count}</span>', 'error_count'))


@scheduler.task('interval', id='tick5', seconds=5)
def tick5():
    with app.app_context():
        with open(r'Bot/Configs/general.yml') as f:
            loaded_yaml = ruamel.yaml.YAML(typ="safe").load(f)
            config = loaded_yaml['bot']
        token = config['token']
        headers = {
            'Authorization': f'Bot {token}',
            'Content-Type': 'application/json'
        }
        bot = requests.get(f"https://discord.com/api/v10/users/@me", headers=headers)
        if bot.status_code != 200:
            return turbo.stream(turbo.prepend(f'<div class="alert alert-danger" role="alert" id="error">An error occurred while trying to get the bot information!</div>', target="description"))
        bot = bot.json()
        turbo.push(turbo.replace(f'<span id="bot_name">{bot["username"]}#{bot["discriminator"]}</span>', 'bot_name'))


def shutdown_scheduler(exception=None):
    if scheduler.running:
        scheduler.shutdown(wait=False)


@app.route('/assets/<path:filename>', methods=['GET'])
def assets(filename):
    assets_dir = os.path.join(app.root_path, 'templates', 'assets')
    if not os.path.isfile(os.path.join(assets_dir, filename)):
        flask.abort(404)
    return flask.send_from_directory(assets_dir, filename)


@app.route('/languages', methods=['GET', 'POST'])
def languages():
    if 'otp_verified' in session and session['otp_verified']:
        if flask.request.method == 'POST':
            action = flask.request.form.get('action')
            if action == 'save':
                # Handle saving updated language files
                for key in flask.request.form:
                    if key.startswith('lang_'):
                        file_key = key[len('lang_'):]  # e.g., 'command_folder/filename.json'
                        updated_content = flask.request.form.get(key)
                        command_folder, filename = file_key.split('/', 1)
                        file_path = os.path.join('Bot', 'Commands', command_folder, 'lang', filename)
                        # Validate JSON
                        try:
                            json.loads(updated_content)
                            with open(file_path, 'w', encoding='utf-8') as f:
                                f.write(updated_content)
                        except json.JSONDecodeError as e:
                            flask.flash(f"Error parsing JSON in {filename}: {e}")
                            return flask.redirect(flask.url_for('languages'))
                flask.flash('Language files saved successfully.')
                return flask.redirect(flask.url_for('languages'))
            elif action == 'copy':
                # Handle duplication
                original_file_key = flask.request.form.get('original_file_key')
                new_language_code = flask.request.form.get('new_language_code')
                if not original_file_key or not new_language_code:
                    flask.flash('Invalid data for duplication.')
                    return flask.redirect(flask.url_for('languages'))
                command_folder, original_filename = original_file_key.split('/', 1)
                original_file_path = os.path.join('Bot', 'Commands', command_folder, 'lang', original_filename)
                new_filename = f"{new_language_code}.json"
                new_file_path = os.path.join('Bot', 'Commands', command_folder, 'lang', new_filename)
                if os.path.exists(new_file_path):
                    flask.flash(f"Language file {new_filename} already exists in {command_folder}.")
                    return flask.redirect(flask.url_for('languages'))
                # Copy the original file to the new file
                with open(original_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                with open(new_file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                flask.flash(f"Language file {new_filename} created successfully in {command_folder}.")
                return flask.redirect(flask.url_for('languages'))
            else:
                flask.flash('Invalid action.')
                return flask.redirect(flask.url_for('languages'))
        else:
            # GET method
            if flask.request.args.get('reload') is None:
                return flask.render_template('wating.html')

            # Load language files grouped by command pack
            language_files = {}  # key: command_folder, value: dict of language files
            for command_folder in os.listdir(os.path.join('Bot', 'Commands')):
                lang_folder = os.path.join('Bot', 'Commands', command_folder, 'lang')
                if os.path.isdir(lang_folder):
                    files = {}
                    for filename in os.listdir(lang_folder):
                        if filename.endswith('.json'):
                            file_path = os.path.join(lang_folder, filename)
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                files[filename] = content
                    if files:
                        language_files[command_folder] = files
            return flask.render_template('languages.html', language_files=language_files)
    else:
        return flask.redirect(flask.url_for('login'))

@app.route('/allowed_users', methods=['GET', 'POST'])
def allowed_users():
    if 'otp_verified' in session and session['otp_verified']:
        config_path = pathlib.Path('Bot/Configs/allowed_users.yml')
        yaml = ruamel.yaml.YAML()

        if config_path.exists():
            with config_path.open('r', encoding='utf-8') as f:
                config_data = yaml.load(f) or {}
        else:
            config_data = {}

        allowed_users_list = config_data.get('allowed_users', [])

        if flask.request.method == 'POST':
            action = flask.request.form.get('action')
            if action == 'add_user':
                user_id = flask.request.form.get('user_id')
                if user_id:
                    if user_id not in allowed_users_list:
                        allowed_users_list.append(user_id)
                        config_data['allowed_users'] = allowed_users_list
                        with config_path.open('w', encoding='utf-8') as f:
                            yaml.dump(config_data, f)
                        flask.flash(f'User {user_id} added successfully.')
                    else:
                        flask.flash(f'User {user_id} is already in the allowed list.')
                else:
                    flask.flash('User ID cannot be empty.')
            elif action == 'remove_user':
                user_id = flask.request.form.get('user_id')
                if user_id:
                    if user_id in allowed_users_list:
                        allowed_users_list.remove(user_id)
                        config_data['allowed_users'] = allowed_users_list
                        with config_path.open('w', encoding='utf-8') as f:
                            yaml.dump(config_data, f)
                        flask.flash(f'User {user_id} removed successfully.')
                    else:
                        flask.flash(f'User {user_id} is not in the allowed list.')
                else:
                    flask.flash('User ID cannot be empty.')
            return flask.redirect(flask.url_for('allowed_users'))

        return flask.render_template('allowed_users.html', allowed_users=allowed_users_list)
    else:
        return flask.redirect(flask.url_for('login'))

@app.route('/logout', methods=['GET'])
def logout():
    session.clear()
    return flask.redirect(flask.url_for('login'))


def console_colors_into_span(text: str):
    final_text = ""
    result = ""
    while '\033' in text:
        start = ""
        if not text.startswith("\033"):
            start = text[:text.index("\033")]
            text = text[text.index("\033"):]
            if text.endswith("</span>"):
                text = text[:-7]
                start += "</span>"
            final_text += start
        result = console_colors_into_span_r(text)
        text = result
    if result == "":
        return console_colors_into_span_r(text)
    return final_text + result


def console_colors_into_span_r(text: str):
    COLORS = {
        "30": '<span style="color: black;">text</span>', # Black
        "31": '<span style="color: red;">text</span>', # Red
        "32": '<span style="color: #6afa74;">text</span>', # Green
        "33": '<span style="color: #e3936f;">text</span>', # Yellow
        "34": '<span style="color: blue;">text</span>', # Blue
        "35": '<span style="color: #686de9;">text</span>', # Magenta
        "36": '<span style="color: #7df1cf;">text</span>', # Cyan
        "37": '<span style="color: white;">text</span>', # White
        "30 Bright": '<span style="color: grey;">text</span>', # Bright Black (Gray)
        "31 Bright": '<span style="color: lightcoral;">text</span>', # Bright Red
        "32 Bright": '<span style="color: lightgreen;">text</span>', # Bright Green
        "33 Bright": '<span style="color: lightyellow;">text</span>', # Bright Yellow
        "34 Bright": '<span style="color: lightblue;">text</span>', # Bright Blue
        "35 Bright": '<span style="color: lightpink;">text</span>', # Bright Magenta
        "36 Bright": '<span style="color: lightcyan;">text</span>', # Bright Cyan
        "37 Bright": '<span style="color: lightgrey;">text</span>', # Bright White
    }
    text = text.replace("\n", "")
    if not text.startswith("\033"):
        return COLORS['37'].replace("text", text)

    color_code = text.split("\033[")[1].split("m")[0]
    pure_text = "m".join(text.split("m")[1:])
    if len(color_code) > 2: # 16-color
        color = color_code.split(";")
        if color[0] == "0":
            return COLORS[color[1]].replace("text", pure_text)
        return COLORS[f"{color[1]} Bright"].replace("text", pure_text)
    if len(color_code) == 2: # 256-color
        if color_code[0] == "9":
            return COLORS[f'3{color_code[1]} Bright'].replace("text", pure_text)
        return COLORS[color_code].replace("text", pure_text)
    return COLORS['37'].replace("text", pure_text)

def register_package_routes(app): # Register web routes for each package if there is a web folder (Beta)
    """
    Flask blueprint by default does not support prefixing the template loader with the package name.
    In this case I think package should be able naming there file somthing like 'index.html' so I used the jinja_loader to register them manually rather using the builtin functionality of blueprint.
    :param app: Flask app instance
    :return: None
    """
    prefix_loaders = {}
    commands_path = os.path.join('Bot', 'Commands')
    for package in os.listdir(commands_path):
        package_path = os.path.join(commands_path, package)
        web_path = os.path.join(package_path, 'web', 'routes.py')
        templates_path = os.path.join(package_path, 'web', 'templates')

        if os.path.isfile(web_path): # Register blueprint if routes.py exists
            try:
                module_name = f"{package}_routes"
                spec = importlib.util.spec_from_file_location(module_name, web_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                if hasattr(module, 'blueprint'):
                    app.register_blueprint(module.blueprint, url_prefix=f"/{package}")
                    print(f"[+] Registered web routes for package: {package}")
                if hasattr(module, "get_sidebar_item"):
                    item = module.get_sidebar_item()
                    if isinstance(item, dict):
                        app.config.setdefault("EXTRA_SIDEBAR_ITEMS", [])
                        app.config["EXTRA_SIDEBAR_ITEMS"].append(item)
            except Exception as e:
                print(f"[!] Failed to register web route for {package}: {e}")

        if os.path.isdir(templates_path): # Register template loader if templates exist
            prefix_loaders[package] = jinja2.FileSystemLoader(templates_path)
            print(f"[+] Registered templates for package: {package}")

    if prefix_loaders: # Merge into Flask's template loader
        if not isinstance(app.jinja_loader, jinja2.ChoiceLoader):
            app.jinja_loader = jinja2.ChoiceLoader([app.jinja_loader])
        app.jinja_loader.loaders.append(jinja2.PrefixLoader(prefix_loaders))



if __name__ == '__main__':
    register_package_routes(app) #This is beta feature, if errors occur, please report them to the developer and add # to the start of this line
    app.run(debug=False, host='0.0.0.0', port=None)