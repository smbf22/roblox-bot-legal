import os
import time
import secrets
import html
from datetime import datetime, timezone

import aiohttp
import discord
from discord import app_commands
from aiohttp import web

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
DISCORD_CHANNEL_ID = int(os.environ["DISCORD_CHANNEL_ID"])
BASE_URL = os.environ["BASE_URL"].rstrip("/")
PORT = int(os.environ.get("PORT", "8080"))
LINK_LIFETIME_SECONDS = 30 * 60

# In-memory, one-time links. Restarting the service invalidates outstanding links.
links = {}


def page(content: str, title: str = "Roblox Profile Sharing", status: int = 200):
    return web.Response(
        text=f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 560px; margin: 40px auto;
padding: 0 18px; line-height: 1.6; }}
input, button {{ box-sizing: border-box; max-width: 100%; padding: 11px; margin: 8px 0; }}
input[type=text] {{ width: 100%; }}
button {{ cursor: pointer; }}
.notice {{ background: #f2f2f2; padding: 12px; border-radius: 8px; }}
</style>
</head>
<body><main><h1>{html.escape(title)}</h1>{content}</main></body>
</html>""",
        content_type="text/html",
        status=status,
    )


def error_page(message: str, status: int = 400):
    return page(f"<p>{html.escape(message)}</p>", "Request error", status)


def get_link(token: str):
    record = links.get(token)
    if not record:
        return None
    if time.time() > record["expires"]:
        links.pop(token, None)
        return None
    return record


async def lookup_roblox_user(username: str):
    url = "https://users.roblox.com/v1/usernames/users"
    payload = {"usernames": [username], "excludeBannedUsers": False}
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, json=payload) as response:
            if response.status != 200:
                raise RuntimeError("Roblox lookup failed")
            data = await response.json()

    results = data.get("data", [])
    if not results:
        return None
    user = results[0]
    return {
        "id": int(user["id"]),
        "username": str(user["name"]),
        "display_name": str(user["displayName"]),
    }


async def home(request):
    return page(
        "<p>This site lets you voluntarily share your public Roblox profile "
        "with a Discord server.</p><p>Open the unique link provided by the "
        "bot to continue. No Roblox password or login is requested.</p>"
    )


async def share_page(request):
    token = request.match_info["token"]
    if not get_link(token):
        return error_page("This link is invalid or has expired.", 404)

    content = """
<p>Enter your Roblox username to find your public profile. You do not need
to sign in, and you must never enter a password or authentication cookie.</p>
<form method="post">
<input type="hidden" name="action" value="lookup">
<label for="username">Roblox username</label>
<input id="username" name="username" type="text" maxlength="20"
       autocomplete="off" required>
<button type="submit">Find profile</button>
</form>
<p class="notice">Your profile details will not be sent to Discord unless
you review the result and explicitly confirm sharing.</p>
"""
    return page(content)


async def submit_page(request):
    token = request.match_info["token"]
    record = get_link(token)
    if not record:
        return error_page("This link is invalid or has expired.", 404)

    form = await request.post()
    action = str(form.get("action", ""))

    if action == "lookup":
        username = str(form.get("username", "")).strip()
        if not username or len(username) > 20:
            return error_page("Enter a valid Roblox username.")

        try:
            profile = await lookup_roblox_user(username)
        except (aiohttp.ClientError, TimeoutError, RuntimeError, ValueError, KeyError):
            return error_page("Roblox could not be reached. Please try again.", 502)

        if profile is None:
            return error_page("No matching Roblox user was found.")

        # The visitor reviews the exact profile before choosing to share it.
        record["candidate"] = profile
        display_name = html.escape(profile["display_name"])
        profile_username = html.escape(profile["username"])
        user_id = profile["id"]
        profile_url = f"https://www.roblox.com/users/{user_id}/profile"

        content = f"""
<p>Review this profile before sharing it:</p>
<ul>
<li><strong>Display name:</strong> {display_name}</li>
<li><strong>Username:</strong> {profile_username}</li>
<li><strong>User ID:</strong> {user_id}</li>
</ul>
<p><a href="{profile_url}" rel="noopener noreferrer" target="_blank">
View Roblox profile</a></p>
<p class="notice">If you confirm, these public profile details and the
consent time will be sent to the configured Discord channel.</p>
<form method="post">
<input type="hidden" name="action" value="share">
<label><input type="checkbox" name="consent" value="yes" required>
I agree to share this public profile with the Discord server.</label><br>
<button type="submit">Confirm and share</button>
</form>
"""
        return page(content, "Confirm profile sharing")

    if action == "share":
        if form.get("consent") != "yes":
            return error_page("Consent is required before sharing.")

        profile = record.get("candidate")
        if not profile:
            return error_page("Please look up a profile first.")

        # Consume before sending to prevent repeat submissions.
        links.pop(token, None)
        consent_time = datetime.now(timezone.utc)
        profile_url = f"https://www.roblox.com/users/{profile['id']}/profile"

        try:
            channel = bot.get_channel(DISCORD_CHANNEL_ID)
            if channel is None:
                channel = await bot.fetch_channel(DISCORD_CHANNEL_ID)

            embed = discord.Embed(
                title="Roblox profile shared with consent",
                url=profile_url,
                color=discord.Color.blurple(),
                timestamp=consent_time,
                description="A visitor explicitly confirmed sharing these public profile details.",
            )
            embed.add_field(name="Username", value=profile["username"], inline=True)
            embed.add_field(name="Display name", value=profile["display_name"], inline=True)
            embed.add_field(name="Roblox user ID", value=str(profile["id"]), inline=True)
            embed.add_field(
                name="Consent recorded (UTC)",
                value=consent_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
                inline=False,
            )
            embed.set_footer(text="Public profile information only")
            await channel.send(embed=embed)
        except (discord.DiscordException, OSError):
            return error_page(
                "The share could not be delivered. Please contact the server owner.",
                503,
            )

        return page(
            "<p>Your public profile was shared successfully.</p>"
            "<p>You can close this page now.</p>",
            "Profile shared",
        )

    return error_page("Unknown action.")


class ProfileBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)
        self.runner = None

    async def setup_hook(self):
        await self.tree.sync()
        app = web.Application(client_max_size=16 * 1024)
        app.router.add_get("/", home)
        app.router.add_get("/s/{token}", share_page)
        app.router.add_post("/s/{token}", submit_page)

        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "0.0.0.0", PORT)
        await site.start()
        print(f"Web server listening on port {PORT}")

    async def close(self):
        if self.runner is not None:
            await self.runner.cleanup()
        await super().close()


bot = ProfileBot()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


@bot.tree.command(
    name="generatelink",
    description="Generate a one-time Roblox profile-sharing link",
)
@app_commands.default_permissions(manage_guild=True)
@app_commands.checks.has_permissions(manage_guild=True)
async def generate_link(interaction: discord.Interaction):
    token = secrets.token_urlsafe(24)
    links[token] = {
        "expires": time.time() + LINK_LIFETIME_SECONDS,
        "candidate": None,
    }
    url = f"{BASE_URL}/s/{token}"
    await interaction.response.send_message(
        f"Voluntary Roblox profile-sharing link (expires in 30 minutes):\n{url}",
        ephemeral=True,
    )


@generate_link.error
async def generate_link_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
):
    if isinstance(error, app_commands.MissingPermissions):
        message = "You need Manage Server permission to generate links."
    else:
        message = "Something went wrong. Check the bot's hosting logs."
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
