"""HTML parser."""

from bs4 import BeautifulSoup
from typing import Any, Dict

from .base import BaseParser


class HTMLParser(BaseParser):

    @property
    def supported_extensions(self) -> list[str]:
        return [".html", ".htm"]

    async def parse(self, file_path: str) -> Dict[str, Any]:
        with open(file_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, "html.parser")

        # Remove script/style tags
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        # Get title
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""

        # Extract main text
        text = soup.get_text(separator="\n", strip=True)

        # Clean up excessive whitespace
        lines = [line.strip() for line in text.split("\n")]
        lines = [line for line in lines if line]
        clean_text = "\n".join(lines)

        return {
            "text": clean_text,
            "metadata": {"title": title},
            "tables": [],
        }
