import json
from openai import AsyncOpenAI

from config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    BAKERY_PROFILE
)


client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def generate_caption(
    user_notes: str,
    image_urls: list[str]
) -> tuple[str, str]:

    content = []

    notes = user_notes.strip()

    if not notes:
        notes = (
            "No written product notes were supplied. "
            "Use only information that can reasonably be determined "
            "from the photos."
        )

    content.append({
        "type": "input_text",
        "text": f"""
Create an Instagram caption for the bakery.

BAKER'S NOTES:
{notes}

Carefully examine all attached photos.

Use the photos to understand the product and presentation,
but do not invent details that cannot reasonably be determined.

Follow the bakery profile and return only the final caption.
"""
    })

    for image_url in image_urls:
        content.append({
            "type": "input_image",
            "image_url": image_url
        })

    response = await client.responses.create(
        model=OPENAI_MODEL,
        instructions=BAKERY_PROFILE,
        input=[
            {
                "role": "user",
                "content": content
            }
        ]
    )

    return response.output_text.strip(), response.id


async def revise_caption(
    previous_response_id: str,
    current_caption: str,
    instruction: str
) -> tuple[str, str]:

    prompt = f"""
Revise the Instagram caption you previously created.

CURRENT CAPTION:

{current_caption}

REVISION REQUEST:

{instruction}

Keep the same product/photo context and factual details.

Return ONLY the complete revised Instagram caption.
"""

    response = await client.responses.create(
        model=OPENAI_MODEL,
        previous_response_id=previous_response_id,
        input=prompt
    )

    return response.output_text.strip(), response.id