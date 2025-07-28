# SETUP

Would need to download some libraries to be able to use this tool, run the following command in cmd:
> pip install keyboard pyautogui opencv-python numpy pytesseract pillow pygetwindow termcolor

Afterwards make sure to download and install Tesseract OCR from https://github.com/tesseract-ocr/tesseract
Once installed replace the following in the script with your installation path of Tesseract-OCR
located in the config.py file, open with a text editor and search for `tesseract_path = r"D:\Dev\Tesseract-OCR\tesseract.exe"`:
> `tesseract_path = YOUR/PATH/TO/tesseract.exe`

# DEBUGGING
By default the debugging of the tool is set to `False`, could be changed to `True` inside the config.py file.
What it does it logs all characters found on screen into a file in /logs and then it also shows a popup of what was screencaptured at the moment alongside the keywords and so on.

# Usage

To use: open in cmd via 'py curio_tracker.py`

# Appreciate any feedback ^^
