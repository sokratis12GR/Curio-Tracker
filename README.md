# Curio Tracker

[![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/sokratis12gr/curio-tracker/total)](https://github.com/sokratis12GR/Curio-Tracker/releases) ![GitHub commit activity](https://img.shields.io/github/commit-activity/m/sokratis12gr/curio-tracker)

This tool allows you to quickly take a screenshot of the **Grand Heist Curio Displays** and save them as reward data, so you can easily analyze the loot you find during your runs.

Each capture has a toast in the top right as a notification which shows the captured items, their value (poe.ninja), rarity and ownership status (PoE Ladder).

**Website:** https://sokratis.space/curio_tracker/

**Curio Stats:** https://sokratis.space/curio_tracker/stats/

<a href='https://ko-fi.com/C0C4DR49' target='_blank'><img height='36' style='border:0px;height:36px;' src='https://storage.ko-fi.com/cdn/kofi5.png?v=6' border='0' alt='Buy Me a Coffee at ko-fi.com' /></a>

## Keybinds (Adjustable)

| Keybind   | Action                                                                           |
| --------- | -------------------------------------------------------------------------------- |
| **F5**    | Captures the current Blueprint layout and item level.                            |
| **F2**    | Captures all Curios currently visible on screen. Duplicate detection is enabled. |
| **F4**    | Opens the region/snippet capture tool. Duplicate captures are allowed.           |
| **F3**    | Closes the tool.                                                                 |
| **Alt+1** | Duplicates the latest saved entry.                                               |
| **Alt+2** | Deletes the latest saved entry (must be loaded in the tool).                     |
| **Alt+3** | Highlights the highest-value Curio from the current wing.                        |
| **Alt+4** | Cycles through the enchantment type on the Blueprint.                            |

**F5** should always be used when entering a Grand Heist. It captures the current layout (i.e. `Prohibited Library`) and item level (i.e. `83`), allowing every reward saved afterwards to be associated with the correct Blueprint.

**F2** captures the entire screen, reads the Curios on it and saves the data as well as adding it to the display tree. It checks for duplicates within the last 60 seconds (adjustable) and ignores them.

**F4** opens the snippet tool, allowing you to capture a selected region. This bypasses the duplicate check and is recommended for capturing Currency/Scarabs.

### Example Usage

<img width="1195" height="751" alt="image" src="https://github.com/user-attachments/assets/510b933c-d900-4d9c-98c5-8f90dfef6329" />

## Toasts

When capturing a Curio, a toast in the top-right of the screen shows the captured item(s), value, rarity and ownership status.

<img width="1919" height="1079" alt="image" src="https://github.com/user-attachments/assets/526b818a-6734-4c2f-9dcf-2851bf292d17" />


## Sorting

<img width="1190" height="743" alt="image" src="https://github.com/user-attachments/assets/b6c5171d-5dda-4a49-8416-8aa7c9e2c22f" />


## Saved Data

Captured data is saved in the `./saved/` folder as either `matches.csv` or `matches.json`, depending on the selected save format.

Both formats can also be loaded directly into Curio Stats for further analysis.

<img width="1069" height="966" alt="image" src="https://github.com/user-attachments/assets/74bd3890-abbe-4ab1-a7d6-f64bf5c63640" />

Example `matches.csv` output:

<img width="1685" height="741" alt="image" src="https://github.com/user-attachments/assets/5daa892a-a293-4281-bebc-f58e04c68420" />

## Curio Stats

You can analyze your captured data using the web-based stats viewer:

https://sokratis.space/curio_tracker/stats/

Load your `matches.csv` or `matches.json` to view statistics such as:

* Reward and Curio probabilities
* Curio tiers and rarest finds
* Wings per Curio tier
* Blueprint and reward type distributions
* Individual reward statistics
* Filtering by league, Blueprint, enchantment and reward type

Your data is processed locally in your browser.

## Light Mode

<img width="1197" height="750" alt="image" src="https://github.com/user-attachments/assets/2b80fead-4a1b-4dfb-8687-dea81e8a2866" />

# Extras

* **Real-time data correction**

  * Delete entries through the tree view by selecting an item and pressing delete.
  * Correct incorrectly captured stack sizes through the UI. Changes save automatically and update the estimated value.
* **PoE Ladder integration** - Shows Curio rarity and ownership information, helping you determine which reward to pick when running a Grand Heist wing. See PoE Ladder's [How do I know which item to pick from a Curio box?](https://poeladder.com/faqs#How_do_I_know_which_item_to_pick_from_a_Curio_box_when_I_run_a_Grand_Heist_Wing) FAQ for more information. Thanks to [halfacandan](https://github.com/halfacandan) and the PoE Ladder community.
* **Economy support** - Uses poe.ninja for estimated item values.
* **Older dataset support** - Automatically converts older save formats into the currently supported format.

# Setup (Quick)

Go to [All Releases](https://github.com/sokratis12GR/Curio-Tracker/releases) and download the latest `Heist Curio Tracker.exe`.

For more information and updates:

https://sokratis.space/curio_tracker/

## Setup for PoE Ladder / poe.ninja

Go to https://www.pathofexile.com/my-account. Under your avatar you will see your profile name and tag. Use the full `name#tag` to retrieve the correct PoE Ladder data.

<img width="218" height="172" alt="image" src="https://github.com/user-attachments/assets/e9400d62-612e-4ef4-ab00-6c9711dacbee" />

Open the tool -> File -> Settings -> PoE Profile: i.e. `sokratis12GR#6608` | Data League: your current league -> **Fetch Data** -> Restart the app.

# Video on how to use

https://youtu.be/7eR9DzgUWNk

Older version:

https://youtu.be/BW5GyrDTVss

# Troubleshooting

If the app crashes or shows an error, please create an issue at [Create Issue](https://github.com/sokratis12GR/Curio-Tracker/issues/new).

* Provide a screenshot or detailed explanation of the issue.
* If something is not occurring correctly, provide the log file located at:
  `%appdata%/HeistCurioTracker/logs/tracker.log`

***Appreciate any feedback ^^***
