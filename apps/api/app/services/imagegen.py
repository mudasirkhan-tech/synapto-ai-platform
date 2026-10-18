"""Optional local image generation via a Stable Diffusion WebUI-compatible API (AUTOMATIC1111 / Forge, --api)."""
import base64

import httpx


class ImageGenError(Exception):
    pass


async def txt2img(base_url: str, prompt: str, negative: str, width: int, height: int, steps: int) -> bytes:
    payload = {"prompt": prompt, "negative_prompt": negative, "width": width, "height": height, "steps": steps}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=600.0)) as client:
            res = await client.post(f"{base_url.rstrip('/')}/sdapi/v1/txt2img", json=payload)
            res.raise_for_status()
            data = base64.b64decode(res.json()["images"][0])
    except httpx.ConnectError as exc:
        raise ImageGenError("Cannot reach the image generator. Is Stable Diffusion WebUI running with --api?") from exc
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        raise ImageGenError("The image generator returned an error.") from exc
    if not data.startswith(b"\x89PNG"):
        raise ImageGenError("The image generator returned an unexpected format.")
    return data
