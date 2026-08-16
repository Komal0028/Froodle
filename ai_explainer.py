

import os
import base64
from dotenv import load_dotenv

load_dotenv()


class DrawingExplainer:
    def __init__(self, api_key: str = None, model: str = "gpt-4o"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model

    def is_configured(self) -> bool:
        return bool(self.api_key)

    @staticmethod
    def _encode_image(image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def explain(self, image_path: str) -> str:
        if not self.is_configured():
            return (
                "⚠️ No OpenAI API key found. Set the OPENAI_API_KEY "
                "environment variable to enable 'Explain My Drawing'. "
                "The whiteboard itself works perfectly fine without it."
            )

        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key)
            base64_image = self._encode_image(image_path)

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "This is a hand-drawn sketch made in the air "
                                    "using a webcam and hand tracking. Describe "
                                    "what appears to be drawn, in 2-3 friendly "
                                    "sentences."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{base64_image}"},
                            },
                        ],
                    }
                ],
                max_tokens=200,
            )
            return response.choices[0].message.content.strip()

        except ImportError:
            return (
                "⚠️ The 'openai' package is not installed. Run "
                "'pip install openai' to enable this feature."
            )
        except Exception as error:
            return f"⚠️ Could not reach the AI explanation service: {error}"
