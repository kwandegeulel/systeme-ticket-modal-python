import json
import discord
from discord.ext import commands
import os
import asyncio

TICKET_CONFIG_FILE = 'ticket_config.json'
TICKET_TRACKING_FILE = 'ticket_tracking.json'
TICKET_MESSAGE_FILE = 'ticket_message.json'

def load_ticket_config():
    if os.path.exists(TICKET_CONFIG_FILE):
        with open(TICKET_CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

# Sauvegarder la configuration dans le fichier JSON
def save_ticket_config(config):
    with open(TICKET_CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

ticket_config = load_ticket_config()

# Charger le suivi des tickets ouverts
def load_ticket_tracking():
    if os.path.exists(TICKET_TRACKING_FILE):
        with open(TICKET_TRACKING_FILE, 'r') as f:
            return json.load(f)
    return {}

# Sauvegarder le suivi des tickets ouverts
def save_ticket_tracking(tracking):
    with open(TICKET_TRACKING_FILE, 'w') as f:
        json.dump(tracking, f, indent=4)

ticket_tracking = load_ticket_tracking()

# Charger les IDs des messages de ticket
def load_ticket_message_ids():
    if os.path.exists(TICKET_MESSAGE_FILE):
        with open(TICKET_MESSAGE_FILE, 'r') as f:
            return json.load(f)
    return {}

# Sauvegarder les IDs des messages de ticket
def save_ticket_message_ids(message_ids):
    with open(TICKET_MESSAGE_FILE, 'w') as f:
        json.dump(message_ids, f, indent=4)

ticket_message_ids = load_ticket_message_ids()

class TicketManagementView(discord.ui.View):
    def __init__(self, member: discord.Member, ticket_channel: discord.TextChannel, guild_config):
        super().__init__(timeout=None)
        self.member = member
        self.ticket_channel = ticket_channel
        self.config = guild_config

    @discord.ui.button(label="Fermer le Ticket", style=discord.ButtonStyle.secondary, custom_id="close_ticket")
    async def close_ticket_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        permitted_roles = self.config.get('permitted_roles', [])
        has_role = any(role.id in permitted_roles for role in interaction.user.roles)

        if interaction.user == self.member or interaction.user.guild_permissions.manage_channels or has_role:
            embed = discord.Embed(
                title="Ticket Fermé",
                description=f"Ticket fermé par {interaction.user.mention}.",
                color=discord.Color.from_str('#000000')
            )
            await self.ticket_channel.send(embed=embed)
            await self.ticket_channel.set_permissions(self.member, read_messages=False, send_messages=False)
            guild_id = str(interaction.guild.id)
            user_id = str(self.member.id)
            if guild_id in ticket_tracking and user_id in ticket_tracking[guild_id]:
                del ticket_tracking[guild_id][user_id]
                save_ticket_tracking(ticket_tracking)
            await interaction.response.defer()
        else:
            await interaction.response.send_message("Vous n'avez pas la permission de fermer ce ticket.", ephemeral=True)

    @discord.ui.button(label="Supprimer le Ticket", style=discord.ButtonStyle.danger, custom_id="delete_ticket")
    async def delete_ticket_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        permitted_roles = self.config.get('permitted_roles', [])
        has_role = any(role.id in permitted_roles for role in interaction.user.roles)

        if interaction.user.guild_permissions.manage_channels or has_role:
            embed = discord.Embed(
                title="Suppression du Ticket",
                description="Patientez cinq secondes, le ticket va être supprimé.",
                color=discord.Color.from_str('#000000')
            )
            await self.ticket_channel.send(embed=embed)
            await interaction.response.defer()
            await asyncio.sleep(5)
            guild_id = str(interaction.guild.id)
            user_id = str(interaction.user.id)
            if guild_id in ticket_tracking and user_id in ticket_tracking[guild_id]:
                del ticket_tracking[guild_id][user_id]
                save_ticket_tracking(ticket_tracking)
            await self.ticket_channel.delete()
        else:
            await interaction.response.send_message("Vous n'avez pas la permission de supprimer ce ticket.", ephemeral=True)

class TicketButtonView(discord.ui.View):
    def __init__(self, guild_id: str, button_label: str, category_id: int):
        super().__init__(timeout=None)  # Assurez-vous que la vue n'a pas de timeout
        self.guild_id = guild_id
        self.button_label = button_label
        self.category_id = category_id

    @discord.ui.button(label="Ouvrir un Ticket", style=discord.ButtonStyle.primary, custom_id="open_ticket_button")
    async def ticket_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = ticket_config.get(self.guild_id, {}).get(self.button_label)
        user_id = str(interaction.user.id)
        if config:
            # Vérifier si l'utilisateur a déjà un ticket ouvert
            if user_id in ticket_tracking.get(self.guild_id, {}):
                ticket_channel_id = ticket_tracking[self.guild_id][user_id]
                ticket_channel = interaction.guild.get_channel(ticket_channel_id)
                if ticket_channel:
                    # Message éphémère informant que l'utilisateur a déjà un ticket ouvert
                    await interaction.response.send_message(f"Vous avez déjà un ticket ouvert : {ticket_channel.mention}", ephemeral=True)
                    return
                else:
                    # Si le canal n'existe plus mais que l'entrée de suivi est toujours présente, la supprimer
                    del ticket_tracking[self.guild_id][user_id]
                    save_ticket_tracking(ticket_tracking)

            # Continuer la création du ticket si aucun n'est ouvert
            category = interaction.guild.get_channel(config['category_id'])
            permitted_roles = config.get('permitted_roles', [])
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True, embed_links=True, manage_messages=True, manage_channels=True)
            }

            for role_id in permitted_roles:
                role = interaction.guild.get_role(int(role_id))
                if role:
                    overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True, manage_channels=True)

            if category and isinstance(category, discord.CategoryChannel):
                ticket_channel = await interaction.guild.create_text_channel(
                    name=f"ticket-{interaction.user.name}",
                    category=category,
                    overwrites=overwrites
                )
                color_value = config.get('color', '#000000').strip()
                color = discord.Color.from_str(color_value) if color_value else discord.Color.default()
                embed = discord.Embed(
                    title=f"Ticket ouvert par {interaction.user}",
                    description="**Patientez, un membre du staff arrivera dès que possible.**",
                    color=color
                )
                if config.get('thumbnail_url'):
                    embed.set_thumbnail(url=config['thumbnail_url'])
                if 'footer_text' in config:
                    embed.set_footer(text=config['footer_text'], icon_url=interaction.client.user.avatar.url)
                view = TicketManagementView(interaction.user, ticket_channel, config)
                await ticket_channel.send(embed=embed, view=view)
                if self.guild_id not in ticket_tracking:
                    ticket_tracking[self.guild_id] = {}
                ticket_tracking[self.guild_id][user_id] = ticket_channel.id
                save_ticket_tracking(ticket_tracking)
                await interaction.response.send_message(f"Ticket créé avec succès : {ticket_channel.mention}", ephemeral=True)
            else:
                await interaction.response.send_message("Catégorie de ticket invalide ou non trouvée.", ephemeral=True)
        else:
            await interaction.response.send_message("Configuration des tickets non trouvée.", ephemeral=True)

class TicketConfigModal(discord.ui.Modal):
    def __init__(self, title):
        super().__init__(title=title)
        self.add_item(discord.ui.TextInput(
            label="Description",
            style=discord.TextStyle.paragraph,
            placeholder="Entrez la description de l'embed",
            required=True,
            custom_id="ticket_description"
        ))
        self.add_item(discord.ui.TextInput(
            label="Couleur et Footer",
            style=discord.TextStyle.short,
            placeholder="Couleur HEX (ex: #00FF00), Texte du footer (séparés par une virgule)",
            required=False,
            custom_id="ticket_color_footer"
        ))
        self.add_item(discord.ui.TextInput(
            label="Vignette",
            style=discord.TextStyle.short,
            placeholder="URL de la vignette",
            required=False,
            custom_id="ticket_thumbnail"
        ))
        self.add_item(discord.ui.TextInput(
            label="ID Catégorie",
            style=discord.TextStyle.short,
            placeholder="ID de la catégorie de tickets",
            required=True,
            custom_id="ticket_category_id"
        ))
        self.add_item(discord.ui.TextInput(
            label="ID du Salon",
            style=discord.TextStyle.short,
            placeholder="ID du salon pour envoyer l'embed",
            required=True,
            custom_id="ticket_channel_id"
        ))

    async def on_submit(self, interaction: discord.Interaction):
        description = self.children[0].value
        color_footer = self.children[1].value.split(',')
        color = color_footer[0].strip() if len(color_footer) > 0 else '#000000'
        footer_text = color_footer[1].strip() if len(color_footer) > 1 else None
        thumbnail_url = self.children[2].value.strip() if self.children[2].value else None
        category_id = int(self.children[3].value)
        channel_id = int(self.children[4].value)

        guild_id = str(interaction.guild_id)
        button_name = f"Ticket {category_id}"  # Unique button name based on category_id
        if guild_id not in ticket_config:
            ticket_config[guild_id] = {}

        ticket_config[guild_id][button_name] = {
            'description': description,
            'color': color,
            'button_name': button_name,
            'category_id': category_id,
            'channel_id': channel_id,
            'thumbnail_url': thumbnail_url,
            'footer_text': footer_text
        }
        save_ticket_config(ticket_config)

        embed = discord.Embed(
            title="Ticket",
            description=description,
            color=int(color.strip('#'), 16)
        )
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
        if footer_text:
            embed.set_footer(text=footer_text, icon_url=interaction.client.user.avatar.url)

        view = TicketButtonView(guild_id, button_name, category_id)
        channel = interaction.guild.get_channel(channel_id)
        if channel:
            message = await channel.send(embed=embed, view=view)
            ticket_message_ids[str(message.id)] = {'guild_id': guild_id, 'button_name': button_name, 'category_id': category_id}
            save_ticket_message_ids(ticket_message_ids)
            await interaction.response.send_message("Configuration des tickets enregistrée avec succès!", ephemeral=True)
        else:
            await interaction.followup.send_message("ID du salon invalide.", ephemeral=True)

@client.tree.command(name="ticket-config", description="Configurez le système de tickets")
@discord.app_commands.checks.has_permissions(administrator=True)
async def configure_ticket(interaction: discord.Interaction):
    try:
        modal = TicketConfigModal("Configuration des Tickets")
        await interaction.response.send_modal(modal)
    except Exception as e:
        print(f"Erreur lors de l'envoi du modal: {e}")
        await interaction.response.send_message("Une erreur est survenue lors de l'ouverture du modal.", ephemeral=True)

@configure_ticket.error
async def configure_ticket_error(interaction: discord.Interaction, error):
    if isinstance(error, discord.app_commands.errors.MissingPermissions):
        await interaction.response.send_message("Vous n'avez pas les permissions nécessaires pour utiliser cette commande.", ephemeral=True)
    else:
        await interaction.response.send_message("Une erreur est survenue lors de la configuration des tickets.", ephemeral=True)