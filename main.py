import secrets

import discord


class Client(discord.Client):
    async def on_ready(self):
        print(f'{self.user} has logged in!')

    async def on_message(self, message):
        # check for event URLs in the message
        event = extract_event_from_url(message.content)
        if event:
            await message.channel.send(f"Found event: {event['name']} at {event['time']}")
        else:
            await message.channel.send("No event found in the provided URL.")

intents = discord.Intents.default()
intents.message_content = True

client = Client(intents=intents)
client.run(secrets.DISCORD_BOT_TOKEN)