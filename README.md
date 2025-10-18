# Curio Tracker

![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/sokratis12gr/curio-tracker/total)
![GitHub commit activity](https://img.shields.io/github/commit-activity/m/sokratis12gr/curio-tracker)

This tool allows you to quickly take a screenshot of the **grand heist curio displays** and save them as reward data so
that you can quickly analyze the kind of loot you found during your runs.

Each capture has a toast in the top right as a notification which shows you the captured items, their value (poe.ninja), rarity and ownership status (poeladder).

## Keybinds (Adjustable):
F5 - Captures the current layout (i.e layout: Prohibited Library, ilvl: 83), should always start with this when entering
the Grand Heist as it will make every reward saved bound to that layout and ilvl.

F2 - Screen capture the entire screen, takes a screenshot of the current screen, reads the text on it and save the
data in a .csv output as well as adding it on the display tree, checks for duplicates (in the last 60 seconds - adjustable) and doesn't save them in the file/tool.

F4 - Enter the snippet tool, allows for selection capture of a region, bypasses the duplicate check (allows for duplicate captures) - Recommended for capturing currency/scarabs.

F3 - Closes the tool.

Alt+1 - Duplicates the latest saved entry

Alt+2 - Deletes the latest saved entry (must be loaded in the tool)

### Example Usages of the tool:

<img width="1917" height="1030" alt="image" src="https://github.com/user-attachments/assets/e6bfbebd-131d-4883-9175-028e3aca3895" />

## Toasts when capturing a curio that showcase the captured item(s) in the top right of the screen:

<img width="1919" height="1079" alt="image" src="https://github.com/user-attachments/assets/34404e62-c6bf-48f1-9fbf-670ec2246cf0" />

## Sorting

<img width="1917" height="1030" alt="image" src="https://github.com/user-attachments/assets/2a69cdb0-8531-4ec3-88a8-734b5ce8e59d" />

It will save the data in a `.csv` file (`saves/matches.csv`) like the following (supported by google sheets, excel and
so on)
<img width="1069" height="966" alt="image" src="https://github.com/user-attachments/assets/74bd3890-abbe-4ab1-a7d6-f64bf5c63640" />

Example `matches.csv` output:
<img width="1685" height="741" alt="image" src="https://github.com/user-attachments/assets/5daa892a-a293-4281-bebc-f58e04c68420" />

## Light Mode

<img width="1912" height="1028" alt="image" src="https://github.com/user-attachments/assets/a1de9e14-d7b5-4c97-b5b1-81c3baec00cd" />

# Extras

- Real-time data correction:
    - Allows deletion of entries via the tree view, just select the item and press the delete btn.
    - Allows correcting stack size in case an incorrect value was captured via the UI, it saves automatically and
      updates the estimated value.
- PoE ladder integration with the help of thanks to the help of [halfacandan](https://github.com/halfacandan) and the poeladder community
- Economy Support (Estimated Value) - Pulls from poe.ninja the item's estimated value
- Support for older data sets, automatically converts the old matches.csv versions into an up-to-date supported version.

# SETUP (Quick)

Go to releases [All Releases](https://github.com/sokratis12GR/Curio-Tracker/releases) -> Download the latest `Heist Curio Tracker.exe`.

## Setup for PoELadder / poe.ninja:
To setup the poeladder function you need to go to https://www.pathofexile.com/my-account, from there under your avatar you will see your profile name#tag, you will need to use that to get the correct poeladder data.

<img width="218" height="172" alt="image" src="https://github.com/user-attachments/assets/e9400d62-612e-4ef4-ab00-6c9711dacbee" />


Open the tool -> File -> Settings -> PoE Profile: i.e `sokratis12GR#6608` | Data League: `Mercenaries` -> "Fetch Data"/Restart the app.

# Video on how to use:

https://youtu.be/BW5GyrDTVss

# Troubleshooting

In case the app crashes or has an error image, please do not hesitate to create an issue ticket
at [Create Issue](https://github.com/sokratis12GR/Curio-Tracker/issues/new).

- Provide a screenshot, or a detailed explanation of the issue
- In case of something not occuring please provide a the log file located inside
  `%appdata%/HeistCurioTracker/logs/tracker.log`


***Appreciate any feedback ^^***










