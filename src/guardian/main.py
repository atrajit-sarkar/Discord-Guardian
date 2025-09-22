import asyncio
import logging
import os
from typing import Optional

import discord
from discord import app_commands

from .config import get_config
from .roles import role_for_hearts, ordered_roles, role_color
from .gemini_client import analyze_message
from .firestore_store import Store


def setup_logging(level: str):
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


class GuardianClient(discord.Client):
    def __init__(self, *, intents: discord.Intents, store: Store, config):
        super().__init__(intents=intents)
        self.store = store
        self.config = config
        self.logger = logging.getLogger("guardian")
        self.tree = app_commands.CommandTree(self)
        # Build quick lookup for special users and special role IDs
        specials = (self.config.special_users or [])
        self._special_ids = set(str(u.get("id")) for u in specials if u.get("id"))
        self._special_role_ids = set(str(u.get("roleId")) for u in specials if u.get("roleId"))

    def is_admin(self, member: discord.Member) -> bool:
        # Admin if they have Administrator permission OR any of the configured admin roles
        if member.guild_permissions.administrator:
            return True
        ids = set(self.config.admin_role_ids or [])
        if not ids:
            return False
        for r in member.roles:
            if str(r.id) in ids:
                return True
        return False

    async def on_ready(self):
        self.logger.info(f"Logged in as {self.user} (id={self.user.id})")
        # Ensure roles exist on all guilds where the bot is present
        for guild in self.guilds:
            # Restrict to allowed guild if configured
            if self.config.allowed_guild_id and str(guild.id) != str(self.config.allowed_guild_id):
                self.logger.info(f"Skipping guild '{guild.name}' ({guild.id}) due to ALLOWED_GUILD_ID restriction")
                continue
            await self.ensure_roles(guild)
            # Apply special user startup hearts and roles
            await self.apply_specials_in_guild(guild)
            # Sync slash commands per guild for faster availability
            try:
                await self.tree.sync(guild=guild)
            except Exception as e:
                self.logger.warning(f"Slash command sync failed for {guild.name}: {e}")
        self.logger.info("Guardian is ready.")

    def is_special(self, member: discord.Member) -> bool:
        if str(member.id) in self._special_ids:
            return True
        if self._special_role_ids:
            for r in member.roles:
                if str(r.id) in self._special_role_ids:
                    return True
        return False

    async def apply_specials_in_guild(self, guild: discord.Guild):
        # Ensure minimum hearts and optional roles for special users and members with special roles
        cfg = self.config
        specials = cfg.special_users or []
        if not specials:
            return
        # Build per-rule application: either user id or roleId
        for su in specials:
            uid = str(su.get("id") or "").strip()
            rid = str(su.get("roleId") or "").strip()
            targets: list[discord.Member] = []
            if uid:
                try:
                    member = guild.get_member(int(uid)) or await guild.fetch_member(int(uid))
                    if member:
                        targets.append(member)
                except Exception:
                    pass
            elif rid:
                # Collect all members with role rid
                role_obj = guild.get_role(int(rid))
                if role_obj:
                    targets = list(role_obj.members)
            # Apply settings for targets
            for member in targets:
                key = f"{guild.id}:{member.id}"
                self.store.get_or_create_user(key, str(member), cfg.heart_start, guild_id=str(guild.id))
                if isinstance(su.get("hearts"), (int, float)):
                    try:
                        self.store.ensure_min_hearts(key, int(su["hearts"]))
                    except Exception as e:
                        self.logger.debug(f"Failed ensure_min_hearts for {member.id}: {e}")
                roles = su.get("roles")
                if isinstance(roles, list) and roles:
                    await self.assign_configured_roles(member, roles)

    async def assign_configured_roles(self, member: discord.Member, roles: list):
        guild = member.guild
        # roles can be IDs or names
        to_add: list[discord.Role] = []
        existing_by_name = {r.name: r for r in guild.roles}
        existing_by_id = {str(r.id): r for r in guild.roles}
        for r in roles:
            r_str = str(r)
            role_obj = existing_by_id.get(r_str) or existing_by_name.get(r_str)
            if role_obj:
                to_add.append(role_obj)
        if not to_add:
            return
        try:
            await member.add_roles(*to_add, reason="Guardian special user role assignment")
        except Exception as e:
            self.logger.debug(f"Failed to assign special roles to {member.display_name}: {e}")

    async def ensure_roles(self, guild: discord.Guild):
        needed = set(ordered_roles())
        existing = {r.name: r for r in guild.roles}
        for name in ordered_roles():
            if name not in existing:
                try:
                    # Create role using color from roles.json if available
                    color_hex = role_color(name)
                    colour = discord.Color(value=color_hex) if isinstance(color_hex, int) else discord.Color.purple()
                    await guild.create_role(name=name, colour=colour, reason="Guardian auto-setup")
                    self.logger.info(f"Created role '{name}' in guild '{guild.name}'")
                except discord.Forbidden:
                    self.logger.warning(f"Missing permissions to create role '{name}' in '{guild.name}'")
                except Exception as e:
                    self.logger.error(f"Error creating role '{name}' in '{guild.name}': {e}")

    async def send_reward_dm(
        self,
        user: discord.abc.User,
        guild: discord.Guild,
        amount: int,
        reason: str,
        hearts_after: int | None = None,
        channel: discord.abc.GuildChannel | None = None,
        jump_url: str | None = None,
    ):
        # Compose a rich embed DM with channel and message links
        try:
            title = f"You earned +{amount}❤️"
            desc_parts = [f"Reason: `{reason}`"]
            if channel is not None:
                # Channel mention (user can click it if they share the guild)
                desc_parts.append(f"Channel: <#{channel.id}>")
            if jump_url:
                desc_parts.append(f"[Open message]({jump_url})")
            description = "\n".join(desc_parts)

            embed = discord.Embed(title=title, description=description, color=discord.Color.green())
            embed.add_field(name="Server", value=f"**{guild.name}**", inline=True)
            if hearts_after is not None:
                embed.add_field(name="New total", value=f"**{hearts_after}❤️**", inline=True)
            embed.set_footer(text="Discord Guardian • Keep it up ✨")
            try:
                if guild.icon:
                    embed.set_thumbnail(url=guild.icon.url)  # type: ignore[attr-defined]
            except Exception:
                pass

            await user.send(embed=embed)
        except discord.Forbidden:
            # User has DMs closed; ignore silently
            self.logger.debug(f"Cannot DM {getattr(user, 'name', 'user')} — DMs disabled")
        except Exception as e:
            self.logger.debug(f"Failed to DM reward notice: {e}")

    async def assign_role_for_hearts(self, member: discord.Member, hearts: int) -> str | None:
        target_name = role_for_hearts(hearts)
        guild = member.guild
        # Find roles
        existing = {r.name: r for r in guild.roles}
        target_role = existing.get(target_name)
        if not target_role:
            await self.ensure_roles(guild)
            target_role = discord.utils.get(guild.roles, name=target_name)
        if not target_role:
            self.logger.warning(f"Target role '{target_name}' still missing in guild '{guild.name}'")
            return None
        # Remove other roles from the set
        known_names = set(ordered_roles())
        roles_to_remove = [r for r in member.roles if r.name in known_names and r != target_role]
        try:
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason="Guardian role update")
            if target_role not in member.roles:
                await member.add_roles(target_role, reason="Guardian role update")
        except discord.Forbidden:
            self.logger.warning(f"Insufficient permissions to manage roles for {member.display_name}")
        except Exception as e:
            self.logger.error(f"Error assigning roles for {member.display_name}: {e}")
        return target_name

    async def maybe_kick(self, member: discord.Member, reason: str) -> bool:
        try:
            await member.kick(reason=reason)
            self.logger.info(f"Kicked {member.display_name} for reaching 0 hearts")
            # Delete user data after successful kick
            user_key = f"{member.guild.id}:{member.id}"
            try:
                self.store.delete_user(user_key)
            except Exception as e:
                self.logger.warning(f"Failed to delete Firestore doc for {member.display_name}: {e}")
            return True
        except discord.Forbidden:
            self.logger.warning(f"Insufficient permissions to kick {member.display_name}")
        except Exception as e:
            self.logger.error(f"Error kicking {member.display_name}: {e}")
        return False

    async def on_message(self, message: discord.Message):
        # Ignore ourselves and other bots
        if message.author.bot:
            return
        if not message.guild:
            return  # only moderate servers
        if self.config.allowed_guild_id and str(message.guild.id) != str(self.config.allowed_guild_id):
            return

        cfg = self.config
        store = self.store

        # Build a per-guild user key
        user_key = f"{message.guild.id}:{message.author.id}"
        profile = store.get_or_create_user(user_key, str(message.author), cfg.heart_start, guild_id=str(message.guild.id))

        # Apply daily bonus if due (once per day per user per guild)
        new_hearts_after_bonus = store.apply_daily_bonus_if_due(user_key, cfg.heart_daily_bonus)
        if new_hearts_after_bonus is not None:
            role_name = await self.assign_role_for_hearts(message.author, new_hearts_after_bonus)
            if role_name:
                store.update_user(user_key, {"role": role_name})

    # Analyze content with Gemini
        analysis = analyze_message(cfg.gemini_api_key, message.content)
        flagged = analysis.get("flagged", False)
        reasons = analysis.get("reasons", [])
        good_advice = analysis.get("good_advice", False)
        problem_solved = analysis.get("problem_solved", False)
        praise = analysis.get("praise", False)

        hearts_now: Optional[int] = None

        # Special users: do not penalize or record flags; only allow positive increases as usual
        is_special = str(message.author.id) in self._special_ids

        if flagged and not is_special:
            # Deduct hearts and record flag; store only flagged message content
            store.record_flag(user_key, {
                "guild_id": str(message.guild.id),
                "channel_id": str(message.channel.id),
                "message_id": str(message.id),
                "author_id": str(message.author.id),
                "content": message.content,
                "reasons": reasons,
            })
            store.increment_flag(user_key)
            hearts_now = store.add_hearts(user_key, -cfg.heart_penalty_flag)
            try:
                await message.reply(
                    f"⚠️ Your message was flagged for: {', '.join(reasons) or 'policy violations'}. "
                    f"{cfg.heart_penalty_flag}❤️ deducted. Current: {hearts_now}❤️. Please keep it polite.",
                    mention_author=True,
                )
            except Exception:
                pass

        # Positive signals
        # Rule:
        # - good_advice: reward the author (they are giving advice)
        # - problem_solved or praise: reward the helper (the replied-to user or the first mentioned user)
        delta_author = 0
        if good_advice:
            delta_author += cfg.heart_advice

        helper_member = None
        if message.reference and message.reference.resolved and isinstance(message.reference.resolved, discord.Message):
            # Reward the author of the message being replied to
            replied_msg: discord.Message = message.reference.resolved
            if replied_msg.author and not replied_msg.author.bot:
                helper_member = replied_msg.author
        if not helper_member:
            # Fallback: first mentioned member
            if message.mentions:
                cand = next((m for m in message.mentions if (not m.bot) and (m.id != message.author.id)), None)
                if cand:
                    helper_member = cand
        # Do not allow self-rewarding by replying to self or self-mentioning
        if helper_member and helper_member.id == message.author.id:
            helper_member = None

        delta_helper = 0
        if problem_solved:
            delta_helper += cfg.heart_problem_solved
        if praise:
            delta_helper += cfg.heart_problem_solved  # treat praise as 10 hearts like problem solved

        # Apply deltas
        if delta_author:
            hearts_now = store.add_hearts(user_key, delta_author)
            try:
                await message.add_reaction("❤️")
            except Exception:
                pass
            # DM author about the reward
            try:
                await self.send_reward_dm(
                    message.author,
                    message.guild,
                    delta_author,
                    "Good advice",
                    hearts_now,
                    channel=message.channel if isinstance(message.channel, discord.abc.GuildChannel) else None,
                    jump_url=getattr(message, "jump_url", None),
                )
            except Exception:
                pass
        if helper_member and delta_helper:
            helper_key = f"{message.guild.id}:{helper_member.id}"
            store.get_or_create_user(helper_key, str(helper_member), cfg.heart_start, guild_id=str(message.guild.id))
            helper_hearts = store.add_hearts(helper_key, delta_helper)
            # Update helper's role
            role_name_h = await self.assign_role_for_hearts(helper_member, helper_hearts)
            if role_name_h:
                store.update_user(helper_key, {"role": role_name_h})
            try:
                await message.add_reaction("✅")
            except Exception:
                pass
            # DM helper about the reward
            helper_reason_bits = []
            if problem_solved:
                helper_reason_bits.append("Problem solved")
            if praise:
                helper_reason_bits.append("Praise received")
            helper_reason = ", ".join(helper_reason_bits) or "Contribution recognized"
            try:
                await self.send_reward_dm(
                    helper_member,
                    message.guild,
                    delta_helper,
                    helper_reason,
                    helper_hearts,
                    channel=message.channel if isinstance(message.channel, discord.abc.GuildChannel) else None,
                    jump_url=getattr(message, "jump_url", None),
                )
            except Exception:
                pass

        # If we didn't change hearts yet, fetch current hearts for role assignment
        if hearts_now is None:
            # Read back profile to get current hearts
            profile = store.get_or_create_user(user_key, str(message.author), cfg.heart_start, guild_id=str(message.guild.id))
            hearts_now = profile.hearts

        # Assign appropriate role
        role_name = await self.assign_role_for_hearts(message.author, hearts_now)
        if role_name:
            store.update_user(user_key, {"role": role_name})

        # Kick if hearts are zero (not for special users)
        if hearts_now <= 0 and not is_special:
            await self.maybe_kick(message.author, reason="Guardian: 0 hearts")


def main():
    cfg = get_config()
    setup_logging(cfg.log_level)
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.guilds = True

    collection = os.getenv("FIRESTORE_COLLECTION", "discord-guardian")
    store = Store(collection)

    client = GuardianClient(intents=intents, store=store, config=cfg)
    # Register slash commands

    @client.tree.command(name="hearts", description="Show your current hearts")
    async def hearts_cmd(interaction: discord.Interaction, member: Optional[discord.Member] = None):
        await interaction.response.defer(ephemeral=True)
        if interaction.guild is None:
            return await interaction.followup.send("This command only works in servers.", ephemeral=True)
        if cfg.allowed_guild_id and str(interaction.guild.id) != str(cfg.allowed_guild_id):
            return await interaction.followup.send("This bot is restricted to a specific server.", ephemeral=True)
        target = member or interaction.user
        user_key = f"{interaction.guild.id}:{target.id}"
        # Ensure exists to initialize starting hearts
        profile = store.get_or_create_user(user_key, str(target), cfg.heart_start, guild_id=str(interaction.guild.id))
        hearts = store.get_user_hearts(user_key)
        await interaction.followup.send(f"{target.mention} has {hearts}❤️", ephemeral=True)

    @client.tree.command(name="leaderboard", description="Top hearts in this server")
    async def leaderboard_cmd(interaction: discord.Interaction):
        await interaction.response.defer()
        if interaction.guild is None:
            return await interaction.followup.send("This command only works in servers.")
        if cfg.allowed_guild_id and str(interaction.guild.id) != str(cfg.allowed_guild_id):
            return await interaction.followup.send("This bot is restricted to a specific server.")
        rows = store.top_users_by_guild(str(interaction.guild.id), limit=10)
        if not rows:
            return await interaction.followup.send("No data yet.")
        lines = []
        for i, (doc_id, data) in enumerate(rows, start=1):
            name = data.get("username", doc_id)
            hearts = int(data.get("hearts", 0))
            lines.append(f"{i}. {name} — {hearts}❤️")
        await interaction.followup.send("Leaderboard:\n" + "\n".join(lines))

    @client.tree.command(name="award", description="Award hearts to a member (admin only)")
    @app_commands.describe(amount="Number of hearts to add")
    async def award_cmd(interaction: discord.Interaction, member: discord.Member, amount: int):
        if not client.is_admin(interaction.user):
            return await interaction.response.send_message("You need Manage Server permission.", ephemeral=True)
        await interaction.response.defer()
        if interaction.guild is None:
            return await interaction.followup.send("This command only works in servers.")
        if member.id == interaction.user.id:
            return await interaction.followup.send("You cannot award hearts to yourself.", ephemeral=True)
        if cfg.allowed_guild_id and str(interaction.guild.id) != str(cfg.allowed_guild_id):
            return await interaction.followup.send("This bot is restricted to a specific server.")
        user_key = f"{interaction.guild.id}:{member.id}"
        store.get_or_create_user(user_key, str(member), cfg.heart_start, guild_id=str(interaction.guild.id))
        hearts_now = store.add_hearts(user_key, abs(int(amount)))
        role_name = await client.assign_role_for_hearts(member, hearts_now)
        if role_name:
            store.update_user(user_key, {"role": role_name})
        await interaction.followup.send(f"Awarded {amount}❤️ to {member.mention}. Now {hearts_now}❤️.")
        # DM member about the award
        try:
            await client.send_reward_dm(
                member,
                interaction.guild,
                abs(int(amount)),
                "Admin award",
                hearts_now,
                channel=interaction.channel if isinstance(interaction.channel, discord.abc.GuildChannel) else None,
                jump_url=None,
            )
        except Exception:
            pass

    @client.tree.command(name="penalize", description="Penalize hearts from a member (admin only)")
    @app_commands.describe(amount="Number of hearts to deduct")
    async def penalize_cmd(interaction: discord.Interaction, member: discord.Member, amount: int):
        if not client.is_admin(interaction.user):
            return await interaction.response.send_message("You need Manage Server permission.", ephemeral=True)
        await interaction.response.defer()
        if interaction.guild is None:
            return await interaction.followup.send("This command only works in servers.")
        if member.id == interaction.user.id:
            return await interaction.followup.send("You cannot penalize yourself via command.", ephemeral=True)
        if cfg.allowed_guild_id and str(interaction.guild.id) != str(cfg.allowed_guild_id):
            return await interaction.followup.send("This bot is restricted to a specific server.")
        # Block penalizing special users
        if client.is_special(member):
            return await interaction.followup.send("This member is exempt from penalties (special user).", ephemeral=True)
        user_key = f"{interaction.guild.id}:{member.id}"
        store.get_or_create_user(user_key, str(member), cfg.heart_start, guild_id=str(interaction.guild.id))
        hearts_now = store.add_hearts(user_key, -abs(int(amount)))
        role_name = await client.assign_role_for_hearts(member, hearts_now)
        if role_name:
            store.update_user(user_key, {"role": role_name})
        if hearts_now <= 0:
            await client.maybe_kick(member, reason="Guardian penalize to 0 hearts")
        await interaction.followup.send(f"Deducted {amount}❤️ from {member.mention}. Now {hearts_now}❤️.")
    client.run(cfg.discord_token)


if __name__ == "__main__":
    main()
