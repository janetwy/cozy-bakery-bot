import json
import discord

from discord.ext import commands

from config import (
    DISCORD_BOT_TOKEN,
    CAPTION_CHANNEL_ID
)

from database import (
    initialize_database,
    create_session,
    get_session,
    update_session
)

from caption_service import (
    generate_caption,
    revise_caption
)


# ---------------------------------------------------------
# Discord setup
# ---------------------------------------------------------

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

IMAGE_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".webp"
)


def is_image(attachment: discord.Attachment) -> bool:

    if attachment.content_type:
        return attachment.content_type.startswith("image/")

    filename = attachment.filename.lower()

    return filename.endswith(IMAGE_EXTENSIONS)


def caption_message(caption: str) -> str:
    return (
        "**Instagram Caption**\n\n"
        f"{caption}"
    )


# ---------------------------------------------------------
# Custom edit modal
# ---------------------------------------------------------

class CustomEditModal(discord.ui.Modal):

    def __init__(self, session_id: int):
        super().__init__(title="Edit Instagram Caption")

        self.session_id = session_id

        self.instructions = discord.ui.TextInput(
            label="What should I change?",
            placeholder=(
                "Example: Make it more playful and emphasize "
                "that the lemon curd is homemade."
            ),
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000
        )

        self.add_item(self.instructions)


    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        await interaction.response.defer()

        session = get_session(self.session_id)

        if session is None:
            await interaction.followup.send(
                "I couldn't find this caption session.",
                ephemeral=True
            )
            return

        try:

            caption, response_id = await revise_caption(
                previous_response_id=session.openai_response_id,
                current_caption=session.current_caption,
                instruction=self.instructions.value
            )

            update_session(
                self.session_id,
                caption,
                response_id
            )

            await interaction.message.edit(
                content=caption_message(caption),
                view=CaptionControls(self.session_id)
            )

        except Exception as error:

            print(error)

            await interaction.followup.send(
                "Something went wrong while editing the caption.",
                ephemeral=True
            )


# ---------------------------------------------------------
# Caption buttons
# ---------------------------------------------------------

class CaptionControls(discord.ui.View):

    def __init__(self, session_id: int):

        super().__init__(timeout=None)

        self.session_id = session_id


    async def perform_revision(
        self,
        interaction: discord.Interaction,
        instruction: str
    ):

        await interaction.response.defer()

        session = get_session(self.session_id)

        if session is None:

            await interaction.followup.send(
                "I couldn't find this caption session.",
                ephemeral=True
            )

            return

        try:

            caption, response_id = await revise_caption(
                previous_response_id=session.openai_response_id,
                current_caption=session.current_caption,
                instruction=instruction
            )

            update_session(
                self.session_id,
                caption,
                response_id
            )

            await interaction.message.edit(
                content=caption_message(caption),
                view=CaptionControls(self.session_id)
            )

        except Exception as error:

            print(error)

            await interaction.followup.send(
                "Something went wrong while revising the caption.",
                ephemeral=True
            )


    @discord.ui.button(
        label="Regenerate",
        emoji="🔄",
        style=discord.ButtonStyle.secondary
    )
    async def regenerate(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await self.perform_revision(
            interaction,
            """
Create a substantially different version of the caption.

Keep all factual product details accurate.

Use a different hook and different wording,
but maintain the Cozy Cakes & Bakes brand voice.
"""
        )


    @discord.ui.button(
        label="Shorter",
        emoji="✂️",
        style=discord.ButtonStyle.secondary
    )
    async def shorter(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await self.perform_revision(
            interaction,
            """
Make the caption noticeably shorter and more concise.

Preserve important product information,
pricing if present, and useful hashtags.
"""
        )


    @discord.ui.button(
        label="More Casual",
        emoji="😊",
        style=discord.ButtonStyle.secondary
    )
    async def casual(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await self.perform_revision(
            interaction,
            """
Make the caption more casual, warm, and conversational.

It should sound like it was personally written by the
owner of a small local bakery rather than a marketing department.
"""
        )


    @discord.ui.button(
        label="More Sales-Focused",
        emoji="🛍️",
        style=discord.ButtonStyle.secondary
    )
    async def sales(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await self.perform_revision(
            interaction,
            """
Make the caption slightly more sales-focused.

Highlight why someone would want the product and make
the important purchasing information easy to notice.

Do not become pushy or overly promotional.
Do not invent ordering instructions.
"""
        )


    @discord.ui.button(
        label="Custom Edit",
        emoji="✏️",
        style=discord.ButtonStyle.primary
    )
    async def custom_edit(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        modal = CustomEditModal(self.session_id)

        await interaction.response.send_modal(modal)


# ---------------------------------------------------------
# Bot events
# ---------------------------------------------------------

@bot.event
async def on_ready():

    print("--------------------------------")
    print(f"Logged in as {bot.user}")
    print("--------------------------------")


@bot.event
async def on_message(message: discord.Message):

    # Ignore messages sent by bots.
    if message.author.bot:
        return

    # Restrict generation to configured channel.
    if (
        CAPTION_CHANNEL_ID is not None
        and message.channel.id != CAPTION_CHANNEL_ID
    ):
        await bot.process_commands(message)
        return

    # Find image attachments.
    images = [
        attachment
        for attachment in message.attachments
        if is_image(attachment)
    ]

    # No photos = do nothing.
    if not images:
        await bot.process_commands(message)
        return

    image_urls = [
        attachment.url
        for attachment in images
    ]

    user_notes = message.content.strip()

    status_message = await message.reply(
        "✨ Creating your Instagram caption..."
    )

    try:

        caption, response_id = await generate_caption(
            user_notes=user_notes,
            image_urls=image_urls
        )

        session_id = create_session(
            discord_message_id=message.id,
            discord_channel_id=message.channel.id,
            user_notes=user_notes,
            image_urls=json.dumps(image_urls),
            caption=caption,
            openai_response_id=response_id
        )

        await status_message.edit(
            content=caption_message(caption),
            view=CaptionControls(session_id)
        )

    except Exception as error:

        print("Caption generation error:")
        print(error)

        await status_message.edit(
            content=(
                "❌ I couldn't generate the caption. "
                "Check the bot logs for the error."
            )
        )

    await bot.process_commands(message)


# ---------------------------------------------------------
# Startup
# ---------------------------------------------------------

if __name__ == "__main__":

    initialize_database()

    if not DISCORD_BOT_TOKEN:
        raise RuntimeError(
            "DISCORD_BOT_TOKEN is missing from .env"
        )

    bot.run(DISCORD_BOT_TOKEN)