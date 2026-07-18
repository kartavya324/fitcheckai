import ipaddress
import socket
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, HttpUrl

from app.api.deps import UploadServiceDep
from app.core.exceptions import AppError
from app.models.job import UploadKind
from app.schemas.upload import UploadCreatedResponse, record_to_created_response
from app.api.deps import UploadServiceDep, StorageServiceDep

router = APIRouter(prefix="/products", tags=["products"])

class ProductFetchRequest(BaseModel):
    url: HttpUrl

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
# Browser-like headers reduce bot-wall responses from retail sites
BROWSER_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}
MAX_IMAGE_SIZE = 10 * 1024 * 1024
MAX_REDIRECTS = 5


def _assert_public_url(url: str) -> None:
    """
    SSRF guard: only allow http(s) URLs whose host resolves to a *public*
    address. Blocks localhost, private ranges, link-local (cloud metadata at
    169.254.169.254), and reserved space — so a crafted product URL can't make
    the server reach internal services.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise AppError("Only http and https URLs are allowed",
                       code="INVALID_URL", status_code=400)
    host = parsed.hostname
    if not host:
        raise AppError("URL has no host", code="INVALID_URL", status_code=400)

    try:
        infos = socket.getaddrinfo(host, parsed.port or 80, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise AppError(f"Could not resolve host: {host}",
                       code="INVALID_URL", status_code=400) from e

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            raise AppError("URL resolves to a non-public address and is blocked",
                           code="BLOCKED_URL", status_code=400)


async def _safe_get(client: httpx.AsyncClient, url: str, **kwargs) -> httpx.Response:
    """GET that validates every redirect hop against the SSRF guard."""
    for _ in range(MAX_REDIRECTS):
        _assert_public_url(url)
        resp = await client.get(url, follow_redirects=False, **kwargs)
        if resp.is_redirect and resp.headers.get("location"):
            url = str(resp.url.join(resp.headers["location"]))
            continue
        return resp
    raise AppError("Too many redirects", code="TOO_MANY_REDIRECTS", status_code=400)

def _amazon_image(soup: BeautifulSoup, html: str) -> str | None:
    """Amazon product pages don't expose og:image; the main photo lives on
    #landingImage (data-old-hires / data-a-dynamic-image) or in hiRes JSON."""
    import json
    import re

    landing = soup.find("img", id="landingImage")
    if landing:
        hires = landing.get("data-old-hires")
        if hires and str(hires).startswith("http"):
            return str(hires)
        dyn = landing.get("data-a-dynamic-image")
        if dyn:
            try:
                candidates = json.loads(dyn)  # {url: [w, h], ...}
                if candidates:
                    return max(
                        candidates, key=lambda u: candidates[u][0] * candidates[u][1]
                    )
            except (json.JSONDecodeError, TypeError, IndexError):
                pass
        if landing.get("src", "").startswith("http"):
            return str(landing["src"])

    m = re.search(r'"hiRes"\s*:\s*"(https://[^"]+)"', html)
    if m:
        return m.group(1)
    return None


def _jsonld_product_image(soup: BeautifulSoup) -> str | None:
    """schema.org Product markup — many stores (Flipkart, Ajio, boutiques)."""
    import json

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("@type") not in ("Product", "ProductGroup"):
                continue
            image = item.get("image")
            if isinstance(image, str) and image.startswith("http"):
                return image
            if isinstance(image, list) and image:
                first = image[0]
                if isinstance(first, str) and first.startswith("http"):
                    return first
                if isinstance(first, dict) and str(first.get("url", "")).startswith("http"):
                    return str(first["url"])
    return None


def get_largest_image(soup: BeautifulSoup, html: str = "") -> str | None:
    # Site-specific extractors first — the generic paths miss these stores
    amazon = _amazon_image(soup, html)
    if amazon:
        return amazon

    # og:image (Myntra, most stores)
    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.get("content"):
        return str(og_image["content"])

    # schema.org Product JSON-LD
    jsonld = _jsonld_product_image(soup)
    if jsonld:
        return jsonld

    # twitter:image
    tw = soup.find("meta", attrs={"name": "twitter:image"})
    if tw and tw.get("content"):
        return str(tw["content"])

    # Then largest img by width/height
    images = soup.find_all("img")
    best_img = None
    max_area = 0
    for img in images:
        src = img.get("src") or img.get("data-src")
        if not src:
            continue
            
        w_str = img.get("width")
        h_str = img.get("height")
        try:
            w = int(w_str) if w_str and w_str.isdigit() else 0
            h = int(h_str) if h_str and h_str.isdigit() else 0
            area = w * h
            if area > max_area:
                max_area = area
                best_img = src
        except ValueError:
            pass
            
    if best_img:
        return str(best_img)
        
    # Fallback to first image with a src
    for img in images:
        src = img.get("src") or img.get("data-src")
        if src:
            return str(src)
            
    return None

@router.post(
    "/fetch",
    response_model=UploadCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def fetch_product_image(
    body: ProductFetchRequest,
    upload_service: UploadServiceDep,
    storage_service: StorageServiceDep,
) -> UploadCreatedResponse:
    url_str = str(body.url)

    # trust_env=False: ignore HTTP(S)_PROXY env vars — proxied egress gets
    # bot-walled by retail sites (Amazon returns a 3.7KB interstitial).
    async with httpx.AsyncClient(headers=BROWSER_HEADERS, trust_env=False) as client:
        try:
            resp = await _safe_get(client, url_str, timeout=15.0)
            resp.raise_for_status()
        except httpx.RequestError as e:
            raise AppError(f"Failed to fetch URL: {str(e)}", code="FETCH_ERROR", status_code=400)
        except httpx.HTTPStatusError as e:
            raise AppError(f"Site returned error: {e.response.status_code}", code="SITE_ERROR", status_code=400)

        soup = BeautifulSoup(resp.text, "html.parser")
        img_url = get_largest_image(soup, resp.text)
        if not img_url:
            import logging
            logging.getLogger(__name__).warning(
                "products/fetch extraction failed: status=%s len=%s url=%s",
                resp.status_code, len(resp.text), url_str,
            )
        
        if not img_url:
            raise AppError("No product image found on the provided page", code="NO_IMAGE_FOUND", status_code=400)
            
        if img_url.startswith("//"):
            img_url = "https:" + img_url
        elif img_url.startswith("/"):
            parsed = httpx.URL(url_str)
            img_url = f"{parsed.scheme}://{parsed.host}{img_url}"
            
        try:
            img_resp = await _safe_get(client, img_url, timeout=15.0)
            img_resp.raise_for_status()
        except httpx.RequestError as e:
            raise AppError(f"Failed to download image: {str(e)}", code="FETCH_ERROR", status_code=400)
        except httpx.HTTPStatusError as e:
            raise AppError(f"Image download returned error: {e.response.status_code}", code="SITE_ERROR", status_code=400)
            
        content_type = img_resp.headers.get("Content-Type", "image/jpeg")
        
        image_bytes = img_resp.content
        if len(image_bytes) > MAX_IMAGE_SIZE:
            raise AppError("Image is too large (max 10MB)", code="PAYLOAD_TOO_LARGE", status_code=413)
            
        if len(image_bytes) == 0:
            raise AppError("Downloaded image is empty", code="EMPTY_IMAGE", status_code=400)
            
        filename = img_url.split("/")[-1].split("?")[0]
        if not filename or "." not in filename:
            filename = "fetched_image.jpg"
            
        try:
            upload_record = await upload_service.save_garment_upload(
                filename=filename,
                content_type=content_type,
                data=image_bytes,
            )
            from app.api.v1.uploads import _extension_for_record
            from app.config import get_settings
            url = storage_service.build_upload_url(
                upload_record.upload_id,
                upload_record.kind,
                _extension_for_record(upload_record),
                base_url=get_settings().public_base_url,
            )
            return record_to_created_response(upload_record, url=url)
        except Exception as e:
            if isinstance(e, AppError):
                raise e
            raise AppError(f"Failed to process image: {str(e)}", code="PROCESS_ERROR", status_code=400)
