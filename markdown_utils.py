import re
import webbrowser


def render_markdown_to_textbox(textbox, markdown_text):
    textbox.configure(state="normal")
    textbox.delete("1.0", "end")

    if not markdown_text.strip():
        textbox.insert(
            "end",
            "No release notes were provided."
        )
        textbox.configure(state="disabled")
        return

    textbox.tag_config(
        "h1",
        spacing1=10,
        spacing3=6
    )

    textbox.tag_config(
        "h2",
        spacing1=8,
        spacing3=5
    )

    textbox.tag_config(
        "h3",
        spacing1=6,
        spacing3=4
    )

    textbox.tag_config(
        "code",
        lmargin1=12,
        lmargin2=12
    )

    lines = markdown_text.splitlines()

    in_code_block = False

    for raw_line in lines:
        line = raw_line.rstrip()

        # -------------------------
        # Fenced code block
        # -------------------------
        if line.startswith("```"):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            textbox.insert(
                "end",
                "    " + line + "\n",
                "code"
            )
            continue

        # -------------------------
        # Headings
        # -------------------------
        if line.startswith("### "):
            textbox.insert(
                "end",
                f"▸ {line[4:]}\n",
                "h3"
            )
            continue

        if line.startswith("## "):
            textbox.insert(
                "end",
                f"\n{line[3:].upper()}\n",
                "h2"
            )
            continue

        if line.startswith("# "):
            textbox.insert(
                "end",
                f"\n{line[2:].upper()}\n",
                "h1"
            )
            continue

        # -------------------------
        # Horizontal rules
        # -------------------------
        if line.strip() in ("---", "***", "___"):
            textbox.insert(
                "end",
                "────────────────────────────\n"
            )
            continue

        # -------------------------
        # Bullets
        # -------------------------
        if line.startswith("- ") or line.startswith("* "):
            textbox.insert(
                "end",
                "• "
            )

            insert_inline_markdown(
                textbox,
                line[2:]
            )

            textbox.insert(
                "end",
                "\n"
            )

            continue

        # -------------------------
        # Numbered list
        # -------------------------
        match = re.match(
            r"^(\d+)\.\s+(.*)$",
            line
        )

        if match:
            textbox.insert(
                "end",
                f"{match.group(1)}. "
            )

            insert_inline_markdown(
                textbox,
                match.group(2)
            )

            textbox.insert(
                "end",
                "\n"
            )

            continue

        # -------------------------
        # Blockquote
        # -------------------------
        if line.startswith("> "):
            textbox.insert(
                "end",
                "│ "
            )

            insert_inline_markdown(
                textbox,
                line[2:]
            )

            textbox.insert(
                "end",
                "\n"
            )

            continue

        # -------------------------
        # Normal text
        # -------------------------
        insert_inline_markdown(
            textbox,
            line
        )

        textbox.insert(
            "end",
            "\n"
        )

    textbox.configure(state="disabled")


def insert_inline_markdown(textbox, text):
    pattern = re.compile(
        r"(\*\*.*?\*\*|`.*?`|\[.*?\]\(.*?\))"
    )

    pos = 0

    for match in pattern.finditer(text):
        if match.start() > pos:
            textbox.insert(
                "end",
                text[pos:match.start()]
            )

        token = match.group(0)

        # -------------------------
        # Bold
        # -------------------------
        if token.startswith("**"):
            textbox.insert(
                "end",
                token[2:-2]
            )

        # -------------------------
        # Inline code
        # -------------------------
        elif token.startswith("`"):
            textbox.insert(
                "end",
                f"‹{token[1:-1]}›"
            )

        # -------------------------
        # Markdown link
        # -------------------------
        elif token.startswith("["):
            link_match = re.match(
                r"\[(.*?)\]\((.*?)\)",
                token
            )

            if link_match:
                label = link_match.group(1)
                url = link_match.group(2)

                tag_name = (
                    f"link_"
                    f"{str(textbox.index('end')).replace('.', '_')}_"
                    f"{match.start()}"
                )

                textbox.insert(
                    "end",
                    label,
                    tag_name
                )

                textbox.tag_config(
                    tag_name,
                    underline=True
                )

                textbox.tag_bind(
                    tag_name,
                    "<Button-1>",
                    lambda e, u=url: webbrowser.open_new(u)
                )

                textbox.tag_bind(
                    tag_name,
                    "<Enter>",
                    lambda e: textbox.configure(
                        cursor="hand2"
                    )
                )

                textbox.tag_bind(
                    tag_name,
                    "<Leave>",
                    lambda e: textbox.configure(
                        cursor=""
                    )
                )

        pos = match.end()

    if pos < len(text):
        textbox.insert(
            "end",
            text[pos:]
        )
