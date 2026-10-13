# CS2 Spending Tracker

Find out what you have really spent on Counter-Strike — keys, cases, skins, stickers, passes — and what you got back from selling. The tracker reads history you copy from Steam and from marketplaces, then builds a single report page you open in your browser.

It runs entirely on your own computer. Nothing is uploaded, and there is nothing to install besides Python.

Free and open source under the [MIT License](LICENSE).

---

## Safety at a glance

- **No internet access in the code.** The script has no networking code at all. The only time anything goes online is when *you* answer **Y** to "Open that page in your browser now?" — your own browser opens a Steam page.
- **Reads only what you pick, writes only one file.** It reads the files you select (or text you paste) and writes exactly one file: the HTML report, where you choose to save it.
- **The report cannot "phone home".** It contains a built-in security policy that blocks the page from loading or sending anything over the network.
- **Check it yourself.** Open `CS2 Spending Tracker - Github.py` in Notepad (or any text editor) and press Ctrl+F for `socket`, `requests`, `urllib`, `subprocess`, `exec`, `eval`. The only place you will find them is the safety notice at the top. The full list of modules it uses is printed in that notice too, and all of them come with Python.

---

## Requirements

- **Python 3.9 or newer** from [python.org](https://www.python.org/downloads/). On Windows, tick **"Add python.exe to PATH"** during setup.
- Run it in a real terminal window (Command Prompt, PowerShell, Windows Terminal, the VS Code terminal, or the Mac/Linux Terminal). The animated prompts and file picker need a terminal.

---

## Quick start

1. Download `CS2 Spending Tracker - Github.py` into a folder of your choice.
2. Open a terminal in that folder and run:
   ```
   python "CS2 Spending Tracker - Github.py"
   ```
3. Read the safety notice and press any key.
4. Keep or change the default key price ($2.49 USD — only used by the optional "Estimate missing keys" feature).
5. Work through the three steps. **Every step offers the same choices:**

   | Option | What it does |
   |---|---|
   | 1 | Load a saved file (a file window opens) |
   | 2 | Paste the text directly (finish with a line that says `END`) |
   | 3 | Skip this step |
   | 4 | Start over from Step 1 |
   | 5 | Abort (closes the program, nothing is saved) |

6. At the end, choose **1 Save the HTML report**, pick where to save it, and open it in your browser.

If you skip every step, the program prints `nothing has been selected.` and ends.

---

## Step 1 — Steam purchase history

This holds your key purchases, passes and other in-game buys.

1. Go to https://store.steampowered.com/account/history/ (you must be logged in).
2. Click **Load more transactions** until the list stops growing.
3. Press **Ctrl+A**, then **Ctrl+C**.
4. Paste into Notepad and save it with any name, for example `Steam purchases 1.txt`.
5. In the tracker, choose **1** and select that file.

Tip: loading this step also lets the tracker give **exact dates** to your Steam Market history in Step 2.

## Step 2 — Steam Market history

1. Make sure you are logged in to Steam in your browser.
2. Open https://steamcommunity.com/market/myhistory/render/?query=&l=english&count=500&start=0 — the page looks like a wall of text, that is correct.
3. Press **Ctrl+S** and save it with any name, for example `Market 1.txt`.
4. In the tracker, choose **1** and select it. If you have more than 500 market transactions, the tracker lists the next pages to save, already named for you: `Market 2.txt`, `Market 3.txt`, …

## Step 3 — Marketplaces

Various marketplaces may have different pages for all transactions, all orders, etc. Try to find the page that has an itemized breakdown of each purchase. You may need to paste two different data sets, one for purchases, one for items sold.

Tips for finding the right page:

- Look in your account area for pages called something like **Orders**, **Transactions**, **History** or **Trades**.
- The best page lists **each item with its own price**, not just one total per order.
- Some sites show purchases and sales on **separate tabs**. Copy each tab separately; the tracker asks which one you pasted.
- If the site offers a **CSV export**, use it — it is the most accurate option.
- Cancelled or open orders are skipped automatically.
- Each marketplace you add is named `Marketplace 1`, `Marketplace 2`, … unless you type your own name.

If nothing on a site works, you can type a simple text file yourself, one transaction per line:

```
Mar 3, 2024 | Example Case | -$1.25      (minus = you spent money)
Apr 2, 2024 | AK-47 | Sample Skin | +$14.00   (plus = you received money)
Mar 30, 2024 | 2x Example Case | -$2.10   (2x = two items for that total)
```

Press **Enter** at the Step 3 menu to finalize your data or skip this step entirely.

---

## Try it first with the example files

The **`examples`** folder holds completely made-up data (no real account, person, place or purchase). Run the script as usual and pick these files when the file window opens:

| File | Use it in |
|---|---|
| `Steam purchases 1.txt` | Step 1, option 1 |
| `Market 1.txt`, `Market 2.txt` | Step 2, option 1 (load both) |
| `Marketplace 1.txt`, `Marketplace 2.txt` | Step 3, option 1 (load both, then press Enter) |

You should see "Dates verified against your Steam purchase history (512 of 512 rows)" in Step 2.

---

## Reading the report

- **Summary** — plain-English answers (did you come out ahead, biggest purchase and sale, busiest year/month/day, last 12 months, trend), totals by category with a click-to-expand list of items, by source and by year.
- **Items Sold / Items Purchased** — every item with quantity, total and dates, plus a search box that shows a live count and exact total.
- **Containers** — money spent on each case and on its keys.
- **All Transactions** — every row, searchable (try an item name, `2024-03`, `Sale` or `Key`).
- **Reconciliation** — profit or loss for each data source, and a check for the same transaction showing up in two sources.

Rows marked `*` have an estimated year; rows marked ⚠ are estimated keys.

---

## Safe file handling and data hygiene

- Keep your history files and reports in **one private folder** on your own computer.
- **Never upload them** to GitHub, forums, Discord or public cloud folders. They contain your full purchase history.
- **Delete the copied files when you are done** if you do not need them again.
- The report is a normal file: anyone you send it to can see everything in it.
- Before sharing a screenshot, **hide your account name** and anything else that identifies you.
- When asking for help, **never post your real files**. Describe the problem, or rebuild a few lines using the example format with made-up items and prices.
- Only download the script from the official repository's Releases page, and compare its checksum (below).

---

## Verify your download

Each release lists a SHA-256 checksum. Compare it with yours:

- **Windows:** `certutil -hashfile "CS2 Spending Tracker - Github.py" SHA256`
- **Mac / Linux:** `shasum -a 256 "CS2 Spending Tracker - Github.py"`

If the numbers differ, do not run the file.

---

## Limitations

- Market dates are exact when Step 1 is loaded; otherwise years are estimated (marked `*`).
- Some marketplaces only show relative dates ("9 months ago"), so those dates are approximate.
- "Estimate missing keys" is a guess: it assumes every case you bought and did not sell was opened.
- Amounts are shown in the currency found in your Steam data; different currencies are not converted.

---

## Support

- [Steam Support](https://help.steampowered.com/)
- [Anthropic Support](https://support.claude.com/)
- [GitHub Support](https://support.github.com/)

---

## Legal

Any marketplace name information has been removed to ensure this does not go against any TOS for any marketplaces for public usage as the author does not condone script injection or misuse of AI scripts.

This project is not affiliated with or endorsed by Valve Corporation. Counter-Strike and Steam are trademarks of Valve Corporation. This application was created with help from Claude AI.

**Please always review the code you plan on using. The author does not assume liability in the event your data is mishandled or shared in a way that compromises your account. Your spending history and account data can say a lot about you as a human being.**

## License

Released under the [MIT License](LICENSE). You may use, copy, change and share it freely; it comes with no warranty.
