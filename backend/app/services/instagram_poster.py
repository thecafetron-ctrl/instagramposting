"""
Instagram Graph API service for posting carousels.
Uses the Instagram Content Publishing API.
"""

import httpx
import asyncio
import os
from typing import List, Optional
from app.config import get_settings

settings = get_settings()

GRAPH_API_BASE = "https://graph.instagram.com/v21.0"


async def get_instagram_user_id(access_token: str) -> Optional[str]:
    """Get the Instagram user ID from the access token."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GRAPH_API_BASE}/me",
            params={
                "access_token": access_token,
                "fields": "user_id,username"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get("user_id") or data.get("id")
        else:
            print(f"Error getting user ID: {response.text}")
            return None


async def upload_image_to_hosting(image_path: str, base_url: str) -> str:
    """
    Get a publicly accessible URL for the image.
    The Instagram API requires images to be accessible via public URL.
    """
    # Extract just the filename (remove any path like generated_images/)
    filename = os.path.basename(image_path)
    
    # Clean up base_url - remove trailing slash and any /images suffix
    base_url = base_url.rstrip('/')
    if base_url.endswith('/images'):
        base_url = base_url[:-7]
    
    # Build clean URL
    url = f"{base_url}/images/{filename}"
    print(f"Built image URL: {url} (from path: {image_path})")
    return url


_last_ig_error = None

async def create_media_container(
    user_id: str,
    image_url: str,
    access_token: str,
    is_carousel_item: bool = True
) -> Optional[str]:
    """
    Create a media container for an image.
    Returns the container ID if successful.
    """
    global _last_ig_error
    print(f"Creating media container for: {image_url}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        params = {
            "image_url": image_url,
            "access_token": access_token,
        }
        
        if is_carousel_item:
            params["is_carousel_item"] = "true"
        
        response = await client.post(
            f"{GRAPH_API_BASE}/{user_id}/media",
            params=params
        )
        
        print(f"Instagram API response: {response.status_code} - {response.text[:500]}")
        
        if response.status_code == 200:
            data = response.json()
            return data.get("id")
        else:
            _last_ig_error = response.text
            print(f"Error creating media container: {response.text}")
            return None


def get_last_ig_error():
    return _last_ig_error


async def create_carousel_container(
    user_id: str,
    children_ids: List[str],
    caption: str,
    access_token: str
) -> Optional[str]:
    """
    Create a carousel container that groups multiple media items.
    Returns the container ID if successful.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{GRAPH_API_BASE}/{user_id}/media",
            params={
                "media_type": "CAROUSEL",
                "children": ",".join(children_ids),
                "caption": caption,
                "access_token": access_token,
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get("id")
        else:
            print(f"Error creating carousel container: {response.text}")
            return None


async def check_container_status(
    container_id: str,
    access_token: str
) -> dict:
    """Check the status of a media container."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GRAPH_API_BASE}/{container_id}",
            params={
                "fields": "status_code,status",
                "access_token": access_token,
            }
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"status_code": "ERROR", "error": response.text}


async def wait_for_container_ready(
    container_id: str,
    access_token: str,
    max_attempts: int = 30,
    delay: float = 2.0
) -> bool:
    """Wait for a container to be ready for publishing."""
    for _ in range(max_attempts):
        status = await check_container_status(container_id, access_token)
        status_code = status.get("status_code", "")
        
        if status_code == "FINISHED":
            return True
        elif status_code == "ERROR":
            print(f"Container error: {status}")
            return False
        elif status_code in ["EXPIRED", "FAILED"]:
            print(f"Container failed: {status}")
            return False
        
        # Still processing, wait and retry
        await asyncio.sleep(delay)
    
    print("Timeout waiting for container to be ready")
    return False


async def publish_media(
    user_id: str,
    container_id: str,
    access_token: str
) -> Optional[str]:
    """
    Publish a media container to Instagram.
    Returns the published media ID if successful.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{GRAPH_API_BASE}/{user_id}/media_publish",
            params={
                "creation_id": container_id,
                "access_token": access_token,
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get("id")
        else:
            print(f"Error publishing media: {response.text}")
            return None


async def post_carousel_to_instagram(
    image_paths: List[str],
    caption: str,
    hashtags: str,
    base_url: str = "http://localhost:8000",
    access_token: str = None
) -> dict:
    """
    Post a carousel to Instagram.
    
    Args:
        image_paths: List of local paths to slide images
        caption: The post caption
        hashtags: Hashtags to append to caption
        base_url: Base URL where images are served (for public access)
        access_token: Instagram access token (uses config default if not provided)
    
    Returns:
        dict with status, message, and instagram_post_id if successful
    """
    access_token = access_token or settings.instagram_access_token
    
    if not access_token:
        return {
            "status": "error",
            "message": "No Instagram access token configured"
        }
    
    # Get user ID
    user_id = await get_instagram_user_id(access_token)
    if not user_id:
        return {
            "status": "error",
            "message": "Failed to get Instagram user ID. Access token may be invalid."
        }
    
    # Filter out None values and ensure we have images
    valid_paths = [p for p in image_paths if p and os.path.exists(p)]
    if len(valid_paths) < 2:
        return {
            "status": "error",
            "message": f"Need at least 2 images for a carousel. Found {len(valid_paths)} valid images."
        }
    
    # Limit to 10 images (Instagram max)
    valid_paths = valid_paths[:10]
    
    # Create media containers for each image
    children_ids = []
    for image_path in valid_paths:
        # Get public URL for the image
        image_url = await upload_image_to_hosting(image_path, base_url)
        
        # Create container
        container_id = await create_media_container(
            user_id=user_id,
            image_url=image_url,
            access_token=access_token,
            is_carousel_item=True
        )
        
        if container_id:
            children_ids.append(container_id)
        else:
            return {
                "status": "error",
                "message": f"Failed to create media container for {image_path}. URL: {image_url}. Instagram error: {_last_ig_error}"
            }
    
    # Wait for all containers to be ready
    for container_id in children_ids:
        ready = await wait_for_container_ready(container_id, access_token)
        if not ready:
            return {
                "status": "error",
                "message": f"Container {container_id} failed to process"
            }
    
    # Combine caption and hashtags
    full_caption = f"{caption}\n\n{hashtags}" if hashtags else caption
    
    # Create carousel container
    carousel_id = await create_carousel_container(
        user_id=user_id,
        children_ids=children_ids,
        caption=full_caption,
        access_token=access_token
    )
    
    if not carousel_id:
        return {
            "status": "error",
            "message": "Failed to create carousel container"
        }
    
    # Wait for carousel to be ready
    ready = await wait_for_container_ready(carousel_id, access_token)
    if not ready:
        return {
            "status": "error",
            "message": "Carousel failed to process"
        }
    
    # Publish the carousel
    published_id = await publish_media(
        user_id=user_id,
        container_id=carousel_id,
        access_token=access_token
    )
    
    if published_id:
        return {
            "status": "success",
            "message": "Carousel posted successfully!",
            "instagram_post_id": published_id
        }
    else:
        return {
            "status": "error",
            "message": "Failed to publish carousel"
        }


async def post_single_image_to_instagram(
    image_path: str,
    caption: str,
    hashtags: str,
    base_url: str = "http://localhost:8000",
    access_token: str = None
) -> dict:
    """
    Post a single image to Instagram (for news posts).
    
    Args:
        image_path: Local path to the image
        caption: The post caption
        hashtags: Hashtags to append to caption
        base_url: Base URL where images are served
        access_token: Instagram access token
    
    Returns:
        dict with status, message, and instagram_post_id if successful
    """
    access_token = access_token or settings.instagram_access_token
    
    if not access_token:
        return {
            "status": "error",
            "message": "No Instagram access token configured"
        }
    
    # Get user ID
    user_id = await get_instagram_user_id(access_token)
    if not user_id:
        return {
            "status": "error",
            "message": "Failed to get Instagram user ID. Access token may be invalid."
        }
    
    # Check image exists
    if not image_path or not os.path.exists(image_path):
        return {
            "status": "error",
            "message": f"Image not found: {image_path}"
        }
    
    # Get public URL for the image
    image_url = await upload_image_to_hosting(image_path, base_url)
    
    # Combine caption and hashtags
    full_caption = f"{caption}\n\n{hashtags}" if hashtags else caption
    
    # Create single image container (NOT a carousel item)
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{GRAPH_API_BASE}/{user_id}/media",
            params={
                "image_url": image_url,
                "caption": full_caption,
                "access_token": access_token,
            }
        )
        
        print(f"Single image container response: {response.status_code} - {response.text[:500]}")
        
        if response.status_code != 200:
            return {
                "status": "error",
                "message": f"Failed to create media container. URL: {image_url}. Error: {response.text}"
            }
        
        container_id = response.json().get("id")
    
    if not container_id:
        return {
            "status": "error",
            "message": "Failed to get container ID"
        }
    
    # Wait for container to be ready
    ready = await wait_for_container_ready(container_id, access_token)
    if not ready:
        return {
            "status": "error",
            "message": "Media container failed to process"
        }
    
    # Publish the image
    published_id = await publish_media(
        user_id=user_id,
        container_id=container_id,
        access_token=access_token
    )
    
    if published_id:
        return {
            "status": "success",
            "message": "Image posted successfully!",
            "instagram_post_id": published_id
        }
    else:
        return {
            "status": "error",
            "message": "Failed to publish image"
        }


async def verify_access_token(access_token: str = None) -> dict:
    """Verify the access token is valid and get account info."""
    access_token = access_token or settings.instagram_access_token
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GRAPH_API_BASE}/me",
            params={
                "access_token": access_token,
                "fields": "user_id,username,account_type,media_count"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            return {
                "status": "valid",
                "user_id": data.get("user_id") or data.get("id"),
                "username": data.get("username"),
                "account_type": data.get("account_type"),
                "media_count": data.get("media_count")
            }
        else:
            error_data = response.json() if response.text else {}
            return {
                "status": "invalid",
                "error": error_data.get("error", {}).get("message", response.text)
            }
