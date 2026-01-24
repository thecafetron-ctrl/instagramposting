"""
Social Media Posting Service
Handles posting videos to Instagram, TikTok, and YouTube with platform-specific optimizations.
"""
import os
import logging
import httpx
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class PlatformContent:
    """Platform-specific content optimized for each social network."""
    title: str
    description: str
    hashtags: List[str]
    tags: List[str]  # For YouTube tags
    

def generate_platform_content(
    base_caption: str,
    hook: str,
    category: str,
    platform: str,
) -> PlatformContent:
    """
    Generate optimized content for each platform.
    
    - Instagram: Short, punchy, trending hashtags
    - TikTok: Trendy, challenge-friendly, viral hashtags
    - YouTube: SEO-optimized, keyword-rich descriptions and tags
    """
    # Common viral hashtags by category
    category_hashtags = {
        "funny": {
            "instagram": ["#funny", "#comedy", "#viral", "#lol", "#memes", "#fyp", "#reels", "#humor", "#trending", "#funnyvideos"],
            "tiktok": ["#funny", "#comedy", "#viral", "#fyp", "#foryou", "#foryoupage", "#humor", "#memes", "#lol", "#trending"],
            "youtube": ["funny", "comedy", "viral video", "hilarious", "must watch", "trending"],
        },
        "educational": {
            "instagram": ["#educational", "#learn", "#facts", "#didyouknow", "#knowledge", "#tips", "#howto", "#fyp", "#reels"],
            "tiktok": ["#educational", "#learnontiktok", "#facts", "#didyouknow", "#fyp", "#foryou", "#knowledge", "#tips"],
            "youtube": ["educational", "learn", "facts", "how to", "tutorial", "explained", "knowledge"],
        },
        "dramatic": {
            "instagram": ["#dramatic", "#storytime", "#viral", "#mustwatch", "#shocking", "#reels", "#fyp", "#trending"],
            "tiktok": ["#dramatic", "#storytime", "#viral", "#fyp", "#foryou", "#shocking", "#pov", "#trending"],
            "youtube": ["dramatic", "story time", "must watch", "viral", "shocking", "incredible"],
        },
        "default": {
            "instagram": ["#viral", "#trending", "#reels", "#fyp", "#explore", "#instagood", "#foryou", "#content", "#creator"],
            "tiktok": ["#viral", "#fyp", "#foryou", "#foryoupage", "#trending", "#tiktok", "#viral", "#content"],
            "youtube": ["viral", "trending", "must watch", "amazing", "incredible", "2026"],
        },
    }
    
    # Get category-specific hashtags
    cat_key = category.lower() if category.lower() in category_hashtags else "default"
    platform_tags = category_hashtags[cat_key].get(platform.lower(), category_hashtags["default"]["instagram"])
    
    if platform.lower() == "instagram":
        # Instagram: Short caption + hook + hashtags (max 30 hashtags, ~2200 chars)
        title = hook[:100] if hook else base_caption[:100]
        description = f"{hook}\n\n{base_caption[:500]}\n\n" + " ".join(platform_tags[:20])
        return PlatformContent(
            title=title,
            description=description,
            hashtags=platform_tags[:20],
            tags=[],
        )
    
    elif platform.lower() == "tiktok":
        # TikTok: Very short, punchy, hashtag-heavy (max ~150 chars visible)
        title = hook[:80] if hook else base_caption[:80]
        # TikTok description is limited, focus on hashtags
        hashtags = platform_tags[:10]
        description = f"{hook[:100] if hook else base_caption[:100]} " + " ".join(hashtags)
        return PlatformContent(
            title=title,
            description=description[:150],
            hashtags=hashtags,
            tags=[],
        )
    
    elif platform.lower() == "youtube":
        # YouTube: SEO-optimized, long description with timestamps and keywords
        title = f"{hook[:70]} | Must Watch!" if hook else f"{base_caption[:70]} | Viral Video"
        
        # Build SEO-rich description
        description_parts = [
            f"🔥 {hook if hook else base_caption[:200]}",
            "",
            "📌 WATCH TILL THE END!",
            "",
            base_caption[:1000] if base_caption else "",
            "",
            "─" * 30,
            "",
            "📊 More content like this coming soon!",
            "👍 LIKE if you enjoyed",
            "💬 COMMENT your thoughts",
            "🔔 SUBSCRIBE for more!",
            "",
            "─" * 30,
            "",
            "🏷️ Tags:",
            ", ".join(platform_tags[:15]),
            "",
            "#Shorts #Viral #Trending #YouTube #MustWatch",
        ]
        description = "\n".join(description_parts)
        
        return PlatformContent(
            title=title[:100],  # YouTube title max 100 chars
            description=description[:5000],  # YouTube description max 5000 chars
            hashtags=platform_tags[:5],  # YouTube hashtags (in title/description)
            tags=platform_tags[:30],  # YouTube video tags (separate field)
        )
    
    # Default
    return PlatformContent(
        title=hook or base_caption[:100],
        description=base_caption[:500],
        hashtags=platform_tags[:10],
        tags=[],
    )


class InstagramPoster:
    """Post videos to Instagram Reels via Graph API."""
    
    def __init__(self, access_token: str, instagram_account_id: str = None):
        self.access_token = access_token
        self.account_id = instagram_account_id
        self.api_base = "https://graph.facebook.com/v18.0"
    
    async def get_account_id(self) -> str:
        """Get Instagram Business Account ID."""
        if self.account_id:
            return self.account_id
        
        async with httpx.AsyncClient() as client:
            # Get pages
            res = await client.get(
                f"{self.api_base}/me/accounts",
                params={"access_token": self.access_token}
            )
            data = res.json()
            
            if "data" not in data or not data["data"]:
                raise ValueError("No Facebook pages found")
            
            page = data["data"][0]
            page_id = page["id"]
            page_token = page["access_token"]
            
            # Get Instagram account linked to page
            res = await client.get(
                f"{self.api_base}/{page_id}",
                params={
                    "fields": "instagram_business_account",
                    "access_token": page_token,
                }
            )
            data = res.json()
            
            if "instagram_business_account" not in data:
                raise ValueError("No Instagram business account linked to page")
            
            self.account_id = data["instagram_business_account"]["id"]
            return self.account_id
    
    async def post_video(
        self,
        video_url: str,
        caption: str,
        share_to_feed: bool = True,
    ) -> Dict[str, Any]:
        """
        Post a video to Instagram Reels.
        
        Args:
            video_url: Public URL of the video file
            caption: Caption with hashtags
            share_to_feed: Whether to also share to feed
        """
        account_id = await self.get_account_id()
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Step 1: Create media container
            res = await client.post(
                f"{self.api_base}/{account_id}/media",
                data={
                    "media_type": "REELS",
                    "video_url": video_url,
                    "caption": caption,
                    "share_to_feed": str(share_to_feed).lower(),
                    "access_token": self.access_token,
                }
            )
            container_data = res.json()
            
            if "id" not in container_data:
                logger.error(f"Instagram container creation failed: {container_data}")
                raise ValueError(f"Failed to create media container: {container_data.get('error', {}).get('message', 'Unknown error')}")
            
            container_id = container_data["id"]
            logger.info(f"Created Instagram media container: {container_id}")
            
            # Step 2: Wait for processing and publish
            import asyncio
            for _ in range(30):  # Wait up to 5 minutes
                await asyncio.sleep(10)
                
                status_res = await client.get(
                    f"{self.api_base}/{container_id}",
                    params={
                        "fields": "status_code",
                        "access_token": self.access_token,
                    }
                )
                status_data = status_res.json()
                status = status_data.get("status_code")
                
                if status == "FINISHED":
                    break
                elif status == "ERROR":
                    raise ValueError("Instagram video processing failed")
            
            # Step 3: Publish
            publish_res = await client.post(
                f"{self.api_base}/{account_id}/media_publish",
                data={
                    "creation_id": container_id,
                    "access_token": self.access_token,
                }
            )
            publish_data = publish_res.json()
            
            if "id" not in publish_data:
                raise ValueError(f"Failed to publish: {publish_data}")
            
            return {
                "platform": "instagram",
                "success": True,
                "post_id": publish_data["id"],
                "url": f"https://www.instagram.com/reel/{publish_data['id']}/",
            }


class TikTokPoster:
    """Post videos to TikTok via their Content Posting API."""
    
    def __init__(self, client_key: str, client_secret: str, access_token: str = None):
        self.client_key = client_key
        self.client_secret = client_secret
        self.access_token = access_token
        self.api_base = "https://open.tiktokapis.com/v2"
    
    async def refresh_access_token(self, refresh_token: str) -> str:
        """Refresh the access token."""
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{self.api_base}/oauth/token/",
                data={
                    "client_key": self.client_key,
                    "client_secret": self.client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                }
            )
            data = res.json()
            if "access_token" in data:
                self.access_token = data["access_token"]
                return data["access_token"]
            raise ValueError(f"Failed to refresh token: {data}")
    
    async def post_video_by_url(
        self,
        video_url: str,
        title: str,
        privacy_level: str = "PUBLIC_TO_EVERYONE",
        disable_comment: bool = False,
        disable_duet: bool = False,
        disable_stitch: bool = False,
    ) -> Dict[str, Any]:
        """
        Post a video to TikTok using URL pull method.
        
        Args:
            video_url: Public URL of the video (must be accessible from TikTok servers)
            title: Video title/caption (max 150 chars)
            privacy_level: PUBLIC_TO_EVERYONE, MUTUAL_FOLLOW_FRIENDS, SELF_ONLY
        """
        if not self.access_token:
            raise ValueError("Access token required for TikTok posting")
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Initialize video upload
            init_res = await client.post(
                f"{self.api_base}/post/publish/video/init/",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "post_info": {
                        "title": title[:150],
                        "privacy_level": privacy_level,
                        "disable_comment": disable_comment,
                        "disable_duet": disable_duet,
                        "disable_stitch": disable_stitch,
                    },
                    "source_info": {
                        "source": "PULL_FROM_URL",
                        "video_url": video_url,
                    }
                }
            )
            
            init_data = init_res.json()
            
            if init_data.get("error", {}).get("code") != "ok":
                logger.error(f"TikTok init failed: {init_data}")
                raise ValueError(f"TikTok upload failed: {init_data.get('error', {}).get('message', 'Unknown error')}")
            
            publish_id = init_data.get("data", {}).get("publish_id")
            
            return {
                "platform": "tiktok",
                "success": True,
                "publish_id": publish_id,
                "status": "processing",
                "message": "Video submitted to TikTok. It will appear on your profile once processed.",
            }


class YouTubePoster:
    """Post videos to YouTube via Data API v3."""
    
    def __init__(
        self,
        api_key: str,
        client_id: str = None,
        client_secret: str = None,
        refresh_token: str = None,
    ):
        self.api_key = api_key
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.access_token = None
        self.api_base = "https://www.googleapis.com/youtube/v3"
        self.upload_base = "https://www.googleapis.com/upload/youtube/v3"
    
    async def get_access_token(self) -> str:
        """Get access token using refresh token."""
        if self.access_token:
            return self.access_token
        
        if not self.refresh_token or not self.client_id or not self.client_secret:
            raise ValueError("OAuth credentials required for YouTube upload")
        
        async with httpx.AsyncClient() as client:
            res = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self.refresh_token,
                    "grant_type": "refresh_token",
                }
            )
            data = res.json()
            
            if "access_token" in data:
                self.access_token = data["access_token"]
                return self.access_token
            
            raise ValueError(f"Failed to get YouTube access token: {data}")
    
    async def upload_video(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: List[str],
        category_id: str = "22",  # People & Blogs
        privacy_status: str = "public",
        made_for_kids: bool = False,
    ) -> Dict[str, Any]:
        """
        Upload a video to YouTube.
        
        Args:
            video_path: Local path to video file
            title: Video title (max 100 chars)
            description: Video description (max 5000 chars)
            tags: Video tags (max 500 chars total)
            category_id: YouTube category ID
            privacy_status: public, unlisted, or private
        """
        access_token = await self.get_access_token()
        
        # Read video file
        video_data = video_path.read_bytes()
        
        # Prepare metadata
        metadata = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags[:30],
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": made_for_kids,
            }
        }
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            # Resumable upload - Step 1: Initialize
            init_res = await client.post(
                f"{self.upload_base}/videos",
                params={
                    "uploadType": "resumable",
                    "part": "snippet,status",
                },
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "X-Upload-Content-Type": "video/mp4",
                    "X-Upload-Content-Length": str(len(video_data)),
                },
                json=metadata,
            )
            
            if init_res.status_code != 200:
                raise ValueError(f"YouTube upload init failed: {init_res.text}")
            
            upload_url = init_res.headers.get("Location")
            if not upload_url:
                raise ValueError("No upload URL returned from YouTube")
            
            # Step 2: Upload video data
            upload_res = await client.put(
                upload_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "video/mp4",
                },
                content=video_data,
            )
            
            if upload_res.status_code not in [200, 201]:
                raise ValueError(f"YouTube video upload failed: {upload_res.text}")
            
            result = upload_res.json()
            video_id = result.get("id")
            
            return {
                "platform": "youtube",
                "success": True,
                "video_id": video_id,
                "url": f"https://www.youtube.com/shorts/{video_id}" if result.get("snippet", {}).get("liveBroadcastContent") != "none" else f"https://www.youtube.com/watch?v={video_id}",
            }


class SocialMediaManager:
    """Unified manager for posting to multiple platforms."""
    
    def __init__(self, settings):
        self.settings = settings
        
        # Initialize posters based on available credentials
        self.instagram = None
        self.tiktok = None
        self.youtube = None
        
        if settings.instagram_access_token:
            self.instagram = InstagramPoster(settings.instagram_access_token)
        
        if settings.tiktok_client_key and settings.tiktok_access_token:
            self.tiktok = TikTokPoster(
                settings.tiktok_client_key,
                settings.tiktok_client_secret,
                settings.tiktok_access_token,
            )
        
        if settings.youtube_refresh_token:
            self.youtube = YouTubePoster(
                settings.youtube_api_key,
                settings.youtube_client_id,
                settings.youtube_client_secret,
                settings.youtube_refresh_token,
            )
    
    async def post_to_instagram(
        self,
        video_url: str,
        caption: str,
        hook: str = "",
        category: str = "default",
    ) -> Dict[str, Any]:
        """Post to Instagram with optimized content."""
        if not self.instagram:
            return {"platform": "instagram", "success": False, "error": "Instagram not configured"}
        
        content = generate_platform_content(caption, hook, category, "instagram")
        
        try:
            result = await self.instagram.post_video(
                video_url=video_url,
                caption=content.description,
            )
            return result
        except Exception as e:
            logger.error(f"Instagram post failed: {e}")
            return {"platform": "instagram", "success": False, "error": str(e)}
    
    async def post_to_tiktok(
        self,
        video_url: str,
        caption: str,
        hook: str = "",
        category: str = "default",
    ) -> Dict[str, Any]:
        """Post to TikTok with optimized content."""
        if not self.tiktok:
            return {"platform": "tiktok", "success": False, "error": "TikTok not configured"}
        
        content = generate_platform_content(caption, hook, category, "tiktok")
        
        try:
            result = await self.tiktok.post_video_by_url(
                video_url=video_url,
                title=content.description,  # TikTok uses title as main text
            )
            return result
        except Exception as e:
            logger.error(f"TikTok post failed: {e}")
            return {"platform": "tiktok", "success": False, "error": str(e)}
    
    async def post_to_youtube(
        self,
        video_path: Path,
        caption: str,
        hook: str = "",
        category: str = "default",
    ) -> Dict[str, Any]:
        """Post to YouTube with SEO-optimized content."""
        if not self.youtube:
            return {"platform": "youtube", "success": False, "error": "YouTube not configured"}
        
        content = generate_platform_content(caption, hook, category, "youtube")
        
        try:
            result = await self.youtube.upload_video(
                video_path=video_path,
                title=content.title,
                description=content.description,
                tags=content.tags,
            )
            return result
        except Exception as e:
            logger.error(f"YouTube post failed: {e}")
            return {"platform": "youtube", "success": False, "error": str(e)}
    
    async def post_to_all(
        self,
        video_path: Path,
        video_url: str,
        caption: str,
        hook: str = "",
        category: str = "default",
    ) -> Dict[str, Any]:
        """Post to all configured platforms."""
        results = {
            "instagram": None,
            "tiktok": None,
            "youtube": None,
            "success_count": 0,
            "fail_count": 0,
        }
        
        # Post to each platform
        if self.instagram:
            results["instagram"] = await self.post_to_instagram(video_url, caption, hook, category)
            if results["instagram"].get("success"):
                results["success_count"] += 1
            else:
                results["fail_count"] += 1
        
        if self.tiktok:
            results["tiktok"] = await self.post_to_tiktok(video_url, caption, hook, category)
            if results["tiktok"].get("success"):
                results["success_count"] += 1
            else:
                results["fail_count"] += 1
        
        if self.youtube:
            results["youtube"] = await self.post_to_youtube(video_path, caption, hook, category)
            if results["youtube"].get("success"):
                results["success_count"] += 1
            else:
                results["fail_count"] += 1
        
        return results


# TikTok OAuth flow helpers
def get_tiktok_auth_url(client_key: str, redirect_uri: str, state: str = "state123") -> str:
    """Generate TikTok OAuth authorization URL."""
    scopes = "user.info.basic,video.upload,video.publish"
    return (
        f"https://www.tiktok.com/v2/auth/authorize/"
        f"?client_key={client_key}"
        f"&scope={scopes}"
        f"&response_type=code"
        f"&redirect_uri={redirect_uri}"
        f"&state={state}"
    )


async def exchange_tiktok_code(
    code: str,
    client_key: str,
    client_secret: str,
    redirect_uri: str,
) -> Dict[str, Any]:
    """Exchange TikTok authorization code for access token."""
    async with httpx.AsyncClient() as client:
        res = await client.post(
            "https://open.tiktokapis.com/v2/oauth/token/",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_key": client_key,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            }
        )
        return res.json()
