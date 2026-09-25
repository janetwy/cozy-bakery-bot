# 🍰 AI Instagram Caption Discord Bot

A Discord bot that uses the OpenAI API to analyze product photos and generate ready-to-use Instagram captions.

Originally built to streamline the social media workflow for a small home bakery, the bot turns a Discord channel into a simple content creation workspace: upload product photos, add optional notes, and receive an Instagram caption generated from both the images and product information.

The generated caption can then be refined directly in Discord without losing the context of the original photos.

## ✨ Features

* 📷 Automatically detects image uploads in a designated Discord channel
* 🤖 Uses OpenAI's multimodal models to analyze product photos
* 📝 Generates complete Instagram captions from photos and optional product notes
* 🧠 Maintains context when revising captions
* 💾 Stores caption sessions and revision context using SQLite
* 🎛️ Provides interactive Discord controls for refining captions
* 🔒 Restricts automatic generation to a configurable Discord channel
* ⚙️ Uses environment variables for secrets and configuration

### Caption Controls

After generating a caption, the bot provides several options:

* 🔄 **Regenerate** — Generate a substantially different caption
* ✂️ **Shorter** — Create a more concise version
* 😊 **More Casual** — Make the caption warmer and more conversational
* 🛍️ **More Sales-Focused** — Emphasize the product and purchasing information
* ✏️ **Custom Edit** — Provide your own revision instructions

Revisions continue using the context of the original caption-generation request.

## 🖼️ Example Workflow

Post product photos and optional notes in the configured Discord channel:

```text
Lemon curd shortbread cookies
8 for $10
Lemon curd is homemade
```

Attach one or more product photos.

The bot analyzes the images and notes and responds with a finished caption:

```text
🍋 Buttery shortbread + homemade lemon curd makes for
the perfect little bite of sunshine.

These lemon curd shortbread cookies are tender, buttery,
and filled with bright homemade lemon curd.

8 cookies — $10

#DFWBakery #HomeBakery #LemonCookies #ShortbreadCookies
```

Interactive buttons beneath the response allow the caption to be revised without creating a new request from scratch.

## 🏗️ Architecture

```text
Discord
   │
   │ Product photos + notes
   ▼
┌──────────────────────────┐
│      Discord Bot         │
│      discord.py          │
│                          │
│   ┌──────────────────┐   │
│   │ Caption Service  │────────► OpenAI API
│   └──────────────────┘   │       Image analysis
│                          │       + caption generation
│   ┌──────────────────┐   │
│   │      SQLite      │   │
│   │ Caption Sessions │   │
│   └──────────────────┘   │
└────────────┬─────────────┘
             │
             ▼
       Discord Caption
             │
     ┌───────┴────────┐
     │ Revision       │
     │ Controls       │
     └────────────────┘
```

## 🛠️ Tech Stack

* **Python 3**
* **discord.py** — Discord bot and interactive UI
* **OpenAI Responses API** — multimodal image analysis and caption generation
* **SQLite** — caption session persistence
* **python-dotenv** — environment configuration

## 📁 Project Structure

```text
.
├── bot.py
├── caption_service.py
├── config.py
├── database.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

### `bot.py`

Handles Discord events, image detection, interactive buttons, and custom-edit modals.

### `caption_service.py`

Handles communication with the OpenAI API, including initial multimodal caption generation and subsequent revisions.

### `database.py`

Stores caption sessions, current captions, Discord message information, and OpenAI response context using SQLite.

### `config.py`

Contains application configuration and the system prompt used to define the caption-writing style.

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
cd YOUR_REPOSITORY
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
```

Activate it on macOS/Linux:

```bash
source .venv/bin/activate
```

On Windows:

```powershell
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create a Discord application

Create an application through the Discord Developer Portal and add a bot to it.

Enable the **Message Content Intent** for the bot.

Invite the bot to your server with the permissions required to:

* View the configured channel
* Read message history
* Send messages
* Use application commands/interactions

### 5. Create an OpenAI API key

Create an OpenAI API project and API key.

API usage is billed separately from consumer ChatGPT subscriptions.

### 6. Configure environment variables

Create a `.env` file in the project root:

```env
DISCORD_BOT_TOKEN=your_discord_bot_token
OPENAI_API_KEY=your_openai_api_key
CAPTION_CHANNEL_ID=your_discord_channel_id
```

`CAPTION_CHANNEL_ID` should contain the numeric ID of the Discord channel where image uploads should trigger caption generation.

> **Important:** Never commit your `.env` file, Discord bot token, or OpenAI API key to source control.

### 7. Start the bot

```bash
python bot.py
```

Once connected, upload one or more photos to the configured Discord channel.

## 🔐 Security

Secrets are loaded from environment variables and should never be committed to the repository.

The following files should be excluded through `.gitignore`:

```gitignore
.env
*.db
__pycache__/
.venv/
venv/
.DS_Store
```

If an API key or Discord token is accidentally committed to a public repository, revoke and replace it immediately. Removing the value from a later commit is not sufficient because it may remain accessible through Git history.

## 🧠 Context and Caption Revisions

Each initial caption request creates a caption session.

The session stores information such as:

```text
Discord message
       │
       ├── Product notes
       ├── Image references
       ├── Original caption
       ├── Current caption
       └── OpenAI response context
```

When a revision is requested, the bot continues from the previous OpenAI response context. This allows instructions such as:

```text
Make it shorter.
```

or:

```text
Make this more playful and emphasize the homemade lemon curd.
```

without requiring the user to describe the product again.

## ⚠️ Current Limitations

This project is intentionally lightweight and was designed primarily for use in a small private Discord server.

Current limitations include:

* Caption sessions are stored locally using SQLite.
* Discord attachment URLs are stored as part of session data.
* Deployment and multi-instance synchronization are not implemented.
* Interactive controls may require additional persistent-view configuration to survive bot restarts.
* The prompt is currently optimized for bakery and food-product photography.

## 🔮 Possible Future Improvements

Potential additions include:

* Persistent Discord controls across bot restarts
* Caption history and version restoration
* Slash commands for caption generation
* Multiple brand/style profiles
* Product catalog integration
* Automatic product and price recognition from stored product data
* Hashtag presets
* Platform-specific captions for Instagram, Facebook, and TikTok
* Approval/publishing workflow
* Cloud deployment
* Automated tests

## 💡 Motivation

Creating social media content for a small business involves more than simply taking a photo. Product information, pricing, brand voice, hashtags, and repeated caption revisions can make the process surprisingly time-consuming.
This project explores using multimodal AI as part of a practical small-business workflow rather than as a standalone chatbot. Discord acts as the user interface and organizational workspace, while the OpenAI API handles image understanding and content generation.
The goal is a simple workflow:
Upload → Generate → Refine → Post

## 📄 License

This project is available under the MIT License.
