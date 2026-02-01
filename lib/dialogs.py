# -*- coding: utf-8 -*-
"""
Custom dialogs for Subtitle Translator addon.
"""

import xbmc
import xbmcgui

# Window IDs
ACTION_PREVIOUS_MENU = 10
ACTION_BACK = 92
ACTION_NAV_BACK = 9
ACTION_SELECT_ITEM = 7

# Control IDs for custom dialog
CTRL_BACKGROUND = 100
CTRL_THUMBNAIL = 101
CTRL_TITLE = 102
CTRL_MESSAGE = 103
CTRL_YES_BUTTON = 201
CTRL_NO_BUTTON = 202


class TranslateConfirmDialog(xbmcgui.WindowXMLDialog):
    """
    Custom dialog with thumbnail for translation confirmation.
    Falls back to standard yesno dialog if XML not available.
    """
    
    def __init__(self, *args, **kwargs):
        self.title = kwargs.get('title', 'Subtitle Translator')
        self.message = kwargs.get('message', '')
        self.thumbnail = kwargs.get('thumbnail', '')
        self.media_title = kwargs.get('media_title', '')
        self.result = False
        super().__init__(*args, **kwargs)
    
    def onInit(self):
        """Initialize dialog controls."""
        try:
            # Set thumbnail
            if self.thumbnail:
                self.getControl(CTRL_THUMBNAIL).setImage(self.thumbnail)
            
            # Set title
            self.getControl(CTRL_TITLE).setLabel(self.media_title or self.title)
            
            # Set message
            self.getControl(CTRL_MESSAGE).setLabel(self.message)
            
            # Focus on No button (safer default)
            self.setFocusId(CTRL_NO_BUTTON)
        except Exception as e:
            xbmc.log(f"[SubtitleTranslator] Dialog init error: {e}", xbmc.LOGWARNING)
    
    def onClick(self, controlId):
        """Handle button clicks."""
        if controlId == CTRL_YES_BUTTON:
            self.result = True
            self.close()
        elif controlId == CTRL_NO_BUTTON:
            self.result = False
            self.close()
    
    def onAction(self, action):
        """Handle actions."""
        action_id = action.getId()
        if action_id in (ACTION_PREVIOUS_MENU, ACTION_BACK, ACTION_NAV_BACK):
            self.result = False
            self.close()


def show_translate_confirm(title, message, thumbnail=None, media_title=None):
    """
    Show translation confirmation dialog with thumbnail.
    
    Args:
        title: Dialog title
        message: Confirmation message
        thumbnail: Path to thumbnail image
        media_title: Title of the media being translated
    
    Returns:
        True if user confirmed, False otherwise
    """
    # Try to get thumbnail if not provided
    if not thumbnail:
        thumbnail = get_current_thumbnail()
    
    if not media_title:
        media_title = get_current_media_title()
    
    # Try custom dialog with thumbnail first
    try:
        # Check if our custom dialog XML exists
        import xbmcaddon
        import xbmcvfs
        import os
        
        addon = xbmcaddon.Addon()
        addon_path = xbmcvfs.translatePath(addon.getAddonInfo('path'))
        dialog_xml = os.path.join(addon_path, 'resources', 'skins', 'default', '1080i', 'TranslateConfirmDialog.xml')
        
        if xbmcvfs.exists(dialog_xml):
            dialog = TranslateConfirmDialog(
                'TranslateConfirmDialog.xml',
                addon_path,
                'default',
                '1080i',
                title=title,
                message=message,
                thumbnail=thumbnail,
                media_title=media_title
            )
            dialog.doModal()
            result = dialog.result
            del dialog
            return result
    except Exception as e:
        xbmc.log(f"[SubtitleTranslator] Custom dialog failed: {e}", xbmc.LOGWARNING)
    
    # Fallback: Use built-in dialog with thumbnail notification
    if thumbnail and media_title:
        # Show a brief notification with thumbnail first
        xbmcgui.Dialog().notification(
            title,
            media_title,
            thumbnail,
            3000,
            sound=False
        )
    
    # Then show standard yesno dialog
    return xbmcgui.Dialog().yesno(
        title,
        message,
        autoclose=30000  # Auto-close after 30 seconds (decline)
    )


def get_current_thumbnail():
    """Get thumbnail of currently playing media."""
    # Try different art types
    art_types = ['thumb', 'poster', 'banner', 'fanart', 'landscape']
    
    for art_type in art_types:
        thumb = xbmc.getInfoLabel(f'Player.Art({art_type})')
        if thumb:
            return thumb
    
    # Try video info tag
    try:
        player = xbmc.Player()
        if player.isPlayingVideo():
            info = player.getVideoInfoTag()
            # Try to get art from info tag
            thumb = xbmc.getInfoLabel('VideoPlayer.Cover')
            if thumb:
                return thumb
    except:
        pass
    
    # Try ListItem art
    thumb = xbmc.getInfoLabel('ListItem.Art(thumb)')
    if thumb:
        return thumb
    
    thumb = xbmc.getInfoLabel('ListItem.Thumb')
    if thumb:
        return thumb
    
    return None


def get_current_media_title():
    """Get title of currently playing media."""
    # Try Player labels
    title = xbmc.getInfoLabel('Player.Title')
    if title:
        return title
    
    title = xbmc.getInfoLabel('VideoPlayer.Title')
    if title:
        return title
    
    # Try video info tag
    try:
        player = xbmc.Player()
        if player.isPlayingVideo():
            info = player.getVideoInfoTag()
            title = info.getTitle()
            if title:
                return title
            
            # Try original title
            title = info.getOriginalTitle()
            if title:
                return title
    except:
        pass
    
    # Fallback to filename
    title = xbmc.getInfoLabel('Player.Filename')
    if title:
        # Remove extension
        import os
        return os.path.splitext(title)[0]
    
    return None
