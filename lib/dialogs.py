# -*- coding: utf-8 -*-
"""
Dialogs for Subtitle Translator addon.
"""

import xbmc
import xbmcgui


def show_translate_confirm(title, message, thumbnail=None, media_title=None):
    """
    Show translation confirmation dialog.
    
    Args:
        title: Dialog title
        message: Confirmation message
        thumbnail: Path to thumbnail image (used in notification)
        media_title: Title of the media being translated
    
    Returns:
        True if user confirmed, False otherwise
    """
    # Try to get thumbnail if not provided
    if not thumbnail:
        thumbnail = get_current_thumbnail()
    
    if not media_title:
        media_title = get_current_media_title()
    
    # Show a brief notification with thumbnail first (if available)
    if thumbnail and media_title:
        try:
            xbmcgui.Dialog().notification(
                title,
                media_title,
                thumbnail,
                3000,
                sound=False
            )
        except:
            pass
    
    # Use standard yesno dialog (safe, works with all skins)
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
