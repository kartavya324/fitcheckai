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

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
MAX_IMAGE_SIZE = 10 * 1024 * 1024

def get_largest_image(soup: BeautifulSoup) -> str | None:
    # First try og:image
    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.get("content"):
        return str(og_image["content"])
        
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
    
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        try:
            resp = await client.get(url_str, timeout=10.0)
            resp.raise_for_status()
        except httpx.RequestError as e:
            raise AppError(f"Failed to fetch URL: {str(e)}", code="FETCH_ERROR", status_code=400)
        except httpx.HTTPStatusError as e:
            raise AppError(f"Site returned error: {e.response.status_code}", code="SITE_ERROR", status_code=400)
            
        soup = BeautifulSoup(resp.text, "html.parser")
        img_url = get_largest_image(soup)
        
        if not img_url:
            raise AppError("No product image found on the provided page", code="NO_IMAGE_FOUND", status_code=400)
            
        if img_url.startswith("//"):
            img_url = "https:" + img_url
        elif img_url.startswith("/"):
            parsed = httpx.URL(url_str)
            img_url = f"{parsed.scheme}://{parsed.host}{img_url}"
            
        try:
            img_resp = await client.get(img_url, timeout=15.0)
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
            url = storage_service.build_upload_url(upload_record.upload_id, upload_record.kind)
            return record_to_created_response(upload_record, url=url)
        except Exception as e:
            if isinstance(e, AppError):
                raise e
            raise AppError(f"Failed to process image: {str(e)}", code="PROCESS_ERROR", status_code=400)
