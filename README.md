# Roblox Public Profile Sharing Discord Bot

A Python Discord bot and small website. `/generatelink` creates a unique, short-lived link. A visitor enters a Roblox username, reviews the matching public profile, and explicitly confirms before the details are sent to a configured Discord channel.

This project does **not** collect passwords, authentication cookies, or private credentials.

## Files

- `bot.py` — Discord bot and web server
- `requirements.txt` — Python dependencies
- `terms.html` — Terms of Service page
- `privacy.html` — Privacy Policy page

## Discord setup

1. Create an application at https://discord.com/developers/applications.
2. In **Bot**, create the bot and copy its token. Keep the token secret.
3. Under **OAuth2 → URL Generator**, select scopes `bot` and `applications.commands`.
4. Select bot permissions `View Channels`, `Send Messages`, and `Embed Links`.
5. Use the generated invite URL to add it to your server.
6. Create a private channel for notifications. Give the bot access to view and send messages there.
7. Enable Developer Mode in Discord settings and copy the channel ID.

Privileged Gateway Intents are not required.

## Hosting on Render

Create a Web Service at https://render.com/ and connect this repository.

- Build command: `pip install -r requirements.txt`
- Start command: `python bot.py`

Set these environment variables in the hosting dashboard:

- `DISCORD_TOKEN` — bot token
- `DISCORD_CHANNEL_ID` — numeric ID of the private notification channel
- `BASE_URL` — public HTTPS service URL, without a trailing slash

Render supplies `PORT` automatically; the app reads it.

Use an always-on plan if you need the bot online continuously. Confirm current hosting pricing and terms.

## Publish the legal pages

The two HTML files are included for convenience. Review and customize them so they accurately describe your use of the service.

For GitHub Pages:
1. Push the files to a GitHub repository.
2. Open **Settings → Pages**.
3. Choose **Deploy from a branch**, branch `main`, folder `/(root)`, then save.
4. After publication, test the URLs:
   - `https://YOUR-USERNAME.github.io/YOUR-REPOSITORY/terms.html`
   - `https://YOUR-USERNAME.github.io/YOUR-REPOSITORY/privacy.html`
5. Put the real, working URLs into your Discord application's **General Information** fields.

Do not use example URLs before the pages are published.

## Test

1. Deploy the service and confirm its logs show the web server and bot starting.
2. Run `/generatelink` in your server (requires Manage Server permission).
3. Open the link, look up your own Roblox username, review the result, and confirm sharing.
4. Confirm the embed arrives in the configured private channel.

## Limitations

- Links expire after 30 minutes.
- Link data is in memory, so restarts invalidate outstanding links.
- A link is single-use after sharing; it is intended for voluntary profile sharing, not authentication.
- Public profile lookup depends on Roblox's API being available.
- Review applicable laws and platform terms before deploying.
