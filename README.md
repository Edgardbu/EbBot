# EbBot

**EbBot** is a modular, web-controlled Discord bot framework designed for flexibility, customization, and ease of use. It features a clean package system for commands, a built-in web dashboard, OTP-secured login, and support for dynamic language and configuration editing.

## 🌟 Features

- 🎛️ **Web Dashboard**: Start/stop the bot, view real-time logs, monitor uptime, RAM usage, error count, and more.
- 📦 **Package System**: Drop-in command packages with individual `requirements.txt`, config, and language files.
- 🗃️ **SQLite Database**: Persistent storage used across packages.
- 🌐 **Multi-language Support**: Easy translation editing via the web.
- ⚙️ **Dynamic Configuration**: Edit YAML config files via the web with live reload support.
- 🔐 **OTP-based Authentication**: Secure login via Discord DM verification.
- 🪄 **Auto Module Installer**: Installs dependencies from package-specific `requirements.txt` files automatically.
- 💻 **Console Integration**: View colored output in-browser, with real-time TurboFlask updates.

---

## 🚀 Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/Edgardbu/EbBot.git
cd EbBot
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Start the Web Interface

```bash
python main.py
```

If using Pterodactyl or other virtualized environments, make sure to update this line in `main.py`:

```python
app.run(debug=False, host='0.0.0.0', port=None)
```

To include your assigned port (e.g. 1234):

```python
app.run(debug=False, host='0.0.0.0', port=1234)
```

Ensure you have **two available ports**: one for the web UI and one for the bot.

---

## 📦 Installing Command Packages

Official command packages are hosted at: [EbBotCommands](https://github.com/Edgardbu/EbBotCommands)

To install a package:

1. Copy the GitHub URL of the desired package folder, e.g.:
   `https://github.com/Edgardbu/EbBotCommands/tree/main/Embed%20Manager`
2. Paste it into: [https://download-directory.github.io](https://download-directory.github.io)
3. Download and extract the ZIP.
4. Place the extracted content into the `Bot/Commands` and `Bot/Configs` folders.

Restart the bot — and you're done!

> ❗ You are responsible for third-party packages. Only install trusted ones. Malicious code can compromise your system.

To remove a package, delete its folder from `Bot/Commands` and its config from `Bot/Configs`, then restart the bot.

---

## 🌐 Web Interface

- **Login** with your Discord ID and a secure OTP sent via DM.
- **Dashboard**: Start/stop the bot, monitor stats, and view the console.
- **Configs Page**: Edit and save config files directly.
- **Languages Page**: Translate bot responses easily.
- **Allowed Users Page**: Manage who can log in.

---

## 🛠️ Create Your Own Packages

Each package can include:

- Python command files with an `init()` function.
- `requirements.txt` for dependencies.
- `lang/` folder with JSON files for translations.
- YAML config file placed in `Bot/Configs`.

When the bot starts, it automatically loads all valid packages and installs their dependencies.

---

## 📅 Roadmap
- [x] Multi-language support system  
- [x] Web-based config editor  
- [x] Discord OTP-based authentication  
- [x] Modular package system with dependency injection
- [ ] GUI embed builder (drag & drop style)  
- [ ] Plugin/package manager via web UI  
- [ ] Real-time analytics and logs in dashboard

---

## 📂 Project Structure

```
EbBot/
├── Bot/
│   ├── bot.py              # Main bot controller
│   ├── utils.py
│   ├── Commands/           # All installed command packages
│   ├── Configs/            # All YAML config files
│   └── data.db             # SQLite database
├── templates/              # Web UI templates
├── main.py                 # Starts the web interface
├── requirements.txt
```

---

## 💬 Support & Community

Join our community on Discord: **[Discord Server](https://discord.gg/gRxfAQTtkP)**

We welcome contributors and encourage package development. Feel free to fork, improve, and share your work!

---

## 📜 License

MIT License
