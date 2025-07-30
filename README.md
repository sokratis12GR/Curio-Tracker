# SETUP

This program runs on python, you will need to have it on your system, you can get it via the following link: https://www.python.org/downloads/

**Important**: During installation, check the box `"Add Python to PATH"`

Would need to download some libraries to be able to use this tool, run the following command in cmd:
> pip install keyboard pyautogui opencv-python numpy pytesseract pillow pygetwindow termcolor

Afterwards make sure to download and install Tesseract OCR from https://github.com/tesseract-ocr/tesseract

Once installed replace the following in the script with your installation path of Tesseract-OCR
located in the config.py file, open with a text editor and search for `tesseract_path = r"D:\Dev\Tesseract-OCR\tesseract.exe"`:
> `tesseract_path = r"YOUR/PATH/TO/tesseract.exe"`

## CONFIG (TL;DR)
Update the following entries

`poe_league = "3.26"` to the current league

`poe_user = "sokratis12GR"` to the player that's running the blueprints

### Keybinds
If you dislike the current set of keys used, you can change them here just type in the key you want to use instead of the 'f2-5' keys
```
capture_key = "f2"
exit_key = "f3"
snippet_key = "f4"
layout_capture_key = "f5"
```

# DEBUGGING
By default the debugging of the tool is set to `False`, could be changed to `True` inside the config.py file.
What it does it logs all characters found on screen into a file in /logs and then it also shows a popup of what was screencaptured at the moment alongside the keywords and so on.

# Usage

To use: open in cmd via `py curio_tracker.py`

# Appreciate any feedback ^^
