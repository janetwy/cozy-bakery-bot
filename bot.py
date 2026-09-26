import json
import discord

from discord.ext import commands

from config import (
    DISCORD_BOT_TOKEN,
    CAPTION_CHANNEL_ID,
    FINALIZED_CHANNEL_ID
)

from database import (
    initialize_database,
    create_session,
    create_version,
    get_session,
    get_version,
    get_version_by_number,
    get_latest_version,
    get_version_count,
    finalize_version,
    get_approved_captions,
    set_finalized_discord_message
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


def caption_message(
    caption: str,
    version_number: int,
    version_count: int,
    finalized: bool = False
) -> str:

    status = " ⭐ APPROVED" if finalized else ""

    return (
        f"**Instagram Caption — "
        f"Version {version_number}/{version_count}"
        f"{status}**\n\n"
        f"{caption}"
    )


# ---------------------------------------------------------
# Custom edit modal
# ---------------------------------------------------------

class CustomEditModal(discord.ui.Modal):

    def __init__(
        self,
        session_id: int,
        version_number: int
    ):

        super().__init__(
            title="Edit Instagram Caption"
        )

        self.session_id = session_id
        self.version_number = version_number

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

        version = get_version_by_number(
            self.session_id,
            self.version_number
        )

        if version is None:

            await interaction.followup.send(
                "I couldn't find this caption version.",
                ephemeral=True
            )

            return

        try:

            caption, response_id = await revise_caption(
                previous_response_id=version.openai_response_id,
                current_caption=version.caption,
                instruction=self.instructions.value
            )

            new_version = create_version(
                session_id=self.session_id,
                caption=caption,
                openai_response_id=response_id,
                revision_type="custom"
            )

            count = get_version_count(
                self.session_id
            )

            await interaction.message.edit(
                content=caption_message(
                    new_version.caption,
                    new_version.version_number,
                    count
                ),
                view=CaptionControls(
                    self.session_id,
                    new_version.version_number
                )
            )

        except Exception as error:

            print(error)

            await interaction.followup.send(
                "Something went wrong while editing the caption.",
                ephemeral=True
            )
    
async def post_finalized_caption(
    bot: commands.Bot,
    session_id: int,
    version
):
    session = get_session(session_id)

    if session is None:
        raise ValueError(
            f"Caption session {session_id} not found."
        )

    if FINALIZED_CHANNEL_ID is None:
        raise ValueError(
            "FINALIZED_CHANNEL_ID is not configured."
        )

    channel = bot.get_channel(
        FINALIZED_CHANNEL_ID
    )

    if channel is None:
        channel = await bot.fetch_channel(
            FINALIZED_CHANNEL_ID
        )

    message_content = (
        "## ⭐ Ready to Post\n\n"
        f"### Caption\n"
        f"{version.caption}\n\n"
        f"*Version {version.version_number}*"
    )

    # Fetch the original message for fresh attachment URLs and filenames.
    source_channel = bot.get_channel(session.discord_channel_id)
    if source_channel is None:
        source_channel = await bot.fetch_channel(session.discord_channel_id)

    source_message = await source_channel.fetch_message(
        session.discord_message_id
    )
    images = [attachment for attachment in source_message.attachments
              if is_image(attachment)]
    if not images:
        raise RuntimeError("Could not retrieve any of the original photos.")

    files = []
    try:
        # Download all photos into memory before changing the existing post.
        for attachment in images:
            files.append(await attachment.to_file())

        existing_message = None
        if session.finalized_discord_message_id:
            try:
                existing_message = await channel.fetch_message(
                    session.finalized_discord_message_id
                )
            except discord.NotFound:
                # The ready-to-post message was manually deleted.
                pass

        if existing_message is not None:
            return await existing_message.edit(
                content=message_content,
                attachments=files,
                embeds=[]
            )

        finalized_message = await channel.send(
            content=message_content,
            files=files
        )
    finally:
        for file in files:
            file.close()

    set_finalized_discord_message(
        session_id,
        finalized_message.id
    )

    return finalized_message

# ---------------------------------------------------------
# Caption buttons
# ---------------------------------------------------------

class CaptionControls(discord.ui.View):

    def __init__(
        self,
        session_id: int,
        displayed_version: int
    ):

        super().__init__(timeout=None)

        self.session_id = session_id
        self.displayed_version = displayed_version


    async def refresh_message(
        self,
        interaction: discord.Interaction,
        version_number: int
    ):

        session = get_session(self.session_id)

        version = get_version_by_number(
            self.session_id,
            version_number
        )

        if session is None or version is None:
            await interaction.followup.send(
                "I couldn't find that caption version.",
                ephemeral=True
            )
            return

        count = get_version_count(self.session_id)

        is_approved = (
            session.is_finalized
            and session.approved_version_id == version.id
        )

        await interaction.message.edit(
            content=caption_message(
                version.caption,
                version.version_number,
                count,
                is_approved
            ),
            view=CaptionControls(
                self.session_id,
                version.version_number
            )
        )


    async def perform_revision(
        self,
        interaction: discord.Interaction,
        instruction: str,
        revision_type: str
    ):

        await interaction.response.defer()

        version = get_version_by_number(
            self.session_id,
            self.displayed_version
        )

        if version is None:

            await interaction.followup.send(
                "I couldn't find this caption version.",
                ephemeral=True
            )

            return

        try:

            caption, response_id = await revise_caption(
                previous_response_id=version.openai_response_id,
                current_caption=version.caption,
                instruction=instruction
            )

            new_version = create_version(
                session_id=self.session_id,
                caption=caption,
                openai_response_id=response_id,
                revision_type=revision_type
            )

            await self.refresh_message(
                interaction,
                new_version.version_number
            )

        except Exception as error:

            print(error)

            await interaction.followup.send(
                "Something went wrong while revising the caption.",
                ephemeral=True
            )


    #
    # Revision controls
    #

    @discord.ui.button(
        label="Regenerate",
        emoji="🔄",
        style=discord.ButtonStyle.secondary,
        row=0
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
""",
            "regenerate"
        )


    @discord.ui.button(
        label="Shorter",
        emoji="✂️",
        style=discord.ButtonStyle.secondary,
        row=0
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
""",
            "shorter"
        )


    @discord.ui.button(
        label="More Casual",
        emoji="😊",
        style=discord.ButtonStyle.secondary,
        row=0
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

It should sound personally written by the owner
of a small local bakery.
""",
            "casual"
        )


    @discord.ui.button(
        label="More Sales-Focused",
        emoji="🛍️",
        style=discord.ButtonStyle.secondary,
        row=0
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

Highlight why someone would want the product and
make important purchasing information easy to notice.

Do not become pushy.
Do not invent ordering instructions.
""",
            "sales"
        )


    @discord.ui.button(
        label="Custom Edit",
        emoji="✏️",
        style=discord.ButtonStyle.primary,
        row=0
    )
    async def custom_edit(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        modal = CustomEditModal(
            self.session_id,
            self.displayed_version
        )

        await interaction.response.send_modal(modal)


    #
    # History controls
    #

    @discord.ui.button(
        label="Previous",
        emoji="◀️",
        style=discord.ButtonStyle.secondary,
        row=1
    )
    async def previous(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.defer()

        previous_number = self.displayed_version - 1

        if previous_number < 1:

            await interaction.followup.send(
                "You're already viewing the first version.",
                ephemeral=True
            )

            return

        await self.refresh_message(
            interaction,
            previous_number
        )


    @discord.ui.button(
        label="Next",
        emoji="▶️",
        style=discord.ButtonStyle.secondary,
        row=1
    )
    async def next_version(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.defer()

        count = get_version_count(self.session_id)

        next_number = self.displayed_version + 1

        if next_number > count:

            await interaction.followup.send(
                "You're already viewing the newest version.",
                ephemeral=True
            )

            return

        await self.refresh_message(
            interaction,
            next_number
        )

    @discord.ui.button(
        label="Finalize",
        emoji="⭐",
        style=discord.ButtonStyle.success,
        row=1
    )
    async def finalize(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.defer(
            ephemeral=True
        )

        version = get_version_by_number(
            self.session_id,
            self.displayed_version
        )

        if version is None:

            await interaction.followup.send(
                "I couldn't find this caption version.",
                ephemeral=True
            )

            return

        try:

            #
            # Mark this version as approved.
            #
            finalize_version(
                self.session_id,
                version.id
            )

            #
            # Post/update it in #ready-to-post.
            #
            await post_finalized_caption(
                bot,
                self.session_id,
                version
            )

            #
            # Refresh original caption message.
            #
            await self.refresh_message(
                interaction,
                version.version_number
            )

            await interaction.followup.send(
                (
                    f"⭐ Version {version.version_number} "
                    "has been approved and sent to "
                    "the ready-to-post channel."
                ),
                ephemeral=True
            )

        except Exception as error:

            print(
                "Finalize error:",
                error
            )

            await interaction.followup.send(
                (
                    "The caption was approved, but I had "
                    "trouble posting it to the "
                    "ready-to-post channel."
                ),
                ephemeral=True
            )

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

        approved_captions = get_approved_captions(
            limit=5
        )

        caption, response_id = await generate_caption(
            user_notes=user_notes,
            image_urls=image_urls,
            approved_captions=approved_captions
        )

        session_id = create_session(
            discord_message_id=message.id,
            discord_channel_id=message.channel.id,
            user_notes=user_notes,
            image_urls=json.dumps(image_urls)
        )

        version = create_version(
            session_id=session_id,
            caption=caption,
            openai_response_id=response_id,
            revision_type="original"
        )

        await status_message.edit(
            content=caption_message(
                caption,
                version_number=1,
                version_count=1
            ),
            view=CaptionControls(
                session_id,
                displayed_version=1
            )
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
