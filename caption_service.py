import json
from openai import AsyncOpenAI

from config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_REASONING_EFFORT,
    BAKERY_PROFILE
)


client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def generate_caption(
    user_notes: str,
    image_urls: list[str],
    approved_captions: list[str] | None = None
) -> tuple[str, str]:

    content = []

    notes = user_notes.strip()

    if not notes:
        notes = (
            "No written product notes were supplied. "
            "Use only information that can reasonably be determined "
            "from the photos."
        )

    if approved_captions:

        examples = "\n\n".join(
            f"EXAMPLE {index + 1}:\n{caption}"
            for index, caption
            in enumerate(approved_captions)
        )

        style_examples = f"""
    PREVIOUSLY APPROVED CAPTIONS:

    The bakery owner previously selected the captions below as
    captions they liked and approved.

    Use them as examples of the owner's preferred writing style,
    tone, length, formatting, emoji usage, and overall voice.

    Do NOT copy phrases or sentences from these examples.
    Do NOT assume product details from these examples apply to
    the current product.

    {examples}
    """

    else:

        style_examples = """
    There are no previously approved caption examples yet.
    Follow the bakery brand profile.
    """

    content.append({
        "type": "input_text",
        "text": f"""
    Create a polished Instagram caption for Cozy Cakes & Bakes.

    BAKER'S NOTES:
    {notes}

    {style_examples}

    Carefully analyze ALL attached photos before writing the caption.

    Consider:
    - What baked good is shown
    - Its texture, appearance, filling, topping, and presentation
    - Which visual qualities would make it appealing to a customer
    - What information from the baker's notes is most important
    - What would make a strong but natural opening line
    - How to make the caption sound personally written by a small
    home baker rather than generated marketing copy
    - Whether emojis improve the caption or feel unnecessary
    - Which hashtags are actually relevant

    The previously approved captions are STYLE REFERENCES ONLY.

    Never copy product details, prices, flavors, ingredients,
    or other factual information from previous captions.

    For factual information about the current product, rely ONLY
    on the current baker's notes and attached photos.

    Do not invent ingredients, flavors, prices, ordering methods,
    or product characteristics that aren't supported by the photos
    or baker's notes.

    Internally consider multiple possible caption approaches and
    choose the strongest one.

    Return ONLY the finished Instagram caption.
    Do not show your analysis, alternatives, or reasoning.
    """
    })

    for image_url in image_urls:
        content.append({
            "type": "input_image",
            "image_url": image_url
        })

    response = await client.responses.create(
        model=OPENAI_MODEL,
        reasoning={
            "effort": OPENAI_REASONING_EFFORT
        },
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
        reasoning={
            "effort": OPENAI_REASONING_EFFORT
        },
        previous_response_id=previous_response_id,
        input=prompt
    )

    return response.output_text.strip(), response.id